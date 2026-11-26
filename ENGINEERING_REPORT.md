# AeroBrowse engineering report

**Release recommendation: NOT_PRODUCTION_READY.**

Source fixes, tests, CI and evidence are implemented on the draft follow-up branch
`fix/phase2-adversarial-validation`, targeting `fix/production-hardening`. Original
draft PR #1 remains at `943ca57e9ef8ef5c4993a0aff25a8b8539e42713`. Main is unchanged;
neither PR is merged. No package publication or version change was made.

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

## Verification and evidence

The original repository baseline was `44f3e73409d3f0c4e6e376f0c98198abd00ccc0f`:
Python 5 passes, with live third-party dependencies; the original Rust toolchain
failed before execution. Phase-two baseline at PR #1 head had 67 Python passes,
4 platform skips and 5 Rust tests. These are different baselines and are not added.

| Gate | Verified result | Revision and evidence |
|---|---|---|
| Local Python suite | 146 passes, 2 platform skips, 64 browser/native deselections | source through `fe159f9`; `evidence/phase2/python-final-reviewed.xml` |
| Python matrix | All 8 Linux/Windows jobs pass on Python 3.11ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦ÃƒÂ¢Ã¢â€šÂ¬Ã…â€œ3.14 | source `f1ce086`, green run `45833263200`; later `c963127` matrix also passes |
| Rust | Formatting, strict Clippy, tests, release build, native contract and dependency audit pass | green run `45833263200`; final-source rerun tracked separately |
| Linux browser boundary/actions/frameworks | 43 passes, zero skips | `evidence/phase2/ci-f1ce086/ci-browser.xml` |
| Linux kernel/runtime suite | 19 passes, 2 Windows-only skips | `ci-f1ce086/phase2/ci-runtime-kernel.xml` |
| Final focused Linux runtime | 25 passes, 2 Windows-only skips | source `c963127`, run `45837608925`; `runtime-c963127/runtime-boundary.xml` |
| Final Windows runtime | 16 passes, 3 Linux-only skips, 8 browser deselections | `runtime-final-windows.xml` |
| MCP framing/deadlines | 15 passes using real subprocess pipes | `protocol-final-reviewed.xml` |
| MCP malformed/session concurrency | 16 focused passes | `mcp-session-recheck.xml`; these overlap the full suite |
| Native/Python refusal contract | 18 passes against a real built native executable | `native-contract.xml`; narrower negative contract, not full parity |
| Required supervised browser soak | 1,800.735 seconds, 931 successful lifecycle/action iterations | source `f1ce086`, run `45833263200`; raw and summary below |
| External analyzer | Two private-tmpfs path findings remain open | Sonar quality gate is not green; no suppression applied |

Receipts live under `evidence/phase2/`. `VERIFICATION.md` indexes them;
`receipt-manifest.json` records hashes. These are integrity aids, not independent
custody or assessment. CI may use a synthetic PR merge checkout; the raw receipt
records that checkout. Skipped/deselected tests are not passes. Repeated/focused
suites must not be summed as unique tests. Failed intermediate receipts are retained.

The final runtime gate kills the actual main browser process and all owned
renderers, verifies failure of the old action, cleanup and fresh-session navigation.
Renderer recovery uses the request deadline (3 seconds in the test), not immediate
crash notification. Linux parent death verifies worker termination plus cgroup and
temporary-directory removal. Kernel tests observe actual OOM kill and denied forks.

## Thirty-minute soak

The green run used source `f1ce086`, synthetic merge checkout
`1710acaf4f4f0e877a53653f525939b688143b51`, Linux x86_64 and Python 3.12.16.
It completed 931 sequential navigate/fill/click/close cycles over 1,800.735 seconds.
All 931 raw rows match the summary and record zero remaining descendants and zero
active sessions after cleanup. No orphan processes or permanently occupied slots
were observed. Parent controller RSS after cleanup rose from 44,367,872 bytes to
45,510,656 bytes, which was also its observed maximum.

This is one owned synthetic fixture, a 256-task session budget and unchanged
256-task aggregate ceiling, with `max_sessions=2`. It is not concurrent browser
load, a browser peak-memory measurement or indefinite leak freedom. The later source
has an independently passing runtime gate; its full repeated soak is still active
until a separate completion receipt is recorded.

The first soak failed immediately. The default Linux 64-task session cap rejected
Chromium thread creation: `pids.events.max=66`, `oom_kill=0`. Default and aggregate
caps were retained. Browser acceptance/soak declares the larger session budget;
low-budget exhaustion returns `WORKER_RESOURCE_LIMIT` and retires its session.

## Measurements

These are exploratory controlled-fixture measurements, not a paired before/after
experiment. No speedup or memory improvement is claimed. The benchmark reports
`dirty=true` because generated build/test evidence exists. Exact raw values and
configuration are in `ci-f1ce086/phase2/benchmark-linux.json`.

| Metric | Before | Observed after | Evidence and limit |
|---|---|---|---|
| Security findings | Original confirmed P0s in `AUDIT.md` | Implemented controls with remaining P0/P1 scope gaps | `PHASE2_AUDIT.md`; no invented closed-finding count |
| Python tests | Original 5; phase-two 67 | Local 146 passes; full matrix passes at stated revisions | JUnit and CI above; different test scopes |
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
`PHASE2_AUDIT.md` is the current finding/status matrix.

## Operator configuration verification

Source `929cc25` adds operator-only `AEROBROWSE_SESSION_TASKS` configuration for
the packaged MCP command. Canonical integers 1ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã¢â‚¬Å“256 are accepted; absence retains
64. Aggregate task, memory and CPU ceilings stay unchanged. Eleven negative/default/
ceiling configuration checks pass locally. Linux run `45840796649` passed 37 tests with 2 Windows-only skips, including real
stdio MCP initialize/navigate/Fidelity-fill/close flow with an explicit owned fixture
allowance and the operator budget, alongside the existing kernel/crash regressions.
The network allowance is trusted fixture setup, never an MCP client argument.
This source change does not assert that more concurrent browsers fit the pool.

The final combined local MCP/runtime rerun passed 58 tests with 3 platform skips
and 27 browser/native deselections (`mcp-runtime-operator.xml`). The full local source rerun subsequently passed 157 tests with 3 platform skips
and 65 browser/native deselections; focused tests are not added to that count. Source/receipt hashes were verified against 49 committed Git
blobs without mismatch; this establishes integrity, not independent assessment.

Final implementation local suite: **157 passed, 3 platform skips, 65 browser/native
deselections in 199.07 seconds**, source `929cc25` (`python-source929-final.xml`).
Wheel and source distribution both build; all 16 package Python modules are present
in the wheel (`build-source929.json`). Setuptools reports deprecated TOML license
metadata/classifier warnings; builds pass and a future packaging update is needed.
No artifacts were published. This does not convert CI browser deselections to passes.

## Final source-review corrections

Source `7f5c859` fixes two reproduced P1 defects. MCP JSON integers above 128
digits return bounded parse errors rather than escaping Python's decoder and
terminating the server; a real-pipe test then pings successfully. Session shutdown
tracks outstanding shielded worker-cleanup tasks and awaits them before closing
the aggregate pool. A gated real-worker close/shutdown overlap test failed before
the fix, then passed with worker/temp cleanup and closed-pool assertions. Four
focused regressions pass; this later source needs fresh broader CI/soak receipts.
Earlier results remain explicitly bound to their tested revisions.

Corrected-source Linux run `45842826008` passed **38 runtime tests with 2 Windows-only
skips**, including the overlapping real-worker close/shutdown regression, actual
MCP stdio browser flow, crash recovery and quota controls. Receipt:
`runtime-7f5c859/runtime-boundary.xml`. The framing/integer recovery path separately
passed the real-pipe focused regression; broader local MCP/runtime rerun is active.

The corrected-source broader local MCP/runtime suite passed 62 tests, 3 platform
skips and 27 browser/native deselections (`review-suites.xml`). These overlap the
full suite. No failed intermediate run was relabelled or overwritten. Final-source
full CI/soak is queued behind the ongoing earlier revision soak; pending is not pass.

Final corrected implementation `7f5c859`: **161 passed, 3 platform skips and
65 browser/native deselections in 210.94 seconds** on Windows/Python 3.12,
`python-source7f-final.xml`. This supersedes the 157-test local result at `929cc25`.
Current receipt head `582b74c` independently passes the Linux runtime gate; its
full verification remains queued until the earlier required soak finishes.

## Second completed full run

Source `c963127`, run `45837621519`, is fully green. Required Linux browser tests:
46 passes, zero skips. Kernel/runtime: 25 passes, 2 Windows-only skips. All eight
Python matrix jobs, Rust and dependency audit pass. The repeated soak completed
1,801.102 seconds / 1,068 successful sequential cycles, with zero observed orphans
or permanently occupied slots. Every raw row matches the summary. Controller RSS
44,494,848 bytes initially, 45,756,416 bytes last/max. Configuration and limitations
match the earlier sequential 256-task session/aggregate fixture. Source includes
final renderer recovery semantics but precedes the operator setting and the two
review fixes. Reviewed-head run `45843650844` is now active; do not transfer the
second run's complete acceptance status to later source. Receipts: `ci-c963127/`.
