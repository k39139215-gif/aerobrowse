# Contributing to AeroBrowse

Thank you for your interest in contributing to AeroBrowse! AeroBrowse is built with radical honesty, precision engineering, and open-source principles to make web browsing featherweight and token-efficient for AI agents.

## Development Setup

### 1. Prerequisites
- Python 3.10+ (for Python SDK & FastMCP server)
- Rust 1.75+ (for Native Rust Core)
- System browser installed (Google Chrome or Microsoft Edge)

### 2. Python Setup
```bash
git clone https://github.com/k39139215-gif/aerobrowse.git
cd aerobrowse
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .venv\Scripts\activate
pip install -e ".[dev]"
playwright install chromium
```

### 3. Rust Core Setup
```bash
cd rust_core
cargo check
cargo test
cargo build --release
```

## Running Tests
Run the automated pytest test suite:
```bash
pytest tests/ -v
```

Run Rust unit tests:
```bash
cargo test --manifest-path rust_core/Cargo.toml
```

## Contribution Guidelines
1. **Zero Hallucination Pruning**: Ensure semantic pruner edits preserve 100% of human-readable text and headings.
2. **Empirical Measurements**: All speed and token claims must be verifiable via real benchmarks in `benchmarks/`.
3. **Commit Messages**: Follow Conventional Commits (`feat:`, `fix:`, `docs:`, `perf:`, `test:`).
4. **Pull Requests**: Ensure all GitHub Actions CI checks pass before requesting review.
