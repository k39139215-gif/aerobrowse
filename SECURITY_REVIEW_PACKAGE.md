# External security review package

Status: NOT_PRODUCTION_READY. This package supports an external assessment; it is
not an independent penetration test, certification or release authorization.

## Scope and trust boundaries

The trust flow is local MCP client -> bounded newline transport -> official SDK ->
owner-checked session manager -> correlated process IPC -> worker -> Chromium CDP.
The worker's SafeTransport is the host-side network broker. Chromium is untrusted,
web content is hostile, and client arguments are untrusted. Operator, kernel,
Python runtime/dependencies, Playwright controller, system libraries/browser image
and cgroup setup are trusted. Rust native HTTP is an independent implementation;
Rust MCP launches the authoritative Python browser runtime (Option B).

## Browser and broker architecture

Bubblewrap isolates Chromium and descendants in user/network/mount/PID/IPC/UTS
namespaces. No host broker port is reachable. CDP pipes cross the boundary; the
host controller services intercepted HTTP(S) requests. SafeTransport validates
all DNS answers, pins numeric destinations, preserves TLS verification and
revalidates each redirect. Private destinations require explicit operator CIDRs.
Standalone HTTP filters credentials and response cookies. For supported browser
requests, Chromium-selected Cookie and Set-Cookie fields pass only through the
pinned per-hop broker; Chromium applies credential scope. Form/cookie authentication
is supported in ephemeral owned contexts; HTTP Authorization, WebSockets, service
workers and popups remain unsupported.

Private home/tmp/run/proc and minimal device mounts plus read-only runtime mounts
reduce filesystem exposure. Namespace creation alone is not proof: the regression
suite observes descendant namespace IDs, interfaces/mounts and canary contents.
A network namespace is not automatically a filesystem sandbox or a full Chromium
sandbox. Chromium's inner sandbox is not enabled/proven; kernel/Chromium sandbox
escapes, installed system-library secrets and malicious dependencies remain threats.
The trusted host-side broker can access allowlisted internal services; internal CIDR
configuration is an explicit security capability, never a client tool parameter.

## Lifecycle and resources

Per-session process workers have startup/operation/lifetime limits, serialized
commands, hard termination, reaping and retained capacity on failed cleanup.
Linux cgroups enforce memory/swap/CPU/PIDs; Windows nested jobs enforce worker
memory/CPU/process limits, while Fidelity is unavailable there. An independent
Linux guardian observes controller pipe death and kills worker group/cgroup and
removes temporary files. Review launch-before-attach ordering, parent-death races,
reaper lifetime, cancellation/reentrancy, cgroup migration and cleanup errors.
Limits/configuration are in SECURITY.md. Public SDK workers enforce quotas;
session admission reserves configured task/memory budgets against its aggregate
pool. Shared-pool exhaustion counters are checked. Separate renderer/browser caps
and cross-instance global deployment quotas remain release gaps.

## Protocol/session model

Only stdio is exposed. Client identity derives from the local SDK transport owner;
there is no remote authentication or HTTP multi-tenant security claim. Requests
require explicit opaque session IDs; ownership checks precede operations. Each
session has independent page state and lock. Frame byte limits precede decoding;
shape/ID/method limits precede SDK dispatch. Active ID collisions close the transport.
Review stalled input/output, malformed Unicode/nesting, SDK-version dependency,
cancellation, output amplification and disconnect cleanup. Raw exceptions are not
serialized to clients and submitted form values are not logged.

## Action contract

Isolated-world Map stores exact nodes; document/generation/URL/mutation epoch and
state are validated in the same renderer task as synthetic DOM activation. No
ordinal/selector fallback. Reentrant focus handlers trigger another validation.
Review restoration mutations, duplicate labels, disconnected handles, CSS/event
semantics and response snapshot coherence. isTrusted-dependent sites are unsupported.
Business semantics inside arbitrary website event handlers are outside target-identity
proof. Page text is data, not trusted agent instructions.

## Reproduction and evidence

Use uv sync --locked --extra dev --no-build --no-install-project. Unit/protocol:
python -m pytest -m 'not browser and not native_contract'. Install Chromium with
python -m playwright install --with-deps chromium. On disposable Ubuntu with
Bubblewrap and delegated cgroup controls, follow .github/workflows/ci.yml exactly.
Build pinned frameworks using the commands in COMPATIBILITY.md. Required Linux
suite: pytest -m browser and tests/runtime under scripts/ci-in-quota.sh. The
30-minute soak is python -m benchmarks.phase2.soak --seconds 1800. Do not interpret
platform skips or absent delegation as a security pass. Do not run adversarial
fixtures with real credentials/customer data.

Evidence records and exact tested source revisions are indexed by PHASE2_AUDIT.md,
ENGINEERING_REPORT.md and evidence/phase2. Earlier phase-one receipts are historical.
Raw benchmark outputs use exclusive file creation and controlled local fixtures.

Tested attack families: loopback/private/reserved/IDNA/alternate-IP rejection,
mixed DNS and pinning, redirect internal target, browser fetch/XHR/resources/
iframes/WebSockets/workers/service-workers/popups/download attempts and UDP WebRTC
canary, direct fetch with routing removed, host filesystem/environment canaries,
mutation/replacement/restoration actions, malformed/oversized MCP, real worker
crash/cancellation, kernel allocation/fork denial where run.

Not exhaustively tested: every browser utility/network mechanism, external exploit
chains, hostile kernel/system libraries, comprehensive real-world authenticated
sites, all framework scenarios/versions, indefinite leaks, high-load browser/MCP
session fairness, per-renderer caps, cross-instance quota control or formal isolation.
Unfinished evidence and P0/P1 scope exclusions are explicit release blockers.


## Developer continuation evidence

Implementation8db91bf: name/role discovery waits,synthetic keyboard editing with
beforeinput identity revalidation,bounded semantic metadata,static Rust disclosure
regressions,offline checked vocabularies and safe benchmark receipt output. Review
exact admission reservation and aggregate PID/OOM error semantics,partial browser
support,and local metric scope. Latest focused Linux run45880812905 is SUCCESS;
full current-source CI/soak remains pending. The latest analyzer report has46 open
findings,including2 private-tmpfs path findings,not only two total findings.
Evidence: evidence/developer/source-8db91bf.json,verification-8db91bf.json and
ci-8db91bf/. No independent assessment or release authorization is implied.
