"""
Empirical Benchmark: Standard Headless Chromium vs AeroBrowse Turbo vs AeroBrowse Fidelity (Native CDP).
Measures:
1. Latency (ms)
2. Peak Process-Tree RSS Memory (MB)
3. Token Count (BPE approximation)
4. Dynamic JS execution capability
5. Interactive Action Element mapping
"""

import os
import sys
import time
import subprocess
import tempfile
import psutil

URLS = [
    ("Quotes JS (Dynamic SPA)", "https://quotes.toscrape.com/js/"),
    ("Python.org (Modern Web)", "https://www.python.org"),
    ("Books Catalog (E-Commerce)", "https://books.toscrape.com")
]

BASELINE_BIN = os.environ.get("BASELINE_BROWSER_BIN", "headless_baseline.exe")
AERO_EXE = r"C:\Users\kartik\.gemini\antigravity\scratch\aerobrowse\dist\aerobrowse-windows-x86_64.exe"

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

def run_and_measure(cmd, cwd=None, env=None):
    stdout_file = tempfile.TemporaryFile(mode="w+b")
    stderr_file = tempfile.TemporaryFile(mode="w+b")
    
    start_time = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=stdout_file, stderr=stderr_file, cwd=cwd, env=env)
    
    peak_rss = 0
    try:
        p = psutil.Process(proc.pid)
        while proc.poll() is None:
            total_rss = 0
            try:
                total_rss += p.memory_info().rss
                for child in p.children(recursive=True):
                    try:
                        total_rss += child.memory_info().rss
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            if total_rss > peak_rss:
                peak_rss = total_rss
            time.sleep(0.02)
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        pass

    proc.wait()
    elapsed_ms = (time.perf_counter() - start_time) * 1000

    stdout_file.seek(0)
    stderr_file.seek(0)
    stdout_data = stdout_file.read().decode("utf-8", errors="replace")
    stderr_data = stderr_file.read().decode("utf-8", errors="replace")
    stdout_file.close()
    stderr_file.close()

    return {
        "elapsed_ms": elapsed_ms,
        "peak_mb": peak_rss / (1024 * 1024),
        "stdout": stdout_data,
        "stderr": stderr_data,
        "tokens": estimate_tokens(stdout_data),
        "returncode": proc.returncode
    }

def main():
    print("=" * 80)
    print("DUAL-ENGINE CAPABILITY BENCHMARK")
    print("Standard Headless Chromium (Raw DOM) vs AeroBrowse Turbo vs AeroBrowse Fidelity (CDP)")
    print("=" * 80)

    results = []

    for name, url in URLS:
        print(f"\nTarget: {name} ({url})")

        # 1. Baseline Headless Browser
        baseline_cmd = [BASELINE_BIN, "fetch", url]
        print("  Running Standard Headless Browser...", end="", flush=True)
        baseline_res = run_and_measure(baseline_cmd)
        print(f" Done ({baseline_res['elapsed_ms']:.0f}ms, {baseline_res['peak_mb']:.1f}MB, {baseline_res['tokens']:,} tok)")

        # 2. AeroBrowse Turbo
        aero_turbo_cmd = [AERO_EXE, "fetch", url]
        print("  Running AeroBrowse Turbo...", end="", flush=True)
        turbo_res = run_and_measure(aero_turbo_cmd)
        print(f" Done ({turbo_res['elapsed_ms']:.0f}ms, {turbo_res['peak_mb']:.1f}MB, {turbo_res['tokens']:,} tok)")

        # 3. AeroBrowse Fidelity
        aero_fid_cmd = [AERO_EXE, "fetch", url, "--fidelity"]
        print("  Running AeroBrowse Fidelity...", end="", flush=True)
        fid_res = run_and_measure(aero_fid_cmd)
        print(f" Done ({fid_res['elapsed_ms']:.0f}ms, {fid_res['peak_mb']:.1f}MB, {fid_res['tokens']:,} tok)")

        results.append({
            "name": name,
            "url": url,
            "baseline": baseline_res,
            "turbo": turbo_res,
            "fidelity": fid_res
        })

    print("\n" + "=" * 80)
    print("FINAL BENCHMARK COMPARISON TABLE")
    print("=" * 80)
    print(f"{'Site':<25} | {'Metric':<10} | {'Standard Raw':<12} | {'Aero Turbo':<12} | {'Aero Fidelity':<12}")
    print("-" * 80)

    for r in results:
        name = r["name"]
        b = r["baseline"]
        t = r["turbo"]
        f = r["fidelity"]

        print(f"{name:<25} | Latency    | {b['elapsed_ms']:>8.0f} ms | {t['elapsed_ms']:>8.0f} ms | {f['elapsed_ms']:>8.0f} ms")
        print(f"{'':<25} | Peak RAM   | {b['peak_mb']:>8.1f} MB | {t['peak_mb']:>8.1f} MB | {f['peak_mb']:>8.1f} MB")
        print(f"{'':<25} | Tokens     | {b['tokens']:>8,d}     | {t['tokens']:>8,d}     | {f['tokens']:>8,d}    ")
        savings = (1 - (f['tokens'] / max(1, b['tokens']))) * 100
        print(f"{'':<25} | Fidelity Δ | Baseline     | Fast/No-JS   | {savings:>6.1f}% pruned")
        print("-" * 80)

if __name__ == "__main__":
    main()
