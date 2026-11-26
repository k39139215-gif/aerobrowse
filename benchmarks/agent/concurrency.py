"""Reproducible two-worker full browser task load; no speedup claim."""

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import psutil

from aerobrowse import AeroBrowser
from aerobrowse.runtime import ResourceLimits
from aerobrowse.security import NetworkPolicy
from benchmarks.agent.fixture import AgentFixture
from benchmarks.agent.workflows import search_history_tabs


def run(concurrency=2, iterations=3):
    def task(index):
        start = time.monotonic()
        with (
            AgentFixture() as fixture,
            AeroBrowser(
                default_mode="fidelity",
                policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
                resource_limits=ResourceLimits(processes=256),
            ) as browser,
        ):
            search_history_tabs(browser, fixture)
            pid = browser._worker.pid
            sid = browser.session_id
        return {
            "index": index,
            "session_id": sid,
            "elapsed_seconds": time.monotonic() - start,
            "success": True,
            "worker_reaped": not psutil.pid_exists(pid),
        }

    start = time.monotonic()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        rows = list(pool.map(task, range(iterations * concurrency)))
    duration = time.monotonic() - start
    return {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "concurrency": concurrency,
        "completed_tasks": len(rows),
        "duration_seconds": duration,
        "successful_tasks_per_second": len(rows) / duration,
        "rows": rows,
        "limitations": [
            "Owned tiny fixture; public supervised SDK, not browser/MCP saturation or fairness proof",
            "Per-browser independent resource pools; operator process manager must bound aggregate independent SDK instances",
            "Failure aborts without emitting a success receipt",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--output", default="evidence/agent/concurrency.json")
    args = parser.parse_args()
    if not 1 <= args.concurrency <= 4 or not 1 <= args.iterations <= 20:
        parser.error("concurrency1..4 and iterations1..20 required")
    result = run(args.concurrency, args.iterations)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
