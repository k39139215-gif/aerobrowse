# AeroBrowse engineering report

**Release recommendation: NOT_PRODUCTION_READY.**

Implementation source: `7f5c859fc72cf6473890751c7809f15c3889a50f`.
Active full CI receipt head: `582b74c4d39976dfa16a37a6523ca99bb5a0109d`.
All 72 tracked implementation/test/CI/benchmark files match that active head.
Draft follow-up PR #2 targets `fix/production-hardening`; original draft PR #1
against main remains unchanged. No PR merge, package publication or version change.

## Implemented behavior

- HTTP requests use centralized public-destination validation, IDNA normalization,
  validation of all DNS answers, numeric connection pinning with TLS hostname
  verification, bounded redirects, request/response limits and absolute deadlines.
  Environment proxies and implicit credential forwarding are disabled.
- Chromium runs behind mandatory Linux Bubblewrap network, mount, user, PID, IPC
  and UTS namespaces. It receives minimal read-only runtime mounts, private writable
  storage, a private proc view and a scrubbed environment. A trusted host broker
  performs pinned HTTP requests. Real tests remove routing and verify that the OS
  boundary still blocks host TCP/UDP canaries. Unsupported platforms fail closed.
- MCP sessions own killable worker processes rather than unkillable browser threads.
  Per-owner locks, bounded queues, correlated IPC and explicit lifecycle states
  prevent requests from acting on another session. Linux cgroup v2 and Windows Job
  Objects enforce aggregate memory/CPU/task limits. Cleanup handles cancellation,
  deadlines, worker/browser crashes and parent death. Linux guardians use inherited
  directory descriptors with generated basenames; traversal and symlinks are tested.
- Turbo-to-Fidelity escalation navigates the current URL and returns a fresh live
  snapshot with `STALE_ACTION_ID`; the caller must choose a live action before
  activation. Static HTML action identifiers are never silently reused.
- Snapshot HTML and live actions are captured together in an isolated CDP world.
  Activation validates the exact retained node, document, URL, generation, mutation
  epoch, visibility and state in the same renderer task. Focus reentrancy is checked.
  There is no ordinal/selector fallback. These are explicitly synthetic DOM events.
- The supported MCP stdio entry point bounds bytes, UTF-8, nesting and object shape
  before SDK decoding. It limits in-flight requests, rejects duplicate active IDs,
  preserves response correlation, handles cancellation, and bounds partial-frame
  and blocked-output waits. Raw worker IPC now handles partial writes correctly.
- Controlled local React, Vue, Next.js and Angular applications are pinned and built
  in CI. Tests verify actual input/select state, action identity, counter updates,
  dialogs, routes, hidden/disabled controls and stale-generation refusal.
- Python is the authoritative browser runtime. Rust retains narrower native HTTP
  retrieval and integrates Python for MCP; native unrestricted CDP is disabled.
  Actual compiled native/Python rejection contracts are tested. This narrower
  architecture is documented and does not waive the original full-parity requirement.
- Semantic output preserves structured content and embedded-content indicators.
  Token measurements record real tokenizer identity/version and separate character
  reduction from token reduction. The benchmark harness stores raw observations,
  percentiles, failure rates, token metadata and the scope of each load measurement.

See `SECURITY.md`, `COMPATIBILITY.md`, `docs/ENGINE_PARITY.md` and
`SECURITY_REVIEW_PACKAGE.md` for exact contracts, assumptions and reproduction.

## Current verification

Original baseline `44f3e734`: 5 Python passes with live third-party dependencies;
Rust could not execute because the installed toolchain was broken. Phase-two
baseline at PR #1 head `943ca57e`: 67 Python passes, 4 platform skips, 5 Rust tests.
These are different scopes and are not added.

| Gate | Latest verified result | Source and evidence |
|---|---|---|
| Full local Python | 161 passed, 3 platform skips, 65 browser/native deselections; 210.94 seconds | implementation `7f5c859`; `python-source7f-final.xml` |
| Python matrix | All 8 Linux/Windows Python 3.11 through 3.14 jobs pass | active full run `45843650844`, head `582b74c` |
| Rust | fmt, strict Clippy, tests, release build, native refusal contract and audit pass | same active run, Rust job completed |
| Dependency audit | Pass | same active run |
| Linux runtime | 38 passed, 2 Windows-only skips | implementation `7f5c859`, run `45842826008`; `runtime-7f5c859/runtime-boundary.xml` |
| Broader local MCP/runtime | 62 passed, 3 platform skips, 27 browser/native deselections | `review-suites.xml`; overlaps full suite |
| Final review regressions | 4 passed after both defects were reproduced as failures | `review-regressions.xml`; real stdio and real worker |
| Native refusal contract | 18 passed against actual compiled native executable | `native-contract.xml`; negative contract, not full browser parity |
| Package | Wheel and sdist build; all 16 module bytes match implementation | `build-reviewed.json`; license metadata deprecation remains |
| Current browser/soak job | Browser tests/benchmarks completed; mandatory 30-minute soak active from 15:00:33 UTC | run `45843650844`; completion not yet counted |
| Sonar | Two private-tmpfs path findings remain open | Analyzer gate red; no suppression |

Receipts are under `evidence/phase2/`; `VERIFICATION.md` indexes them and
`receipt-manifest.json` hashes them. All 95 manifest entries were checked for hash
and byte-length equality. This is integrity evidence, not independent custody or
assessment. CI may run a synthetic PR merge; raw receipts record that checkout.
Skipped/deselected tests are not passes. Focused suites overlap and must not be
summed. Failed intermediate runs are retained.

## Verified changes from final review

A 5,000-digit JSON integer below the wire cap previously escaped the decoder and
terminated MCP. Integer literals are now capped at 128 digits independently of
Python's global setting; fixed parse errors are followed by a successful real-pipe
ping. Concurrent shutdown previously missed workers already retiring. It now tracks
and awaits shielded cleanup before closing the aggregate pool. A real-worker
close/shutdown overlap test failed before the fix and passes with process/temp
cleanup and closed-pool assertions. The read-only recheck found no additional
issue in those paths; runtime regressions and CI supply the execution evidence.

Operator-only `AEROBROWSE_SESSION_TASKS` accepts canonical integers 1 through 256;
absence retains 64, aggregate CPU/memory/task ceilings remain unchanged. Invalid
values fail startup. The real Linux stdio MCP initialize/navigate/Fidelity-fill/
close flow passes with the explicit budget and a trusted owned-fixture allowance.
MCP clients cannot alter those permissions. More than one concurrent browser is
not established by this configuration.

Crash tests kill the actual browser process and all owned renderers, then verify
old action failure, cleanup and fresh-session navigation. Renderer recovery uses
the operation deadline (3 seconds in its test), not immediate crash notification.
Linux parent death verifies cgroup/temp removal. Kernel tests observe actual OOM
kills and denied forks. The direct SDK has no equivalent supervised quotas.

## Completed historical full runs

| Source / full run | Browser / runtime | Soak | Controller RSS after cleanup |
|---|---|---|---|
| `f1ce086` / `45833263200` | 43 browser passes; 19 runtime passes, 2 platform skips | 931 successful cycles / 1,800.735 seconds | 44,367,872 to 45,510,656 bytes; last equals max |
| `c963127` / `45837621519` | 46 browser passes; 25 runtime passes, 2 platform skips | 1,068 successful cycles / 1,801.102 seconds | 44,494,848 to 45,756,416 bytes; last equals max |

Both full runs are green, including eight Python jobs, Rust and dependency audits.
Every raw soak row matches its summary and records zero descendants/active sessions
after close. Zero orphan processes or permanently occupied slots were observed.
These runs precede final operator/review fixes and do not certify later source.
Current reviewed-source full run requires its own completion receipt; at report update, its mandatory soak is active and not counted.

Scope: one owned sequential navigate/fill/click/close fixture, 256-task session and
unchanged 256-task aggregate ceiling, `max_sessions=2`. This is not concurrent
browser load, browser peak memory or indefinite leak freedom. Initial soak failed
immediately under the default 64-task session cap: `pids.events.max=66`,
`oom_kill=0`. Defaults/aggregate caps remain; browser acceptance explicitly chooses
the larger session budget. Exhaustion returns `WORKER_RESOURCE_LIMIT` and retires
its slot. Failed soak evidence is never counted as successful duration.

## Measurements

These are exploratory controlled-fixture measurements, not a paired before/after
experiment. No speedup or memory improvement is claimed. The benchmark reports
`dirty=true` because generated build/test evidence exists. Exact raw values and
configuration are in `ci-f1ce086/phase2/benchmark-linux.json`.

| Metric | Before | Observed after | Evidence and limit |
|---|---|---|---|
| Security findings | Original confirmed P0s in `AUDIT.md` | Implemented controls with remaining P0/P1 scope gaps | `PHASE2_AUDIT.md`; no invented closed-finding count |
| Python tests | Original 5; phase-two 67 | Local 161 passes; full matrix passes at stated revisions | JUnit and CI above; different test scopes |
| Rust tests | Original not executable; phase-two 5 | 5 native tests plus 18 cross-language refusal checks | Rust CI; narrower native browser capability |
| Turbo warm latency | No comparable controlled baseline | Median 2.63 ms, p95 2.96 ms, n=100 | Owned tiny fixture, direct SDK |
| Fidelity warm latency | No comparable controlled baseline | Median 24.67 ms, p95 26.84 ms, n=99 | Direct SDK; not supervised MCP latency |
| Peak RAM | Historical measurement has different scope | Sampled aggregate process-tree RSS 1,453,219,840 bytes | 20 ms sampling, harness/fixture included |
| Token reduction | Historical character estimate invalid | HTML 118 tokens to Markdown 45, 61.86% | `tiktoken 0.14.0/cl100k_base`; action metadata excluded |
| Concurrent sessions | No comparable browser load baseline | SDK Turbo load levels 1/2/4/8/16 recorded | Not browser/MCP fairness or throughput |

Earlier exploratory source `0caf7e7` receipts remain preserved; values differ across
CI hosts. No 90% token-savings, fixed-memory, universal-compatibility or complete
information-preservation claim is supported. The tiny fixture has no general recall
measurement. Cold/operation timing distributions and all raw rows remain available.

## Remaining release blockers

| Requirement | Status | Release implication |
|---|---|---|
| OS browser boundary | Implemented and verified for declared Linux canary/process scenarios | Full utility/network mechanism audit and inner Chromium sandbox remain open |
| Killable MCP worker lifecycle | Verified bounded contract, including crashes and parent death | Renderer detection is timeout-based; broader hostile-load assessment absent |
| Kernel resource controls | Verified supervised session/pool caps | Direct SDK, separate renderer and cross-instance limits not implemented |
| Deterministic action identity | Verified declared synthetic DOM contract | Trusted physical events, file inputs and broader interactions unsupported |
| MCP framing/owner isolation | Implemented and covered by real-pipe tests | No remote authenticated transport; broad fuzz/load coverage incomplete |
| Framework compatibility | Four real controlled framework fixtures pass | Broad validation, lazy/infinite content, large-page recall and error states incomplete |
| Rust/Python parity | Explicit narrower native architecture with refusal tests | Full original native browser/action parity not implemented |
| Performance evidence | Raw repeatable harness and 30-minute sequential soak | No paired baseline, production-site, browser/MCP concurrency/fairness measurements |
| External quality gate | Open private `/tmp` findings; actual mount is private tmpfs in tests | Analyzer gate not green; needs review, no suppression |
| Independent assessment | Reproduction package prepared | External security assessment not performed |

No scope exclusion is approved. Open requirements prevent a production release.
Keep both PRs draft and unmerged. No fake implementation or passing test substitutes
for these requirements. `AUDIT.md` and Git history preserve earlier findings;
`PHASE2_AUDIT.md` is the current finding/status matrix. `ACCEPTANCE.md` maps every
original requirement group to verified, partial or unimplemented scope.
