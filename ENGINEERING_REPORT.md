# AeroBrowse engineering report

**Release recommendation: NOT_PRODUCTION_READY.**

Historical phase2 implementation source: `7f5c859fc72cf6473890751c7809f15c3889a50f`.
Verified full CI receipt head: `582b74c4d39976dfa16a37a6523ca99bb5a0109d`.
At that historical checkpoint, all 72 tracked implementation/test/CI/benchmark
files matched that verified head. The current continuation is recorded below.
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
| Python matrix | All 8 Linux/Windows Python 3.11 through 3.14 jobs pass | green full run `45843650844`, head `582b74c` |
| Rust | fmt, strict Clippy, tests, release build, native refusal contract and audit pass | same green run, Rust job completed |
| Dependency audit | Pass | same green run |
| Linux runtime | 38 passed, 2 Windows-only skips | implementation `7f5c859`, run `45842826008`; `runtime-7f5c859/runtime-boundary.xml` |
| Broader local MCP/runtime | 62 passed, 3 platform skips, 27 browser/native deselections | `review-suites.xml`; overlaps full suite |
| Final review regressions | 4 passed after both defects were reproduced as failures | `review-regressions.xml`; real stdio and real worker |
| Native refusal contract | 18 passed against actual compiled native executable | `native-contract.xml`; negative contract, not full browser parity |
| Package | Wheel and sdist build; all 16 module bytes match implementation | `build-reviewed.json`; license metadata deprecation remains |
| Final browser/soak job | 47 browser passes/zero skips; 38 runtime passes/2 Windows-only skips; 688 successful cycles over 1,801.468 seconds | green run `45843650844`; `ci-582b74c/browser/` |
| Sonar | Two private-tmpfs path findings remain open | Analyzer gate red; no suppression |

Receipts are under `evidence/phase2/`; `VERIFICATION.md` indexes them and
`receipt-manifest.json` hashes them. All final manifest entries were checked for hash
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
kills and denied forks. At the historical phase-two source, the direct SDK had no
equivalent supervised quotas. The agent continuation below replaces the normal
public SDK/CLI entry point with owned process supervision.

## Completed historical full runs

| Source / full run | Browser / runtime | Soak | Controller RSS after cleanup |
|---|---|---|---|
| `f1ce086` / `45833263200` | 43 browser passes; 19 runtime passes, 2 platform skips | 931 successful cycles / 1,800.735 seconds | 44,367,872 to 45,510,656 bytes; last equals max |
| `c963127` / `45837621519` | 46 browser passes; 25 runtime passes, 2 platform skips | 1,068 successful cycles / 1,801.102 seconds | 44,494,848 to 45,756,416 bytes; last equals max |

Both full runs are green, including eight Python jobs, Rust and dependency audits.
Every raw soak row matches its summary and records zero descendants/active sessions
after close. Zero orphan processes or permanently occupied slots were observed.
These runs precede final operator/review fixes and do not certify later source.
The reviewed-source run also completed green, with its separate receipt below.

Scope: one owned sequential navigate/fill/click/close fixture, 256-task session and
unchanged 256-task aggregate ceiling, `max_sessions=2`. This is not concurrent
browser load, browser peak memory or indefinite leak freedom. Initial soak failed
immediately under the default 64-task session cap: `pids.events.max=66`,
`oom_kill=0`. Defaults/aggregate caps remain; browser acceptance explicitly chooses
the larger session budget. Exhaustion returns `WORKER_RESOURCE_LIMIT` and retires
its slot. Failed soak evidence is never counted as successful duration.

## Final reviewed-source full CI result

Run `45843650844`, head `582b74c`, completed successfully at 15:31 UTC. All eleven
jobs passed: eight Python matrix jobs, Rust, dependency audits, browser/integration.
CI's synthetic merge checkout is `0b594a7f5b8156866b6195b0d89ea55458a47da5`.
Required Linux browser suite: **47 passed, zero skips**. Kernel/runtime suite:
**38 passed, 2 Windows-only skips**. Linux Python 3.12: **161 passed, 21 skips**;
18 of those are native checks separately run and passed in the Rust job, with
3 platform skips. The Rust job passed 5 native unit tests plus 18 shared refusal
checks, formatting, strict Clippy, release build and audit. No suites are summed.

Mandatory soak: **1,801.468 seconds, 688 successful sequential lifecycle cycles**.
All 688 raw rows agree with the summary and show zero descendants/active sessions
after cleanup; zero orphan processes/permanently occupied slots observed.
Controller RSS: first 44,396,544 bytes; last/max 45,670,400 bytes. Same controlled
256-task session/aggregate fixture and limitations as the earlier two runs. Fewer
cycles than earlier hosts is an observation, not evidence of a measured regression
or improvement: there is no paired comparable baseline. These results do not prove
indefinite leak freedom, browser/MCP concurrency, peak memory or production readiness.

Receipts: `ci-582b74c/final-run.json`, `final-jobs.json`, `browser/`,
`python-linux312/ci-python.xml`, `rust-job.log` and `dependencies/ci-pip-audit.json`.
Current Python advisory scan covers 112 resolved dependencies with zero findings.
Bundled unprefixed baseline XML/JSON in CI artifacts are explicitly historical;
`ci-582b74c/README.md` distinguishes them. Sonar remains red on two unsuppressed
private-tmpfs path findings; full engineering workflow green does not close that gate.

## Measurements

These are exploratory controlled-fixture measurements, not a paired before/after
experiment. No speedup or memory improvement is claimed. The benchmark reports
`dirty=true` because generated build/test evidence exists. Exact raw values and
configuration are in `ci-582b74c/browser/phase2/benchmark-linux.json`.

| Metric | Before | Observed after | Evidence and limit |
|---|---|---|---|
| Security findings | Original confirmed P0s in `AUDIT.md` | Implemented controls with remaining P0/P1 scope gaps | `PHASE2_AUDIT.md`; no invented closed-finding count |
| Python tests | Original 5; phase-two 67 | Local 161 passes; full matrix passes at stated revisions | JUnit and CI above; different test scopes |
| Rust tests | Original not executable; phase-two 5 | 5 native tests plus 18 cross-language refusal checks | Rust CI; narrower native browser capability |
| Turbo warm latency | No comparable controlled baseline | Median 3.71 ms, p95 3.98 ms, n=100 | Owned tiny fixture, direct SDK |
| Fidelity warm latency | No comparable controlled baseline | Median 32.86 ms, p95 36.16 ms, n=99 | Direct SDK; not supervised MCP latency |
| Peak RAM | Historical measurement has different scope | Sampled aggregate process-tree RSS 1,437,868,032 bytes | 20 ms sampling, harness/fixture included |
| Token reduction | Historical character estimate invalid | HTML 118 tokens to Markdown 45, 61.86% | `tiktoken 0.14.0/cl100k_base`; action metadata excluded |
| Concurrent sessions | No comparable browser load baseline | SDK Turbo load levels 1/2/4/8/16 recorded | Not browser/MCP fairness or throughput |

Earlier exploratory source `0caf7e7` receipts remain preserved; values differ across
CI hosts. No 90% token-savings, fixed-memory, universal-compatibility or complete
information-preservation claim is supported. The tiny fixture has no general recall
measurement. Cold/operation timing distributions and all raw rows remain available. The table
uses reviewed-source run `45843650844`, merge checkout
`0b594a7f5b8156866b6195b0d89ea55458a47da5`, Linux x86_64/Python 3.12.16.
Controller/fixture resources are included; no paired speedup comparison exists.

## Remaining release blockers

| Requirement | Status | Release implication |
|---|---|---|
| OS browser boundary | Implemented and verified for declared Linux canary/process scenarios | Full utility/network mechanism audit and inner Chromium sandbox remain open |
| Killable MCP worker lifecycle | Verified bounded contract, including crashes and parent death | Renderer detection is timeout-based; broader hostile-load assessment absent |
| Kernel resource controls (historical phase2) | Verified supervised session/pool caps | Public SDK supervision added in continuation; separate renderer and cross-instance deployment limits remain open |
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

## Agent workflow continuation (current work)

Current implementation/benchmark source: `0530488`; production browser modules
match `3e1d399` after
normalizing checkout line endings. Focused delegated Linux run `45860943458`
passed 14 workflow/auth/storage/error-document tests, followed by 38 runtime
passes and 2 Windows-only skips. Full final-source CI, including the Python
matrix, Rust, broader security/framework suite, concurrency measurements and
30-minute soak, passed in final PR run `45864277407`. Earlier green runs do not certify changed code.
Actual-model evaluation is `NOT_RUN`: `OPENAI_API_KEY` and
`AEROBROWSE_EVAL_MODEL` are missing.

Useful scripted tasks now complete through public supervised SDK and real MCP:
login through a form, read protected content, update a record, share authentication
with another explicit tab, reload and log out; search/open detail/back/forward;
multistep select/checkbox/validation/submission; stale-ID rejection and fresh
snapshot recovery. Server state supplies the verdict. Auth does not depend on a
host credential jar or unrestricted networking. Every redirect uses direct CDP
Fetch interception because pinned Playwright route() skipped subsequent hops.

Public SDK/CLI now own killable workers/kernel pools, resource bounds and absolute
request/session deadlines. Its timeout regression exposed and fixed a startup
closed-pipe race. Internal engine tests explicitly use trusted low-level classes.
Canonical output token costs include live actions, tab/session metadata; the actual
model harness separately counts complete serialized MCP tool envelopes.

| Metric | Before continuation | After/current evidence | Evidence |
|---|---|---|---|
| Auth workflows | Redirect login failed | Scripted SDK/MCP login/update/logout passes | focused Linux run 45860943458 |
| Python local | Historical 161 component passes |206 passed, 21 skips, 67 browser deselections at final source | evidence/agent/python-source-final.xml |
| Rust | 5 native units + 18 refusal contracts | Final run passed fmt, strict Clippy, tests, release build, shared refusal contract and dependency audit | run 45864277407; no native browser scope expansion |
| Turbo/Fidelity latency | No comparable baseline | Warm medians 2.872 ms / 27.096 ms; 100 / 99 samples; no speedup claim | evidence/agent/ci-0530488/runtime/phase2/benchmark-linux.json |
| Peak RAM | No comparable baseline | 1,441,820,672 bytes sampled process-tree maximum across full operation/load run; 20 ms interval, not exact peak | same corrected benchmark receipt |
| Token cost | Markdown-only, omitted actions | Synthetic long article:1913 HTML /1504 Markdown /1820 complete JSON tokens (4.86% complete reduction); tiny cases expand | evidence/agent/token-fixtures-source0530488.json; runtime/MCP overhead additional |
| Concurrent browser tasks | Complete tasks unmeasured | 6 tasks / 2 workers / 9.152 seconds; 0.656 tasks/s, all workers reaped | evidence/agent/ci-0530488/runtime/agent/concurrency.json |
| Actual AI model success | Not measured |NOT_RUN | model-evaluation-sourcedac1c1d.json |

Fixed and verified in the declared controlled scope: authentication, forms, tabs,
history, stale recovery, runtime quotas, output/recovery metadata and benchmark
guards. The complete final-source cleanup soak passed. Partial: general extraction recall and capacity/fairness. Not implemented: native
Rust live browser parity, trusted physical input, file transfer, WebSockets, service
workers, HTTP Authorization. Known limitations: Linux-only Fidelity; host operator
must provision cgroup/namespaces; independent SDK instances need enclosing aggregate
budget; external security review and remaining Sonar findings remain open.

AGENT_QUICKSTART.md and examples.agent_sdk/examples.agent_mcp reproduce complete
owned tasks. benchmarks.agent.run offers actual-model evaluation through real MCP;
scripted passes must never be represented as model success.

### Corrected measurement receipt

Run `45864267717` at `0530488` is green: 14 workflow/auth/storage tests,
38 runtime passes with 2 Windows-only skips, corrected operation benchmarks,
and six complete tasks with two SDK workers. Warm operation medians on the owned
fixture: snapshot 7.066 ms, click 7.914 ms, fill 8.822 ms. One actual handoff
sample took 600.796 ms; a single sample is not a latency distribution.
Post-escalation samples are labeled live Fidelity. The earlier repeated handoff
aggregate was mislabeled because the engine correctly retained the live session;
those rows are excluded from Turbo/escalation claims, not silently rewritten.

The benchmark RSS maximum covers the entire sampled tree during all operations
and load cases, not one steady browser or a measured exact peak. CPU observations
exclude exited child processes. These tiny fixture results do not establish public
website speed, success, fairness, production capacity or improvement over baseline.

Reported operation medians use the harness's documented nearest-rank50th
percentile (lower middle sample for even counts),not the arithmetic mean of two
middle samples. Raw counts,failure rates,p50/p90/p95/p99 values and concurrent-task
throughput/unique-session/reaping assertions were recomputed and matched.

## Final agent-continuation acceptance evidence

Full run [45864277407](https://github.com/k39139215-gif/aerobrowse/actions/runs/45864277407)
is **SUCCESS** at head0530488, tested PR merge1f59be05. All81 indexed
implementation/test/workflow/benchmark Git blobs match the branch source.
Later commits contain documentation and evidence only. Both draft PRs remain
unmerged; no package release or production-readiness claim is made.

| Metric | Before | Final observation | Evidence |
|---|---|---|---|
| Security findings | Original unsafe network/action/session paths in AUDIT.md | Declared regression-covered fixes pass; independent review, auxiliary-target assessment and2 analyzer findings remain open | AUDIT.md,PHASE2_AUDIT.md,ACCEPTANCE.md |
| Python tests | Historical67 passes/4 skips | Each of8 Linux/Windows Python3.11-3.14 jobs:206 passes/21 skips; browser68 passes/0 skips; kernel38 passes/2 Windows-only skips | ci-0530488/full/ receipts |
| Rust tests |5 native units |5 native units+18 actual compiled native/Python refusal contracts; fmt,strict Clippy,release,audit pass | ci-0530488/rust.log and final-run.json |
| Warm Turbo latency | No comparable baseline | nearest-rank p50 4.324 ms,p95 4.755 ms,n100 | final browser/phase2/benchmark-linux.json |
| Warm Fidelity latency | No comparable baseline | nearest-rank p50 34.545 ms,p95 38.625 ms,n99 | same final benchmark |
| Peak RAM | No comparable baseline | sampled tree maximum1,472,843,776 bytes across complete operation/load run;20 ms sampling,not exact peak | same final benchmark |
| Token reduction | Character estimates/Markdown-only | Long synthetic article1913 HTML/1504 Markdown/1820 complete JSON tokens;4.86% complete reduction;small fixtures expand | token-fixtures-source0530488.json |
| Concurrent sessions | Complete tasks unmeasured |6 complete tasks/2 workers/10.982 seconds;0.546 tasks/s;all reaped | final browser/agent/concurrency.json |
| Cleanup soak | No comparable baseline |739 sequential successful cycles over1801.544 seconds;zero observed orphans/permanent slots | final browser/phase2/soak-linux.json and.jsonl |

Final operation p50: snapshot9.836 ms,click11.162 ms,fill11.111 ms,n100 each.
One actual handoff859.873 ms is a single observation,not a latency distribution.
Raw1,133 rows reproduce all16 p50/p90/p95/p99/sample/failure summaries. Complete
load receipt reproduces task throughput,six unique sessions and all reaping flags.
Every739 soak row reports success,zero active sessions and zero descendants after
cleanup. Parent RSS first85,094,400,last/max86,003,712 bytes; this is controller
RSS at cycle completion,not peak browser RAM or an indefinite leak proof.

The21 non-browser skips are18 native contracts run separately by Rust CI,2
Windows quota-denial scenarios covered by platform/runtime tests,and1 namespace
launch scenario covered by required Linux browser CI. They are not unreported
passes. The final Linux runtime suite separately skips2 Windows-only tests.

Fixed and verified: declared public HTTP/network,action identity,hybrid handoff,
owned process/session lifecycle,controlled authentication/tabs/history/forms,
semantic edge regressions and deterministic measurements. Partial: broad site
recall,resource fairness,complete observability and auxiliary browser compatibility.
Not implemented: native Rust live-browser parity,trusted physical events,file
transfer,WebSockets,service workers,HTTP Authorization. Not independently verified:
external security assessment and production load. Actual-model evaluation remains
NOT_RUN without explicit credentials/model. These open items prevent production
acceptance; no scope exclusions are approved.
