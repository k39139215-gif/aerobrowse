"""Deterministic browser fixtures. Never use third-party sites in CI."""

import sys

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = pytest.mark.browser


@pytest.fixture
def browser():
    if sys.platform != "linux":
        pytest.skip("OS-isolated Chromium requires Linux; refusal tested separately")
    value = AeroBrowser(policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)))
    yield value
    value.close()


def action(snapshot, name):
    return next(a["id"] for a in snapshot["actions"] if a["label"] == name)


def test_handoff_and_live_actions(browser, site):
    first = browser.fetch(site + "/form")
    assert first["success"] and first["engine"] == "turbo"
    synced = browser.click("1")
    assert synced["error"]["code"] == "STALE_ACTION_ID"
    assert synced["synchronized"] and synced["engine"] == "fidelity"
    old = action(synced, "Name")
    filled = browser.fill(old, '\\";window.injected=true;//', synced["generation"])
    assert filled["success"]
    assert "window.injected" not in str(filled)
    stale = browser.click(old, synced["generation"])
    assert stale["error"]["code"] == "STALE_ACTION_ID"
    selected = browser.select(action(filled, "Choice"), "b", filled["generation"])
    assert selected["success"]
    checked = browser.perform(
        "check", action(selected, "Agree"), True, selected["generation"]
    )
    assert checked["success"]
    clicked = browser.click(action(checked, "Update"), checked["generation"])
    assert clicked["success"] and "Changed by JavaScript" in clicked["markdown"]
    assert browser._fidelity.current_page.evaluate("window.injected === true") is False
    assert browser.scroll(y=20)["success"]


def test_dynamic_staleness_and_cleanup(browser, site):
    snap = browser.fetch(site + "/form", force_fidelity=True)
    assert snap["success"]
    page = browser._fidelity.current_page
    page.evaluate(
        "document.querySelector('button').outerHTML='<button>Replacement</button>'"
    )
    result = browser.click(action(snap, "Update"), snap["generation"])
    assert result["error"]["code"] == "STALE_ACTION_ID"
    browser.close()
    assert browser._fidelity is None


def test_host_private_network_is_blocked_without_allowlist(site):
    browser = AeroBrowser(default_mode="fidelity")
    try:
        result = browser.fetch(site)
        assert result["error"]["code"] == "BLOCKED_DESTINATION"
    finally:
        browser.close()


def test_live_links_redact_sensitive_components(browser, site):
    snap = browser.fetch(site + "/form", force_fidelity=True)
    assert snap["success"]
    browser._fidelity.current_page.evaluate(
        "document.body.insertAdjacentHTML('beforeend','<a href=\"https://user:secret@example.com/path?token=SECRET#SECRET\">Safe label</a>')"
    )
    snap = browser.snapshot()
    link = next(a for a in snap["actions"] if a["label"] == "Safe label")
    assert link["href"] == "https://example.com/path"
    assert "SECRET" not in str(snap) and "user:secret" not in str(snap)


def test_mutate_then_restore_invalidates_action(browser, site):
    snap = browser.fetch(site + "/form", force_fidelity=True)
    assert snap["success"]
    browser._fidelity.current_page.evaluate(
        "const b=document.querySelector('button');const old=b.textContent;b.textContent='Temporary';b.textContent=old"
    )
    result = browser.click(action(snap, "Update"), snap["generation"])
    assert result["error"]["code"] == "STALE_ACTION_ID"
