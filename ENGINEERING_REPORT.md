# Phase-two engineering report

Release recommendation: **NOT_PRODUCTION_READY**.

This is an implementation/evidence report, not an external security assessment.
Open P0 gates and unapproved P1 exclusions prevent a production recommendation.
Phase-one report is preserved below as historical evidence, not current acceptance.

## Implemented source and architecture

Follow-up draft PR #2 targets fix/production-hardening; PR #1 and main remain
unchanged and unmerged. Preflight source/base and baseline are in PHASE2_AUDIT.md.

- aerobrowse/isolation.py now builds Bubblewrap user/network/mount/PID/IPC/UTS
  boundaries with only runtime mounts, private tmp/home/proc and scrubbed environment.
  Real canaries test host egress and secret-file exclusion; routing is not the final
  network boundary. See SECURITY.md for the explicit no-sandbox Chromium limitation.
- aerobrowse/runtime.py and sessions.py replace thread-owned browser state with
  process workers, lifecycle states, bounded correlated IPC, hard teardown and
  capability-gated kernel quotas. Windows uses nested jobs; Linux uses delegated
  cgroup v2 and an independent guardian with descriptor-confined cleanup.
- aerobrowse/actions.py and fidelity.py capture HTML/actions in one isolated-world
  renderer task and activate exact retained nodes after generation/document/epoch/
  state checks. No selector/ordinal fallback exists. Events are synthetic DOM events;
  physical trusted-event semantics are excluded and documented.
- aerobrowse/mcp_transport.py bounds newline UTF-8 frames before SDK decoding,
  validates depth/shape/protocol envelopes, caps in-flight requests, rejects duplicate
  active IDs and terminates stalled framing/output. Official SDK owns MCP negotiation.
- tests/compatibility contains pinned, locally built React/Vue/Next.js/Angular
  applications and checks actual controlled state, route, modal and action identity.
  Coverage is narrower than universal framework support; COMPATIBILITY.md lists gaps.
- docs/ENGINE_PARITY.md selects Option B: Python authoritative browser runtime;
  native Rust HTTP remains a narrower independent implementation, Rust MCP integrates
  Python. Real native/Python refusal contract tests prevent security-model fallback.
- benchmarks/phase2 stores raw timings, token metadata, distributions, Turbo load
  levels and a mandatory kernel-supervised browser/action cleanup soak.

## Verification ledger

Results are bound to the stated source/environment; they do not transfer automatically
to every later revision. CI uses a GitHub PR merge checkout, whose hash appears in
raw receipts. Failed and cancelled runs are retained and do not count as passes.

| Area | Before | Phase-two observed result | Evidence/limits |
|---|---|---|---|
| Python baseline | 67 pass, 4 platform skips | 146 pass,2 platform skips locally;64 browser/native deselections | python-final-reviewed.xml, sourcefe159f9 plus pending audit-only change |
| Python CI | phase-one matrix | all eight Python3.11-3.14 Linux/Windows pass at f1ce086 | run45833263200; includes lint, formatting, mypy, tests, package build |
| Rust | 5 tests | fmt, strict clippy, tests, release build, native refusal contracts and cargo-audit pass at0caf7e7 | run45831559623 Rust job; later source contract rerun pending |
| Browser/action/framework/egress | 5 plain fixtures | 41 pass with zero skips at0caf7e7 | ci-0caf7e7/ci-browser.xml; real Linux canaries, atomicity and four frameworks |
| Kernel/runtime | no kernel quota proof | 17 pass, 2 Windows-only skips at0caf7e7 | ci-runtime-kernel.xml; actual Linux OOM/fork denial |
| MCP framing | SDK buffering only | 14 protocol tests and 16 malformed/session tests pass locally | mcp-protocol-latest.xml, mcp-session-recheck.xml; actual pipes |
| Worker/local security | earlier thread cleanup | 60 pass, 2 platform skips,5 browser deselections atf1ce086 | limits-final-local.xml |
| Long browser soak | absent | first run failed immediately; configured-budget rerun active | do not count active/failed run as 30-minute evidence |
| Dependency audit | historical pass | Python audit passes current runs; cargo audit passed0caf7e7 | CI receipts, no guarantee of future advisory absence |
| External quality gate | previous head passed | Sonar gate fails on two literal private/tmpfs path findings | no suppression; actual guardian traversal finding remediated with fd regression |

## Measurements and their limits

One controlled Linux fixture at source0caf7e7 via merge99ebb5d15a1263f22405c4144ba164f2170e8817,
Python3.12.16/x86_64; raw receipt reports dirty=true because generated evidence/build
artifacts were present. No controlled before/after experiment establishes improvement.

| Metric | Before | Observed phase-two value | Evidence |
|---|---|---|---|
| Turbo warm | no comparable controlled baseline | median2.55ms, p95 2.81ms, n100 | benchmark-linux.json statistics |
| Fidelity warm | no comparable baseline | median23.04ms, p95 26.76ms, n99 | same, SDK not supervised MCP |
| Browser cold | no comparable baseline | 560.42ms, n1 | one observation; no distribution claim |
| Snapshot/click/fill | no comparable baseline | medians5.94/7.03/7.57ms, n100 each | same synthetic fixture |
| Select/scroll/wait/screenshot | no comparable baseline | medians6.91/7.44/6.25/21.17ms,n100 | same |
| New Python import | no comparable baseline | median177.56ms,n30 | parent-spawned new interpreters |
| Sampled RSS | historical measurement different scope | aggregate tree1,478,348,800bytes |20ms sampling; harness/fixture included |
| Token reduction | historical token fixtures different inputs |118->45Markdown tokens,61.86% |tiktoken0.14.0/cl100k_base; actions excluded |
| Concurrency | historical two Turbo workers | raw SDK Turbo1/2/4/8/16 levels | does not measure browser/MCP fairness/throughput |

No claim of faster performance, fixed memory footprint, universal compatibility,
full information preservation or independent security certification is made.

## Remaining findings and release impact

PHASE2_AUDIT.md is the finding matrix; SECURITY_REVIEW_PACKAGE.md is the external
review reproduction package. The observed quota failure was real: Linux counts
threads as tasks; default64/session produced pids.events.max=66,oom_kill=0.
The default and aggregate caps were retained. Real browser acceptance and soak
explicitly configure256/session under the unchanged256 aggregate ceiling. Low-budget
exhaustion now returns WORKER_RESOURCE_LIMIT and retires the session.

| Finding | Severity | Status | Evidence | Release impact |
|---|---|---|---|---|
| Supervised browser30min cleanup |P0|Active rerun, not yet verified|first failed soak + required CI|Blocking|
| Direct SDK quotas / separate renderer caps |P0|Not implemented|trusted embedding API only; aggregate cap exists|Blocking|
| Browser/renderer crash and Linux parentdeath proof |P0|Partial|worker crash/timeout/cancel and Windows parentdeath pass|Blocking|
| Full descendant/utility egress threat coverage |P0|Partial|observed browser/renderer namespaces + TCP/UDP attacks pass|Broader review needed|
| Adversarial DOM contract |P0|Implemented and tested declared synthetic scope|mutation/focus/main-world tests|physical trusted input unsupported|
| Broad framework scenarios and recall metrics |P1|Partial|four real fixtures, narrow assertions|Exclusion not approved|
| MCP/browser concurrency load/resource fairness |P1|Partial|session owner/locks/protocol concurrency covered|Exclusion not approved|
| Performance baseline/cold distributions |P1|Partial|raw synthetic statistics, no paired baseline|No speedup claim|
| Sonar private tmpfs findings |P1 gate|Open analyzer review|negative mount/canary tests|Gate not green|
| Independent penetration test |P1|Not performed|review package prepared|No certification claim|

No exclusion has been approved by the user. Keep both PRs draft and unmerged;
do not publish PyPI/stable releases or change package version.

---

# Historical phase-one report

# Engineering report - remediation candidate

Baseline revision: 44f3e73409d3f0c4e6e376f0c98198abd00ccc0f.
This branch is **not production-ready**. It contains real source fixes and regression
coverage, with substantial unsupported/unverified acceptance requirements.

| Metric | Before | After | Evidence |
|---|---|---|---|
| Security findings | 4 P0 audit findings | HTTP pinning and session isolation regression-tested; Chromium/native feature restrictions; full browser boundary unverified | AUDIT.md, tests/test_security.py, tests/test_mcp.py |
| Python tests | 5 passed, live-site dependencies | 67 passed, 4 Linux-only skips locally | evidence/python-tests.xml |
| Rust tests | Could not run with damaged host toolchain | 5 passed | Local Rust 1.100.0 LLVM Windows test run |
| Rust lint/build | No verified baseline | fmt, strict Clippy, release build passed locally | Required cargo commands executed |
| Turbo latency | Not measured | Warm median 16.60 ms (4 samples), cold 492.20 ms; no improvement comparison | evidence/benchmark-local.json |
| Fidelity latency | Not measured | Unsupported on Windows; failures recorded | evidence/benchmark-local.json |
| Peak RAM | Not measured | 77.32 MiB sampled process-tree RSS | evidence/benchmark-local.json |
| Token reduction | Historical character estimates | Actual tokenizer counts on 8 synthetic categories | evidence/token-fixtures.json |
| Concurrent sessions | Not measured | 2 concurrent SDK Turbo workers, 10/10 successful requests; 91.64/s fixture only | evidence/benchmark-local.json |

## Fixed and locally verified

- Default Python loopback/private/metadata/IPv6 rejection, mixed DNS rejection,
  numeric socket pinning under resolver rebinding, redirect destination/count
  validation, body/URL limits and request deadline failures.
- MCP transport-owner session isolation, explicit capacity, concurrent snapshots,
  real SDK tool schemas, safe error envelopes.
- Static hybrid snapshot state and no browser fallback after network policy failure.
- Selector fallback and malformed/stale generation rejection before browser startup.
- Python table/header metadata, iframe notices, parser depth limits, form-value
  omission and measured tokenizer counts. Native token/depth/value regressions.
- Native unsafe CDP execution removed; unrestricted browser launch cannot occur.

## Verified browser scope and remaining browser checks

Five controlled Linux browser tests pass on c09500a. They exercise namespace
launch/host broker, Turbo/Fidelity handoff, live fill/select/check/click, scroll,
JavaScript value safety, generation staleness, node replacement, mutate-restore,
live URL redaction and normal close. Wait/keyboard/screenshot, exhaustive egress
paths, independent leak profiling and crash recovery still lack integration proof.

## Partial or not implemented

- Native Rust Fidelity/live actions/parity: explicitly unavailable. Rust MCP uses
  the Python runtime. This is a documented breaking restriction, not parity.
- Authenticated sessions/cookies, multiple tabs, back/forward, WebSockets, service
  workers and downloads: unsupported. Popups are denied.
- React/Vue/Next/Angular controlled application compatibility suite: absent.
- Independent process cleanup/leak and browser crash-recovery proof: absent.
- Hard termination of stuck workers, global CPU/RAM/PID quotas: absent.
- Atomic action validation/execution under adversarial DOM mutation: not proven;
  retained handles prevent ordinal fallback but do not establish semantic intent.
- Native table and ARIA extraction parity: incomplete.
- Full operation metrics/exporters: incomplete. Session admission is capped at 16 calls.
- MCP malformed-frame/oversized protocol request fuzzing: not implemented; SDK
  protocol behavior is used, but application response limits are not a transport cap.
- Rust network integration/rebinding/redirect regression suite: incomplete.
- Benchmark cold interpreter start, click/fill, Linux Fidelity, long-running leak
  profiling, representative production-site recall and full-payload token savings:
  not measured. No performance optimization claim.

## Compatibility and operational risks

Read CHANGELOG.md for intentional security restrictions. Default APIs remain
importable but action/session contracts and CLI output changed. No production
release or version bump has been published. The shared 0.2.0 version is not proof
that PyPI or old binaries contain these changes. The namespace is a network
boundary, not filesystem/Chromium sandbox escape isolation. Deploy only in a
restricted environment without host secrets while remaining gates are open.

## CI and publishing

Source 384ae90 passes SonarCloud's external quality gate, all eight Python
3.11-3.14 Linux/Windows jobs (lint/format/types/tests/package build), all five
Linux browser fixtures, and the Python dependency audit. Rust fmt, strict Clippy,
tests, release build and cargo-audit also pass. All 11 engineering jobs and the
external SonarCloud quality gate passed. Receipt: evidence/ci-384ae90.json.
Current run: https://github.com/k39139215-gif/aerobrowse/actions/runs/45771375649.
Browser receipt: evidence/ci-384ae90-browser/ci-browser.xml.
Sonar receipt: evidence/sonar-384ae90.json.

Earlier all-green engineering source c09500a receipts remain historical; they do
not establish the current external gate status. Subsequent static analysis
exposed benchmark output overwrite risk, blocking async Rust process management,
and dependency setup builds. These were corrected with regressions, meaningful
refactors and wheel-only CI dependencies. No analyzer suppression was introduced.

Local Python: 67 passed, 4 Linux-only skips; Rust: 5 passed, strict Clippy/fmt
passed. Python wheel/source builds succeed. No known Python dependency advisory
was found at the recorded scan. Tests are evidence for their covered paths,
not independent security certification or exhaustive browser egress proof.

Measurements are bound to clean source c09500a before maintainability refactors;
no measured performance improvement is claimed for later revisions. See receipt
limitations and BENCHMARKS.md. Draft PR remains open and unmerged:
https://github.com/k39139215-gif/aerobrowse/pull/1.

## Additional final-source review

The complete local suite throughfe159f9 passed146 tests,2 platform skips and64
explicit browser/native deselections in191.74seconds. Partial raw worker pipe
writes were corrected with a content-corruption regression; zero writes fail closed.
The runtime positional-force-Fidelity path is now checked before browser launch
when kernel quotas are unavailable; its regression is queued for Linux CI.
Browser/renderer kill and Linux parentdeath regressions have been added; those
remain unverified until required Linux CI runs. No fake worker/browser replaces
these required browser checks. Quota/system/process fixtures run only on owned
local data and explicit internal CIDRs.

Final focused crash validation found an incorrect renderer trigger: Chromium may
have a spare renderer. Killing all owned session renderers instead caused the
in-flight CDP call to hit its request deadline, followed by hard worker termination.
This is bounded timeout recovery, not immediate renderer-crash detection. The
regression now verifies3second renderer timeout, no live descendants/capacity leak
and fresh-session navigation. Required Linux parentdeath, main-browser-process
crash recovery, fd-cleanup traversal, IPC partial-write and positional quota-denial
checks passed source6d2e932 independently; renderer final rerun remains pending.
Failed intermediate receipts are retained under evidence/phase2/runtime-*-failed.

At sourcec963127, independent Linux run45837608925 passed25 runtime tests with2
Windows-only skips (runtime-c963127/runtime-boundary.xml): actual browser main
process and renderer-kill deadline recovery, fresh browser navigation, Linux
controller-parent death/cgroup/temp cleanup, kernel memory/fork denial, fd-relative
cleanup traversal/symlink, closed managers, IPC partial writes and positional
Fidelity denial without quotas. This verifies the declared bounded runtime contract;
it does not provide separate renderer quotas, direct SDK enforcement or indefinite
leak-freedom. The renderer error was TIMEOUT after the configured3second deadline.
