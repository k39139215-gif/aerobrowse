# 📊 AeroBrowse Empirical Benchmark Suite

This directory contains standalone, reproducible benchmark and quality audit scripts comparing AeroBrowse against standard headless browsers across live production web targets.

## Benchmark Scripts

| Script | Purpose | Run Command |
| :--- | :--- | :--- |
| **`multi_sites.py`** | 8-site empirical test across Wikipedia, MDN, Python.org, Books, Quotes, Hacker News. Tracks RSS memory (`psutil`), latency, tokens, and actions. | `python benchmarks/multi_sites.py` |
| **`engine_comparison.py`** | Triple-engine comparison across SPAs and dynamic sites (Standard Headless Chromium vs AeroBrowse Turbo vs AeroBrowse Fidelity). | `python benchmarks/engine_comparison.py` |
| **`content_quality.py`** | Verifies zero-data-loss content fidelity on complex nested cards, quotes, and product listings. | `python benchmarks/content_quality.py` |
| **`comparison.py`** | Head-to-head comparison on Example.com and Hacker News. | `python benchmarks/comparison.py` |

## Reproduction Instructions

1. Install benchmark dependencies:
   ```bash
   pip install psutil curl_cffi beautifulsoup4 requests
   ```
2. Build the native Rust binary:
   ```bash
   cd rust_core && cargo build --release
   ```
3. Run any benchmark:
   ```bash
   python benchmarks/multi_sites.py
   ```
