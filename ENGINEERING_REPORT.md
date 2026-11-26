# Engineering report - remediation candidate

Baseline revision: 44f3e73409d3f0c4e6e376f0c98198abd00ccc0f.
This branch is **not production-ready**. It contains real source fixes and regression
coverage, with substantial unsupported/unverified acceptance requirements.

| Metric | Before | After | Evidence |
|---|---|---|---|
| Security findings | 4 P0 audit findings | HTTP pinning and session isolation regression-tested; Chromium/native feature restrictions; full browser boundary unverified | AUDIT.md, tests/test_security.py, tests/test_mcp.py |
| Python tests | 5 passed, live-site dependencies | 54 passed, 2 skipped locally | evidence/python-tests.xml |
| Rust tests | Could not run with damaged host toolchain | 5 passed | Local Rust 1.100.0 LLVM Windows test run |
| Rust lint/build | No verified baseline | fmt, strict Clippy, release build passed locally | Required cargo commands executed |
| Turbo latency | Not measured | Warm median 30.31 ms (4 samples), cold 596.18 ms; no improvement comparison | evidence/benchmark-local.json |
| Fidelity latency | Not measured | Unsupported on Windows; failures recorded | evidence/benchmark-local.json |
| Peak RAM | Not measured | 79.13 MiB sampled process-tree RSS | evidence/benchmark-local.json |
| Token reduction | Historical character estimates | Actual tokenizer counts on 8 synthetic categories | evidence/token-fixtures.json |
| Concurrent sessions | Not measured | 2 concurrent SDK Turbo workers, 10/10 successful requests; 107.08/s fixture only | evidence/benchmark-local.json |

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

## Implemented but browser verification pending

Python Linux namespace launcher/host broker, Turbo/Fidelity live handoff,
ElementHandle actions, live DOM invalidation, clicks/fills/select/check/press,
scroll/wait/screenshot, Chromium cleanup/crash detection. Tests are present but
Windows cannot execute the required boundary. CI must establish these behaviors.

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
- Full operation metrics/exporters and request queue admission bounds: incomplete.
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
Linux browser fixtures, strict Rust checks and dependency audits. Its final
remote status is not yet known. Local Python dependency advisory scan found no known
vulnerabilities in the installed environment; evidence/pip-audit.json records the scan. Draft PR will remain unmerged; production
acceptance cannot be inferred from its creation or a subset of green jobs.

Remote checkpoint: all eight Python matrix jobs passed, as did Linux Rust fmt,
Clippy, tests and release build on ca233b9. Initial browser job failed closed
because namespace creation was denied. CI provisioning was added; rerun pending.
Local benchmark receipt was captured from a dirty working tree; its recorded Git
revision is a base revision, not an exact source binding. No speedup claim.
