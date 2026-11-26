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

## Browser boundary and platform capabilities

Linux Fidelity uses Bubblewrap user, network, mount, PID, IPC and UTS namespaces.
The network namespace has no usable external interface; no broker socket or proxy
port is exposed to the browser. The trusted host Playwright controller fulfills
intercepted HTTP(S) requests through SafeTransport, which pins validated numeric
socket addresses. Routing is a compatibility/mediation layer, not the final egress
boundary. Removing it still leaves the browser without host network access.
The browser receives only its exact installed distribution, read-only system
libraries/fonts/certificates, private tmpfs home/tmp/run, a private proc view and
minimal devices. Environment credentials and host home contents are not mounted.
Windows/macOS Fidelity return NETWORK_ISOLATION_UNAVAILABLE. There is no weaker
network fallback. Turbo remains available with the same public-destination policy.

WebSockets and service workers are disabled; popups are closed and downloads are
not accepted. Cookies/authorization are deliberately not forwarded by the broker;
authenticated browser sessions are not supported. Chromium currently starts with
Playwright's no-sandbox default inside the outer namespace/mount boundary. This
is an explicit limitation: network namespaces alone are neither a filesystem
sandbox nor a complete Chromium sandbox. The additional mount restrictions do
not establish protection against kernel/browser exploits. Runtime library mounts
are trusted system data and may include platform-wide configuration. Do not place
secrets in browser distribution or system runtime paths.

## Workers and kernel quotas

MCP sessions own killable child processes with correlated, bounded JSON IPC,
serialized actions, startup/request/lifetime deadlines, idle reaping and teardown.
Linux requires an operator-delegated cgroup v2 root in AEROBROWSE_CGROUP_ROOT for
Fidelity worker operations. Missing kernel controls return
RESOURCE_ISOLATION_UNAVAILABLE; only Turbo/snapshot remains available. Workers
enter the quota before browser startup. Delegation requires the controller process
inside the delegated hierarchy as well as correct subtree ownership. There is no
runtime sudo or automated permission change. Use disposable CI workers to test
setup; scripts/ci-in-quota.sh is CI-only provisioning, not a deployment installer.

Windows process workers use nested kill-on-close Job Objects for memory, CPU and
process caps; that does not enable Windows Fidelity. Defaults: 1 GiB/session,
4 GiB/pool, 64 processes/session, 256/pool, 100% one core/session and 200%/pool,
15-second worker startup, 1800-second session lifetime, 300-second idle lifetime,
45-second request deadline, 8 sessions and 16 outstanding calls/session. Python
ResourceLimits and SessionManager configure these limits. Separate browser versus
renderer process counts are not enforced; aggregate PID limits include threads
on Linux. Pools are per server instance; operators must cap multiple instances
with an enclosing deployment quota. CPU caps bound consumption, not wall latency. The default Linux 64-task/session
budget is intentionally conservative and can reject Chromium startup because
Linux counts threads too; supervised-browser acceptance/soak explicitly configures
256/session while retaining the 256 aggregate ceiling. This is not equivalent
to supporting eight concurrent browsers. Low budgets fail with WORKER_RESOURCE_LIMIT
and retire the session; choose and benchmark explicit deployment quotas.

Hard termination precedes slot release. Cleanup failures retain capacity accounting.
Linux uses cgroup.kill plus process-group termination and a guardian for parent-death
cleanup; Windows closes Job handles. Tests and evidence must verify each OS path.
The direct synchronous SDK retains namespace isolation, but is a trusted embedding
API and does not inherit MCP per-session quotas. This is an open production gate;
use the supervised runtime for bounded untrusted operations. The host controller,
Python worker, operator and cgroup delegation are trusted. The mount sandbox covers
Chromium descendants, not the host-side Python process or its dependency supply chain.

## Browser actions

Action IDs encode a random snapshot generation, retain exact node identities in
an isolated CDP execution world, and are never resolved by ordinal or selector.
Snapshot HTML and actions are captured in one renderer task. MutationObserver
records, including mutation/restoration, invalidate the generation. Validation
checks document, URL, identity, visibility, disabled state and fingerprint immediately
before DOM activation in the same task; focus handlers are revalidated. These are
synthetic DOM events, not trusted physical pointer/keyboard input. Sites requiring
isTrusted are unsupported. Enter/Escape keyboard DOM events have no guaranteed
native default action. No click target substitution occurs on stale state.

A site's own event handler may intentionally navigate, submit or change state.
Atomic target identity does not prove the business meaning of arbitrary JavaScript.
Page content and screenshots remain sensitive, untrusted outputs. No prompt-injection
immunity, secret classifier or external security certification is claimed.

## MCP transport and ownership

The supported CLI transport is UTF-8 newline stdio, limited to 128 KiB per frame
before SDK JSON decoding, depth 32, 8192 nodes, 2048 entries/container and 64 KiB
characters/string; JSON integer literals are capped at 128 digits regardless of
Python's interpreter-wide integer conversion setting. Partial frames have a 10-second total deadline, 64 requests
may be active and duplicate active request IDs terminate the connection. Replies
have an 8 MiB serialized cap and 10-second output-write deadline. SDKs still own
negotiation, cancellation and request/tool schemas. Unsupported batches are rejected.
See docs/ENGINE_PARITY.md for the full contract and in-process API limitations.

Stdio is local-process trust, not remote authentication. Transport-owner checks
and random session IDs isolate clients; one process-wide SDK session is not an
HTTP multi-tenant service. Logs omit URLs, submitted values, headers, cookies and
raw tracebacks. Public errors never echo request content or filesystem paths.
Screenshots and extracted content may naturally contain sensitive website data.

## Reporting

Report reproducible issues privately to k39139215@gmail.com, including revision,
platform, minimal reproduction and impact. Do not include credentials or customer
data. No response-time SLA is guaranteed. Older 0.2.0 deployments do not inherit
these branch changes merely by sharing a version number.

The packaged MCP command accepts the operator-only environment variable
`AEROBROWSE_SESSION_TASKS` as a canonical integer from 1 through 256. It changes
only the per-session task budget; aggregate CPU/memory/task ceilings stay at their
defaults. Invalid values fail at startup with `INVALID_RUNTIME_CONFIG`. Omitting
it retains 64. For the tested Chromium configuration, explicitly set it to 256;
this does not imply multiple concurrent browsers fit the aggregate pool. Tool
arguments cannot change this setting, and it never enables private-network access.

## Stateful browsing continuation

The public AeroBrowser SDK and CLI now use bounded supervised process workers,
with the same kernel quota requirement for browser actions as MCP. Internal engine
classes remain low-level trusted embedding APIs. In-memory Chromium cookies are
forwarded only from intercepted browser-selected request headers through the pinned
one-hop broker. Ordinary HTTP continues stripping Cookie/Authorization/Set-Cookie.
Chromium applies Set-Cookie domain/path/Secure/HttpOnly/SameSite/expiry policy;
there is no host-side credential jar. HTTP Authorization remains unsupported.
Tabs share the owned context; other sessions have independent ephemeral storage.
Explicit tabs are bounded at8 and popups remain denied. IDs never execute across
snapshot/tab/document generations. Operator development allowlists are explicit.
