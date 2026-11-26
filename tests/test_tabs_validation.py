"""Portable validation never starts Chromium to reject untrusted tab requests."""

import pytest

from aerobrowse.engine import AeroBrowser


@pytest.mark.parametrize("operation", ["switch_tab", "close_tab"])
@pytest.mark.parametrize("tab_id", [None, "", "../other", "f" * 33, 12])
def test_malformed_tab_ids_fail_before_browser_startup(operation, tab_id):
    with AeroBrowser() as browser:
        result = getattr(browser, operation)(tab_id)
        assert result["error"]["code"] == "INVALID_TAB_ID"
        assert browser._fidelity.browser is None


def test_tabs_and_history_on_empty_session_do_not_start_browser():
    with AeroBrowser() as browser:
        assert browser.tabs()["tabs"] == []
        assert browser.back()["error"]["code"] == "NO_ACTIVE_PAGE"
        assert browser.forward()["error"]["code"] == "NO_ACTIVE_PAGE"


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "http://127.0.0.1", "http://169.254.169.254"]
)
def test_new_tab_policy_precedes_browser_startup(url):
    with AeroBrowser() as browser:
        result = browser.new_tab(url)
        assert result["error"]["code"] in {"BLOCKED_DESTINATION", "INVALID_URL"}
        assert browser._fidelity.browser is None
