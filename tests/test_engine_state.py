from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy


def test_turbo_snapshot_does_not_create_browser(site):
    browser = AeroBrowser(
        default_mode="turbo", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    )
    try:
        first = browser.fetch(site)
        assert first["success"]
        assert browser.current_url == first["url"]
        assert browser.active_engine == "turbo"
        snap = browser.snapshot()
        assert snap["markdown"] == first["markdown"]
        assert browser._fidelity is None
    finally:
        browser.close()


def test_invalid_network_request_never_falls_back():
    browser = AeroBrowser()
    try:
        result = browser.fetch("http://127.0.0.1")
        assert result["error"]["code"] == "BLOCKED_DESTINATION"
        assert browser._fidelity is None
    finally:
        browser.close()


def test_action_without_navigation_fails():
    browser = AeroBrowser()
    try:
        assert browser.click("1")["error"]["code"] == "NO_ACTIVE_PAGE"
        assert browser._fidelity is None
    finally:
        browser.close()
