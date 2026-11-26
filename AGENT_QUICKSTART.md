# Agent quickstart

Supported browser environment: Linux x86_64, Python3.11+, installed Chromium,
Bubblewrap, permitted user/network/mount namespaces, and an operator-delegated
cgroupv2 subtree with cpu,memory,pids controllers. Browser operation fails closed
without these. Windows/macOS cannot run Fidelity. See SECURITY.md and the CI
browser job for disposable-runner provisioning; do not disable host policies broadly.

## Install and host configuration

```sh
uv sync --locked --extra dev
uv run playwright install --with-deps chromium
# Debian/Ubuntu: have the operator install bubblewrap.
export AEROBROWSE_CGROUP_ROOT=/sys/fs/cgroup/aerobrowse
export AEROBROWSE_SESSION_TASKS=256
```

The cgroup path must already exist, be empty except for its dedicated driver
subgroup, be writable by this service user, and have cpu,memory,pids delegated.
The running driver must sit in its own leaf, as scripts/ci-in-quota.sh does for
our CI-provisioned root. Set a deployment memory/CPU/PID budget externally too.
No command here grants delegation automatically. This setup is explicit because
root cgroup ownership and namespace policy are host-specific.

## Complete owned tasks

Run from the repository root in that configured environment:

```sh
uv run python -m examples.agent_sdk
uv run python -m examples.agent_mcp
```

Both examples start an ephemeral localhost application with fixture-only credentials,
log in through a real form, update a protected record across explicit tabs, reload,
log out, and assert the server record and expired session. They fail on unmet
assertions. The SDK example explicitly allows127.0.0.1/32 only for its owned app;
the MCP example launches an actual stdio server with the same operator allowlist.

## Agent tool contract

Discover browser_capabilities first. Navigate with force_js=true for interactive
work and reuse returned session_id. Responses include live tab_id,url,generation
and actions. Choose an action by its accessible name/type, then supply its exact
id and generation. A fill, click, tab switch, reload or new snapshot can replace
the generation; always use the newest map. STALE_ACTION_ID means request a new
snapshot and choose the target again. Never replay a side-effecting click merely
because document navigation interrupted extraction; first inspect the new page.

Tabs: browser_new_tab(url),browser_tabs,browser_switch_tab(tab_id),
browser_close_tab(tab_id), maximum8. History: browser_back,browser_forward,
browser_reload. Cookies and local storage are ephemeral and shared only among
tabs of the same owned session. No host profile import/export or Authorization
header forwarding. Popups, downloads, serviceworkers and WebSockets remain denied.
Keyboard keys are bounded synthetic DOM events, including Enter form submission;
sites requiring trusted physical input remain unsupported.

Normal SDK `from aerobrowse import AeroBrowser` and CLI use supervised workers.
The internal aerobrowse.engine.AeroBrowser, FidelityEngine and TurboEngine are
low-level trusted embedding APIs. They are not the documented agent entrypoint.

## Actual LLM evaluation

```sh
export OPENAI_API_KEY=...  # set securely; never put it in committed files
export AEROBROWSE_EVAL_MODEL=... # explicit model ID supported by chat/completions
uv run python -m benchmarks.agent.run
```

This connects the selected model to the actual MCP server and evaluates six
owned tasks. Missing credentials produce NOT_RUN, never a passing result.
See AGENT_EVALUATION.md for measurement scope and latest evidence.
