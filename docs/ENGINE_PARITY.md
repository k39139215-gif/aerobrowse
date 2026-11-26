# Engine capability contract

Decision: **Option B**. Python is the authoritative interactive browser runtime.
Rust supplies an independent, bounded read-only HTTP CLI and an MCP integration
command that starts the installed Python runtime. This is not native browser parity.
No unsupported Rust operation launches unrestricted Chromium or silently changes
security models. Deploying Rust MCP requires a compatible Python installation.

| Capability | Authoritative Python behavior | Native Rust behavior | Shared path / evidence |
|---|---|---|---|
| Turbo navigation | DNS-pinned HTTP with per-hop validation and limits | Independent reqwest transport with DNS pinning and limits | Separate implementations; security tests, Rust security unit tests |
| Fidelity navigation | Linux isolated Chromium; other platforms fail closed | NETWORK_ISOLATION_UNAVAILABLE | Rust MCP delegates to Python; Rust fidelity test |
| Snapshot generation | Static candidates or live generation-scoped DOM actions | Static extraction only | Tests extraction/actions; no native live actions |
| Click | Live Python action contract | UNSUPPORTED_OPERATION | Rust MCP uses Python tool |
| Fill | Bounded value, live identity/state validation | UNSUPPORTED_OPERATION | Rust MCP uses Python tool |
| Select | Live select by value | Not exposed natively | Rust MCP uses Python tool |
| Check/uncheck | Live checkbox boolean | Not exposed natively | Rust MCP uses Python tool |
| Scroll | Bounded distance | Not exposed natively | Rust MCP uses Python tool |
| Wait | Existing live action identity, bounded timeout | Not exposed natively | Rust MCP uses Python tool |
| Screenshot | Bounded PNG; sensitive output | Not exposed natively | Rust MCP uses Python tool |
| Session lifecycle | Owned isolated sessions with concurrency/admission policy | Native read-only fetch has no interactive session | Rust MCP uses same Python SessionManager |
| Isolation | Required Linux browser boundary, explicit unavailable errors | No native browser process is created | Python isolation tests and Rust refusal test |
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

The official pinned MCP/FastMCP SDK still implements initialization, method schemas,
request cancellation and response correlation. The adapter uses its low-level
stream API and FastMCP lifespan/context integration; pinned versions must be
revalidated before upgrades. No HTTP/SSE transport is exposed by the CLI. Stdio
client identity is local-process trust, not remote authentication.

## Release limitations

Authenticated browser sessions, tabs/history, WebSockets, service workers and
native live Rust extraction are outside the implemented native scope. This decision
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
cancellation with concurrent malformed input, eight separate owned sessions, and
MCP EOF cleanup of actual worker descendants. Required CI should execute these
alongside OS/browser tests; none is proof of Chromium network isolation.
