# Contributing

Use Python >=3.11, the locked environment (`uv sync --locked --extra dev`), and current stable Rust. See README.md for Chromium/Linux namespace requirements and all verification commands.

Write regression tests for security/correctness fixes. Use controlled fixtures in CI. Record measurement configuration, failures and tokenizer identity; do not use character estimates as token savings. Preserve public interfaces where safe and document necessary security restrictions in CHANGELOG.md. Review AUDIT.md and ENGINEERING_REPORT.md before declaring acceptance.
