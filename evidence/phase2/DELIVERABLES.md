# Review package index

Implementation source7f5c859; active full CI head582b74c matches all72tracked
implementation/test/workflow/benchmark files. Final full run45843650844 is active;
its completion and browser/soak raw receipt must be recorded before final status.

| Deliverable | Location | Review limit |
|---|---|---|
| Initial complete audit and baseline | AUDIT.md; evidence/baseline-inventory.txt | Historical original code |
| Current finding matrix | PHASE2_AUDIT.md | Unapproved exclusions remain blocking |
| Original requirement map | ACCEPTANCE.md | Partial/not-implemented items explicit |
| Final report | ENGINEERING_REPORT.md | Read tested revisions and measurement limits |
| Threat model / reproduction package | SECURITY.md; SECURITY_REVIEW_PACKAGE.md | No independent assessment |
| Python fixes | aerobrowse/ | Supported Linux browser scope |
| Rust fixes | rust_core/src/ | Native read-only HTTP; Python MCP integration |
| Security regressions | tests/security/; tests/runtime/ | Declared fixtures/canaries, not exhaustive certification |
| Live action / framework tests | tests/browser/; tests/compatibility/ | Synthetic DOM events, four pinned fixture apps |
| MCP / concurrency tests | tests/mcp/; tests/runtime/ | Real stdio/processes, bounded declared contract |
| Measurement harness | benchmarks/phase2/; BENCHMARKS.md | No comparable before/after speedup claim |
| CI / locks | .github/workflows/; uv.lock; rust_core/Cargo.lock | External Sonar gate still open |
| API/capability contract | docs/ENGINE_PARITY.md; COMPATIBILITY.md | Full native parity not claimed |
| Compatibility changes | CHANGELOG.md; README.md | Current0.2.0package not published |
| Final local JUnit | python-source7f-final.xml |161pass/3skip/65deselected |
| Linux kernel/runtime | runtime-7f5c859/runtime-boundary.xml |38pass/2Windows-onlyskip |
| Final package build | build-reviewed.json | Wheel/sdist succeeded;16module bytes match |
| Full-run historical raw receipts | ci-f1ce086/; ci-c963127/ | Earlier source, cannot certify later fixes |
| Current completed short jobs | ci-582b74c/ | Soak completion still required |
| Receipt integrity | receipt-manifest.json; source-final.json | Integrity is not independent custody |

Draft PR#1 targets main; draft PR#2 targets the original hardening branch.
No merge, release, main modification or package publication is authorized here.
