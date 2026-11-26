# Verification index

Release recommendation: **NOT_PRODUCTION_READY**. A passing engineering gate does
not satisfy the unimplemented or unverified scope in ACCEPTANCE.md.

## Current agent continuation

Source: `dac1c1db4146f5b4053b3cc1d97e347ca1250578`. Production modules match
`3e1d399994638a9d08269b642f5c306ce317a1c4` after CRLF normalization; later source
changes affect the model harness and a storage-isolation test. Source Git-blob and
checkout hashes: `evidence/agent/source-dac1c1d.json`.

| Gate | Result | Receipt |
|---|---|---|
| Focused delegated Linux workflows | 14 passed, no skips | run45860943458; evidence/agent/ci-dac1c1d/runtime/agent/quick-workflows.xml |
| Linux kernel/runtime | 38 passed, 2 Windows-only skips | same run; evidence/agent/ci-dac1c1d/runtime/phase2/runtime-boundary.xml |
| Local non-browser | 206 passed, 21 skips, 67 browser deselections | evidence/agent/python-source-final.xml |
| Later focused local tests | 46 passed | evidence/agent/focused-sourcea0dbc66.xml |
| Static checks | Ruff, formatting and mypy pass | local checks of18 production modules |
| Package | Wheel and sdist build;18 wheel modules match checkout | evidence/agent/build-match-source3e1d399.json |
| Actual-model evaluation | NOT_RUN: missing explicit key/model | evidence/agent/model-evaluation-sourcedac1c1d.json |
| Corrected measurements | Complete at0530488;6 tasks/2 workers, operation rows correctly identify engine | run45864267717; evidence/agent/ci-0530488/runtime/ |
| Full final-source CI | Python matrix, Rust and dependencies green; browser cleanup soak running | run45864277407 |

Receipt SHA256 and byte lengths: `evidence/agent/receipt-manifest.json`.
This is local provenance bookkeeping, not independent custody certification.

## Reproduction

Install the locked development environment, build the pinned framework fixtures,
and provision the supported Linux namespace/cgroup environment as documented in
AGENT_QUICKSTART.md and .github/workflows/ci.yml. Do not bypass network isolation
or kernel quotas to make a browser test pass.

```sh
uv sync --locked --extra dev
uv run ruff check aerobrowse tests benchmarks/agent benchmarks/phase2
uv run ruff format --check aerobrowse tests benchmarks/agent benchmarks/phase2
uv run mypy aerobrowse --ignore-missing-imports --check-untyped-defs
uv run python -m pytest -m "not browser"
# In the delegated supported Linux environment:
uv run python -m pytest -m browser -v
uv run python -m pytest tests/runtime -v
uv run python -m benchmarks.agent.concurrency --concurrency 2 --iterations 3
cargo fmt --check --manifest-path rust_core/Cargo.toml
cargo clippy --locked --manifest-path rust_core/Cargo.toml --all-targets --all-features -- -D warnings
cargo test --locked --manifest-path rust_core/Cargo.toml
cargo build --locked --release --manifest-path rust_core/Cargo.toml
```

The Rust job separately runs18 native/Python destination-rejection contracts.
Those tests are skipped locally when no compiled native executable is configured.
Browser tests deliberately skip unsupported Windows hosts; required Linux CI
must execute them. Actual-model evaluation requires explicit credentials/model
and is separate from deterministic workflow tests.

## Historical phase-two results

`evidence/phase2/ci-582b74c/` contains the previously verified full run45843650844:
47 browser passes,38 runtime passes/2 Windows-only skips,688 sequential cycles
in1,801.468 seconds. Earlier receipts describe their tested revision only.
The continuation reproduced login redirect failures and a deadline race; failed
runs are indexed in `evidence/agent/failed-runs.json` and original failing browser
XML is retained. Passing focused receipts do not erase those failures.

Current corrected measurement receipt: `evidence/agent/ci-0530488/runtime/`.
All16 nearest-rank percentile groups reproduce from1,133 raw rows. Six concurrent
tasks use six unique sessions and all worker reaping flags are true. Token fixture
refresh:`evidence/agent/token-fixtures-source0530488.json` contains24 rows with
both Markdown and complete canonical extraction-output costs under3 tokenizers.
The small fixtures expand after metadata; no fixed token-savings claim applies.
