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

Turbo works on supported Python platforms. Fidelity requires Linux with `unshare`
and permission to create user/network namespaces. Windows/macOS Fidelity returns
`NETWORK_ISOLATION_UNAVAILABLE`. Do not bypass this restriction. Chromium is
launched with no network interfaces and host-brokered, validated HTTP requests.
This process boundary has not yet been verified in this branch's Linux CI.

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

Modes: `turbo` never escalates; `fidelity` requires Chromium; `auto` escalates
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
| browser_wait | action_id, generation; optional timeout_ms |
| browser_screenshot | none |
| browser_close | none |

Tool responses use `success`, structured `error.code`/`error.message` on failure,
and page snapshots on successful actions. Request operations include request and
session IDs. Do not assume HTTP success from a returned dictionary: inspect
`success`. Session defaults: 8 active sessions, 300-second idle lifetime,
45-second request timeout. Idle cleanup runs every 10 seconds. Cancellation
retires the session and queues cleanup. A stuck native worker cannot yet be
forcibly terminated; see known limitations.

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
verification use the normalized hostname. Proxies from the environment, cookies,
authorization headers and compressed responses are not used. Legitimate
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

- Authenticated browser sessions, cookie persistence, WebSockets, service workers,
  popups/downloads, multiple tabs and back/forward are not supported yet.
- Browser namespace operation, iframe request isolation and crash recovery require
  Linux integration evidence. Local Windows refusal does not prove Linux safety.
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
