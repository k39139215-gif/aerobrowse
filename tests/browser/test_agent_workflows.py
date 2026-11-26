"""Server-asserted complete workflows through public SDK and actual MCP."""

import sys

import pytest

from aerobrowse import AeroBrowser
from aerobrowse.runtime import ResourceLimits
from aerobrowse.security import NetworkPolicy
from benchmarks.agent.fixture import AgentFixture
from benchmarks.agent.workflows import (
    MCPBrowser,
    login_update_logout,
    search_history_tabs,
    wizard_and_stale,
)

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        sys.platform != "linux",
        reason="requires isolated Linux Chromium and delegated cgroups",
    ),
]


@pytest.mark.parametrize("interface", ["sdk", "mcp"])
@pytest.mark.parametrize(
    "workflow", [login_update_logout, search_history_tabs, wizard_and_stale]
)
def test_complete_owned_task(interface, workflow):
    with AgentFixture() as fixture:
        if interface == "sdk":
            browser = AeroBrowser(
                default_mode="fidelity",
                policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
                resource_limits=ResourceLimits(processes=256),
            )
        else:
            browser = MCPBrowser()
        try:
            workflow(browser, fixture)
        finally:
            browser.close()


def test_concurrent_public_sessions_complete_without_state_crossing():
    from concurrent.futures import ThreadPoolExecutor

    import psutil

    processes = []

    def run(index):
        with (
            AgentFixture() as fixture,
            AeroBrowser(
                default_mode="fidelity",
                policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
                resource_limits=ResourceLimits(processes=256),
            ) as browser,
        ):
            search_history_tabs(browser, fixture)
            processes.append(browser._worker.pid)
            return browser.session_id, fixture.receipt_state()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))
    assert len({sid for sid, _ in results}) == 2
    assert all(
        state["details"] > 0 and state["record"] == "Original" for _, state in results
    )
    assert not any(psutil.pid_exists(pid) for pid in processes)


def test_enter_submits_search_and_native_required_validation():
    from benchmarks.agent.workflows import action, good

    with (
        AgentFixture() as fixture,
        AeroBrowser(
            default_mode="fidelity",
            policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
            resource_limits=ResourceLimits(processes=256),
        ) as browser,
    ):
        snapshot = good(browser.fetch(fixture.url + "/search"))
        snapshot = action(browser, snapshot, "Search", "fill", "widget")
        field = next(a for a in snapshot["actions"] if a["label"] == "Search")
        submitted = browser.press(field["id"], "Enter", snapshot["generation"])
        if not submitted.get("success"):
            submitted = browser.snapshot()
        assert "Widget W42" in good(submitted)["markdown"]
        snapshot = good(browser.fetch(fixture.url + "/wizard"))
        action(browser, snapshot, "Next")
        assert fixture.receipt_state()["submitted"] is False
        assert "Plan request" in good(browser.snapshot())["markdown"]


def test_error_document_never_reports_success(site):
    from aerobrowse.engine import AeroBrowser as InternalBrowser

    with InternalBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        assert browser.fetch(site + "/form")["success"]
        page = browser._fidelity.current_page
        for session in browser._fidelity._brokers.values():
            session.detach()
        try:
            page.goto("http://127.0.0.1:1", timeout=1000)
        except __import__("playwright.sync_api", fromlist=["Error"]).Error:
            pass
        assert not browser.snapshot()["success"]
