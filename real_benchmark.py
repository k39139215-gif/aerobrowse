import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
import psutil
from playwright.sync_api import sync_playwright
from aerobrowse.turbo import TurboEngine
from aerobrowse.fidelity import FidelityEngine

def count_tokens(text: str) -> int:
    """Accurate offline token estimation (standard 3.8 chars per token)."""
    return max(1, round(len(text) / 3.8))

def get_process_tree_memory_mb(pid: int) -> float:
    total_bytes = 0
    try:
        parent = psutil.Process(pid)
        total_bytes += parent.memory_info().rss
        for child in parent.children(recursive=True):
            try:
                total_bytes += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except Exception:
        pass
    return round(total_bytes / (1024 * 1024), 2)

def benchmark_standard_chrome(url: str):
    t0 = time.perf_counter()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        current_pid = os.getpid()
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        html = page.content()
        mem_mb = get_process_tree_memory_mb(current_pid)
        browser.close()
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "engine": "Standard Headless Chrome",
        "elapsed_ms": elapsed_ms,
        "memory_mb": mem_mb,
        "raw_chars": len(html),
        "tokens": count_tokens(html)
    }

def benchmark_aerobrowse_turbo(url: str):
    current_pid = os.getpid()
    t0 = time.perf_counter()
    engine = TurboEngine()
    res = engine.fetch(url)
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
    mem_mb = round(psutil.Process(current_pid).memory_info().rss / (1024 * 1024), 2)

    return {
        "engine": "AeroBrowse Turbo",
        "elapsed_ms": elapsed_ms,
        "memory_mb": mem_mb,
        "raw_chars": res.get("original_chars", 0),
        "pruned_chars": res.get("pruned_chars", 0),
        "tokens": count_tokens(res.get("markdown", "")),
        "reduction_pct": res.get("reduction_pct", 0),
        "actions_found": len(res.get("actions", []))
    }

def benchmark_aerobrowse_fidelity(url: str):
    current_pid = os.getpid()
    t0 = time.perf_counter()
    fidelity = FidelityEngine(headless=True, block_heavy_resources=True)
    res = fidelity.navigate(url)
    mem_mb = get_process_tree_memory_mb(current_pid)
    fidelity.close()
    elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)

    return {
        "engine": "AeroBrowse Fidelity",
        "elapsed_ms": elapsed_ms,
        "memory_mb": mem_mb,
        "raw_chars": res.get("original_chars", 0),
        "pruned_chars": res.get("pruned_chars", 0),
        "tokens": count_tokens(res.get("markdown", "")),
        "reduction_pct": res.get("reduction_pct", 0),
        "actions_found": len(res.get("actions", []))
    }

def run_test(url: str):
    print(f"\n=======================================================", flush=True)
    print(f"  LIVE EMPIRICAL BENCHMARK: {url}", flush=True)
    print(f"=======================================================", flush=True)

    print("[*] Running Standard Headless Chrome...", flush=True)
    c = benchmark_standard_chrome(url)
    print(f"    Done: {c['elapsed_ms']}ms | {c['memory_mb']} MB RAM | {c['tokens']:,} tokens", flush=True)

    print("[*] Running AeroBrowse Turbo...", flush=True)
    t = benchmark_aerobrowse_turbo(url)
    print(f"    Done: {t['elapsed_ms']}ms | {t['memory_mb']} MB RAM | {t['tokens']:,} tokens", flush=True)

    print("[*] Running AeroBrowse Fidelity...", flush=True)
    f = benchmark_aerobrowse_fidelity(url)
    print(f"    Done: {f['elapsed_ms']}ms | {f['memory_mb']} MB RAM | {f['tokens']:,} tokens", flush=True)

    print("\n--- MEASURED RESULTS TABLE ---", flush=True)
    header = f"{'Metric':<24} | {'Std Headless Chrome':<20} | {'AeroBrowse (Turbo)':<20} | {'AeroBrowse (Fidelity)':<20}"
    print(header, flush=True)
    print("-" * len(header), flush=True)

    print(f"{'Latency':<24} | {c['elapsed_ms']} ms{'':<13} | {t['elapsed_ms']} ms{'':<13} | {f['elapsed_ms']} ms", flush=True)
    print(f"{'Memory (RAM)':<24} | {c['memory_mb']} MB{'':<13} | {t['memory_mb']} MB{'':<13} | {f['memory_mb']} MB", flush=True)
    print(f"{'Tokens sent to LLM':<24} | {c['tokens']:,} tokens{'':<8} | {t['tokens']:,} tokens{'':<8} | {f['tokens']:,} tokens", flush=True)

    t_saved = round((1 - t['tokens'] / max(1, c['tokens'])) * 100, 1)
    f_saved = round((1 - f['tokens'] / max(1, c['tokens'])) * 100, 1)
    print(f"{'Token Savings vs Chrome':<24} | {'0% (Baseline)':<20} | {t_saved}% saved{'':<10} | {f_saved}% saved", flush=True)
    print(f"{'Interactive Action Map':<24} | {'None (raw HTML)':<20} | {t['actions_found']} elements{'':<9} | {f['actions_found']} elements", flush=True)

if __name__ == "__main__":
    run_test("https://news.ycombinator.com")
    run_test("https://example.com")
