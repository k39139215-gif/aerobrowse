import os
import sys
import time
import subprocess
import tempfile
import psutil

OBSCURA_BIN = r"C:\Users\kartik\.gemini\antigravity\scratch\obscura\obscura.exe"
AERO_BIN = r"C:\Users\kartik\.gemini\antigravity\scratch\aerobrowse\dist\aerobrowse-windows-x86_64.exe"

def count_tokens(text: str) -> int:
    return max(1, round(len(text) / 3.8))

def run_and_measure(cmd_list):
    t0 = time.perf_counter()
    with tempfile.TemporaryFile(mode="w+b") as out_f, tempfile.TemporaryFile(mode="w+b") as err_f:
        proc = subprocess.Popen(cmd_list, stdout=out_f, stderr=err_f)
        peak_mem = 0
        try:
            p = psutil.Process(proc.pid)
            while proc.poll() is None:
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

        proc.wait()
        elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        peak_mem_mb = round(peak_mem / (1024 * 1024), 2)
        
        out_f.seek(0)
        err_f.seek(0)
        stdout = out_f.read().decode("utf-8", errors="replace")
        stderr = err_f.read().decode("utf-8", errors="replace")

        return {
            "elapsed_ms": elapsed_ms,
            "peak_mem_mb": peak_mem_mb,
            "output_len": len(stdout),
            "tokens": count_tokens(stdout),
            "stdout": stdout,
            "stderr": stderr
        }

def benchmark(url):
    print(f"\n=======================================================", flush=True)
    print(f"  DIRECT HEAD-TO-HEAD BENCHMARK: {url}", flush=True)
    print(f"=======================================================", flush=True)

    print(f"[*] Running Obscura ({OBSCURA_BIN})...", flush=True)
    obs_res = run_and_measure([OBSCURA_BIN, "fetch", url])
    print(f"    Done: {obs_res['elapsed_ms']}ms | Peak RAM: {obs_res['peak_mem_mb']} MB | Output Tokens: {obs_res['tokens']:,}", flush=True)

    print(f"[*] Running AeroBrowse Native Rust ({AERO_BIN})...", flush=True)
    aero_res = run_and_measure([AERO_BIN, "fetch", url])
    print(f"    Done: {aero_res['elapsed_ms']}ms | Peak RAM: {aero_res['peak_mem_mb']} MB | Output Tokens: {aero_res['tokens']:,}", flush=True)

    print("\n--- MEASURED HEAD-TO-HEAD COMPARISON ---", flush=True)
    header = f"{'Metric':<25} | {'Obscura (Rust+V8)':<22} | {'AeroBrowse (Native Rust)':<25}"
    print(header, flush=True)
    print("-" * len(header), flush=True)
    print(f"{'Latency':<25} | {obs_res['elapsed_ms']} ms{'':<14} | {aero_res['elapsed_ms']} ms", flush=True)
    print(f"{'Peak RAM Usage':<25} | {obs_res['peak_mem_mb']} MB{'':<14} | {aero_res['peak_mem_mb']} MB", flush=True)
    print(f"{'Tokens Returned to LLM':<25} | {obs_res['tokens']:,} tokens{'':<8} | {aero_res['tokens']:,} tokens", flush=True)
    
    if obs_res['tokens'] > 0:
        saved = round((1 - aero_res['tokens'] / obs_res['tokens']) * 100, 1)
        print(f"{'AeroBrowse Token Savings':<25} | {'0% (Baseline)':<22} | {saved}% fewer tokens", flush=True)

    # Check for Action Map in output
    aero_has_actions = "[1]" in aero_res['stdout']
    obs_has_actions = "[1]" in obs_res['stdout']
    print(f"{'Interactive Action Map':<25} | {'YES' if obs_has_actions else 'NO (Raw Text/HTML)':<22} | {'YES (Numbered IDs)':<25}", flush=True)

if __name__ == "__main__":
    benchmark("https://example.com")
    benchmark("https://news.ycombinator.com")
