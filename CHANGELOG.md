# Unreleased - production hardening candidate

## Implemented

- DNS-pinned, bounded public HTTP retrieval and redirect validation in Python/Rust.
- Fail-closed Chromium boundary; Linux namespace/host broker implementation in Python.
- Explicit hybrid page state, live resnapshot handoff, generation-scoped node handles.
- Owned MCP sessions, serialized workers, capacity/idle limits, safe errors.
- Bounded semantic extraction, iframe notices and table/header metadata in Python.
- Actual tokenizer measurements, exact dependency locks, deterministic regressions.
- Structured CLI JSON and reproducible measurement harness.

## Breaking security restrictions

- Python Fidelity now requires Linux namespaces; unrestricted Windows/macOS launch
  is unavailable. Native Rust Fidelity/click/fill are unavailable pending parity.
- Native Rust MCP requires the Python SDK instead of the previous native server.
- Executable action IDs are generation-scoped strings; numeric IDs and arbitrary
  CSS selectors are rejected. Turbo candidates require live synchronization.
- MCP actions require session_id and generation; outputs are structured dictionaries.
- Cookies/authorization forwarding, WebSockets, service workers, popups and downloads
  are unavailable. Authenticated browsing is not supported by this candidate.
- Python requires >=3.11. CLI fetch outputs JSON; legacy display switches are accepted.
- reduction_pct now means measured token reduction; character_reduction_pct is separate.

These restrictions remove unsafe behavior and are not claims of full feature parity.
Read ENGINEERING_REPORT.md for outstanding acceptance criteria and verification.
