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

CI configuration adds Python matrices, lint/types/build, deterministic tests,
Linux browser fixtures, strict Rust checks and dependency audits. All jobs passed on verified source c09500a; final evidence-only commits must
be distinguished from that tested source. Local Python dependency advisory scan found no known
vulnerabilities in the installed environment; evidence/pip-audit.json records the scan. Draft PR will remain unmerged; production
acceptance cannot be inferred from its creation or a subset of green jobs.

Current source checkpoint c09500a: all eight Python matrix jobs and all five
Linux browser fixtures passed in run 45769090597. Rust/advisory job also passed: all 11 jobs are green.
Receipt: evidence/ci-c09500a.json; run URL:
https://github.com/k39139215-gif/aerobrowse/actions/runs/45769090597. Earlier runs reproduced namespace provisioning and label
extraction failures; these were corrected without skipping Linux tests. All jobs
passed on the earlier caf543c source, including cargo audit. Final head evidence
must be checked independently of that earlier success.

The local measurement receipt is bound to clean source c09500a; it supersedes an
earlier dirty-tree receipt. It records tiny controlled fixtures and is not a
speedup claim. No independent security certification or production readiness
claim is made. Draft PR: https://github.com/k39139215-gif/aerobrowse/pull/1.

Separate SonarCloud gate failed on 4cbfb6d despite passing engineering CI.
Benchmark path restrictions, asynchronous Rust MCP process management, cancellation
cleanup and complexity refactors were implemented; final reanalysis is pending.
Do not interpret the earlier 11-job receipt as a fully green PR status.
