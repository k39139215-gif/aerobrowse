"""Verify selected receipts without network access or modifying evidence."""

import argparse
import hashlib
import json
import math
import subprocess
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


def read(path):
    raw = path.read_bytes()
    return json.loads(
        raw.decode("utf-16" if raw.startswith(b"\xff\xfe") else "utf-8-sig")
    )


def verify(root, checkout):
    index = read(root / "receipt-index-8db91bf.json")
    for relative, receipt in index["files"].items():
        path = root / relative
        assert path.stat().st_size == receipt["bytes"], relative
        assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["sha256"], (
            relative
        )
    source = read(root / "source-8db91bf.json")
    for relative, binding in source["files"].items():
        blob = subprocess.check_output(
            ["git", "rev-parse", "HEAD:" + relative], cwd=checkout, text=True
        ).strip()
        assert blob == binding["git_blob"], relative
        assert (
            hashlib.sha256((checkout / relative).read_bytes()).hexdigest()
            == binding["sha256"]
        ), relative
    benchmark = read(root / "ci-8db91bf/phase2/benchmark-linux.json")
    assert benchmark["revision"] == source["revision"]
    groups = defaultdict(list)
    for row in benchmark["raw"]:
        groups[row["operation"]].append(row)
    for operation, rows in groups.items():
        values = sorted(row["elapsed_ms"] for row in rows)
        summary = benchmark["statistics"][operation]
        assert summary["samples"] == len(rows)
        for key, quantile in [
            ("median_ms", 0.5),
            ("p90_ms", 0.9),
            ("p95_ms", 0.95),
            ("p99_ms", 0.99),
        ]:
            assert summary[key] == values[math.ceil(quantile * len(values)) - 1], (
                operation
            )
        assert summary["failure_rate"] == sum(not row["success"] for row in rows) / len(
            rows
        )
    quality = read(root / "extraction-quality-8db91bf.json")
    assert quality["missing_requirements"] == sum(
        len(row["missing"]) for row in quality["cases"]
    )
    assert quality["checked_requirements"] == sum(
        row["checked_requirements"] for row in quality["cases"]
    )
    assert (
        quality["recall"]
        == 1 - quality["missing_requirements"] / quality["checked_requirements"]
    )
    load = read(root / "ci-8db91bf/developer/shared-browser-load.json")
    assert load["limits"]["aggregate_processes"] == 512
    assert load["successful_operations"] == load["completed_operations"] == 12
    assert sum(row["completed"] for row in load["sessions"]) == 12
    assert all(row["worker_reaped"] for row in load["sessions"])
    assert load["active_sessions_after_cleanup"] == 0
    assert load["overload_rejections"] == 2
    assert load["foreign_session_rejected"] and load["capacity_rejected"]
    counts = {}
    for relative in [
        "python-8db91bf.xml",
        "native-contract-8db91bf.xml",
        "ci-8db91bf/agent/quick-workflows.xml",
        "ci-8db91bf/phase2/runtime-boundary.xml",
    ]:
        suites = ET.parse(root / relative).getroot().findall("testsuite")
        totals = {
            key: sum(int(suite.attrib.get(key, 0)) for suite in suites)
            for key in ["tests", "failures", "errors", "skipped"]
        }
        assert totals["errors"] == totals["failures"] == 0, relative
        counts[relative] = totals
    full = root / "full-8db91bf/final-run.json"
    if full.exists():
        run = read(full)
        assert run["headSha"] == source["revision"]
        assert run["conclusion"] == "success"
        assert all(job["conclusion"] == "success" for job in run["jobs"])
    return {
        "revision": source["revision"],
        "artifact_hashes": len(index["files"]),
        "source_blobs": len(source["files"]),
        "raw_rows": len(benchmark["raw"]),
        "distributions": len(groups),
        "tests": counts,
        "full_ci_receipt_present": full.exists(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(
        json.dumps(
            verify(Path(__file__).resolve().parent, args.checkout.resolve()), indent=2
        )
    )
