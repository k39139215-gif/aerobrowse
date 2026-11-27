# Developer update remediation plan

Goal: Close actionable developer-facing reliability, extraction, observability and
shared-runtime load gaps from the original authorized remediation.
Architecture: Preserve supervised Python workers, exact generation/node identity,
mandatory Linux isolation and pinned broker. Keep existing interfaces compatible.
Spec: Original production remediation; ACCEPTANCE.md. Continue work in main session.

## Work units
1. Bounded dynamic waits: preserve existing ID+generation immediate identity check;
   add accessible-name/role discovery with timeout/polling and new live generation.
   Never execute or remap an old ID; timeouts return a machine-readable error.
   Regression: late inserted/disabled controls, absence timeout, changed DOM,
   existing ID staleness, invalid arguments, SDK and MCP schemas.
2. Extraction: infer table row/column headers (including spans), keep explicit
   headers authoritative; retain document language/direction and landmarks.
   Regression: realistic financial tables, scoped groups, nested tables, malformed
   spans, RTL and multilingual content. Add controlled recall grading harness.
3. Observability: bounded low-cardinality operation/error/latency counters with
   sampling scope; SDK request IDs/structured logs and operator snapshot/export.
   No values,URLs,cookies,selectors or client-provided operation labels in metrics.
   Regression: real successful/failed requests, owner isolation, bounded keys,
   cancellation/timeouts, export escaping and cleanup.
4. Shared-pool stress: measure actual SessionManager workers using bounded queues
   and one aggregate quota pool; exercise concurrent same-session calls,foreign
   owner rejection, overload, progress per session and cleanup. Raw timings,
   scope/limits recorded; do not claim fairness from tiny workload.
5. Run full local checks and required Linux browser/kernel/CI gates on changed
   source; inspect diff; coherent commits, updated docs, reports and draft PR.

Native Rust browser parity and wider browser capabilities remain original scope.
Do not label delegation as independent native implementation or disabled operations
as implemented. Do not publish/merge/version-bump without explicit authorization.
