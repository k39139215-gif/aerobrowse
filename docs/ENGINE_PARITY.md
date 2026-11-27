# Engine capability contract

Decision: **Option B**. Python is the authoritative interactive browser runtime.
Rust supplies bounded HTTP retrieval and an independent native Linux CDP browser session. The MCP integration command remains Python-authoritative for protocol/session parity.
No unsupported Rust operation launches unrestricted Chromium or silently changes
security models. Deploying Rust MCP requires a compatible Python installation.

| Capability | Authoritative Python behavior | Native Rust behavior | Shared path / evidence |
|---|---|---|---|
| Turbo navigation | DNS-pinned HTTP with per-hop validation and limits | Independent reqwest transport with DNS pinning and limits | Separate implementations; security tests, Rust security unit tests |
| Fidelity navigation | Linux isolated Chromium; other platforms fail closed | Linux isolated Chromium over CDP pipe; other platforms fail closed | Native Linux CDP integration and namespace suite |
| Snapshot generation | Static candidates or live generation-scoped DOM actions | Live generation-scoped DOM actions over the shared runtime | Shared-runtime identity regression and native Linux browser suite |
| Click | Live Python action contract | Live native action contract | Native Linux CDP integration |
| Fill | Bounded value, live identity/state validation | Bounded native value, live identity/state validation | Native Linux CDP integration |
| Select | Live select by value | Live native select by value | Native Linux CDP integration |
| Check/uncheck | Live checkbox boolean | Live native checkbox boolean | Native Linux CDP integration |
| Scroll | Bounded distance | Bounded native distance | Native Linux CDP integration |
| Wait | Existing live action identity, bounded timeout | Exact accessible-name/role wait with fresh IDs | Native Linux CDP integration |
| Screenshot | Bounded PNG; sensitive output | Bounded PNG | Native Linux CDP integration |
| Session lifecycle | Owned isolated sessions with concurrency/admission policy | Owned native CDP session with cgroup guardian | Rust MCP uses same Python SessionManager |
| Isolation | Required Linux browser boundary, explicit unavailable errors | Bubblewrap network/mount/PID boundary and cgroup guardian | Python isolation tests and Rust refusal test |
| Network policy | Public destinations default; explicit internal CIDR opt-in | Public destinations default; native internal allowlists not exposed | Equivalence limited to shared rejection vectors |
| Error behavior | Structured codes, no raw internal exception strings | JSON envelope; native CLI payload shape differs | tests/mcp/test_engine_contract.py (requires built native binary) |
| Timeouts | Bounded network/action/session/transport deadlines | Bounded native HTTP; MCP Python deadlines | No claim native timeouts identical |
| Cancellation | MCP SDK cancellation plus owned runtime cleanup | Rust MCP process kill-on-drop; Python handles tool cancellation | Protocol/runtime tests; native fetch cancellation not API-exposed |

## MCP transport boundary

The stdio entrypoints `python -m aerobrowse.mcp_server`, `aerobrowse mcp`, and Rust
`mcp` use a bounded UTF-8 newline transport before SDK deserialization. A frame is
at most 131072 bytes, JSON depth at most 32, each string at most 65536 characters,
each container at most 2048 entries and the full JSON tree at most 8192 nodes.
Partial frames have a 10-second absolute deadline from the first byte; idle
connections may remain idle. At most 64 requests are active. Output is bounded to
8 MiB per message after SDK serialization; it is not a pre-allocation memory quota.
A blocked stdout pipe has a 10-second absolute write deadline and closes the
transport; a single serialized raw-descriptor write avoids waiting for a blocked
buffered thread during shutdown.
A single daemon raw-descriptor reader uses a bounded one-chunk queue; at most two
4 KiB chunks can exist alongside the current frame. Timeout/EOF/duplicate IDs
close the stream group and run session cleanup without waiting on a blocked input
read. The adapter is a process-lifetime stdio transport, not a reusable socket API.

Malformed frames receive fixed JSON-RPC parse/invalid-request errors without
reflecting input. Unknown requests receive method-not-found; unknown notifications
are ignored. MCP batches are rejected for the supported current protocol. Active
duplicate IDs close the transport, avoiding overwritten SDK responders or ambiguous
replies. IDs may be reused after the corresponding response is written. An oversized
unterminated frame closes the transport after a fixed error. Limits do not apply to
in-process FastMCP Client connections; those are trusted embedding APIs, not stdio.
The Rust `native-session` command has a separate bounded JSON-line operation set;
it does not expose the MCP protocol. Native history, tabs and reload remain inside
one owned browser context. Explicit `close` terminates Chromium; EOF cleans the
session through a guardian that kills the delegated cgroup and removes its directory.

The official pinned MCP/FastMCP SDK still implements initialization, method schemas,
request cancellation and response correlation. The adapter uses its low-level
stream API and FastMCP lifespan/context integration; pinned versions must be
revalidated before upgrades. No HTTP/SSE transport is exposed by the CLI. Stdio
client identity is local-process trust, not remote authentication.

## Release limitations

Authenticated browser sessions, WebSockets, service workers and trusted physical input remain outside the implemented scope. Native tabs/history, waits, screenshots and DOM actions are implemented on Linux. This decision
does not waive any unapproved production-scope exclusion. Browser action semantics,
OS controls and their evidence are described separately in the Phase 2 report.

## Recorded focused verification

On the local Windows/Python 3.12 toolchain, the real compiled native CLI and Python
passed all 18 shared destination-rejection/native-browser-refusal contracts in
3.05 seconds; receipt: evidence/phase2/native-contract.xml. This proves only these
negative input vectors, not DNS/redirect integration parity. The native executable
was built from the current working source with the existing Rust toolchain.

The stdio suite uses actual subprocess pipes, not a mocked SDK transport. Covered
cases include strict Unicode/JSON frames, invalid protocol envelopes, shape caps,
trickled partial frames, duplicate active IDs, pipelined request correlation,
cancellation with concurrent malformed input, owned session correlation with
aggregate-budget admission backpressure, and
MCP EOF cleanup of actual worker descendants. Required CI should execute these
alongside OS/browser tests; none is proof of Chromium network isolation.


Developer continuation: Python waits discover exact accessible names/optional
roles with fresh IDs; keyboard editing uses synthetic DOM input/caret events.
Static native extraction now filters hidden ancestors/descendants,uses explicit
accessible labels and sanitized relative links. Rust MCP remains Python-authoritative for protocol/session parity; native Linux live-browser/action parity is covered independently. Native Linux browser suite `46006841440` passed 10 cases with zero skips; its scope does not establish Windows/macOS native support or external assessment.
Python tokenizers are bundled/checksummed/offline; Rust uses its linked tokenizer.
