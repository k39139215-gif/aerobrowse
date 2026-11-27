# AeroBrowse engineering report

Release recommendation: **NOT_PRODUCTION_READY**. This report describes
implementation `0450352ae6d1a6504e8827595f6fb854e71583c6`. Original baseline:
`44f3e73409d3f0c4e6e376f0c98198abd00ccc0f`.

## Verified implementation

Python uses a public-only, DNS-pinned HTTP transport and an isolated Linux
Chromium runtime. The host broker validates every destination and redirect;
Chromium has a separate network namespace, private filesystem mounts, and no
direct TCP/UDP egress. Required cgroups enforce resource budgets. Unsupported
hosts fail closed. Namespace isolation does not establish protection against a
Chromium/kernel escape or replace an independent security assessment.

Hybrid navigation tracks the active page and engine. A Turbo action triggers live
navigation and extraction, then returns a new generation with STALE_ACTION_ID;
it never executes an old static candidate. Live actions retain exact DOM nodes
and validate document/generation/mutation state. Discovery waits return fresh IDs
by exact accessible name/optional role without activation. Keyboard editing uses
synthetic events and checks target identity again after cancellable beforeinput.

Owned MCP sessions use serialized process workers, explicit session IDs bound to
the transport owner, bounded queues, deadlines, cancellation and cleanup. Public
SDK workers use the same supervised runtime. Admission now reserves each declared
session task/memory budget against its aggregate pool. Two 256-task sessions need
an explicitly provisioned 512-task pool; production defaults were not raised.
Aggregate PID/OOM events return a resource error and retire the affected worker.
Separate SDK instances require an enclosing deployment quota.

Extraction preserves bounded headings, lists, nested tables, explicit and inferred
header relationships, forms, embedded-content notices, language/direction and
landmarks. Twelve owned fixtures grade 44 explicit requirements. This corpus is
not a demonstration of general semantic recall or complete information retention.
Token counts use versioned real tokenizers and distinguish Markdown, complete
canonical JSON, and character reduction. Three licensed vocabularies ship with
upstream checksum verification; worker initialization needs no network or cache.

Rust Turbo retains bounded pinned HTTP. Native Linux Fidelity now provides a
persistent isolated Chromium CDP session with pinned request brokering, the shared
Python/Rust action runtime, generation-validated click/fill/select/check/press,
screenshot, exact-name waits, navigation history, tabs and reload. Rust MCP stays
Python-authoritative for protocol/session parity. Windows/macOS native Fidelity
fail closed; trusted physical events, uploads, WebSockets, service workers and
Authorization remain unsupported.

Local operator JSON/Prometheus APIs provide bounded operation/error/rate/latency
and sampled-memory metrics. Request logs contain request/session IDs, engine,
operation, duration and outcome. Inputs never become metric labels. This is not
a public metrics endpoint, external aggregation service or exact peak-memory gauge.

## Verification and measurements

Full engineering run [46006851015](https://github.com/k39139215-gif/aerobrowse/actions/runs/46006851015)
on head `0450352` succeeded across all 11 jobs: eight Python matrix jobs, Rust,
dependency audit and the mandatory browser job. The browser job's 1,801.479-second
soak measured 1,168 cycles, zero orphan processes, zero occupied slots, and an
87,973,888-byte sampled parent RSS maximum. Its receipt identifies the tested
merge tree as `6669d2ff`; it is a sequential owned-fixture lifecycle soak, not a
native-Rust browser soak or an indefinite leak guarantee. Native Linux run
`46006841440` is SUCCESS: 10 tests, 0 failures, 0 skips. Production acceptance
still depends on external security review and unresolved original scope requirements.

Focused Linux run [45880812905](https://github.com/k39139215-gif/aerobrowse/actions/runs/45880812905)
is SUCCESS. All 92 tracked implementation/test/configuration Git blobs match
PR merge tree `13cf4e086bf0fe11a8febae0e4e247d6e6f97a9d`. The source and
receipt indexes are in `evidence/developer/`. These are self-collected receipts;
no independent evidence custody or external assessment is claimed.

| Metric | Before | After / current observation | Evidence |
|---|---|---|---|
| Security findings | Original confirmed network/action/session failures in AUDIT.md | Declared fixes have regression coverage; SonarCloud gate SUCCESS; earlier `8db91bf` analyzer inventory is historical; no independent assessment | run46006851015; analyzer receipts |
| Python tests | Original 5 passed; previous full checkpoint 206 | Each of 8 Linux/Windows Python 3.11–3.14 jobs: 206 passed / 21 explained skips (227 total) | run46006851015; matrix XML under `evidence/native/full-0450352/browser-evidence/agent/ci-0530488/full/` |
| Browser/runtime tests | Earlier checkpoint: 68 browser; 38 runtime passes | Python browser job: 83 tests, 0 failures, 7 expected skips; Python-only collection: 71 tests / 4 skips because native cases run in the separate Rust job; native Chromium/security: 10 passed / 0 skips; Linux runtime job: 42 tests / 2 Windows-only skips | `ci-browser.xml`, `python-tests.xml`, `ci-runtime-kernel.xml`; native run46006841440 |
| Rust tests | 5 native units at prior checkpoint | 9 unit tests; formatting, strict Clippy, release build; native Linux CDP integration 10/10 pass; cargo audit reports an unmaintained dependency | run46006851015 and native run46006841440 |
| Warm Turbo latency | No comparable baseline | p50 3.521 ms; p95 3.870 ms; n=100 | Focused phase2/benchmark-linux.json |
| Warm Fidelity latency | No comparable baseline | p50 29.042 ms; p95 33.832 ms; n=99 | Same raw operation receipt |
| Peak RAM | No comparable baseline | Operation-run sampled tree maximum 1,476,448,256 bytes; shared-pool sample maximum 2,465,923,072 bytes; neither is exact peak | Separate operation/shared-load receipts |
| Token reduction | Character estimates; worker cache misses caused downloads | Long article: 1,713 HTML / 1,304 Markdown / 1,635 complete JSON tokens; 4.55% complete reduction; small fixtures expand | extraction-quality-8db91bf.json; offline wheel check |
| Concurrent sessions | Repeated default 256-task/two-browser workload failed | Explicit 512-task pool: 12 measured snapshots in 2.618 s; 6 per session; 2 queue refusals; all workers reaped | ci-8db91bf/developer/shared-browser-load.json |
| Complete task load | No comparable baseline | 6 complete tasks / 2 independent workers / 8.593 s; all reaped | ci-8db91bf/agent/concurrency.json |
| Cleanup soak | Prior checkpoint: 739 successful cycles | Python browser-worker soak: 1,168 cycles / 1,801.479 seconds; zero observed orphans or occupied slots; sampled parent RSS max 87,973,888 bytes | `evidence/native/full-0450352/browser-evidence/phase2/soak-linux.json`; run46006851015; receipt source tree `6669d2ff` |

The latency and RAM rows above are the **focused run**, not the later full run.
Snapshot/click/fill p50 values are 8.501/9.036/9.841 ms, n=100 each. One actual
Turbo/Fidelity synchronization took 731.090 ms; a single observation is not a
latency distribution. All 1,133 raw rows reproduce the 16 operation summaries.
The shared-pool duration includes initialization/admission work and excludes
cleanup; its 12 snapshots exclude navigation and the separate queue experiment.

These tiny controlled fixtures establish neither production capacity/fairness nor
before/after speedups. Memory receipts use different scopes and must not be added
or treated as physical cgroup peaks. Benchmark dirty=true reflects generated
evidence files; compare tracked source Git blobs, not that flag alone.

The Python matrix's 21 non-browser skips and Linux runtime suite's 2 Windows-only
skips are reported by the test suite. Cargo audit reports `fxhash` as unmaintained
(RUSTSEC-2025-0057, no fixed upgrade available); the command succeeds, but this
remains a dependency maintenance risk.
The native-specific Linux job ran 10 tests with zero skips. Actual-model evaluation is NOT_RUN because
explicit credentials/model are unavailable; scripted success is not a model result.

## Confirmed failures and remediation evidence

- A repeated two-browser workload failed under the default aggregate task quota.
  Reservation admission and aggregate kernel-counter checks address the confirmed
  overcommit/error-reporting defects. The 512-task test configuration is explicit;
  no benchmark silently relaxes production defaults.
- Original Rust regressions exposed hidden-ancestor/descendant labels and unnamed
  credential URLs. The original failures and subsequent native passing tests are
  retained; the native browser now has a 10/10 Linux receipt on source `0450352`.
- Raw MCP requests exceeded response deadlines because fresh worker temp directories
  forced tiktoken downloads. Socket-denial tests for all three encodings and an
  isolated built-wheel test verify offline initialization. Corrupt vocabulary
  data returns TOKENIZER_ERROR instead of an estimate or download fallback.
- Agent benchmark CLIs accepted arbitrary output paths. They now use the existing
  confined, exclusive evidence writer; traversal and overwrite regressions pass.

Original failures remain under `evidence/developer/failed-capacity-e0e4a1d/`,
`red-07b3a17/`, `ci-d4fed85/`, and `rust-pruner-red.txt`. Raw failing XML can
contain whitespace-only traceback lines; byte identity is intentionally preserved.

## Acceptance classification

**Fixed and verified in the declared scope:** pinned HTTP/redirect restrictions,
Linux browser egress boundary regressions, hybrid handoff, exact live action IDs,
owned supervised sessions, controlled authentication/tabs/history/forms, discovery
waits, synthetic input reentrancy, semantic edge cases, offline tokenizer packaging,
safe evidence output, quota admission and bounded local operator telemetry.

**Fixed but not independently verified:** the declared test-covered remediation
has first-party verification; external security and production validation remain absent.

**Partially implemented:** broad site compatibility, general extraction recall,
production load fairness, complete telemetry aggregation and auxiliary-target
browser compatibility. Unbrokered worker/OOPIF requests fail closed.

**Not implemented:** trusted physical input, file upload/download, WebSockets,
service workers and HTTP Authorization. Native Rust Fidelity is Linux-only.

**Not independently verified:** external security assessment, production load,
Chromium/kernel exploit resistance and independent evidence custody. Latest
SonarCloud quality gate is green; historical analyzer snapshots are not current
findings and no security findings were suppressed or waived.

Original draft [PR #1](https://github.com/k39139215-gif/aerobrowse/pull/1) targets
main. Stacked draft [PR #2](https://github.com/k39139215-gif/aerobrowse/pull/2)
contains this continuation. Neither is merged. No package release, production
approval or scope exclusion is authorized. `ACCEPTANCE.md` maps original scope.

The latest SonarCloud gate passed at source `0450352`. The earlier `8db91bf`
analyzer finding inventory is historical and must not be presented as current.


## Final full-run observations

The separate final full-run receipt under `evidence/developer/full-8db91bf/browser/`
tests the earlier Python implementation `8db91bf`, not the later native Rust browser.

Full-run warm Turbo p50/p95=3.155/3.583 ms,n100;warm Fidelity=27.427/29.851 ms,n99.
Snapshot/click/fill p50=7.422/8.304/8.966 ms,n100. Operation-run sampled tree maximum
1,472,442,368 bytes,20 ms sampling; not exact peak. One handoff665.270 ms is a
single observation. All1,133 raw rows reproduce16 summaries. Shared512-task pool
completed12 measured snapshots in2.367 seconds; six per session,all workers reaped.
Six complete tasks/two independent workers took8.355 seconds,all reaped.

The historical `8db91bf` soak reported1,044 cycles over1,800.891 seconds. The
current full-run receipt instead records1,168 cycles over1,801.479 seconds on
merge tree `6669d2ff`, with zero orphans/occupied slots and a sampled parent RSS
maximum of87,973,888 bytes. Neither value is peak browser RAM or indefinite leak
proof. The current browser XML reports83 tests/0 failures/7 skips; native browser
XML reports10/0/0. All11 full CI jobs and SonarCloud pass. No independent
assessment is implied.


## Native Linux parity receipt

Run [46006841440](https://github.com/k39139215-gif/aerobrowse/actions/runs/46006841440) on source `0450352` passed Rust formatting, strict Clippy, Rust unit tests, release build and **10 native/browser tests with 0 failures and 0 skips**. The tests cover live navigation, click/fill/select/check, screenshot, stale generations, injection-safe values, blocked/private destinations, redirects, history back/forward, tabs, reload, exact discovery waits, namespace mounts, controller death and cgroup cleanup. This is a first-party Linux receipt; it does not establish Windows/macOS Fidelity parity or independent security certification.


The previously reported `8db91bf` timings and source receipts are historical
Python/source measurements. They do not characterize native Rust browser latency
or memory. The later 30-minute soak is the Python browser-worker lifecycle test on
merge tree `6669d2ff`; native Rust lifecycle coverage is the dedicated controller
death/cgroup cleanup test in run46006841440, not a 30-minute native soak.
