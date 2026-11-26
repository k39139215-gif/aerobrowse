# Phase-two adversarial audit

Release recommendation: **NOT_PRODUCTION_READY**.

Preflight PR #1 draft head: `943ca57e9ef8ef5c4993a0aff25a8b8539e42713`.
Main/base: `44f3e73409d3f0c4e6e376f0c98198abd00ccc0f`. The working tree was clean
before this phase. Follow-up branch: `fix/phase2-adversarial-validation`. Main and
PR #1 remain untouched. Baseline: 67 Python passes, 4 platform skips; 5 Rust tests.
Original audit and inventory remain in `AUDIT.md` and `evidence/baseline-inventory.txt`.

| Finding | Severity | Root cause, file and impact | Implemented remediation | Verification | Remaining scope / release impact |
|---|---|---|---|---|---|
| Browser direct egress | P0 | `isolation.py`: network-only boundary lacked filesystem/process separation | Mandatory Bubblewrap network/mount/user/PID/IPC/UTS boundary; host broker only | 43 required Linux browser checks at `f1ce086`; TCP/UDP canaries, routing removed, descendants inspected | Declared scenarios verified; exhaustive utility/egress review and inner Chromium sandbox open |
| Host filesystem exposure | P0 | `isolation.py`: browser could see host files/environment | Minimal read-only runtime mounts, private tmp/home/proc/dev, scrubbed environment | Host-secret absence and private-tmpfs mount receipts | Narrow gate verified; no external exploit assessment |
| Unkillable worker operations | P0 | `sessions.py`: thread cancellation could not stop a browser operation | Process-owned sessions, bounded IPC and correlated requests, hard deadline teardown | `c963127`: 25 Linux runtime passes, 2 Windows-only skips; actual browser/renderer crashes and parent death | Bounded contract verified; renderer recovery uses timeout |
| Resource exhaustion | P0 | `runtime.py`: request limits alone do not cap descendants | cgroup v2 / nested Windows Job Objects; aggregate session/pool memory/CPU/task controls | Real OOM and fork denial; default 64-task Chromium failure correctly reproduced; low-budget refusal retires slot | Direct SDK, separate renderer and cross-instance caps remain unimplemented and blocking |
| Action TOCTOU | P0 | `fidelity.py`: separate validation and activation could select changed targets | Isolated-world one-task exact-node/epoch/document/generation/state validation and activation; focus recheck | Actual renderer mutation/restoration, duplicate-target and main-world override tests | Declared synthetic-event contract verified; physical trusted events unsupported |
| Unsafe guardian cleanup | P1 | `runtime.py`: CLI filesystem paths reached recursive cleanup | Inherited parent-directory descriptors plus generated basename validation; no-follow cgroup access | Real Linux traversal/symlink/cleanup regression; actual parentdeath cgroup/temp removal | Implemented and verified; no analyzer traversal finding remains |
| Raw IPC corruption | P1 | `runtime.py`: unbuffered pipe writes assumed complete frames | Loop over partial writes; zero writes fail closed | Real-worker suite plus deterministic partial-write/closed-pipe regression | Verified; no fake browser substituted for crash tests |
| Quota escalation argument | P0 | `runtime.py`: keyword-only force-Fidelity check missed positional argument | Reject both positional and keyword escalation without enforced quotas | Actual no-delegation worker regression passes on Linux | Fixed and verified declared internal transport |
| MCP input buffering | P1 | `mcp_transport.py`: SDK decoding occurred before byte/shape caps | Bounded newline UTF-8 transport, shape/depth caps, bounded in-flight IDs and deadlines | 15 framing/deadline checks, 16 session/malformed subprocess checks | Broad protocol fuzzing and browser-load/disconnect matrices incomplete |
| Framework coverage | P1 | `tests/compatibility`: plain HTML did not demonstrate framework state semantics | Pinned real React/Vue/Next.js/Angular builds and controlled state/dialog/route assertions | Required Linux framework tests pass; no CDN or external site dependency | Lazy/infinite content, extensive validation/error/large-page recall remain open |
| Native capability mismatch | P1 | `rust_core`: separate browser/security semantics were unsafe | Python authoritative browser runtime; narrower native HTTP; Rust MCP integrates Python | Strict Rust CI and real compiled native/Python refusal contracts pass | Full original native browser/action parity not implemented; exclusion not approved |
| Benchmark/soak claims | P1/P0 | Character estimates/tiny samples did not justify speed/memory/reliability claims | Actual tokenizer metadata, raw timing distributions, declared SDK Turbo load scope and mandatory kernel-supervised soak | `f1ce086`: 1,800.735 seconds, 931 successful sequential browser cycles, zero observed orphans/slots | Narrow soak verified; paired baseline, browser/MCP load and broad recall absent |
| Private tmpfs analyzer findings | P1 gate | `isolation.py`: literal `/tmp` mount/chdir flagged as publicly writable path | Actual private tmpfs and host-device exclusion tested; no suppression | Negative host-mount/canary tests pass; Sonar still reports two findings | Open analyzer review; quality gate not green |
| Independent assessment | P1 | Implementation verification is not an external review | `SECURITY_REVIEW_PACKAGE.md` records boundary, assumptions, commands and limitations | Preparation only | External assessment not performed; no certification claim |

## Completed evidence

Green full run `45833263200`, source `f1ce086`, PR merge checkout
`1710acaf4f4f0e877a53653f525939b688143b51`: all 8 Python 3.11–3.14 Linux/Windows
jobs, Rust formatting/strict Clippy/tests/release/native contract, dependency audit,
43 required Linux browser tests and 19 kernel/runtime passes with 2 Windows-only
skips. The soak ran 1,800.735 seconds and completed 931 navigate/fill/click/close
iterations. Every raw row records zero remaining descendants and zero active slots.

The explicit browser session budget was 256 Linux tasks under an unchanged
256-task aggregate cap, sequential owned fixture, `max_sessions=2`. Controller RSS
at completed iterations was 44,367,872 bytes initially and 45,510,656 bytes last/max.
This is not browser peak memory, concurrent browser load or indefinite leak proof.

Source `c963127`, focused run `45837608925`: 25 Linux runtime passes, 2 Windows-only
skips. It verifies real main-browser-process recovery, termination of all owned
renderers with a bounded 3-second operation timeout, replacement navigation, Linux
parentdeath cgroup/temp cleanup, OOM/fork refusal, partial IPC and quota escalation
denial. Later full CI and its repeated soak remain pending until separately recorded.

Local full suite through `fe159f9`: 146 passes, 2 platform skips, 64 browser/native
deselections. Final Windows runtime: 16 passes, 3 Linux-only skips, 8 browser
deselections. These are overlapping scopes, not additive unique-test counts.

## Preserved failures and limits

The first supervised soak failed immediately: Chromium exhausted the default
64-task Linux session limit (`pids.events.max=66`, `oom_kill=0`). Defaults and the
aggregate cap were not lowered. Browser acceptance explicitly declares its larger
session budget; low-budget exhaustion returns `WORKER_RESOURCE_LIMIT` and retires
the session. Failed soak evidence is never counted as 30-minute evidence.

The first renderer test killed a possibly spare renderer. The corrected trigger
kills all owned renderers; its CDP operation reaches the request deadline and the
supervisor kills the tree. The final test verifies that actual timeout recovery,
cleanup and replacement rather than claiming immediate crash notification.

`evidence/phase2/VERIFICATION.md` indexes raw results and their revisions.
`ENGINEERING_REPORT.md` reports measurements and acceptance limits. No P1 exclusion
has user approval. Green tests do not waive unimplemented original requirements or
certify isolation. Both PRs remain draft; no merge or stable release is authorized.
