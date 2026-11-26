# Baseline receipt

- Revision: 44f3e73409d3f0c4e6e376f0c98198abd00ccc0f
- Python 3.12.10: `python -m pytest tests -q`: 5 passed in 11.44s.
- `cargo --version`: no configured default toolchain.
- `cargo +stable test --manifest-path rust_core/Cargo.toml`: failed before compilation,
  missing manifest in stable-x86_64-pc-windows-gnu.
- Docker daemon unavailable. WSL distribution listing returned no distributions.
- No defensible before latency/RAM/token/concurrency benchmark recorded.
- Historical `benchmarks/100_page_audit_results.json` retained as historical data;
  associated scripts estimate tokens by character division, so token claims are unverified.
