# Unreleased phase-two remediation

No version bump, stable release or production-readiness claim.

- Replace thread-owned MCP browsers with correlated process workers, hard teardown,
  lifecycle states and explicit cgroup/Job Object resource capability detection.
- Add minimal Bubblewrap filesystem/process/network boundaries and real TCP/UDP
  canary/descendant checks, including routing-bypass attempts.
- Bind action snapshots and activation to an isolated-world retained node map,
  mutation epoch and document generation in a single renderer task. Actions now
  use synthetic DOM events; isTrusted-dependent flows are unsupported.
- Bound MCP newline frames before SDK decoding, restrict JSON shape and active IDs,
  and enforce partial-frame/output deadlines. MCP batches remain unsupported.
- Add real pinned React/Vue/Next/Angular fixtures and native/Python rejection contracts.
- Declare Python authoritative browser runtime; Rust MCP is an integration layer.
- Add raw percentile benchmarks and a mandatory 30-minute cleanup soak harness.

Compatibility changes: Linux MCP Fidelity now requires delegated kernel quotas;
other platforms keep fail-closed Fidelity. Closed session managers cannot reopen.
Live actions may return STALE_ACTION_ID on any observed DOM mutation and arbitrary
keyboard input is not advertised. See SECURITY.md and docs/ENGINE_PARITY.md.

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

- Added operator-only `AEROBROWSE_SESSION_TASKS` (1–256) for MCP session task
  budgets; invalid configuration fails startup, defaults and aggregate caps remain.
  Verified actual Linux stdio MCP navigation/fill/close under this explicit budget.
