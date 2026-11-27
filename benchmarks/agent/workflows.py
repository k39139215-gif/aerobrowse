"""Scripted workflow driver; not an LLM evaluation."""

import asyncio
from typing import Any

from fastmcp import Client

from benchmarks.agent.run import transport


class MCPBrowser:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.client = Client(transport(), timeout=60)
        self.sid = None
        self.loop.run_until_complete(self.client.__aenter__())

    def call(self, tool_name: str, **arguments) -> dict[str, Any]:
        if self.sid and tool_name not in {"browser_capabilities"}:
            arguments["session_id"] = self.sid
        result = self.loop.run_until_complete(
            self.client.call_tool(tool_name, arguments, raise_on_error=False)
        )
        data = result.data
        if not isinstance(data, dict):
            raise TypeError("Tool response is not structured")
        self.sid = data.get("session_id", self.sid)
        return data

    def fetch(self, url: str, force_fidelity: bool = True):
        return self.call("browser_navigate", url=url, force_js=force_fidelity)

    def snapshot(self):
        return self.call("browser_snapshot")

    def fill(self, action_id, text, generation):
        return self.call(
            "browser_fill", action_id=action_id, value=text, generation=generation
        )

    def click(self, action_id, generation):
        return self.call("browser_click", action_id=action_id, generation=generation)

    def select(self, action_id, value, generation):
        return self.call(
            "browser_select", action_id=action_id, value=value, generation=generation
        )

    def check(self, action_id, checked, generation):
        return self.call(
            "browser_check", action_id=action_id, checked=checked, generation=generation
        )

    def new_tab(self, url):
        return self.call("browser_new_tab", url=url)

    def tabs(self):
        return self.call("browser_tabs")

    def switch_tab(self, tab_id):
        return self.call("browser_switch_tab", tab_id=tab_id)

    def close_tab(self, tab_id):
        return self.call("browser_close_tab", tab_id=tab_id)

    def back(self):
        return self.call("browser_back")

    def forward(self):
        return self.call("browser_forward")

    def reload(self):
        return self.call("browser_reload")

    def close(self):
        try:
            if self.sid:
                result = self.call("browser_close")
                assert result.get("success"), result
        finally:
            self.loop.run_until_complete(self.client.__aexit__(None, None, None))
            self.loop.close()


def good(result):
    assert result.get("success"), result
    return result


def action(browser, snapshot, label, method="click", value=None):
    snapshot = good(snapshot)
    candidate = next(item for item in snapshot["actions"] if item["label"] == label)
    if method == "click":
        result = browser.click(candidate["id"], snapshot["generation"])
    else:
        result = getattr(browser, method)(
            candidate["id"], value, snapshot["generation"]
        )
    # Native form activation can replace the document during extraction.
    # Refreshing is explicit and never retries the side-effecting operation.
    if result.get("error", {}).get("code") in {
        "PAGE_NAVIGATED",
        "ACTION_CONTEXT_FAILED",
        "SNAPSHOT_FAILED",
    }:
        result = browser.snapshot()
    return good(result)


def login_update_logout(browser, fixture):
    snapshot = good(browser.fetch(fixture.url + "/login", force_fidelity=True))
    snapshot = action(browser, snapshot, "Username", "fill", "agent")
    snapshot = action(browser, snapshot, "Password", "fill", "fixture-only")
    snapshot = action(browser, snapshot, "Sign in")
    assert "Protected record" in snapshot["markdown"], snapshot
    first_tab = snapshot["tab_id"]
    shared = good(browser.new_tab(fixture.url + "/record"))
    assert "Protected record" in shared["markdown"]
    snapshot = action(browser, shared, "Record name", "fill", "Agent updated")
    snapshot = action(browser, snapshot, "Save record")
    assert fixture.receipt_state()["record"] == "Agent updated"
    assert len(good(browser.tabs())["tabs"]) == 2
    snapshot = good(browser.switch_tab(first_tab))
    snapshot = good(browser.reload())
    assert "Agent updated" in snapshot["markdown"]
    snapshot = action(browser, snapshot, "Log out")
    assert "Sign in" in snapshot["markdown"]
    denied = good(browser.fetch(fixture.url + "/record"))
    assert "Login required" in denied["markdown"]
    assert fixture.verdict("authenticated_update", "")


def search_history_tabs(browser, fixture):
    snapshot = good(browser.fetch(fixture.url + "/search", force_fidelity=True))
    snapshot = action(browser, snapshot, "Search", "fill", "widget")
    snapshot = action(browser, snapshot, "Search catalog")
    snapshot = action(browser, snapshot, "Widget W42")
    assert "42 USD" in snapshot["markdown"]
    detail_tab = snapshot["tab_id"]
    snapshot = good(browser.back())
    assert "Widget W42" in snapshot["markdown"]
    snapshot = good(browser.forward())
    assert "42 USD" in snapshot["markdown"]
    docs = good(browser.new_tab(fixture.url + "/docs"))
    assert "17 days" in docs["markdown"]
    assert len(good(browser.tabs())["tabs"]) == 2
    snapshot = good(browser.switch_tab(detail_tab))
    assert "42 USD" in snapshot["markdown"]
    good(browser.close_tab(docs["tab_id"]))
    assert len(good(browser.tabs())["tabs"]) == 1
    assert fixture.verdict("search", "W42 costs 42 USD")


def wizard_and_stale(browser, fixture):
    snapshot = good(browser.fetch(fixture.url + "/wizard", force_fidelity=True))
    snapshot = action(browser, snapshot, "Plan", "select", "pro")
    snapshot = action(browser, snapshot, "Agree", "check", True)
    snapshot = action(browser, snapshot, "Next")
    assert "Confirm Pro plan" in snapshot["markdown"]
    snapshot = action(browser, snapshot, "Submit request")
    assert fixture.verdict("multistep_form", "")
    old = good(browser.fetch(fixture.url + "/dynamic"))
    stale_id = next(a["id"] for a in old["actions"] if a["label"] == "Confirm recovery")
    fresh = action(browser, old, "Change content")
    refused = browser.click(stale_id, old["generation"])
    assert refused["error"]["code"] == "STALE_ACTION_ID"
    assert fixture.receipt_state()["dynamic"] == 0
    fresh = good(browser.snapshot())
    action(browser, fresh, "Confirm recovery")
    assert fixture.verdict("stale_recovery", "")
