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
