# Original acceptance map

Historical status below applies to implementation `7f5c859`; verified full CI head `582b74c` has the
same implementation. NOT_PRODUCTION_READY. Earlier green receipts do not certify
later source. Evidence and limitations are in ENGINEERING_REPORT.md.

| Original requirement group | Status | Implementation / evidence | Remaining requirement |
|---|---|---|---|
| Audit entire repository before edits | Completed record | AUDIT.md and baseline inventory; baseline commit | No independent audit certification |
| Dedicated branch, main protected, PR | Implemented | Original draft PR #1 against main; follow-up draft #2 against original branch | Neither merged; final approval not requested |
| Public-only HTTP and redirects | Implemented and regression-tested | security.py / Rust security.rs; DNS pinning, all-address validation, per-hop bounds | Broader native integration parity not demonstrated |
| Chromium equivalent network boundary | Implemented for supported Linux scope | isolation.py / host broker; namespaces, real TCP/UDP canaries with routing removed | Exhaustive browser utility/egress assessment; inner Chromium sandbox; Windows/macOS fail closed |
| Input/output safety | Implemented bounded controls | bytes/depth/body/response/deadline/JSON integer limits; safe errors and redaction tests | Host dependency/controller trusted; comprehensive fuzzing incomplete |
| Hybrid page state and handoff | Implemented and browser-tested | engine.py; live navigation/re-extraction then stale-ID response | Static snapshot is intentionally not executable; no automatic intent remapping |
| Selection/fallback | Implemented heuristics | semantic quality/dynamic indicators and explicit Fidelity option | Broad site classification accuracy not measured |
| Browser lifecycle | Implemented supervised contract | process workers, kernel quotas, parentdeath, browser/renderer timeout cleanup | Renderer recovery deadline-based; public SDK now supervised in continuation |
| Deterministic action IDs | Implemented declared DOM contract | isolated-world exact retained node and generation, mutation epoch, no fallback | Synthetic DOM events; trusted physical interaction and file inputs unsupported |
| Click/fill/select/check/scroll/wait | Implemented declared scope | actual Linux/browser/framework tests | Wait targets existing action ID; no arbitrary selector, broad workflow support unproven |
| Keyboard input | Partial | Enter/Escape synthetic DOM events | General physical keyboard input unsupported |
| MCP tools/sessions/concurrency | Implemented stdio scope | official SDK + predecode bounds, owned workers, locks, cancellation, idle/session caps | No remote transport/authentication; broad browser load/fairness testing absent |
| Semantic extraction | Partial | bounded structure, tables/header data, labels, iframe notices and quality flags | Broad multilingual/RTL/deep malformed and important-content recall coverage incomplete |
| Token measurement | Implemented | real versioned tokenizer counts; character metric separate; multiple encodings | Full JSON count added in continuation; production-site recall/savings absent |
| Reproducible performance harness | Implemented exploratory | raw operation timing distributions, CPU/RSS, declared Turbo SDK load | No comparable before baseline; browser/MCP concurrency/queue/fairness and exact peaks absent |
| Rust hardening | Implemented narrower architecture | safe bounded native HTTP; strict fmt/clippy/test/release/audit; Python MCP integration | Full native live browser/action parity not implemented; exclusion unapproved |
| Security regression tests | Implemented declared attack families | real network canaries, DNS/redirect/input/session/injection/quotas | External exploit-chain assessment not performed |
| Functional compatibility tests | Partial | real pinned plain HTML/React/Vue/Next/Angular flows | Controlled auth/tabs/history implemented in continuation; infinite/lazy content and broader form/error states remain incomplete |
| Concurrency/resource tests | Partial | owned concurrent sessions, locks, actual kernel denial/crash/cleanup | Broad browser throughput, fairness/starvation and production exhaustion not measured |
| CI/dependencies/builds | Implemented engineering pipeline | Python 3.11 through 3.14 matrix; Rust strict checks; audits, locks, browser job, builds | Sonar two private-tmpfs findings open; final current-source full CI/soak green |
| Observability | Partial | request/session/engine/operation/duration/outcome/error JSON logs and bounded counters | Full requested metrics export/aggregation and peak-memory service telemetry incomplete |
| Documentation | Implemented current-scope documentation | README, SECURITY, CHANGELOG, AUDIT, BENCHMARKS, report and review package | Remaining limitations are release blockers, not approved exclusions |
| Independent verification | Not performed | Reproduction package prepared, revision/hash-bound receipts | No external assessment or independent custody claim |

The benchmark table reports measured values and missing baselines explicitly.
No speedup, guaranteed RAM, universal compatibility or 90% token saving is claimed.
No original requirement is waived by this map. Unsupported capabilities fail closed
where safe completion is absent; a draft PR does not establish production readiness.

## Agent usability continuation acceptance

Latest implementation/benchmark checkpoint: `0530488`. Full CI completed SUCCESS in
`45864277407`; all jobs,including its mandatory cleanup soak,passed. Historical green
receipts do not certify changed code. Focused delegated Linux run `45860943458`
passed 14 workflow/auth/storage/error-document tests and 38 runtime tests, with
2 Windows-only skips. Downloaded XML receipts are authoritative.

| Usability requirement | State | Evidence / remaining limit |
|---|---|---|
| Login/protected update/logout | Demonstrated scripted SDK and actual MCP | Real form and fixture record/session state |
| Auth sharing across owned tabs | Demonstrated | New tab reads protected record,update,reload,logout |
| Session cookie/origin/path isolation | Demonstrated controlled scope | Multiple cookies,HttpOnly,path/host,foreign domain,credentials modes |
| Search/detail/back/forward and tabs | Demonstrated | SDK/MCP complete workflow; opaque explicit IDs,max8 |
| Multistep select/checkbox/validation/submission | Demonstrated | Required validation and server submission assertions |
| Stale recovery | Demonstrated scripted | Old ID rejected; no submission before fresh generation |
| Browser crash recovery | Demonstrated controlled failures | Kill/reap/replacement regressions retained |
| Normal SDK resource supervision | Implemented and locally/Linux tested | Real worker,timeouts,lifetime,kill/reap; enclosing multi-instance quota required |
| LLM-driven agent evaluation | Runnable,NOT_RUN | Missing OPENAI_API_KEY,AEROBROWSE_EVAL_MODEL |
| Browser concurrency measurement | Controlled SDK task measurement complete | 6 tasks, 2 workers, 9.152 seconds at0530488; no saturation/fairness claim |
| Native Rust parity | Not implemented | Independent read-only HTTP scope retained |

General public-site task completion, trusted physical events,file uploads,downloads,
WebSockets,service workers,HTTP Authorization,persistent host profiles,remote MCP,
production saturation/fairness and independent security assessment remain unsupported
or unverified. No merge/release authorized or performed.

Final full CI run45864277407 is SUCCESS at head0530488/tested merge1f59be05.
Browser68 passes/0 skips;kernel38 passes/2 Windows-only skips;all8 Python jobs
206 passes/21 explained skips;strict Rust/dependency gates pass. Soak739 cycles
in1801.544 seconds,zero observed orphan processes/permanent slots. All raw rows
and81 tested implementation Git blobs verified. See ENGINEERING_REPORT.md for
final before/after table,limits and remaining NOT_PRODUCTION_READY scope.
