import asyncio
import sys

import psutil
import pytest

from aerobrowse.runtime import ResourceLimits
from aerobrowse.sessions import SessionManager


def test_worker_crash_retires_slot_and_allows_new_session():
    async def run():
        manager = SessionManager(max_sessions=1)
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        process = manager._sessions[sid].worker.process
        psutil.Process(manager._sessions[sid].worker.pid).kill()
        process.wait(timeout=5)
        result = await manager.call("owner", sid, "snapshot")
        assert result["error"]["code"] == "WORKER_CRASHED"
        assert manager.active_sessions == 0
        replacement = await manager.create("owner")
        assert (await manager.call("owner", replacement, "snapshot"))["error"][
            "code"
        ] == "NO_ACTIVE_PAGE"
        await manager.close_all()

    asyncio.run(run())


def test_slow_network_worker_is_killed_on_timeout(site):
    async def run():
        manager = SessionManager(max_sessions=1, allow_networks=("127.0.0.1/32",))
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        pid = manager._sessions[sid].worker.pid
        manager.request_timeout = 0.03
        result = await manager.call("owner", sid, "navigate", site + "/slow")
        assert result["error"]["code"] == "TIMEOUT"
        assert not psutil.pid_exists(pid)
        assert manager.active_sessions == 0
        await manager.close_all()

    asyncio.run(run())


def test_cancelled_network_call_terminates_worker(site):
    async def run():
        manager = SessionManager(allow_networks=("127.0.0.1/32",))
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        pid = manager._sessions[sid].worker.pid
        task = asyncio.create_task(
            manager.call("owner", sid, "navigate", site + "/slow")
        )
        await asyncio.sleep(0.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not psutil.pid_exists(pid)
        assert manager.active_sessions == 0
        await manager.close_all()

    asyncio.run(run())


@pytest.mark.skipif(
    __import__("sys").platform not in {"win32", "linux"},
    reason="Kernel job or Linux guardian parent death",
)
def test_parent_death_closes_job_and_kills_worker():
    import json
    import subprocess
    import sys
    import time

    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import json,sys;from aerobrowse.runtime import ResourcePool,ProcessWorker;p=ResourcePool();w=ProcessWorker(p);w.call('snapshot',(),{});print(json.dumps({'pid':w.pid}),flush=True);sys.stdin.readline()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        worker = json.loads(parent.stdout.readline())["pid"]
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while psutil.pid_exists(worker) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not psutil.pid_exists(worker)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        parent.stdin.close()
        parent.stdout.close()


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux", reason="Required Linux supervised Chromium"
)
def test_supervised_browser_navigation_actions_and_cleanup(site):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=256),
        )
        sid = await manager.create("owner")
        try:
            result = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            group = manager._sessions[sid].worker.group
            counters = {
                name: (group.path / name).read_text()
                for name in (
                    "memory.events",
                    "pids.events",
                    "pids.current",
                    "memory.current",
                )
            }
            assert result.get("success"), {"result": result, "quota_counters": counters}
            aid = next(a["id"] for a in result["actions"] if a["label"] == "Name")
            result = await manager.call(
                "owner", sid, "fill", aid, "Ada", result["generation"]
            )
            assert result.get("success"), result
            assert (await manager.close("owner", sid))["success"]
            assert manager.active_sessions == 0
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux", reason="Linux Chromium task exhaustion"
)
def test_low_task_budget_fails_explicitly_and_releases_slot(site):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=16),
        )
        sid = await manager.create("owner")
        try:
            result = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            assert result["error"]["code"] == "WORKER_RESOURCE_LIMIT", result
            assert manager.active_sessions == 0
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="Linux live browser descendant crashes",
)
@pytest.mark.parametrize("target", ["browser", "renderer"])
def test_live_browser_crash_releases_tree_and_recovers(site, target):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=256),
        )
        sid = await manager.create("owner")
        descendants = []
        try:
            snapshot = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            assert snapshot.get("success"), snapshot
            worker = psutil.Process(manager._sessions[sid].worker.pid)
            descendants = worker.children(recursive=True)
            chromes = [p for p in descendants if p.name() in ("chrome", "chromium")]
            selected = (
                [p for p in chromes if "--type=renderer" in p.cmdline()]
                if target == "renderer"
                else [
                    next(
                        p
                        for p in chromes
                        if not any(a.startswith("--type=") for a in p.cmdline())
                    )
                ]
            )
            # Chromium can prestart a spare renderer; terminate every session renderer
            # so this test cannot accidentally kill only the spare process.
            assert selected
            for process in selected:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            await asyncio.sleep(0.1)
            manager.request_timeout = 3
            aid = next(a["id"] for a in snapshot["actions"] if a["label"] == "Name")
            result = await manager.call(
                "owner",
                sid,
                "fill",
                aid,
                "must not target another page",
                snapshot["generation"],
            )
            assert not result.get("success"), result
            assert result["error"]["code"] in {
                "STALE_ACTION_ID",
                "PAGE_NAVIGATED",
                "NO_ACTIVE_PAGE",
                "WORKER_CRASHED",
                "SNAPSHOT_FAILED",
                "TIMEOUT",
            }, result
            if sid in manager._sessions:
                assert (await manager.close("owner", sid))["success"]
            assert manager.active_sessions == 0
            for process in descendants:
                try:
                    assert process.status() == psutil.STATUS_ZOMBIE, (
                        process.pid,
                        process.name(),
                        process.status(),
                    )
                except psutil.NoSuchProcess:
                    pass
            manager.request_timeout = 45
            replacement = await manager.create("owner")
            fresh = await manager.call(
                "owner", replacement, "navigate", site + "/form", force_fidelity=True
            )
            assert fresh.get("success"), fresh
            assert fresh["generation"] != snapshot["generation"]
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="Linux independent guardian parent death",
)
def test_linux_parent_death_kills_worker_and_cgroup():
    import json
    import subprocess
    import sys
    import time

    code = """import json,sys
from aerobrowse.runtime import ResourcePool,ProcessWorker
pool=ResourcePool();worker=ProcessWorker(pool)
worker.call('snapshot',(),{})
print(json.dumps({'pid':worker.pid,'guardian':worker.guardian.pid,'directory':worker.directory.name,'group':str(worker.group.path)}),flush=True)
sys.stdin.readline()
"""
    with subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as parent:
        receipt = json.loads(parent.stdout.readline())
        worker = psutil.Process(receipt["pid"])
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                live = worker.is_running() and worker.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                live = False
            if (
                not live
                and not __import__("pathlib").Path(receipt["directory"]).exists()
                and not __import__("pathlib").Path(receipt["group"]).exists()
            ):
                break
            time.sleep(0.05)
        assert not live
        assert not __import__("pathlib").Path(receipt["directory"]).exists()
        assert not __import__("pathlib").Path(receipt["group"]).exists()


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="Linux configured MCP real stdio browser flow",
)
def test_configured_mcp_stdio_browser_flow(site):
    import json
    import os
    import queue
    import subprocess
    import sys
    import threading

    env = dict(os.environ, AEROBROWSE_SESSION_TASKS="256")
    # Trusted fixture operator explicitly grants one owned address. No MCP tool can grant it.
    entry = "from aerobrowse.mcp_server import sessions,run_mcp;sessions.pool.allow_networks=('127.0.0.1/32',);run_mcp()"
    process = subprocess.Popen(
        [sys.executable, "-c", entry],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    output = queue.Queue()

    def read():
        for line in process.stdout:
            output.put(json.loads(line))

    reader = threading.Thread(target=read, daemon=True)
    reader.start()

    def exchange(message):
        process.stdin.write(json.dumps(message).encode() + b"\n")
        process.stdin.flush()
        response = output.get(timeout=60)
        assert response.get("id") == message["id"], response
        return response

    try:
        init = exchange(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "configured-runtime", "version": "1"},
                },
            }
        )
        assert "result" in init
        process.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
        process.stdin.flush()
        result = exchange(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "browser_navigate",
                    "arguments": {"url": site + "/form", "force_js": True},
                },
            }
        )["result"]["structuredContent"]
        assert result.get("success"), result
        sid = result["session_id"]
        filled = exchange(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "browser_fill",
                    "arguments": {
                        "session_id": sid,
                        "action_id": next(
                            a["id"] for a in result["actions"] if a["label"] == "Name"
                        ),
                        "generation": result["generation"],
                        "value": "Ada",
                    },
                },
            }
        )["result"]["structuredContent"]
        assert filled.get("success"), filled
        closed = exchange(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "browser_close", "arguments": {"session_id": sid}},
            }
        )["result"]["structuredContent"]
        assert closed.get("success"), closed
        process.stdin.close()
        process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read().decode()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        if not process.stdin.closed:
            process.stdin.close()
        process.stdout.close()
        reader.join(timeout=2)
        process.stderr.close()


@pytest.mark.browser
@pytest.mark.skipif(sys.platform != "linux", reason="Linux aggregate cgroup exhaustion")
def test_aggregate_quota_exhaustion_is_explicit_and_reaps_worker(site):
    from aerobrowse.errors import AeroError
    from aerobrowse.runtime import Cgroup, ProcessWorker, ResourceLimits, ResourcePool

    pool = ResourcePool(ResourceLimits(processes=64), allow_networks=("127.0.0.1/32",))
    worker = ProcessWorker(pool)
    try:
        worker.start()
        assert isinstance(pool.group, Cgroup)
        assert isinstance(worker.group, Cgroup)
        # Force an actual aggregate child-task denial, not a fabricated counter.
        current = int((pool.group.path / "pids.current").read_text())
        (pool.group.path / "pids.max").write_text(str(current))
        process = worker.process
        assert process is not None
        # The real worker command launches Chromium children and must hit the cap.
        try:
            result = worker.call(
                "navigate", (site + "/form",), {"force_fidelity": True}
            )
        except AeroError as exc:
            assert exc.code == "WORKER_RESOURCE_LIMIT", exc.code
        else:
            raise AssertionError(result)
        assert pool.group.resource_events()["pids_max"] > 0
        assert worker.group.resource_events()["pids_max"] == 0
    finally:
        worker.terminate()
        pool.close()
    assert process.poll() is not None
