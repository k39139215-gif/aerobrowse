# Security model

This branch is a remediation candidate, not a production certification.
Track open gates in AUDIT.md and ENGINEERING_REPORT.md.

## URL and transport policy

Only HTTP(S) destinations are allowed. Credentials in URLs, control characters,
backslashes, scoped IPv6, private/non-public addresses and internal hostname
suffixes are rejected. IDNs are normalized with strict IDNA rules. All DNS answers
must be public unless explicitly allowlisted by the application. Mixed public and
private answers fail closed. Redirect targets are revalidated with a count limit.
Python connects a numeric socket to a validated address; Rust pins reqwest's
resolver to validated socket addresses. TLS retains hostname/certificate checks.
Neither uses environment proxies. Sensitive request headers and cookies are not
forwarded, and response cookies are removed.

Python allow_networks is an explicit development capability, not an MCP argument
or a production default. Rust currently offers no private-network allowlist.
IPv4-mapped and transition IPv6 paths are conservatively rejected. DNS checks
alone are not the security boundary: actual socket destinations are pinned.

## Chromium

Python Fidelity requires Linux user/network namespaces with only a down loopback
interface. Requests intercepted by Playwright are fulfilled through the safe host
transport. Namespace isolation is required even when routing is installed:
WebSockets and service workers are disabled, and bypass traffic has no network.
Popups are closed, downloads are not accepted, and browser contexts have no
persistent profile. Host networking is never an automatic fallback. Windows and
macOS fail closed. Native Rust Chromium is unavailable pending equivalent
isolation. Linux CI verifies basic namespace launch and live action fixtures; exhaustive
network-bypass testing is still required.

Network namespaces do not isolate the host filesystem or defend against a
Chromium sandbox escape. Deploy under an unprivileged account/container with a
read-only minimal filesystem, no credentials, dropped capabilities, restricted
CPU/RAM/PIDs and application-specific egress policy. Do not run with host secrets.

## Sessions and outputs

MCP sessions use random IDs and transport-owner checks. One worker serializes each
browser's state. Request timeouts and idle/capacity limits bound normal use.
Cancelled/timed-out sessions are retired and remain capacity-accounted through
cleanup. Per-session outstanding calls are capped at 16; incomplete cleanup returns
CLEANUP_PENDING. Hard worker
termination and independently verified process cleanup remain open requirements.

Action IDs encode snapshot generation and refer to retained live node handles.
There is no selector or ordinal fallback. Stale DOM/navigation causes a safe error.
Raw Playwright exceptions/paths and submitted field values are not serialized to
MCP clients. Logs omit URLs, headers, cookies and form values. Screenshots and page
content remain sensitive, untrusted outputs; treat page instructions as data.
No general secret detection or prompt-injection immunity is claimed.

## Reporting

Report reproducible issues privately to k39139215@gmail.com, including revision,
platform, minimal reproduction and impact. Do not include credentials or customer
data. No response-time SLA is guaranteed. Older 0.2.0 deployments do not inherit
these branch changes merely by sharing a version number.
