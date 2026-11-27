# Reproduce verification

Current implementation: `8db91bf2bbdd84966cb6032cdd9a86b96e2bc06d`.
Release recommendation: **NOT_PRODUCTION_READY**. See ACCEPTANCE.md for all
remaining original scope and ENGINEERING_REPORT.md for measured results.

## Install and check

Use the locked environment and a supported Linux namespace/cgroup host for browser
tests; provisioning is in AGENT_QUICKSTART.md and .github/workflows/ci.yml.
Never remove isolation or quotas to make a test pass.

```sh
uv sync --locked --extra dev
uv run playwright install --with-deps chromium
uv run ruff check aerobrowse tests benchmarks/agent benchmarks/phase2
uv run ruff format --check aerobrowse tests benchmarks/agent benchmarks/phase2
uv run mypy aerobrowse --ignore-missing-imports --check-untyped-defs
uv run python -m pytest -m "not browser"
# On the configured, delegated Linux host:
uv run python -m pytest -m browser -v
uv run python -m pytest tests/runtime -v
cargo fmt --check --manifest-path rust_core/Cargo.toml
cargo clippy --locked --manifest-path rust_core/Cargo.toml --all-targets --all-features -- -D warnings
cargo test --locked --manifest-path rust_core/Cargo.toml
cargo build --locked --release --manifest-path rust_core/Cargo.toml
```

Set AEROBROWSE_NATIVE_BINARY to the built executable and run
`python -m pytest tests/mcp/test_engine_contract.py` for the 18 real compiled
native/Python negative URL/browser-refusal contracts. They do not prove native
live-browser parity. Build pinned real framework fixtures as CI does before
running compatibility tests. No CI test depends on a third-party website.

## Current receipts

- Focused Linux run 45880812905: SUCCESS; 33 workflow passes, 40 runtime passes
  and 2 Windows-only skips; explicit 512-task shared browser load passes.
- Local non-browser: 236 passes / 21 explained native/platform skips. Each of the
  8 full Linux/Windows Python 3.11–3.14 jobs has the same totals.
- Rust formatting, strict Clippy, 8 native units, release build and audit pass.
  Actual compiled native/Python contract passes 18/18 without skips.
- Package wheel matches all 24 source/data entries; all 3 encodings initialize
  offline with socket creation denied. Corrupt vocabulary data fails explicitly.
- Extraction corpus: 44 predefined requirements / 0 missing across 12 fixtures.
  General page recall is not measured.
- Full engineering run45880822782 is SUCCESS:76 browser passes,40 runtime
  passes/2 Windows-only skips;1,044 successful cycles over1,800.891 seconds,
  zero observed orphan processes/occupied slots. Earlier results remain historical.
- SonarCloud remains red: 46 open findings, including 2 private-tmpfs path findings.
  No security finding is suppressed or waived. Actual-model evaluation is NOT_RUN.

From the repository root, run:

```sh
python evidence/developer/verify.py
```

This checks selected artifact hashes, 92 tracked Git source blobs, the 1,133 raw
operation rows and 16 summary calculations, corpus totals, shared-load admission/
reaping and selected test XML. Full final CI is checked when its receipt exists;
absence is printed explicitly. PR merge tree13cf4e086bf0fe11a8febae0e4e247d6e6f97a9d
matches all 92 indexed implementation blobs. These are first-party receipts,
not independent audit or evidence-custody claims.

Generated artifacts can produce benchmark dirty=true. Check tracked source blobs
rather than interpreting that flag as implementation drift. Raw failed XML retains
original whitespace. Source/document whitespace checks exclude preserved receipts.
Original capacity, keyboard and native disclosure failures remain indexed under
evidence/developer/. No benchmark before/after speedup or production capacity is
claimed. See BENCHMARKS.md for the exact measurement and sampling scopes.

Analyzer gate detail:44 CODE_SMELL and2 VULNERABILITY items; new_security_rating
actual4 versus required1. The2 private-tmpfs path items remain open and unsuppressed;
see evidence/developer/ANALYZER_TRIAGE.md. Passing tests do not close this gate.
