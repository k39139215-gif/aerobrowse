# Remaining gaps implementation plan

**Goal:** Continue original production remediation with safe authenticated browser state,
bounded tabs/history, stronger extraction coverage, and measured concurrent browser work.
**Architecture:** Retain Python authoritative isolated runtime and DNS-pinned broker.
Chromium cookie storage stays context-local and memory-only; no credential export.
Tabs use opaque IDs within the owned context, with fresh action generations on activation.
**Tech Stack:** Python 3.11+, Playwright, pinned MCP SDK, Linux Bubblewrap/cgroups, Rust.
**Spec:** Original user production remediation and ACCEPTANCE.md.

## Constraints and review focus
- No private-network default, unconfined Chromium, weakened quota, mock success, secret log.
- Preserve default SafeTransport header stripping; credential forwarding is explicit browser-only.
- Test cross-origin redirects, duplicate Set-Cookie, expired cookies and session separation.
- Test tab limits, foreign IDs, closed tabs, generation staleness, history navigation failure.
- Preserve red baseline tests and bind Linux/browser receipts to actual new revision.

## Task 1: Authenticated browser transport
- Add explicit private browser transport API preserving repeated Set-Cookie fields while public API strips credentials.
- Test real HTTP login cookie/redirect/logout and origin isolation; cookie contents never serialized.
- Integrate browser route fulfillment and Chromium-scoped request cookie headers.

## Task 2: Tabs and history
- Add bounded context-owned opaque tab IDs, list/open/switch/close and back/forward APIs.
- Extend engine, worker allowlist and MCP schemas; invalidate all old active action IDs.
- Test real browser navigation/history, owner/foreign/closed tab rejection and cleanup.

## Task 3: Extraction acceptance coverage
- Exercise malformed Unicode/RTL/nested lists/tables/depth/empty documents.
- Fix observed extraction loss and report explicit quality indicators.
- Include serialized action metadata in separately identified full-output token measurement.

## Task 4: Integration and verification
- Run local static/full nonbrowser tests, Linux integration and security regressions.
- Measure concurrent owned browser lifecycle via reproducible harness without speedup claims.
- Review actual source diff; commit coherent tasks; update acceptance/status/docs and existing draft PR.
- Original scope remains active; native Rust parity, platform support and external review require honest status.
