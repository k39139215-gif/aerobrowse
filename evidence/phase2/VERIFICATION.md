# Phase-two evidence index

Receipts are raw observations and do not constitute independent custody or assessment.
Source and environment are stated in each report; PR CI may use a synthetic merge
checkout. Failed runs remain failed and cancelled runs remain cancelled.

- baseline-python.xml:67 passed/4skips original phase-two baseline.
- python-final-reviewed.xml:146 passed/2skips,64 deselections, Windows/Python3.12;
  source throughfe159f9 (IPC fix included), before positional quota regression.
- protocol-final-reviewed.xml:15 real-pipe protocol/shape/deadline checks.
- mcp-session-recheck.xml:16 protocol/session subprocess checks.
- native-contract.xml:18 shared blocked-destination/native browser refusal checks,
  built real Rust executable; Windows functional contract, not Chromium isolation.
- ci-0caf7e7/ci-browser.xml:41 required real Linux Chromium tests,zero skips.
- ci-0caf7e7/phase2/ci-runtime-kernel.xml:17 passed/2 Windows-only skips.
- ci-0caf7e7/phase2/benchmark-linux.json:100 action samples,99 warm browser samples,
  raw percentiles/Turbo load/token metadata. No paired before/after baseline.
- ci-0caf7e7/phase2/soak-linux.jsonl:failed initial supervised navigation,zero completed
  iterations. The lack of a summary is intentional; this is not30minute evidence.
- runtime-6d2e932-failed/runtime-boundary.xml:renderer trigger selected a spare process;
  other kernel, lifecycle, main-process crash and Linux parentdeath checks passed.
- runtime-64369e1-failed/runtime-boundary.xml:actual renderer kill caused bounded
  TIMEOUT, contrary to test's too-narrow error list; no success falsely returned.
- runtime-c963127/runtime-boundary.xml:25 passed/2 Windows-only skips. Real main
  browser/renderer recovery, Linux parentdeath, quota denial, partial IPC and fd cleanup.
- source-6d2e932.json:tracked source SHA256 inventory before final renderer test edits.
- receipt-manifest.json:SHA256 of downloaded receipts, for integrity tracking only.

JUnit counts include platform skips in the tests attribute. Do not sum baseline,
focused and repeated suites as if they were unique tests. No test that was skipped
or deselected is a passing test. Windows cannot establish Linux namespace boundary.
Network canaries use explicit owned loopback allowances; live-customer credentials,
URLs or data are absent. The default quota failure and synthetic DOM semantics are
covered in ENGINEERING_REPORT.md and SECURITY.md.

- ci-f1ce086:green full CIrun45833263200/sourcef1ce086,merge1710acaf4f4f0e877a53653f525939b688143b51.
 43required browser passes/zero skips;19runtime/kernel passes/2Windows-only skips.
 soak1800.735seconds,931successful raw iterations;zero orphan/slot observations.
 Single synthetic sequential fixture,256session/aggregate task cap; controller RSS
 observations exclude browser peak. This does not transfer automatically to later source.

- runtime-929cc25/runtime-boundary.xml: source `929cc25`, run `45840796649`,
  37 Linux passes and 2 Windows-only skips, including actual MCP stdio initialize/
  navigate/Fidelity-fill/close with the explicit operator task budget. Eleven
  configuration cases reject noncanonical or over-aggregate values and retain defaults.
