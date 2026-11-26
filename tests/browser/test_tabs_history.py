"""Real isolated Chromium tab ownership, bounded creation and history semantics."""

import sys
import uuid

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        sys.platform != "linux", reason="requires isolated Linux Chromium"
    ),
]


@pytest.fixture
def browser(site):
    with AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        assert browser.fetch(site + "/form")["success"]
        yield browser


def test_switch_and_close_never_reuse_inactive_generation(browser, site):
    original = browser.snapshot()
    action = next(a["id"] for a in original["actions"] if a["label"] == "Update")
    opened = browser.new_tab(site + "/form")
    assert opened["success"], opened
    assert opened["tab_id"] != original["tab_id"]
    assert (
        browser.click(action, original["generation"])["error"]["code"]
        == "STALE_ACTION_ID"
    )
    switched = browser.switch_tab(original["tab_id"])
    assert switched["success"]
    assert switched["generation"] != original["generation"]
    assert (
        browser.click(action, original["generation"])["error"]["code"]
        == "STALE_ACTION_ID"
    )
    closed = browser.close_tab(original["tab_id"])
    assert closed["success"] and closed["tab_id"] == opened["tab_id"]
    assert browser.switch_tab(original["tab_id"])["error"]["code"] == "TAB_NOT_FOUND"
    assert browser.switch_tab(uuid.uuid4().hex)["error"]["code"] == "TAB_NOT_FOUND"
    assert browser.close_tab(opened["tab_id"])["success"]
    assert browser.tabs()["tabs"] == []
    assert browser.snapshot()["error"]["code"] == "NO_ACTIVE_PAGE"
    assert browser.new_tab(site + "/form")["success"]


def test_tab_limit_and_closed_background_tab(browser, site):
    initial = browser.tabs()["active_tab_id"]
    for _ in range(7):
        assert browser.new_tab(site + "/form")["success"]
    assert len(browser.tabs()["tabs"]) == 8
    assert browser.new_tab(site + "/form")["error"]["code"] == "TAB_LIMIT"
    assert len(browser.tabs()["tabs"]) == 8
    assert browser.snapshot()["success"]  # Limit rejection preserves the active page.
    active = browser.tabs()["active_tab_id"]
    result = browser.close_tab(initial)
    assert result["success"] and result["tab_id"] == active
    assert browser.new_tab(site + "/form")["success"]


def test_native_history_returns_current_document_and_invalidates_actions(browser, site):
    original = browser.snapshot()
    action = next(a["id"] for a in original["actions"] if a["label"] == "Update")
    assert browser.fetch(site + "/other")["success"]
    back = browser.back()
    assert back["success"] and back["url"] == site + "/form", back
    assert back["generation"] != original["generation"]
    assert (
        browser.click(action, original["generation"])["error"]["code"]
        == "STALE_ACTION_ID"
    )
    forward = browser.forward()
    assert forward["success"] and forward["url"] == site + "/other", forward
    assert browser.forward()["error"]["code"] == "HISTORY_UNAVAILABLE"
    assert browser.current_url == site + "/other"


def test_unsafe_new_tab_does_not_replace_active_page(browser):
    original = browser.tabs()
    result = browser.new_tab("http://169.254.169.254/latest/meta-data/")
    assert result["error"]["code"] == "BLOCKED_DESTINATION"
    assert browser.tabs() == original


def test_same_document_history_is_not_mistaken_for_missing_entry(browser, site):
    page = browser._fidelity.current_page
    original = browser.snapshot()
    page.evaluate("history.pushState({}, '', '/form#section')")
    assert browser.snapshot()["url"] == site + "/form#section"
    back = browser.back()
    assert back["success"] and back["url"] == site + "/form", back
    forward = browser.forward()
    assert forward["success"] and forward["url"] == site + "/form#section", forward
    assert forward["generation"] != original["generation"]


def test_popups_remain_denied_with_multiple_tabs(browser, site):
    assert browser.new_tab(site + "/form")["success"]
    page = browser._fidelity.current_page
    page.evaluate("window.open('/form', '_blank')")
    page.wait_for_timeout(100)
    assert len(browser.tabs()["tabs"]) == 2
    assert len(browser._fidelity.current_context.pages) == 2


def test_turbo_tab_escalation_preserves_original_page(site):
    with AeroBrowser(
        default_mode="turbo", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        assert browser.fetch(site + "/form")["engine"] == "turbo"
        opened = browser.new_tab(site + "/other")
        assert opened["success"], opened
        tabs = browser.tabs()["tabs"]
        assert {tab["url"] for tab in tabs} == {site + "/form", site + "/other"}
        original = next(tab for tab in tabs if tab["url"].endswith("/form"))
        result = browser.switch_tab(original["tab_id"])
        assert result["engine"] == "fidelity"
        assert any(a["label"] == "Update" for a in result["actions"])
        navigated = browser.fetch(site + "/after-escalation")
        assert navigated["engine"] == "fidelity"
        assert navigated["tab_id"] == original["tab_id"]
        assert browser.back()["url"] == site + "/form"
