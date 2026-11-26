# AeroBrowse remediation audit

Baseline: `44f3e73409d3f0c4e6e376f0c98198abd00ccc0f`, inspected 2026-11-26.
Inventory: `evidence/baseline-inventory.txt`. All tracked source, tests, configuration,
examples, notebook cells, documentation, assets and historical benchmark data were inspected.
No repository AGENTS.md was present. User-supplied instructions apply.

## Architecture and baseline

Python has a synchronous Turbo HTTP client, BeautifulSoup semantic extractor,
lazy Playwright Fidelity engine and FastMCP stdio server. Rust independently
implements reqwest retrieval, scraper extraction, CDP WebSocket control and a
hand-written line-oriented JSON-RPC server. Neither implementation shares state
or action semantics with the other. The web demo and examples call the Python SDK.

Baseline Python: **5 passed in 11.44s** on Python 3.12.10; three tests require
third-party sites. Rust baseline could not execute: installed GNU stable toolchain
has a missing manifest; no default toolchain configured. This is an environment
failure, not a passing build. Historical benchmark token counts use character
division and are not tokenizer evidence.

## Confirmed findings

| ID | Priority | Affected files | Root cause and impact | Remediation |
|---|---|---|---|---|
| NET-01 | P0 | Python turbo.py; Rust turbo.rs | Arbitrary destinations and automatic redirects, unrestricted DNS and proxy environment; permits private-service requests | Central policy, public address checks, numeric connection pinning, per-hop validation, no environment proxies |
| NET-02 | P0 | Python fidelity.py; Rust fidelity.rs | Chromium has host networking; arbitrary pages can reach local services | Enforced OS network namespace plus validated host broker; fail closed without isolation |
| ACT-01 | P0 | Rust fidelity.rs | Field data interpolated into JavaScript with incomplete escaping; executable injection possible | Remove unsafe CDP execution path until secure parity exists; explicit unsupported errors |
| SES-01 | P0 | Python mcp_server.py | Global browser shared across tools/clients; no ownership/locking | Explicit session capability plus transport owner, bounded per-session worker, expiry and cleanup |
| ACT-02 | P1 | Python pruner.py, fidelity.py; Rust pruner.rs, fidelity.rs | Parser and live DOM independently number different element sets; Rust falls back to element ordinal | Live node identity and generation mapping; no ordinal fallback |
| HYB-01 | P1 | Python engine.py | Click/fill starts empty Fidelity page after Turbo fetch | Explicit active state; navigate/re-extract then return synchronization snapshot without performing stale action |
| SES-02 | P1 | Rust mcp.rs | Every click/fill launches a fresh browser, ignores navigation failures | Disable unsafe native interaction; do not claim session parity |
| RES-01 | P1 | Both HTTP engines, parsers, MCP servers | No bounded response, parser depth, request length or session limits | Explicit resource limits and timeouts |
| RES-02 | P1 | Rust fidelity.rs | PID-derived port/profile collisions; launch errors leak child; receive loops can block indefinitely; kill without wait | Remove unsafe launch path; retain explicit fail-closed compatibility interface |
| ERR-01 | P1 | Both MCP implementations, Python engines | Raw exception strings and typed form values exposed; unknown JSON-RPC methods return success; Python CLI prints banner to stdio | Safe error envelopes, SDK protocol handling, stderr logs only |
| EXT-01 | P2 | Both pruners | Iframes discarded, tables flattened, recursive depth unbounded, hidden controls exposed | Bounded semantic walk, table/header metadata, explicit embedded-content limitations |
| MET-01 | P2 | CLI, benchmark scripts, README, metadata | Characters labelled tokens; fixed RAM/speed/compatibility claims without reproducible evidence | Actual versioned tokenizers, measured harness, withdraw unsupported claims |
| CI-01 | P2 | .github/workflows/ci.yml, manifests | No Rust lint, Python types/lint/security checks; live-site tests; unbounded dependencies/no locks; workflow-wide write permission | Deterministic fixtures, least privilege, locks, checks and artifacts |
| API-01 | P2 | examples/quickstart_python.py | Imports nonexistent AeroEngine | Correct SDK example and verify import path |

## Risks, not confirmed vulnerabilities

Dependency vulnerabilities require live advisory scans against resolved locks;
absence of a lock is not itself proof of a vulnerable dependency. Browser crash
recovery, framework compatibility and process leak behavior need controlled browser
tests in a supported isolated Linux environment. Word-set recall cannot establish
information preservation, semantic correctness or table relationship fidelity.

## Execution and acceptance

1. Audit/baseline commit.
2. P0 network policy/transport and fail-closed Chromium boundary with regressions.
3. Hybrid state and synchronization.
4. Live action generations and implemented operations.
5. MCP isolated sessions and bounded scheduling.
6. Semantic extraction and tokenizer measurements.
7. Rust network/input hardening and explicit unsupported features.
8. Reproducible measurements; optimize only with measured evidence.
9. CI, documentation and final evidence/status report.

Requirements not safely completed will remain explicitly open. A draft PR does
not establish production readiness. Native Rust browser parity and verified
Chromium namespace operation are acceptance gates, not documentation-only fixes.
## Phase 2 checkpoint

Python transport regression: 36 passed (3.14s). Loopback regression first failed
against baseline by returning the private service content. Namespace launch refusal
first failed against baseline by successfully navigating with unrestricted host networking.
DNS pinning uses a real local TCP server with substituted resolver answers.
Chromium broker and namespace implementation remain unverified on Linux; Windows
launch is deliberately unsupported. Cookies and authorization are not forwarded;
authenticated applications are currently unsupported. Rust P0 paths remain open
until phase 7. No production-readiness claim.
## Phase 3 checkpoint

Hybrid state tests first failed on missing policy/state, security failure fallback,
and action-without-navigation behavior. Explicit URL/engine/session state and lock
now preserve static snapshots and prevent fallback after policy rejection. Turbo to
Fidelity deliberately returns a live synchronization snapshot with STALE_ACTION_ID;
it does not pretend static IDs match browser elements. End-to-end handoff still
requires isolated Linux browser verification.
