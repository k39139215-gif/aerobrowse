"""30-minute minimum real browser worker lifecycle and actions, with raw cleanup receipts."""

import argparse
import asyncio
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import psutil

from aerobrowse.benchmark import write_receipt
from aerobrowse.runtime import ResourceLimits
from aerobrowse.sessions import SessionManager
from benchmarks.phase2.run import Fixture


async def run(seconds, raw_path):
    manager = SessionManager(
        max_sessions=2,
        allow_networks=("127.0.0.1/32",),
        resource_limits=ResourceLimits(processes=256),
    )
    if not manager.pool.enforced:
        raise RuntimeError("Soak requires real kernel resource controls")
    parent = psutil.Process()
    start = time.monotonic()
    rows = []
    with raw_path.open("x", encoding="utf-8") as raw, Fixture() as url:
        try:
            while time.monotonic() - start < seconds:
                sid = await manager.create("soak-owner")
                snapshot = await manager.call(
                    "soak-owner", sid, "navigate", url, force_fidelity=True
                )
                assert snapshot.get("success"), snapshot
                aid = next(a["id"] for a in snapshot["actions"] if a["label"] == "Name")
                snapshot = await manager.call(
                    "soak-owner", sid, "fill", aid, "Ada", snapshot["generation"]
                )
                assert snapshot.get("success"), snapshot
                aid = next(
                    a["id"] for a in snapshot["actions"] if a["label"] == "Update"
                )
                snapshot = await manager.call(
                    "soak-owner", sid, "click", aid, snapshot["generation"]
                )
                assert snapshot.get("success"), snapshot
                assert "Updated" in snapshot["markdown"]
                closed = await manager.close("soak-owner", sid)
                assert closed.get("success"), closed
                deadline = time.monotonic() + 3
                descendants = parent.children(recursive=True)
                while descendants and time.monotonic() < deadline:
                    await asyncio.sleep(0.05)
                    descendants = parent.children(recursive=True)
                assert not descendants, [(p.pid, p.name()) for p in descendants]
                assert manager.active_sessions == 0
                row = {
                    "elapsed_seconds": time.monotonic() - start,
                    "iteration": len(rows) + 1,
                    "parent_rss_bytes": parent.memory_info().rss,
                    "active_sessions": manager.active_sessions,
                    "descendants_after_cleanup": len(descendants),
                    "success": True,
                }
                rows.append(row)
                raw.write(json.dumps(row) + "\n")
                raw.flush()
                if len(rows) % 10 == 0:
                    print(json.dumps(row), flush=True)
        finally:
            await manager.close_all()
    return {
        "duration_seconds": time.monotonic() - start,
        "iterations": len(rows),
        "raw_path": str(raw_path),
        "max_parent_rss_bytes": max(r["parent_rss_bytes"] for r in rows),
        "first_parent_rss_bytes": rows[0]["parent_rss_bytes"],
        "last_parent_rss_bytes": rows[-1]["parent_rss_bytes"],
        "orphan_processes": 0,
        "permanently_occupied_slots": 0,
        "configuration": {
            "requested_seconds": seconds,
            "max_sessions": 2,
            "session_task_limit": 256,
            "aggregate_task_limit": 256,
        },
        "limitations": [
            "single owned synthetic fixture and sequential lifecycle; not adversarial infinite allocation",
            "parent RSS sampled at completed iterations; kernel cgroup enforces worker quota",
            "boundedness measured over this duration only; not a proof for indefinite operation",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=int, default=1800)
    parser.add_argument("--output", default="evidence/phase2/soak.json")
    args = parser.parse_args()
    if args.seconds < 1800:
        parser.error("release evidence requires at least 1800 seconds")
    raw = Path(args.output).with_suffix(".jsonl")
    if raw.parent.resolve() != Path("evidence/phase2").resolve():
        parser.error("output must be in evidence/phase2")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    result = asyncio.run(run(args.seconds, raw))
    result.update(
        revision=revision,
        platform=platform.platform(),
        python=platform.python_version(),
        pid=os.getpid(),
    )
    print(write_receipt(args.output, result))


if __name__ == "__main__":
    main()
