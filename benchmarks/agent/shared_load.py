"""Measure real shared SessionManager admission, queueing and cleanup on owned HTTP."""

import argparse
import asyncio
import subprocess
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import psutil

from aerobrowse.benchmark import write_receipt
from aerobrowse.errors import AeroError
from aerobrowse.runtime import ResourceLimits
from aerobrowse.sessions import SessionManager


async def run(
    sessions_count: int = 2,
    rounds: int = 3,
    browser: bool = False,
    aggregate_processes: int = 256,
) -> dict:
    if sessions_count * 256 > aggregate_processes:
        raise ValueError(
            "aggregate-processes must reserve 256 tasks per declared session"
        )
    if (
        not 1 <= sessions_count <= 4
        or not 1 <= rounds <= 20
        or not 256 <= aggregate_processes <= 2048
    ):
        raise ValueError("sessions1..4 and rounds1..20 required")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = (
                "<h1>Owned session "
                + self.path.removeprefix("/")
                + "</h1><button>Ready</button>"
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    manager = SessionManager(
        max_sessions=sessions_count,
        allow_networks=("127.0.0.1/32",),
        resource_limits=ResourceLimits(
            processes=256, global_processes=aggregate_processes
        ),
    )
    ids = []
    pids = []
    operations = []
    overload = 0
    start = time.monotonic()
    try:
        ids = [await manager.create("owner-" + str(i)) for i in range(sessions_count)]
        try:
            await manager.create("excess-owner")
        except AeroError as exc:
            capacity_rejected = exc.code == "SESSION_LIMIT"
        else:
            capacity_rejected = False
        denied = await manager.call("foreign-owner", ids[0], "snapshot")
        foreign_rejected = denied.get("error", {}).get("code") == "SESSION_NOT_FOUND"
        assert capacity_rejected and foreign_rejected

        async def call(index, operation, *args, **kwargs):
            queued = time.monotonic()
            result = await manager.call(
                "owner-" + str(index), ids[index], operation, *args, **kwargs
            )
            elapsed = time.monotonic() - queued
            if not result.get("success"):
                diagnostics = {"error": result.get("error", {}), "session_index": index}
                if manager.pool.group is not None and hasattr(
                    manager.pool.group, "resource_events"
                ):
                    diagnostics["aggregate_kernel_events"] = (
                        manager.pool.group.resource_events()
                    )
                raise AssertionError(diagnostics)
            assert "Owned session " + str(index) in result["markdown"]
            operations.append(
                {
                    "session_index": index,
                    "operation": operation,
                    "elapsed_seconds_including_queue": elapsed,
                    "success": True,
                    "engine": result["engine"],
                    "request_id": result["request_id"],
                }
            )
            return result

        await asyncio.gather(
            *(
                call(
                    i,
                    "navigate",
                    f"http://127.0.0.1:{server.server_port}/{i}",
                    force_fidelity=browser,
                )
                for i in range(sessions_count)
            )
        )
        pids = [manager._sessions[sid].worker.pid for sid in ids]
        # Hold the exact per-session lock so the admission test has deterministic
        # overlap; all admitted operations then execute against real workers.
        session = manager._sessions[ids[0]]
        await session.lock.acquire()
        tasks = [
            asyncio.create_task(manager.call("owner-0", ids[0], "snapshot"))
            for _ in range(18)
        ]
        try:
            deadline = time.monotonic() + 5
            while sum(task.done() for task in tasks) < 2:
                if time.monotonic() >= deadline:
                    raise AssertionError(
                        "queue admission did not reject excess requests"
                    )
                await asyncio.sleep(0.005)
            overload = sum(
                task.result().get("error", {}).get("code") == "SESSION_BUSY"
                for task in tasks
                if task.done()
            )
            assert overload == 2
        finally:
            session.lock.release()
            responses = await asyncio.gather(*tasks)
        assert sum(bool(r.get("success")) for r in responses) == 16
        # Calls for each session overlap in the controller; the session lock must
        # serialize them while different workers progress independently.
        for _ in range(rounds):
            await asyncio.gather(
                *(call(i, "snapshot") for i in range(sessions_count) for _ in range(2))
            )
        counts = Counter(row["session_index"] for row in operations)
        duration = time.monotonic() - start
        telemetry = manager.metrics_snapshot()
    finally:
        await manager.close_all()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    session_rows = [
        {
            "index": i,
            "completed": counts[i] - 1,
            "worker_reaped": not psutil.pid_exists(pid),
        }
        for i, pid in enumerate(pids)
    ]
    assert all(row["worker_reaped"] for row in session_rows)
    assert manager.active_sessions == 0
    return {
        "revision": (
            await asyncio.to_thread(
                subprocess.check_output, ["git", "rev-parse", "HEAD"], text=True
            )
        ).strip(),
        "mode": "fidelity" if browser else "turbo",
        "duration_seconds": duration,
        "completed_operations": sessions_count * rounds * 2,
        "successful_operations": sessions_count * rounds * 2,
        "overload_rejections": overload,
        "capacity_rejected": capacity_rejected,
        "foreign_session_rejected": foreign_rejected,
        "active_sessions_after_cleanup": manager.active_sessions,
        "sessions": session_rows,
        "operations": operations,
        "telemetry": telemetry,
        "limits": {
            "max_sessions": sessions_count,
            "pending_per_session": 16,
            "per_session_processes": 256,
            "aggregate_processes": manager.pool.limits.global_processes,
        },
        "limitations": [
            "Owned tiny fixture; bounded progress/admission observations,not a production fairness or saturation proof",
            "Duration includes initialization and deliberate queue-admission phase; cleanup duration excluded",
            "Navigation rows and 16 queue-test snapshots excluded from completed_operations; retained separately in telemetry",
            "RSS sampled at request completion; not exact peak",
            "Explicit aggregate task budget recorded; results must not be attributed to default capacity",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--aggregate-processes", type=int, default=256)
    parser.add_argument("--output", default="evidence/developer/shared-load.json")
    args = parser.parse_args()
    result = asyncio.run(
        run(args.sessions, args.rounds, args.browser, args.aggregate_processes)
    )
    write_receipt(args.output, result)


if __name__ == "__main__":
    main()
