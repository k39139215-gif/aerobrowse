# AeroBrowse

AeroBrowse combines bounded HTTP retrieval (Turbo) with an isolated Chromium
engine (Fidelity). This hardening branch is **not production-ready**: read
[AUDIT.md](AUDIT.md) and [ENGINEERING_REPORT.md](ENGINEERING_REPORT.md) for verified
results and open acceptance gates.

## Installation

Python 3.11 or newer is required. From this checkout:

```sh
python -m pip install -e ".[dev]"
python -m playwright install --with-deps chromium
```

For reproducible development, install uv and run `uv sync --locked --extra dev`.
`uv.lock` records exact Python dependency resolutions. Native Rust:

```sh
cargo build --locked --release --manifest-path rust_core/Cargo.toml
```

Turbo works on supported Python platforms. Fidelity requires Linux with Bubblewrap and permission to create user/network/mount
namespaces. Fidelity through either public SDK or MCP additionally requires delegated cgroup v2 memory/CPU/PID
controllers configured through `AEROBROWSE_CGROUP_ROOT`. Windows/macOS Fidelity returns
`NETWORK_ISOLATION_UNAVAILABLE`. Do not bypass this restriction. Chromium is
launched with no network interfaces and host-brokered, validated HTTP requests.
The public synchronous SDK, CLI and MCP runtime own supervised process workers.
Low-level engine classes remain trusted internal embedding APIs. See [SECURITY.md](SECURITY.md).
The CI browser job provisions namespace permissions on its disposable Ubuntu
runner; production hosts must provision their own restricted execution environment.

## Python API

```python
from aerobrowse import AeroBrowser

with AeroBrowser(default_mode="auto") as browser:
    page = browser.fetch("https://example.com")
    if not page["success"]:
        print(page["error"]["code"])
    else:
        print(page["markdown"])
        print(page["original_tokens"], page["extracted_tokens"], page["tokenizer"])
```

See [AGENT_QUICKSTART.md](AGENT_QUICKSTART.md) for complete SDK/MCP task examples
and [AGENT_EVALUATION.md](AGENT_EVALUATION.md) for actual-model evaluation.

Modes: `turbo` does not automatically escalate; `fidelity` requires Chromium; `auto` escalates
sparse application roots and explicit JavaScript requirements. A network-policy
error never triggers fallback. These are heuristics, not framework compatibility
guarantees. Static action candidates have `executable: false`.

`fetch(url, force_fidelity=False)`, `snapshot()`, `click(action_id, generation)`,
`fill(action_id, text, generation)`, `select(action_id, value, generation)`,
`perform("check", action_id, bool, generation)`,
`perform("press", action_id, key, generation)`, `scroll(x=0, y=600)`,
`wait(action_id, generation, timeout_ms=5000)`, `screenshot()`, and `close()`
are implemented in Python. Screenshots return bounded PNG bytes and can contain
sensitive page content. Numeric IDs and arbitrary CSS selectors are not executable.

When an action follows a Turbo fetch, AeroBrowse navigates Fidelity to the tracked
URL, re-extracts the live DOM, and returns `STALE_ACTION_ID` with `synchronized:
true` and a new action map. Select the intended action from that response and
retry using its `id` and `generation`. No action is performed during that handoff.
Every new snapshot invalidates earlier IDs. DOM changes also invalidate IDs.

Snapshots contain title, markdown, actions, table cell/header metadata, extraction
quality indicators and token/character measurements. `reduction_pct` now aliases
**token** reduction, not the old character metric. `character_reduction_pct` is
separate. Default tokenizer: `tiktoken/cl100k_base`; alternative encodings:
`SemanticPruner(tokenizer="o200k_base")` or `p50k_base`. Metrics record library
version. Tokenizer failure is an explicit `TOKENIZER_ERROR`, never an estimate.
No fixed token saving, RAM footprint or latency is promised.

## MCP setup and sessions

```json
{
  "mcpServers": {
    "aerobrowse": {"command": "python", "args": ["-m", "aerobrowse.mcp_server"]}
  }
}
```

Use the Python interpreter from the installed environment. Stdio stdout contains
protocol messages only. The official FastMCP implementation handles protocol
initialization, JSON-RPC, validation and cancellation.

`browser_navigate(url, force_js=false, session_id=null)` creates an owned session
when no ID is supplied. Reuse its returned session ID in subsequent calls. IDs
are bound to the MCP transport session, not just possession of a string. Browser
state is never shared between owners. A dedicated worker serializes each
session's operations and preserves Playwright thread affinity.

| Tool | Required arguments beyond session_id |
|---|---|
| browser_navigate | url; optional force_js |
| browser_snapshot | none |
| browser_click | action_id, generation |
| browser_fill | action_id, generation, value |
| browser_select | action_id, generation, value |
| browser_check | action_id, generation, checked |
| browser_press | action_id, generation, key |
| browser_scroll | optional x, y |
| browser_wait | action_id/generation or exact name; optional role, timeout_ms |
| browser_screenshot | none |
| browser_capabilities | none; no session required |
| browser_tabs | none |
| browser_new_tab | url |
| browser_switch_tab / browser_close_tab | tab_id |
| browser_back / browser_forward / browser_reload | none |
| browser_close | none |

Tool responses use `success`, structured `error.code`/`error.message` on failure,
and page snapshots on successful actions. Request operations include request and
session IDs. Do not assume HTTP success from a returned dictionary: inspect
`success`. Session defaults: configured maximum8 (subject to aggregate budget reservation),300-second idle lifetime,
45-second request timeout. Idle cleanup runs every 10 seconds. Each session admits at most 16 outstanding calls. Cancellation
retires the session and queues cleanup. Retiring resources still count against
capacity; incomplete cleanup returns CLEANUP_PENDING. Owned process workers are
forcibly retired on timeout, cancellation or crash; a replacement session loses
its ephemeral browser login. See AGENT_QUICKSTART.md for recovery.

## Configuration and network restrictions

Configuration is explicit Python code; no environment flag silently permits
private networks:

```python
from aerobrowse.security import NetworkPolicy, Limits
from aerobrowse import AeroBrowser

# Local development only; scope to the smallest required address range.
policy = NetworkPolicy(allow_networks=("127.0.0.1/32",),
                       limits=Limits(timeout=10, response_bytes=2 * 1024 * 1024))
browser = AeroBrowser(policy=policy)
```

Default limits: URL 8192 characters; request body 1 MiB; response/HTML 4 MiB;
network deadline 20 seconds (standalone TurboEngine defaults to 12);
5 redirects; parser 100,000 nodes/128 depth. All DNS answers must pass policy.
Numeric sockets pin the actual connection destination; TLS SNI and certificate
verification use the normalized hostname. Proxies from the environment,
HTTP Authorization and compressed responses are not used. Ordinary HTTP strips
credentials; the Chromium-only pinned broker preserves browser-selected scoped
cookies for ephemeral form authentication. Legitimate
non-UTF-8 content and servers requiring compression may need additional support.
Resource blocking is opt-in: `FidelityEngine(block_heavy_resources=True)`.

## Native Rust scope

Native Turbo validates resolved IPs and pins reqwest destinations. It provides
real `tiktoken-rs/0.12.1:cl100k_base` measurements and static, non-executable
action candidates. Native Chromium and click/fill fail explicitly until an
OS-level boundary and equivalent live-action semantics exist. `aerobrowse mcp`
requires the installed Python SDK and launches its maintained MCP server.
The binary is no longer advertised as a standalone interactive browser.

## Known limitations and troubleshooting

- Ephemeral form/cookie sessions, explicit tabs and history are tested on owned
  fixtures. Host profile import/export, HTTP Authorization, WebSockets, service
  workers, popups/downloads and trusted physical input remain unsupported.
- Linux CI verifies namespace operation and basic handoff/live actions/staleness.
  Exhaustive iframe egress and crash-recovery coverage remain open.
- Native extraction is less complete than Python for tables and ARIA metadata.
- Static extraction cannot establish computed CSS visibility or information recall.
- Active pages and screenshots may themselves contain confidential information.
  Form values are omitted, but arbitrary page prose is not a DLP boundary.
- `BLOCKED_DESTINATION`: check the URL/policy; use narrow explicit allowlists only
  for trusted development services.
- `STALE_ACTION_ID`: request a new snapshot and choose the action again.
- `NETWORK_ISOLATION_UNAVAILABLE`: use a Linux host that permits user/network
  namespaces. No unsafe launch switch is provided.
- `TOKENIZER_ERROR`: encoding initialization may need its initial data download;
  configure the tokenizer cache for offline deployments before serving traffic.

## Verification

```sh
python -m pytest
python -m ruff check aerobrowse tests
python -m ruff format --check aerobrowse tests
python -m mypy aerobrowse --ignore-missing-imports --check-untyped-defs
cargo fmt --manifest-path rust_core/Cargo.toml --check
cargo clippy --manifest-path rust_core/Cargo.toml --all-targets --all-features -- -D warnings
cargo test --locked --manifest-path rust_core/Cargo.toml
cargo build --locked --release --manifest-path rust_core/Cargo.toml
```

Linux browser tests are marked `browser`; deterministic fixtures are used rather
than third-party sites. See [BENCHMARKS.md](BENCHMARKS.md), [SECURITY.md](SECURITY.md)
and [CHANGELOG.md](CHANGELOG.md). MIT license.

## Phase-two runtime contract

[PHASE2_AUDIT.md](PHASE2_AUDIT.md) tracks release blockers.
[COMPATIBILITY.md](COMPATIBILITY.md) describes real pinned framework fixtures and
synthetic DOM action semantics. [docs/ENGINE_PARITY.md](docs/ENGINE_PARITY.md)
selects Python as authoritative browser runtime; native Rust HTTP has a narrower
contract and Rust MCP integrates Python. [SECURITY_REVIEW_PACKAGE.md](SECURITY_REVIEW_PACKAGE.md)
contains external assessment preparation, trust assumptions and reproduction.

The supported MCP CLI uses bounded UTF-8 newline stdio before SDK parsing.
Remote HTTP/SSE is not exposed. Local process trust is required; there is no remote
client authentication. Worker controls and default quotas are in SECURITY.md.
Do not expose trusted in-process FastMCP/SDK APIs as an unbounded multi-tenant service.
Atomic browser activation targets an exact retained DOM node using synthetic DOM
events; flows that require trusted physical user input are unsupported.

For the tested Linux MCP Chromium configuration, the operator can explicitly set
`AEROBROWSE_SESSION_TASKS=256` alongside the delegated `AEROBROWSE_CGROUP_ROOT`.
The default remains 64 tasks per session; the aggregate ceiling remains 256.
Invalid task budgets fail startup. This is a resource setting, not permission to
reach private networks; see SECURITY.md for deployment limits.

## Stateful agent operations

Authenticated cookie sessions work through Chromium-scoped cookies and the pinned
broker. Cookies/storage are ephemeral per owned context; tabs share that context.
Use `new_tab(url)`, `tabs()`, `switch_tab(tab_id)`, `close_tab(tab_id)`, `back()`,
`forward()`, `reload()` and `capabilities()` on the public SDK; MCP has corresponding
browser_ tools. Maximum8 explicit tabs; page-created popups remain denied.
After Fidelity activation, navigation remains in that context to preserve auth.
`serialized_output` measures canonical JSON including action metadata, separately
from Markdown-only extracted_tokens. Recalculate full MCP framing cost in clients.

Operator-only `AEROBROWSE_ALLOW_NETWORKS` is an optional comma-separated strict
CIDR allowlist for MCP development fixtures. Empty by default. Never enable broad
private networks for production; this is not an untrusted tool argument.

## Dynamic controls and operator metrics

`browser.wait(name="Save", role="button", timeout_ms=5000)` waits for an enabled,
visible control by exact accessible name and optional role. The MCP equivalent is
`browser_wait(session_id=..., name="Save", role="button", timeout_ms=5000)`.
It returns fresh action IDs in `wait.matched_action_ids`; it executes nothing.
Multiple matches are returned explicitly. Existing ID/generation waits validate
identity immediately; a missing discovery target returns `WAIT_TIMEOUT`, while a
changed document returns `PAGE_NAVIGATED`. No stale ID is remapped.

The public SDK and trusted `SessionManager` expose `metrics_snapshot()` and
`metrics_prometheus()` for operator-controlled collection. Request logs include
request/session IDs, a bounded operation label, engine, duration and outcome;
URLs, form values and credentials are omitted. Metrics aggregate navigation/action
success, fallbacks, extraction failures, crashes, timeouts, latency histograms,
active sessions and sampled worker-tree RSS. These local methods are intentionally
not MCP tools or an unauthenticated HTTP endpoint. Memory samples include shared
mappings and exclude processes that exited before sampling; they are not exact
peak memory. See BENCHMARKS.md for the shared aggregate-pool workload harness.

Session admission reserves each configured per-session task and memory budget from
the aggregate pool. `SESSION_RESOURCE_LIMIT` means another session cannot be
reserved even if `max_sessions` is higher. For example, a256-task session inside
a256-task pool permits one owned session. Trusted embedding can explicitly choose
`ResourceLimits(processes=256, global_processes=512)` for two sessions after
capacity testing; this does not alter packaged MCP defaults. Kernel exhaustion
returns `WORKER_RESOURCE_LIMIT` and retires the affected worker. Pools with an
observed aggregate exhaustion event require recreation; limits are never relaxed.

Synthetic keyboard editing supports Backspace/Delete, Home/End, Left/Right,
Control+A/Meta+A, single printable Unicode characters and textarea Enter.
Cancellable keydown/beforeinput events are honored; target replacement during
preparation is rejected. Trusted hardware events, clipboard, modifier shortcuts,
Tab default focus movement and full contenteditable editing remain unsupported.
