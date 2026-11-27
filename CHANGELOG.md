## Unreleased developer continuation

- Reserve per-session task/memory budgets against aggregate capacity. A new
  SESSION_RESOURCE_LIMIT refusal is a documented backpressure compatibility change;
  max_sessions alone does not guarantee capacity. No production default was raised.
- Report aggregate kernel PID/OOM exhaustion and retire affected workers.
- Bundle licensed checksum-verified tokenizer vocabularies for offline worker
  startup; corrupted package data fails explicitly with TOKENIZER_ERROR.
- Add synthetic text editing/caret/select-all/textarea newline with cancellable
  input events and exact-node revalidation; trusted physical input stays unsupported.
- Add a native Linux isolated Chromium/CDP session, shared generation-scoped action
  runtime, network pinning, cgroup guardian, tabs, history, waits, screenshots and reload.
- Fix native hidden-action/descendant text and credential URL label disclosure.
- Confine agent benchmark CLI receipts to exclusive files under evidence/.

- Add bounded discovery waits by exact accessible name/role, fresh generations,
  explicit WAIT_TIMEOUT/PAGE_NAVIGATED, and SDK/MCP regression coverage.
- Preserve common row/column table header associations across spans, document
  language/direction, landmarks and language regions, with inference diagnostics.
- Add public SDK request IDs/structured logs and bounded operator JSON/Prometheus
  telemetry; request inputs never become metric labels.
- Add shared aggregate-pool session/queue/ownership/progress/cleanup workload.
- Existing action-ID waits remain immediate identity checks. Browser security
  policy, quota requirements and fail-closed platform behavior stay mandatory.

# Unreleased native parity follow-up

- Implemented a native Linux Chromium CDP session with Bubblewrap network/mount/PID namespaces, delegated cgroup limits, guardian cleanup, pinned request brokering, generation-validated actions, screenshots, waits, history, tabs, reload and structured stdio errors.
- Added a no-skip Linux integration workflow; latest receipt reports 10 tests passed, 0 failed, 0 skipped.
- Shared the exact action runtime between Python packaging and the Rust crate.
- Full CI run46006851015 passed all11 jobs. Native workflow46006841440 passed
 10 integration/security cases with zero skips; SonarCloud passed on the tested head.

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
  is unavailable. Native Rust Fidelity is available on Linux through `native-session`; other hosts fail closed. The stateless click/fill CLI commands return STALE_ACTION_ID; use a live native-session generation.
- Native Rust MCP requires the Python SDK instead of the previous native server.
- Executable action IDs are generation-scoped strings; numeric IDs and arbitrary
  CSS selectors are rejected. Turbo candidates require live synchronization.
- MCP actions require session_id and generation; outputs are structured dictionaries.
- HTTP Authorization forwarding, WebSockets, service workers, popups and downloads
  remain unavailable. Ephemeral form/cookie authentication is implemented in the
  agent continuation below; host profile import/export is unsupported.
- Python requires >=3.11. CLI fetch outputs JSON; legacy display switches are accepted.
- reduction_pct now means measured token reduction; character_reduction_pct is separate.

These restrictions remove unsafe behavior and are not claims of full feature parity.
Read ENGINEERING_REPORT.md for outstanding acceptance criteria and verification.

- Added operator-only `AEROBROWSE_SESSION_TASKS` (1ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“256) for MCP session task
  budgets; invalid configuration fails startup, defaults and aggregate caps remain.
  Verified actual Linux stdio MCP navigation/fill/close under this explicit budget.

- Bound JSON integer conversion independently of interpreter settings; malformed
  frames return fixed errors and preserve subsequent MCP requests.
- Await already-retiring worker termination during shutdown before pool closure.
  Both defects were reproduced and covered by real-pipe/real-worker regressions.

## Unreleased agent workflow continuation

- Public AeroBrowser and CLI now run in supervised process workers. Fidelity
  requires kernel resource delegation; direct engine internals moved out of the
  normal SDK path. Access to private _fidelity/_turbo is not supported by facade.
- Add ephemeral browser cookie auth via pinned one-hop broker, bounded tabs,
  back/forward/reload and supported-capability discovery.
- Improve nested tables/lists/labels and complete snapshot JSON token accounting.
- Add independently judged owned SDK/MCP workflows and runnable actual-model harness.
- Actual model evaluation NOT_RUN without OPENAI_API_KEY,AEROBROWSE_EVAL_MODEL.

## Agent usability continuation

- Public AeroBrowser SDK and CLI now use killable process workers, request/session
  deadlines and kernel resource pools; internal engine classes remain trusted APIs.
- Add ephemeral Chromium-scoped form/cookie authentication and logout. No host
  cookie jar or profile import/export. Validate and pin every redirected request
  through direct CDP Fetch interception; keep mandatory Linux network isolation.
- Add explicit opaque tabs (maximum eight), back/forward/reload, capability discovery
  and current-document recovery information. Live generations are invalidated.
- Reject Chromium error documents as failed snapshots. Synthetic Enter on a text
  input submits its validated form unless the key handler prevents default.
- Preserve nested lists/tables, wrapped form labels and multilingual extraction;
  distinguish Markdown-only token cost from complete canonical output cost.
- Add complete owned SDK/MCP tasks, concurrent task measurements, session storage
  isolation, runnable actual-model MCP evaluation and reproducible examples.
- Correct benchmark engine labels after handoff: subsequent navigation retains
  Fidelity and must not be reported as Turbo or repeated escalation.

Compatibility: normal `from aerobrowse import AeroBrowser` now owns a subprocess.
Unsupported kernel/browser hosts fail closed. Independent SDK instances need an
operator-provided enclosing resource budget. Browser fields are ephemeral and
crash recovery requires a new session and login. Actual-model evaluation is
NOT_RUN without explicit key/model; no general AI task success is claimed.
