# Controlled framework compatibility

Exact fixture versions are pinned in tests/compatibility/package-lock.json:
React 19.3.1, Vue 3.5.46, Next.js 16.4.6 and Angular 22.3.0. They are real framework
applications, bundled locally with esbuild or compiled with Next.js. Tests never
fetch CDN runtime scripts or third-party websites.

Build with Node 24: `cd tests/compatibility`, `npm ci --ignore-scripts`,
`npm run build`, `npm exec -- next build nextjs`. Then run the isolated Linux suite:
`python -m pytest tests/compatibility tests/browser -v`.

The fixture tests check meaningful content presence, exact controlled input and
select state, live counter mutation, dialog visibility, disabled/hidden controls,
client-side history route recognition and old-generation rejection. Next.js uses
its actual production server and prerendered HTML/hydration. React/Vue/Angular
fixtures render client-side. These controlled scenarios do not establish general
framework or version compatibility. Infinite scrolling, comprehensive validation,
large-page recall and error-state coverage remain open.

Action identity contract: an isolated CDP execution world retains node identities
in a private Map. A MutationObserver tracks mutation-and-restoration. Snapshot
HTML, action metadata and generation are captured in one renderer task. Each
activation validates generation, document, URL, node connection, visibility,
disabled state and metadata, then activates the retained node in the same task.
Focus handlers are an explicit reentrancy point and are followed by revalidation.
No selector or ordinal fallback exists.

DOM activation uses synthetic DOM events (`input_mode=synthetic_dom`). Trusted
physical pointer/keyboard events, drag/drop, file inputs and actions gated on
`event.isTrusted` are outside this contract. Press currently supports Enter/Escape
DOM keyboard events only and returns UNSUPPORTED_CAPABILITY for other keys.
Click event handlers can intentionally redirect or mutate the document; no agent
can prove intent against arbitrary code running inside an activation handler.
The guarantee is about selecting and activating the exact validated node, not
preventing a site's own handler side effects. Concurrent requests remain serialized
by the owning session; cross-session generation IDs fail closed.

Local Windows cannot establish the production network/filesystem isolation
boundary. Any standalone action-context smoke test is functional evidence only,
never network-isolation evidence. Linux CI results must be recorded separately.
