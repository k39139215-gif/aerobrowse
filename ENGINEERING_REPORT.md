# AeroBrowse engineering report

Release recommendation: **NOT_PRODUCTION_READY**. This report describes
implementation `8db91bf2bbdd84966cb6032cdd9a86b96e2bc06d`. Later documentation and
evidence commits do not change the implementation. Original baseline:
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

Rust native retrieval remains read-only with input/network restrictions. Static
extraction now filters hidden ancestors and descendant labels and sanitizes
credential-bearing unnamed URL labels. Rust MCP delegates to Python. Native Rust
live-browser/action parity is **not implemented** and is not an approved exclusion.

Local operator JSON/Prometheus APIs provide bounded operation/error/rate/latency
and sampled-memory metrics. Request logs contain request/session IDs, engine,
operation, duration and outcome. Inputs never become metric labels. This is not
a public metrics endpoint, external aggregation service or exact peak-memory gauge.

## Verification and measurements

Final full engineering CI run: **PENDING — 45880822782**. All eight Python jobs,
Rust and dependency auditing have passed; the mandatory 30-minute browser-worker
cleanup soak is in progress. Full broad acceptance remains pending until the run
completes. Earlier green runs do not verify changed source.

Focused Linux run [45880812905](https://github.com/k39139215-gif/aerobrowse/actions/runs/45880812905)
is SUCCESS. All 92 tracked implementation/test/configuration Git blobs match
PR merge tree `13cf4e086bf0fe11a8febae0e4e247d6e6f97a9d`. The source and
receipt indexes are in `evidence/developer/`. These are self-collected receipts;
no independent evidence custody or external assessment is claimed.

| Metric | Before | After / current observation | Evidence |
|---|---|---|---|
| Security findings | Original confirmed network/action/session failures in AUDIT.md | Declared fixes have regression coverage; 46 analyzer findings remain open, including 2 private-tmpfs path findings; no independent assessment | AUDIT.md; sonar-8db91bf.json; failed and passing regressions |
| Python tests | Original 5 passed; previous full checkpoint 206 | Each of 8 Linux/Windows Python 3.11–3.14 jobs: 236 passed / 21 explained skips; local same counts | full-8db91bf/python/; python-8db91bf.xml |
| Browser/runtime tests | Previous full checkpoint: 68 browser; 38 runtime passes | Focused latest source: 33 workflow passes, 40 runtime passes / 2 Windows-only skips; full browser totals pending receipt | ci-8db91bf/agent/quick-workflows.xml; phase2/runtime-boundary.xml |
| Rust tests | 5 native units at prior checkpoint | 8 native units; formatting, strict Clippy, release build and dependency audit pass; 18 compiled native/Python negative contracts pass | Full Rust CI; local rust-*8db91bf.txt; native-contract-8db91bf.xml |
| Warm Turbo latency | No comparable baseline | p50 3.521 ms; p95 3.870 ms; n=100 | Focused phase2/benchmark-linux.json |
| Warm Fidelity latency | No comparable baseline | p50 29.042 ms; p95 33.832 ms; n=99 | Same raw operation receipt |
| Peak RAM | No comparable baseline | Operation-run sampled tree maximum 1,476,448,256 bytes; shared-pool sample maximum 2,465,923,072 bytes; neither is exact peak | Separate operation/shared-load receipts |
| Token reduction | Character estimates; worker cache misses caused downloads | Long article: 1,713 HTML / 1,304 Markdown / 1,635 complete JSON tokens; 4.55% complete reduction; small fixtures expand | extraction-quality-8db91bf.json; offline wheel check |
| Concurrent sessions | Repeated default 256-task/two-browser workload failed | Explicit 512-task pool: 12 measured snapshots in 2.618 s; 6 per session; 2 queue refusals; all workers reaped | ci-8db91bf/developer/shared-browser-load.json |
| Complete task load | No comparable baseline | 6 complete tasks / 2 independent workers / 8.593 s; all reaped | ci-8db91bf/agent/concurrency.json |
| Cleanup soak | Prior checkpoint: 739 successful cycles | Final-source mandatory soak pending | Full CI run 45880822782 |

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

The 21 non-browser skips comprise 18 compiled native contracts run separately and
3 platform-specific scenarios covered by required platform/browser jobs. Linux
runtime skips 2 Windows-only cases. Actual-model evaluation is NOT_RUN because
explicit credentials/model are unavailable; scripted success is not a model result.

## Confirmed failures and remediation evidence

- A repeated two-browser workload failed under the default aggregate task quota.
  Reservation admission and aggregate kernel-counter checks address the confirmed
  overcommit/error-reporting defects. The 512-task test configuration is explicit;
  no benchmark silently relaxes production defaults.
- Original Rust regressions exposed hidden-ancestor/descendant labels and unnamed
  credential URLs. The original failures and subsequent native passing tests are
  retained; broader native browser parity remains absent.
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

**Fixed but awaiting final broad verification:** latest-source full cleanup-soak
completion. Passing focused checks do not close that gate.

**Partially implemented:** broad site compatibility, general extraction recall,
production load fairness, complete telemetry aggregation and auxiliary-target
browser compatibility. Unbrokered worker/OOPIF requests fail closed.

**Not implemented:** native Rust live-browser parity, trusted physical events,
file transfer, WebSockets, service workers and HTTP Authorization.

**Not independently verified:** external security assessment, production load,
Chromium/kernel exploit resistance and independent evidence custody. The analyzer
quality gate remains open; no security findings were suppressed or waived.

Original draft [PR #1](https://github.com/k39139215-gif/aerobrowse/pull/1) targets
main. Stacked draft [PR #2](https://github.com/k39139215-gif/aerobrowse/pull/2)
contains this continuation. Neither is merged. No package release, production
approval or scope exclusion is authorized. `ACCEPTANCE.md` maps original scope.
