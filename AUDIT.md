# AeroBrowse remediation audit

Phase-two superseding evidence and open gates: [PHASE2_AUDIT.md](PHASE2_AUDIT.md),
[ENGINEERING_REPORT.md](ENGINEERING_REPORT.md), and [SECURITY_REVIEW_PACKAGE.md](SECURITY_REVIEW_PACKAGE.md).
Current release recommendation: NOT_PRODUCTION_READY. Earlier receipts below are
historical and do not prove later runtime changes.


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
## Phases 4 and 5 checkpoint

Live DOM mapping now uses retained ElementHandles rather than page-writable ID
attributes or selector/ordinal fallback. IDs embed a random snapshot generation;
DOM content changes, navigation and disconnected nodes are rejected. Static
candidates are marked non-executable. Click/fill/select/check/press/scroll/wait
are implemented in Python; browser execution remains pending Linux integration.
Local action/state/security tests: 41 passed. Session ownership/capacity and
concurrent snapshot tests: 2 passed. Dedicated per-session workers preserve
Playwright thread affinity. Cancellation retires a session and queues cleanup;
hard termination of a stuck worker is not implemented and remains a limitation.
## Phase 6 checkpoint

Extraction regressions: 4 initially failed, then passed; existing four
pruner/Turbo/unified tests also passed (8 combined). Real tokenizer counts use
cl100k_base by default, with o200k_base/p50k_base options. Tokenizer failures
are explicit errors. Character reduction remains a separate field. Full table
cell/header metadata and inaccessible embedded content notices are returned.
All form values are omitted by default. Static visibility remains unknown.
## Phase 7 checkpoint

Rust now validates URLs/resolved addresses, pins reqwest DNS resolution, disables
implicit proxies/redirects, limits bodies/deadlines, and measures real cl100k_base
tokens with tiktoken-rs 0.12.1. Native Chromium was removed from execution because
its process/network boundary was unsafe; it explicitly fails closed. Native MCP
launches the maintained Python stdio server, making Python a documented runtime
requirement for MCP. These are deliberate breaking restrictions, not full native
feature parity. Five Rust tests passed; strict Clippy all-targets/all-features
passed on workspace-local Rust 1.100.0 LLVM Windows target. Native HTML tables
remain less complete than Python. Rust HTTP integration tests still need expansion.
## Phases 8 and 9 checkpoint

No performance optimization was attempted while browser acceptance gates remain
open. A reproducible harness and eight controlled tokenizer cases now record
measurements/failures and explicit limitations. Historical benchmark entrypoints
are retired to prevent character-estimate claims. README/security/changelog and
public metadata were rewritten to match implemented restrictions. CI has locked
Python dependencies, pinned action revisions, deterministic tests, lint/types/build,
Linux browser tests, strict Rust checks and dependency audits. Five native tests,
Clippy all-targets/all-features, fmt and release build passed locally. Remote CI
and browser acceptance are still pending. See ENGINEERING_REPORT.md for open work.
## Local final checkpoint

Python 3.12 locked environment: 54 passed, 2 skipped in 11.37s. Ruff and
mypy passed. Python sdist/wheel built successfully after adding locked packaging
tools. Pip-audit: no known vulnerabilities found (receipt included). Rust 1.100.0
LLVM Windows: 5 tests passed; fmt, strict Clippy and release build passed.
Two skipped tests require Linux browser namespaces. Remote CI remains pending.
## Independent boundary review corrections

Review reproduced a slow-drip header deadline bypass, retiring-resource capacity
bypass, and identified extraction mutation/URL output policy gaps. Added a socket
watchdog including TLS handshake, capacity accounting through completed cleanup,
explicit CLEANUP_PENDING errors, per-session admission bound (16 requests),
MutationObserver epoch validation through extraction/execution, and live href
redaction. Added transport, retiring-worker, queue, special-range and browser
regressions. Conservative Python special-use ranges now match Rust exclusions.
Focused transport/session suite: 47 passed. Linux CI on caf543c passed all three
existing browser tests; new browser regressions require rerun. Rust Linux build,
fmt, tests and strict Clippy also passed; cargo-audit compilation still pending.

## Remote verification checkpoint

Source c09500a: all 11 CI jobs passed in run 45769090597, including 8 Python
matrices, 5 Linux browser fixture tests, pip-audit, Rust fmt/strict Clippy/tests/
release build/cargo-audit. Local suite: 62 passed, 4 Linux-only skips. Evidence:
evidence/ci-c09500a.json and evidence/ci-c09500a-browser/ci-browser.xml.
This closes basic browser fixture verification, not exhaustive network-bypass,
framework compatibility, native parity, leak profiling or production acceptance.
Draft PR #1 remains open and unmerged. Final report records remaining work.

## External static analysis remediation

SonarCloud's separate gate failed on new-code reliability/security. Confined
benchmark CLI outputs to evidence/ with traversal/symlink rejection and exclusive
creation; added regressions. Rust MCP now uses Tokio process management with
kill-on-drop. MCP shutdown awaits its explicitly cancelled child without swallowing
parent cancellation. Refactored transport/parser/benchmark/action routines into
bounded helpers without suppressions. Local tests: 67 passed, 4 Linux-only skips;
Rust 5 tests and strict Clippy passed. Sonar reanalysis and current-source browser
CI remain required. Earlier c09500a green engineering CI does not clear Sonar.

## Final verified source checkpoint

384ae9025c696bb4816681eb0b2adb7bca90056c: all 11 engineering jobs passed in
run 45771375649 and SonarCloud quality gate passed. Eight Python matrices include
lint/format/types, 66 non-browser tests and package builds. Five Linux browser
tests passed; native 5 tests, fmt, strict Clippy, release build and cargo-audit
passed. Local Windows Python: 67 passed, 4 Linux-only skips. Save receipts under
evidence/ci-384ae90.json, evidence/ci-384ae90-browser/ and evidence/sonar-384ae90.json.
Final evidence/documentation commit does not change tested source. Production
acceptance gaps remain as listed in ENGINEERING_REPORT.md; no merge authorized.
