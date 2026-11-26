"""Reproducible latency/token/process-tree RSS measurements; failures are data."""

import argparse
import json
import platform
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path
from threading import Event, Thread
from typing import Any

import psutil

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy


def _sample_memory(
    process: psutil.Process, stop: Event, samples: list[int], sampling_errors: list[str]
) -> None:
    while not stop.wait(0.01):
        try:
            total = process.memory_info().rss
            for child in process.children(recursive=True):
                try:
                    total += child.memory_info().rss
                except psutil.NoSuchProcess:
                    continue
            samples.append(total)
        except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
            sampling_errors.append(type(exc).__name__)


def run(
    url: str,
    *,
    repeats: int = 5,
    allow_networks: tuple[str, ...] = (),
    concurrency: int = 2,
) -> dict[str, Any]:
    if not 1 <= repeats <= 100 or not 1 <= concurrency <= 8:
        raise ValueError("Invalid benchmark bounds")
    policy = NetworkPolicy(allow_networks=allow_networks)
    process = psutil.Process()
    stop = Event()
    samples: list[int] = []
    sampling_errors: list[str] = []

    sampler = Thread(
        target=_sample_memory,
        args=(process, stop, samples, sampling_errors),
        daemon=True,
    )
    sampler.start()
    operations = []
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    try:
        for mode in ("turbo", "fidelity"):
            operations.extend(_measure_engine(url, mode, repeats, policy))

        def worker(_: int) -> bool:
            with AeroBrowser(default_mode="turbo", policy=policy) as browser:
                return bool(browser.fetch(url).get("success"))

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            outcomes = list(pool.map(worker, range(concurrency * repeats)))
        load_elapsed = time.perf_counter() - start
    finally:
        stop.set()
        sampler.join()
    try:
        revision = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        revision = "unavailable"
    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "revision": revision,
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "packages": {
                name: version(name)
                for name in ("playwright", "tiktoken", "beautifulsoup4")
            },
        },
        "configuration": {
            "repeats": repeats,
            "concurrency": concurrency,
            "allow_networks": allow_networks,
        },
        "operations": operations,
        "peak_sampled_process_tree_rss_bytes": max(samples) if samples else None,
        "rss_sample_interval_ms": 10,
        "sampling_errors": sampling_errors,
        "cpu_seconds": time.process_time() - cpu_start,
        "wall_seconds": time.perf_counter() - wall_start,
        "load": {
            "requests": len(outcomes),
            "successes": sum(outcomes),
            "concurrency": concurrency,
            "elapsed_seconds": load_elapsed,
            "successful_requests_per_second": sum(outcomes) / load_elapsed,
        },
        "limitations": [
            "RSS is sampled, not an exact peak",
            "Navigation cold excludes Python interpreter startup",
            "Click/fill latency requires the browser integration benchmark; not measured here",
        ],
    }


def _measure_engine(
    url: str, mode: str, repeats: int, policy: NetworkPolicy
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = []
    with AeroBrowser(default_mode=mode, policy=policy) as browser:
        for index in range(repeats):
            start = time.perf_counter()
            result = browser.fetch(url)
            operations.append(
                {
                    "engine": mode,
                    "operation": "navigate",
                    "temperature": "cold" if index == 0 else "warm",
                    "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                    "success": result.get("success"),
                    "error_code": result.get("error", {}).get("code"),
                    "original_tokens": result.get("original_tokens"),
                    "extracted_tokens": result.get("extracted_tokens"),
                    "token_reduction_pct": result.get("token_reduction_pct"),
                    "tokenizer": result.get("tokenizer"),
                    "quality": result.get("quality"),
                }
            )
            if result.get("success"):
                start = time.perf_counter()
                snap = browser.snapshot()
                operations.append(
                    {
                        "engine": mode,
                        "operation": "snapshot",
                        "elapsed_ms": round((time.perf_counter() - start) * 1000, 3),
                        "success": snap.get("success"),
                    }
                )
    return operations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--output", default="evidence/benchmark.json")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--allow-network", action="append", default=[])
    args = parser.parse_args()
    result = run(
        args.url,
        repeats=args.repeats,
        allow_networks=tuple(args.allow_network),
        concurrency=args.concurrency,
    )
    destination = write_receipt(args.output, result)
    print(str(destination))


def write_receipt(output: str, result: dict[str, Any]) -> Path:
    """Confine CLI output to evidence/ without traversing any symlink components."""
    root = Path.cwd().resolve()
    relative = Path(output)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or not relative.parts
        or relative.parts[0] != "evidence"
    ):
        raise ValueError("Benchmark output must be inside ./evidence")
    destination = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink output paths are not permitted")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation avoids clobbering existing files or following a file symlink.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
    return destination


if __name__ == "__main__":
    main()
