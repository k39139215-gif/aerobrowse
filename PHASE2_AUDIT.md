# Phase 2 adversarial audit

Preflight PR #1 draft head 943ca57e9ef8ef5c4993a0aff25a8b8539e42713, base
44f3e73409d3f0c4e6e376f0c98198abd00ccc0f. Working tree clean before edits;
follow-up branch fix/phase2-adversarial-validation. Main and PR #1 untouched.
Baseline: 67 Python passed / 4 Linux-only skipped; 5 Rust tests passed. Evidence:
evidence/phase2/baseline.json and baseline-python.xml.

| Finding | Severity | Existing evidence | Missing evidence | Implementation | Final status |
|---|---|---|---|---|---|
| Chromium direct egress boundary | P0 | 5 basic Linux tests | canaries, process namespace inheritance, bypass mechanisms | filesystem/network sandbox and real attack canaries | In progress |
| Browser sees host filesystem | P0 | network namespace only | filesystem negative access proof | minimal read-only runtime mounts, private home/tmp/proc/dev | In progress |
| Thread workers cannot be killed | P0 | cleanup queue coverage | OS termination on timeout/crash/disconnect | process workers with lifecycle and hard termination | In progress |
| Resource quotas | P0 | request/queue/session limits | kernel memory/cpu/pid and global quotas | explicit capability-gated cgroup support and OS limits | In progress |
| Action TOCTOU | P0 | epoch precheck then separate action | adversarial mutate during preparation | browser-task atomic guard/operation with retained identity | In progress |
| MCP input buffered before validation | P1 | SDK schemas/session locks | wire bytes/depth/UTF8 bounds, malformed frames | bounded stdio before SDK decode | In progress |
| Framework compatibility | P1 | plain HTML only | pinned real React/Vue/Next/Angular fixtures | controlled builds and content/action metrics | In progress |
| Rust capability contract | P1 | native actions fail closed, Python MCP | explicit declared release architecture/contracts | Option B authoritative Python runtime | In progress |
| Performance/soak evidence | P1/P0 | tiny Turbo sample | distributions, lifecycle soak >=30min | versioned raw benchmark/soak receipts | In progress |
| Independent review preparation | P1 | prior audit | full boundary/repro package | exact evidence and exclusions | In progress |

No finding is fixed by documentation alone. Green CI does not certify isolation.
