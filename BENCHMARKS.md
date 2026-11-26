# Benchmark methodology

Run `python -m benchmarks.controlled` from the repository root for an owned local
HTTP fixture, five cold/warm samples per engine, two concurrent Turbo sessions,
10 ms sampled process-tree RSS and eight synthetic extraction categories.
`python -m aerobrowse.benchmark https://example.com --output evidence/live.json`
measures an explicitly selected public URL. `--allow-network 127.0.0.1/32` is an
explicit local-development capability; it is never enabled implicitly.

Receipts record revision, UTC time, Python/platform/package versions, limits,
engine, outcomes/errors, latency, actual tokenizer counts, quality indicators,
CPU seconds, wall seconds and RSS samples. Inspect failures; do not average
failed browser launches into successful navigation latency. Cold navigation is
browser/engine initialization, not Python interpreter startup. Warm Turbo does
not imply connection pooling: sockets are closed after each bounded operation.
RSS is a sampled high-water mark, not a guaranteed absolute peak. The in-process
local HTTP fixture and tokenizers contribute to measurements. Thread-based load
measures SDK Turbo sessions, not a production multi-tenant MCP service.

`evidence/token-fixtures.json` covers documentation, e-commerce, news, dashboard,
search, long article, nested table and form markup. These are synthetic cases,
not measured production-site compatibility. Negative token reduction is valid
when semantic annotations increase small documents. Tokenizer counts include
Markdown output only; action/table metadata adds further tokens when serialized.
Full tool-payload savings and content-recall grading are not yet measured.

Default encoding: cl100k_base, library/version recorded per receipt. Python also
supports o200k_base and p50k_base. Rust uses tiktoken-rs 0.12.1/cl100k_base.
Character reduction is never labelled token savings.

No defensible before latency/RAM/token/concurrency baseline was recorded. Previous
scripts estimated tokens by character division and had hard-coded local binaries.
Their results cannot establish performance improvements. Historical JSON is kept
for provenance, not accepted as current evidence. Legacy benchmark entrypoints
now direct users to this harness rather than producing misleading numbers.

Current limitations: no verified Linux Fidelity timing, click/fill timing,
interpreter cold start, exact peak RAM or browser memory-leak profile. No speed,
memory or fixed token-saving improvement is claimed. Correctness/security gates
remain open; performance optimization has not been attempted.

Clean-source local receipt at c09500a: cold Turbo 492.197 ms, four warm samples
median 16.604 ms, sampled process-tree RSS 77.324 MiB, 10/10 successful requests
with two concurrent workers in 0.1091 s. These are tiny synthetic fixture timings
and include local server/tokenizer costs; they are not production SLOs or speedups.

| Synthetic fixture | HTML tokens | Markdown tokens | Reduction |
|---|---:|---:|---:|
| Documentation | 41 | 26 | 36.59% |
| E-commerce | 48 | 27 | 43.75% |
| News | 33 | 17 | 48.48% |
| Dashboard | 44 | 11 | 75.00% |
| Search | 43 | 18 | 58.14% |
| Long article | 1913 | 1504 | 21.38% |
| Complex table | 74 | 19 | 74.32% |
| Form | 50 | 12 | 76.00% |

These counts exclude structured actions/tables; lower output counts do not prove
content completeness. Quality indicators and missing-content flags are in receipts.

CLI receipt paths must be under ./evidence, with no traversal or symlink path
components. Existing files are not overwritten; choose a fresh filename. This
reduces accidental overwrite risk from agent-supplied command arguments. A
malicious local filesystem actor racing directory replacement is outside the
benchmark CLI trust boundary.

## Phase-two measurement harness

`python -m benchmarks.phase2.run --samples 100 --browser --output evidence/phase2/benchmark-linux.json`
uses an owned tiny local fixture. It separates new Python interpreter imports,
first browser navigation, reused-context navigation, Turbo, snapshot, fill, select,
wait, click, scroll, screenshot and deliberate handoff synchronization. Raw rows
retain success/error codes and tokenizer/quality metadata when present. The
nearest-rank median/p90/p95/p99 use the operation's actual sample count; one cold
browser observation is not a statistically supported cold-start distribution.
At least 100 observations are needed even for a coarse p99. Process-tree RSS is
sampled at 20 ms, while CPU currently covers the parent only. Per-session browser
CPU/RSS, browser/MCP load and queue/starvation measurements remain open.

Concurrency 1/2/4/8/16 measures Turbo SDK thread workers, not browser or MCP
session throughput. No controlled before/after comparison currently establishes
an improvement. A small dirty-tree Windows smoke receipt only verifies harness
operation; it is not release performance evidence.

`python -m benchmarks.phase2.soak --seconds 1800 --output evidence/phase2/soak-linux.json`
requires real delegated kernel controls. It repeatedly creates a supervised browser
worker, navigates, fills, clicks and closes it, verifying descendants and session
slots are released on every iteration. Exclusive JSONL output preserves completed
iterations if the run fails; the summary is created only after successful completion.
The CI job runs this on a disposable Linux host. RSS observations alone do not
prove unlimited-duration boundedness; the kernel quotas remain the hard boundary.

Raw receipts contain their source commit, OS, Python, configuration, failures and
limitations. Reruns need a new output filename; do not overwrite historical receipts.
The original phase-one token-fixture report remains historical and is not an
information-recall benchmark for the new real framework suite.

Recorded exploratory Linux run 45831559623 used source 0caf7e7 via PR merge checkout
99ebb5d15a1263f22405c4144ba164f2170e8817, Linux x86_64/Python 3.12.16, one tiny
controlled fixture. It observed Turbo warm median 2.55 ms (100 samples), Fidelity
warm 23.04 ms (99), snapshot 5.94 ms, click 7.03 ms, fill 7.57 ms, select 6.91 ms,
scroll 7.44 ms, wait 6.25 ms and screenshot 21.17 ms (100 each). The single cold
browser observation was 560.42 ms; cold Python import median was 177.56 ms (30).
Sampled aggregate tree RSS reached 1,478,348,800 bytes; it includes the harness,
fixture and browser. Turbo HTML 118 tokens -> extracted Markdown 45, 61.86%,
tiktoken 0.14.0/cl100k_base; serialized action metadata is excluded. There is no
important-content recall denominator for this tiny receipt.

This run reported dirty=true because test/build evidence existed. It is raw,
exploratory revision-bound evidence, not a clean controlled before/after production
comparison. The supervised-browser soak failed immediately with navigation failure;
a focused regression subsequently confirmed pids.events.max=66 and oom_kill=0
under the default 64-task session quota. New soak runs explicitly use 256/session
and the unchanged 256-task aggregate ceiling; failed runs remain evidence of the
failure and cannot substantiate stability or a speed improvement.

Subsequent green run45833263200/sourcef1ce086 completed1800.735seconds and931
sequential browser worker/action/cleanup cycles,zero observed orphans/permanent
slots. Configuration:256tasks/session and256aggregate,max_sessions2; this is not
concurrent browser load. Parent controller RSS44,367,872->45,510,656bytes after
cleanup,max45,510,656. The same run's benchmark (different CI host) observed Turbo
warm2.63ms median/p95 2.96ms,n100;Fidelity warm24.67ms/p95 26.84ms,n99; sampled
aggregate tree RSS1,453,219,840bytes. No before/after speedup claim. Receipts:
evidence/phase2/ci-f1ce086/phase2/soak-linux.{json,jsonl},benchmark-linux.json.
