# Phase 2 adversarial audit

Preflight PR #1 draft head 943ca57e9ef8ef5c4993a0aff25a8b8539e42713, base
44f3e73409d3f0c4e6e376f0c98198abd00ccc0f. Working tree clean before edits;
follow-up branch fix/phase2-adversarial-validation. Main and PR #1 untouched.
Baseline: 67 Python passed / 4 Linux-only skipped; 5 Rust tests passed. Evidence:
evidence/phase2/baseline.json and baseline-python.xml.

| Finding | Severity | Existing evidence | Missing evidence | Implementation | Final status |
|---|---|---|---|---|---|
| Chromium direct egress boundary | P0 | 5 basic Linux tests | canaries, process namespace inheritance, bypass mechanisms | filesystem/network sandbox and real attack canaries | Implemented; verification incomplete |
| Browser sees host filesystem | P0 | network namespace only | filesystem negative access proof | minimal read-only runtime mounts, private home/tmp/proc/dev | Implemented; verification incomplete |
| Thread workers cannot be killed | P0 | cleanup queue coverage | OS termination on timeout/crash/disconnect | process workers with lifecycle and hard termination | Implemented; verification incomplete |
| Resource quotas | P0 | request/queue/session limits | kernel memory/cpu/pid and global quotas | explicit capability-gated cgroup support and OS limits | Implemented; verification incomplete |
| Action TOCTOU | P0 | epoch precheck then separate action | adversarial mutate during preparation | browser-task atomic guard/operation with retained identity | Implemented; verification incomplete |
| MCP input buffered before validation | P1 | SDK schemas/session locks | wire bytes/depth/UTF8 bounds, malformed frames | bounded stdio before SDK decode | Implemented; verification incomplete |
| Framework compatibility | P1 | plain HTML only | pinned real React/Vue/Next/Angular fixtures | controlled builds and content/action metrics | Implemented; verification incomplete |
| Rust capability contract | P1 | native actions fail closed, Python MCP | explicit declared release architecture/contracts | Option B authoritative Python runtime | Implemented; verification incomplete |
| Performance/soak evidence | P1/P0 | tiny Turbo sample | distributions, lifecycle soak >=30min | versioned raw benchmark/soak receipts | Implemented; verification incomplete |
| Independent review preparation | P1 | prior audit | full boundary/repro package | exact evidence and exclusions | Implemented; verification incomplete |

No finding is fixed by documentation alone. Green CI does not certify isolation.

## Verified evidence and newly observed blockers

Implementation source 0caf7e7 was tested by CI run 45831559623 (PR merge checkout
99ebb5d15a1263f22405c4144ba164f2170e8817). Its required browser suite passed 41/41,
including real four-framework flows, adversarial action mutation, TCP/UDP canaries,
routing bypass and descendant namespace/mount checks. Kernel/runtime suite passed
17 with 2 explicit Windows-only skips. Receipts: evidence/phase2/ci-0caf7e7.
These are coverage-specific observations, not proof of every subprocess or egress
mechanism in all Chromium builds. The 30-minute soak failed at its first supervised
Chromium navigation; this P0 remains open and a focused quota-counter regression
was added at 9531cd1. No failed soak is treated as 30-minute cleanup evidence.

Local source through 5195aaf: 144 passed, 1 Linux-only skip, 59 browser/native
contract deselections (python-final-local.xml). Runtime descriptor changes through
9aeeb16: 14 passed, 2 platform skips, 3 browser deselections
(runtime-guardian-local.xml). Native rejection contracts run against a real built
Rust binary; strict Rust fmt/clippy/tests/release/audit passed in run 45831559623.

| Finding | Severity | Current evidence | Remaining work | Release impact |
|---|---|---|---|---|
| Direct browser egress / host filesystem | P0 | 41/41 required Linux browser tests, real canaries and descendant checks | broad utility/process audit; inner Chromium sandbox not proven | Narrow coverage verified; broader review required |
| Killable worker lifecycle | P0 | real Windows/Linux timeout/cancellation/crash, parent job death; Linux guardian | browser/renderer crash during action, Linux parent termination | Partial; blocking |
| Kernel quotas | P0 | real Linux OOM/fork denial; Windows memory/process denial | supervised browser compatibility; per-renderer counts; SDK controls | Partial; blocking |
| Browser soak | P0 | harness fails at first supervised navigation | diagnose then complete uninterrupted >=1800 seconds | Open; blocking |
| Action TOCTOU | P0 | 70 mutation iterations plus focus-replacement, exact duplicate identity, isolated primitives | broader concurrent/reentrant adversarial execution | Implemented and tested contract; scope limited to synthetic DOM |
| MCP transport | P1 | 14 framing + 16 malformed/session subprocess checks; bounded predecode | broad protocol fuzzing/client-disconnect under browser load | Partial coverage; no remote transport claim |
| Framework compatibility | P1 | four pinned real frameworks, state/targets/route/modal/hidden checks | recall metrics, infinite scrolling/lazy/error/large pages | Partial; exclusion not approved |
| Python/Rust contract | P1 | Option B documented; real blocked-destination cross-language tests | review narrower package contract | Implemented explicit scope |
| Benchmark rigor | P1 | 100 action samples, 99 warm browser nav, raw percentiles/token data | controlled baseline, cold distributions, MCP/browser load/resource fairness | Partial; no speedup claim |
| Independent review package | P1 | SECURITY_REVIEW_PACKAGE.md, exact architecture/limitations | actual external assessment | Prepared only |
| Guardian argv cleanup | P1 | descriptor-relative generated basename/symlink regression; analyzer no longer reports traversal | latest cross-platform CI | Fixed implementation, verification pending |
| Sonar private tmpfs findings | P1 gate | analyzer flags literal /tmp mount/chdir; private tmpfs isolation regression verifies no host device | human review or structural fix; no suppression | Gate open |

No P1 scope exclusion is approved. Remaining P0s block production readiness.

At f1ce086 the combined supervised-browser regression and hard low-budget refusal
passed before the soak. The soak began 2026-11-26T13:54:26Z in run45833263200;
it is not a pass until the exclusive raw/summary receipts establish >=1800seconds.
Default64/session remains unchanged; acceptance explicitly supplies256/session
under the unchanged256 aggregate task cap. Latest local review also corrected
partial writes on raw worker pipes with corruption/closed-pipe regressions.

Final-source runtime gate sourcec963127: Linux run45837608925 passed25 with2
Windows-only skips. It includes real browser/renderer crash+replacement recovery,
Linux parentdeath cgroup/temp cleanup, fd cleanup attack rejection and quota/error
semantics. Renderer failure is bounded request-timeout recovery (3seconds in test),
not immediate crash detection. Direct SDK/per-renderer/cross-instance caps remain
unimplemented, unapproved production exclusions. Full source matrix/soak pending.
