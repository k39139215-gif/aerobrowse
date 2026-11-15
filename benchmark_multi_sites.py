import os
import sys
import time
import subprocess
import tempfile
import json
import psutil

OBSCURA_BIN = r"C:\Users\kartik\.gemini\antigravity\scratch\obscura\obscura.exe"
AERO_BIN = r"C:\Users\kartik\.gemini\antigravity\scratch\aerobrowse\dist\aerobrowse-windows-x86_64.exe"

URLS = [
    ("Example Domain (Baseline)", "https://example.com"),
    ("Hacker News (Tech Forum)", "https://news.ycombinator.com"),
    ("Quotes to Scrape (Scraping Target)", "https://quotes.toscrape.com"),
    ("Books to Scrape (E-Commerce Catalog)", "https://books.toscrape.com"),
    ("Python.org (Official Docs/Org)", "https://www.python.org"),
    ("HTTPBin (Standard HTML Sample)", "https://httpbin.org/html"),
    ("Wikipedia: AI (Massive Text & Tables)", "https://en.wikipedia.org/wiki/Artificial_intelligence"),
    ("MDN: JavaScript (Heavy Dev Docs)", "https://developer.mozilla.org/en-US/docs/Web/JavaScript"),
]

def count_tokens(text: str) -> int:
    return max(1, round(len(text) / 3.8))

def run_command_measured(cmd_list, timeout_sec=25):
    t0 = time.perf_counter()
    with tempfile.TemporaryFile(mode="w+b") as out_f, tempfile.TemporaryFile(mode="w+b") as err_f:
        try:
            proc = subprocess.Popen(cmd_list, stdout=out_f, stderr=err_f)
        except Exception as e:
            return {"status": "error", "error": str(e), "elapsed_ms": 0, "peak_ram_mb": 0, "tokens": 0, "actions": 0}

        peak_mem = 0
        try:
            p = psutil.Process(proc.pid)
            while proc.poll() is None:
                if (time.perf_counter() - t0) > timeout_sec:
                    proc.kill()
                    return {"status": "timeout", "elapsed_ms": timeout_sec * 1000, "peak_ram_mb": round(peak_mem / (1024 * 1024), 2), "tokens": 0, "actions": 0}
                try:
                    mem = p.memory_info().rss
                    for child in p.children(recursive=True):
                        try:
                            mem += child.memory_info().rss
                        except Exception:
                            pass
                    if mem > peak_mem:
                        peak_mem = mem
                except Exception:
                    pass
                time.sleep(0.01)
        except Exception:
            pass

        proc.wait(timeout=5)
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        peak_ram_mb = round(peak_mem / (1024 * 1024), 2)

        out_f.seek(0)
        err_f.seek(0)
        stdout = out_f.read().decode("utf-8", errors="replace")
        stderr = err_f.read().decode("utf-8", errors="replace")

        # Determine success
        if proc.returncode != 0 and len(stdout) < 50:
            return {
                "status": "failed",
                "returncode": proc.returncode,
                "elapsed_ms": elapsed_ms,
                "peak_ram_mb": peak_ram_mb,
                "tokens": 0,
                "actions": 0,
                "stderr": stderr[:200]
            }

        # Count action items like [1], [2]
        import re
        action_count = len(re.findall(r'\[\d+\]', stdout))
        tokens = count_tokens(stdout)

        return {
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "peak_ram_mb": peak_ram_mb,
            "tokens": tokens,
            "actions": action_count,
            "output_chars": len(stdout)
        }

def run_suite():
    results = []

    print("==========================================================================================", flush=True)
    print("  MULTI-SITE EMPIRICAL BENCHMARK: OBSCURA vs AEROBROWSE NATIVE RUST", flush=True)
    print("==========================================================================================\n", flush=True)

    for name, url in URLS:
        print(f"[*] Testing [{name}]: {url}", flush=True)

        print("    -> Running Obscura...", end="", flush=True)
        obs = run_command_measured([OBSCURA_BIN, "fetch", url])
        print(f" {obs['status'].upper()} ({obs['elapsed_ms']}ms, {obs['peak_ram_mb']}MB, {obs['tokens']} tokens)", flush=True)

        print("    -> Running AeroBrowse Native...", end="", flush=True)
        aero = run_command_measured([AERO_BIN, "fetch", url])
        print(f" {aero['status'].upper()} ({aero['elapsed_ms']}ms, {aero['peak_ram_mb']}MB, {aero['tokens']} tokens, {aero['actions']} actions)", flush=True)

        token_savings = 0.0
        if obs["tokens"] > 0 and aero["tokens"] > 0:
            token_savings = round((1 - aero["tokens"] / obs["tokens"]) * 100, 1)

        speedup = 0.0
        if aero["elapsed_ms"] > 0 and obs["elapsed_ms"] > 0:
            speedup = round(obs["elapsed_ms"] / aero["elapsed_ms"], 2)

        results.append({
            "name": name,
            "url": url,
            "obscura": obs,
            "aerobrowse": aero,
            "token_savings_pct": token_savings,
            "speedup_x": speedup
        })
        print("", flush=True)

    # Save JSON results
    with open("multi_site_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    # Print Summary Markdown Table
    print("\n" + "=" * 90, flush=True)
    print("                      FULL MULTI-SITE EMPIRICAL RESULTS TABLE", flush=True)
    print("=" * 90, flush=True)
    
    headers = [
        f"| {'Target Site':<32} | {'Obscura Latency':<16} | {'Aero Latency':<14} | {'Obscura RAM':<12} | {'Aero RAM':<10} | {'Tokens Obs':<11} | {'Tokens Aero':<12} | {'Token Savings':<14} | {'Actions':<8} |",
        f"|:{'-'*32}-|-{'-'*16}:|-{'-'*14}:|-{'-'*12}:|-{'-'*10}:|-{'-'*11}:|-{'-'*12}:|-{'-'*14}:|-{'-'*8}:|"
    ]
    for h in headers:
        print(h, flush=True)

    for r in results:
        obs = r["obscura"]
        aero = r["aerobrowse"]
        
        obs_lat = f"{obs['elapsed_ms']:.0f}ms" if obs['status'] == 'success' else obs['status']
        aero_lat = f"{aero['elapsed_ms']:.0f}ms" if aero['status'] == 'success' else aero['status']
        obs_ram = f"{obs['peak_ram_mb']:.1f}MB"
        aero_ram = f"{aero['peak_ram_mb']:.1f}MB"
        obs_tok = f"{obs['tokens']:,}" if obs['tokens'] > 0 else "-"
        aero_tok = f"{aero['tokens']:,}" if aero['tokens'] > 0 else "-"
        savings = f"{r['token_savings_pct']}% saved" if r['token_savings_pct'] > 0 else "0%"
        actions = str(aero['actions'])

        print(f"| {r['name']:<32} | {obs_lat:>16} | {aero_lat:>14} | {obs_ram:>12} | {aero_ram:>10} | {obs_tok:>11} | {aero_tok:>12} | {savings:>14} | {actions:>8} |", flush=True)

    print("=" * 90 + "\n", flush=True)

if __name__ == "__main__":
    run_suite()
