"""Explicit requirement recall on owned fixtures; not representative public-site recall."""

import argparse
import hashlib
import json
import subprocess

from aerobrowse.benchmark import write_receipt
from aerobrowse.pruner import SemanticPruner

CASES = [
    (
        "documentation",
        '<nav aria-label="Guide">API</nav><main><h1>Reference</h1><p>Returns a snapshot.</p><pre>fetch(url)</pre></main>',
        [
            ("markdown", "Reference"),
            ("markdown", "Returns a snapshot."),
            ("markdown", "fetch(url)"),
            ("landmarks", "navigation"),
        ],
    ),
    (
        "ecommerce",
        '<h1>Keyboard</h1><p>₹2500</p><img alt="Mechanical keyboard" src="/item.png"><button>Add to basket</button>',
        [
            ("markdown", "₹2500"),
            ("markdown", "Mechanical keyboard"),
            ("actions", "Add to basket"),
        ],
    ),
    (
        "news",
        "<article><h1>Park approved</h1><p>Reporter: Asha</p><p>The council voted Monday.</p></article>",
        [
            ("markdown", "Park approved"),
            ("markdown", "Reporter: Asha"),
            ("markdown", "voted Monday"),
        ],
    ),
    (
        "dashboard",
        '<main><h1>Receivables</h1><dl><dt>Open</dt><dd>₹42</dd></dl><button aria-label="Refresh">↻</button></main>',
        [("markdown", "Receivables"), ("markdown", "₹42"), ("actions", "Refresh")],
    ),
    (
        "search",
        '<ol start="3"><li><a href="/one">First result</a><p>Relevant snippet</p></li><li>Second result</li></ol>',
        [
            ("markdown", "3. "),
            ("markdown", "Relevant snippet"),
            ("markdown", "4. Second result"),
            ("actions", "https://example.com/one"),
        ],
    ),
    (
        "long_article",
        "<article><h1>Long article</h1>"
        + "".join(
            "<p>Section " + str(i) + " discusses 中文 العربية content.</p>"
            for i in range(100)
        )
        + "</article>",
        [
            ("markdown", "Section 0 discusses"),
            ("markdown", "Section 50 discusses"),
            ("markdown", "Section 99 discusses"),
        ],
    ),
    (
        "table",
        '<table><tr><th scope="col">Name</th><th scope="col">Total</th></tr><tr><th scope="row">Alpha</th><td>42</td></tr></table>',
        [
            ("tables", "Total"),
            ("tables", "Alpha"),
            ("tables", '"inferred_headers"'),
            ("tables", '"text": "42"'),
        ],
    ),
    (
        "form",
        '<form><label for="n">Full name</label><input id="n"><label>Choice<select><option>A</option></select></label><label><input type="checkbox" checked>Agree</label><button>Submit</button></form>',
        [
            ("actions", "Full name"),
            ("actions", "Choice"),
            ("markdown", "checked"),
            ("actions", "Submit"),
        ],
    ),
    (
        "rtl",
        '<html lang="ar" dir="rtl"><main><h1>مرحبا</h1><p lang="he" dir="rtl">שלום</p><p>中文 नमस्ते</p></main></html>',
        [
            ("document", '"language": "ar"'),
            ("document", '"direction": "rtl"'),
            ("language_regions", "שלום"),
            ("markdown", "中文 नमस्ते"),
        ],
    ),
    (
        "malformed",
        "<h2>Recovered heading<p>First<b>Bold<ul><li>Nested<li>Last",
        [
            ("markdown", "Recovered heading"),
            ("markdown", "Bold"),
            ("markdown", "Nested"),
            ("markdown", "Last"),
        ],
    ),
    (
        "embeds_dialog",
        '<dialog open aria-label="Confirm"><p>Review before submitting</p><button>Confirm</button></dialog><iframe title="Report" src="https://embed.example/report"></iframe>',
        [
            ("landmarks", "dialog"),
            ("markdown", "Review before submitting"),
            ("markdown", "Report"),
            ("quality", "embedded_content"),
        ],
    ),
    (
        "nested_table",
        '<table><tr><th scope="row">Outer</th><td>42<table><tr><th scope="row">Inner</th><td>9</td></tr></table></td></tr></table>',
        [
            ("tables", "Outer"),
            ("tables", "Inner"),
            ("tables", '"parent_table": 0'),
            ("tables", '"nested_tables": [1]'),
        ],
    ),
]


def run() -> dict:
    pruner = SemanticPruner()
    rows = []
    for name, html, checks in CASES:
        snapshot = pruner.prune(html, "https://example.com")
        missing = [
            {"field": key, "expected": expected}
            for key, expected in checks
            if expected
            not in (
                snapshot[key]
                if isinstance(snapshot[key], str)
                else json.dumps(snapshot[key], ensure_ascii=False)
            )
        ]
        rows.append(
            {
                "fixture": name,
                "input_sha256": hashlib.sha256(html.encode()).hexdigest(),
                "checked_requirements": len(checks),
                "missing": missing,
                "original_html_tokens": snapshot["original_tokens"],
                "markdown_tokens": snapshot["extracted_tokens"],
                "complete_json_tokens": snapshot["serialized_output"]["tokens"],
                "complete_json_reduction_pct": snapshot["serialized_output"][
                    "reduction_pct"
                ],
                "markdown_reduction_pct": snapshot["token_reduction_pct"],
                "character_reduction_pct": snapshot["character_reduction_pct"],
                "tokenizer": snapshot["tokenizer"],
                "quality": snapshot["quality"],
            }
        )
    checked = sum(row["checked_requirements"] for row in rows)
    missing = sum(len(row["missing"]) for row in rows)
    return {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "checked_requirements": checked,
        "missing_requirements": missing,
        "recall": (checked - missing) / checked,
        "cases": rows,
        "limitations": [
            "Owned synthetic corpus; predefined literal/structural requirements,not general semantic recall or live-site compatibility",
            "Complete JSON includes pruner metadata; runtime,MCP,model chat overhead additional",
            "Expected expansion on small fixtures; no fixed savings or speedup claim",
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output", default="evidence/developer/extraction-quality.json"
    )
    args = parser.parse_args()
    result = run()
    write_receipt(args.output, result)
    if result["missing_requirements"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
