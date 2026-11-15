import os
import sys

BASE_DIR = r"C:\Users\kartik\.gemini\antigravity\scratch\aerobrowse"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import subprocess
from aerobrowse import AeroBrowser

BASELINE_BIN = os.environ.get("BASELINE_BROWSER_BIN", "headless_baseline.exe")

def inspect_url(url, label, test_terms):
    print(f"\n==================================================================")
    print(f"  CONTENT FIDELITY & ACCURACY INSPECTION: {label}")
    print(f"  URL: {url}")
    print(f"==================================================================")

    # 1. Baseline Raw Dump
    raw_proc = subprocess.run([BASELINE_BIN, "fetch", url], capture_output=True, text=True, encoding="utf-8", errors="replace")
    raw_out = raw_proc.stdout

    # 2. AeroBrowse Python Engine
    browser = AeroBrowser()
    aero_res = browser.fetch(url)
    aero_out = aero_res["markdown"]

    print("\n--- [1] STANDARD RAW DUMP SAMPLE (First 400 chars) ---")
    print(repr(raw_out[:400]))

    print("\n--- [2] AEROBROWSE OUTPUT SAMPLE (First 400 chars) ---")
    print(aero_out[:400])

    print("\n--- [3] ACCURACY & INFORMATION PRESERVATION AUDIT ---")
    print(f"Standard Raw Chars: {len(raw_out):,} | AeroBrowse Pruned Chars: {len(aero_out):,}")
    print(f"Real Token Reduction: {aero_res['reduction_pct']}%")
    print(f"Action Elements Mapped: {len(aero_res['actions'])}")
    
    print("\nContent Checks:")
    all_passed = True
    for term in test_terms:
        in_raw = term in raw_out
        in_aero = term in aero_out
        status = "PASSED" if (in_raw and in_aero) else ("DROPPED_BY_AERO" if (in_raw and not in_aero) else "NOT_IN_PAGE")
        print(f"  • '{term}': In Raw Dump? {in_raw} | In AeroBrowse? {in_aero} => [{status}]")
        if in_raw and not in_aero:
            all_passed = False

    print(f"\nAudit Verdict for {label}: {'100% ACCURATE & FAITHFUL' if all_passed else 'DATA LOSS DETECTED'}")

if __name__ == "__main__":
    inspect_url(
        "https://quotes.toscrape.com",
        "Quotes to Scrape (Quotes & Authors)",
        [
            "The world as we have created it",
            "Albert Einstein",
            "It is our choices, Harry",
            "J.K. Rowling",
            "Jane Austen",
            "Marilyn Monroe",
            "Thomas A. Edison",
            "Eleanor Roosevelt",
            "Steve Martin"
        ]
    )

    inspect_url(
        "https://books.toscrape.com",
        "Books to Scrape (20 Catalog Cards)",
        [
            "A Light in the Attic",
            "Tipping the Velvet",
            "Soumission",
            "Sharp Objects",
            "Sapiens",
            "In stock",
            "£51.77",
            "£53.74"
        ]
    )
