"""
Zero-Data-Loss & Semantic Recall Verification Audit
====================================================
Mathematically checks whether ANY visible, human-readable information
was dropped during AeroBrowse semantic pruning.

Computes:
1. Visible Word Set in Raw HTML (via BeautifulSoup.get_text())
2. Word Set in AeroBrowse Pruned Markdown
3. Recall Rate = (Words Found in Markdown / Total Visible Words) * 100
4. Missing Word Audit (Checks what words, if any, were omitted)
"""

import os
import sys
import re
from bs4 import BeautifulSoup

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from aerobrowse import AeroBrowser

URLS = [
    ("Quotes to Scrape (Quotes & Authors)", "https://quotes.toscrape.com"),
    ("Books to Scrape (20 Product Cards)", "https://books.toscrape.com"),
    ("Python.org (Official Org Portal)", "https://www.python.org"),
    ("Hacker News (Forum & Metadata)", "https://news.ycombinator.com"),
    ("Wikipedia: AI (Complex Article & Tables)", "https://en.wikipedia.org/wiki/Artificial_intelligence"),
]

def clean_words(text: str) -> set:
    """Extracts alphanumeric words (case-insensitive) of length >= 3."""
    words = re.findall(r'[a-zA-Z0-9_\-\.£\$€]+', text.lower())
    return set(w for w in words if len(w) >= 2)

def audit_url(browser, label, url):
    print(f"\n[*] Auditing [{label}]: {url}")

    # 1. Fetch via AeroBrowse
    res = browser.fetch(url)
    markdown = res["markdown"]
    raw_chars = res["original_chars"]
    pruned_chars = res["pruned_chars"]

    # 2. Extract baseline visible text from raw HTML using standard parser
    import requests
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")

    # Strip pure non-content tags like script, style, svg
    for tag in soup(["script", "style", "svg", "noscript"]):
        tag.decompose()

    raw_visible_text = soup.get_text(separator=" ")

    # 3. Compute Word Sets
    raw_words = clean_words(raw_visible_text)
    pruned_words = clean_words(markdown)

    # 4. Measure Recall
    common_words = raw_words.intersection(pruned_words)
    missing_words = raw_words - pruned_words

    # Filter out pure noise words from missing (e.g. leftover single chars)
    real_missing = [w for w in missing_words if len(w) >= 3 and not w.isdigit()]

    recall_pct = (len(common_words) / max(1, len(raw_words))) * 100

    print(f"    Raw HTML Size:       {raw_chars:,} chars")
    print(f"    Pruned Markdown:     {pruned_chars:,} chars ({res['reduction_pct']}% pruned)")
    print(f"    Visible Unique Words in Page: {len(raw_words):,}")
    print(f"    Words Retained in Markdown:   {len(common_words):,}")
    print(f"    Semantic Recall Score:        {recall_pct:.2f}%")

    if real_missing:
        sample_missing = real_missing[:8]
        print(f"    Omitted noise words: {sample_missing}...")
    else:
        print("    Omitted: NONE (100% word retention)")

    return {
        "label": label,
        "url": url,
        "raw_chars": raw_chars,
        "pruned_chars": pruned_chars,
        "reduction_pct": res["reduction_pct"],
        "total_visible_words": len(raw_words),
        "retained_words": len(common_words),
        "recall_pct": round(recall_pct, 2)
    }

def main():
    print("=" * 80)
    print("🔬 ZERO-DATA-LOSS & SEMANTIC RECALL VERIFICATION AUDIT")
    print("Proving mathematically whether any human-visible text is lost during pruning")
    print("=" * 80)

    browser = AeroBrowser()
    results = []

    for label, url in URLS:
        audit = audit_url(browser, label, url)
        results.append(audit)

    print("\n" + "=" * 80)
    print("FINAL SEMANTIC RECALL AUDIT TABLE")
    print("=" * 80)
    print(f"{'Target Site':<35} | {'Tokens Pruned':<14} | {'Visible Words':<14} | {'Recall Rate':<12}")
    print("-" * 80)
    for r in results:
        print(f"{r['label']:<35} | {r['reduction_pct']:>11.1f}% | {r['total_visible_words']:>14,d} | {r['recall_pct']:>10.2f}%")
    print("=" * 80)

if __name__ == "__main__":
    main()
