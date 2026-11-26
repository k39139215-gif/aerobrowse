"""Owned synthetic fixture measurements. Raw failures are retained; no speedup claims."""

import argparse
import math
import platform
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil

from aerobrowse import AeroBrowser
from aerobrowse.benchmark import write_receipt
from aerobrowse.security import NetworkPolicy

LOCAL_CIDR = "127.0.0.1/32"

HTML = """<html><head><title>Phase2 fixture</title></head><body><h1>Controlled account</h1>
<p>Important invoice balance 42 USD</p><a href='/route'>Account route</a>
<label>Name<input name='name'></label><label>Choice<select><option value='a'>A</option><option value='b'>B</option></select></label>
<button type='button' onclick="this.textContent='Updated'">Update</button><div style='height:2000px'>Scroll content</div></body></html>"""


class Fixture:
    def __enter__(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                raw = HTML.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def log_message(self, *args):
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://127.0.0.1:{self.server.server_port}"

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


def statistics(rows):
    values = sorted(r["elapsed_ms"] for r in rows)

    def percentile(q):
        return values[max(0, math.ceil(q * len(values)) - 1)] if values else None

    return {
        "samples": len(rows),
        "median_ms": percentile(0.5),
        "p90_ms": percentile(0.9),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "min_ms": min(values) if values else None,
        "max_ms": max(values) if values else None,
        "failure_rate": sum(not r["success"] for r in rows) / len(rows)
        if rows
        else None,
        "timeout_rate": sum(r.get("error_code") == "TIMEOUT" for r in rows) / len(rows)
        if rows
        else None,
        "percentile_method": "nearest rank; p99 not robust with <100 samples",
    }


def measure(rows, name, operation):
    start = time.perf_counter()
    try:
        result = operation()
        if isinstance(result, bytes):
            result = {"success": True}
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        # Only exception class is retained. Failed measurements remain explicit data.
        result = {"success": False, "error": {"code": type(exc).__name__}}
    rows.append(
        {
            "operation": name,
            "elapsed_ms": (time.perf_counter() - start) * 1000,
            "success": bool(result.get("success")),
            "error_code": result.get("error", {}).get("code"),
            **{
                key: result[key]
                for key in (
                    "original_tokens",
                    "extracted_tokens",
                    "token_reduction_pct",
                    "tokenizer",
                    "quality",
                )
                if key in result
            },
        }
    )
    return result


def action(snapshot, label):
    matches = [a for a in snapshot.get("actions", []) if a["label"] == label]
    if len(matches) != 1:
        raise ValueError("Action cardinality mismatch")
    return matches[0]["id"]


def browser_samples(url, rows, repeats):
    policy = NetworkPolicy(allow_networks=(LOCAL_CIDR,))
    with AeroBrowser(default_mode="fidelity", policy=policy) as browser:
        for index in range(repeats):
            snapshot = measure(
                rows,
                "browser_cold_navigation" if index == 0 else "browser_warm_navigation",
                lambda: browser.fetch(url),
            )
            if not snapshot.get("success"):
                continue
            snapshot = measure(rows, "snapshot", browser.snapshot)
            snapshot = measure(
                rows,
                "fill",
                lambda snapshot=snapshot: browser.fill(
                    action(snapshot, "Name"), "Ada", snapshot["generation"]
                ),
            )
            snapshot = measure(
                rows,
                "select",
                lambda snapshot=snapshot: browser.select(
                    action(snapshot, "Choice"), "b", snapshot["generation"]
                ),
            )
            snapshot = measure(
                rows,
                "wait",
                lambda snapshot=snapshot: browser.wait(
                    action(snapshot, "Update"), snapshot["generation"]
                ),
            )
            snapshot = measure(
                rows,
                "click",
                lambda snapshot=snapshot: browser.click(
                    action(snapshot, "Update"), snapshot["generation"]
                ),
            )
            measure(rows, "scroll", lambda: browser.scroll(0, 200))
            measure(rows, "screenshot", browser.screenshot)
    with AeroBrowser(default_mode="turbo", policy=policy) as browser:
        for index in range(repeats):
            snapshot = measure(rows, "turbo_navigation", lambda: browser.fetch(url))
            # The safe handoff deliberately returns STALE_ACTION_ID and a fresh live snapshot.
            result = measure(
                rows,
                "turbo_fidelity_escalation",
                lambda snapshot=snapshot: browser.click(action(snapshot, "Update")),
            )
            if result.get("synchronized"):
                rows[-1]["success"] = True
                rows[-1]["expected_error"] = "STALE_ACTION_ID"


def concurrent_samples(url, repeats):
    results = []

    def run_one(_):
        row = []
        with AeroBrowser(
            default_mode="turbo", policy=NetworkPolicy(allow_networks=(LOCAL_CIDR,))
        ) as browser:
            measure(row, "concurrent_turbo", lambda: browser.fetch(url))
        return row[0]

    for concurrency in (1, 2, 4, 8, 16):
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            rows = list(executor.map(run_one, range(concurrency * repeats)))
        elapsed = time.perf_counter() - start
        results.append(
            {
                "concurrency": concurrency,
                "elapsed_seconds": elapsed,
                "throughput_per_second": sum(r["success"] for r in rows) / elapsed,
                "raw": rows,
                "statistics": statistics(rows),
                "scope": "SDK Turbo workers, not MCP/browser session throughput",
            }
        )
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=100)
    parser.add_argument("--output", default="evidence/phase2/benchmark.json")
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    if not 10 <= args.samples <= 1000:
        parser.error("samples must be 10..1000")
    process = psutil.Process()
    cpu = process.cpu_times()
    rss = []
    stop = threading.Event()

    def sample():
        while not stop.wait(0.02):
            try:
                rss.append(
                    sum(
                        p.memory_info().rss
                        for p in [process, *process.children(recursive=True)]
                        if p.is_running()
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

    sampler = threading.Thread(target=sample, daemon=True)
    sampler.start()
    rows = []
    try:
        for _ in range(min(args.samples, 30)):
            measure(
                rows,
                "cold_python_import",
                lambda: {
                    "success": subprocess.run(
                        [sys.executable, "-c", "import aerobrowse"],
                        timeout=30,
                        capture_output=True,
                        check=False,
                    ).returncode
                    == 0
                },
            )
        with Fixture() as url:
            with AeroBrowser(
                default_mode="turbo",
                policy=NetworkPolicy(allow_networks=(LOCAL_CIDR,)),
            ) as browser:
                measure(rows, "turbo_first_navigation", lambda: browser.fetch(url))
                for _ in range(args.samples):
                    measure(rows, "turbo_warm_navigation", lambda: browser.fetch(url))
            if args.browser:
                browser_samples(url, rows, args.samples)
            concurrent = concurrent_samples(url, max(10, args.samples // 10))
    finally:
        stop.set()
        sampler.join()
    result = {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        ),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "configuration": vars(args),
        "raw": rows,
        "statistics": {
            name: statistics([r for r in rows if r["operation"] == name])
            for name in sorted({r["operation"] for r in rows})
        },
        "concurrency": concurrent,
        "sampled_peak_tree_rss_bytes": max(rss) if rss else None,
        "rss_interval_ms": 20,
        "parent_cpu_seconds": process.cpu_times().user
        + process.cpu_times().system
        - cpu.user
        - cpu.system,
        "limitations": [
            "owned tiny synthetic fixture; no production website performance claim",
            "RSS sampled and CPU excludes exited children",
            "cold Python import is a new interpreter; warm browser samples reuse one context",
            "per-session CPU/RSS and MCP/browser load not measured by Turbo load",
            "no controlled before/after speedup comparison",
        ],
    }
    print(write_receipt(args.output, result))


if __name__ == "__main__":
    main()
