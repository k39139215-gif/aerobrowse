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
