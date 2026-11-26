"""Adversarial renderer tasks; no validator mocks or ordinal resolution."""

import sys

import pytest

from aerobrowse import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        sys.platform != "linux", reason="requires isolated Linux Chromium"
    ),
]


@pytest.fixture
def live(site):
    browser = AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    )
    try:
        result = browser.fetch(site + "/form", force_fidelity=True)
        assert result["success"], result
        yield browser, browser._fidelity.current_page
    finally:
        browser.close()


def target(snapshot, name):
    return next(a["id"] for a in snapshot["actions"] if a["label"] == name)


@pytest.mark.parametrize(
    "mutation",
    [
        "el.remove()",
        "el.outerHTML='<button onclick=window.wrong=true>Replacement</button>'",
        "el.parentNode.prepend(el)",
        "el.hidden=true",
        "el.disabled=true",
        "const before=el.textContent;el.textContent='Transient';el.textContent=before",
        "el.closest('body').innerHTML='<button onclick=window.wrong=true>Update</button>'",
    ],
)
def test_mutations_never_click_replacement(live, mutation):
    browser, page = live
    for _ in range(10):
        page.evaluate(
            "document.body.innerHTML='<button onclick=window.original=true>Update</button>'"
        )
        snapshot = browser.snapshot()
        page.evaluate(
            "() => {const el=document.querySelector('button');" + mutation + "}"
        )
        result = browser.click(target(snapshot, "Update"), snapshot["generation"])
        assert not result["success"]
        assert result["error"]["code"] in {
            "STALE_ACTION_ID",
            "ELEMENT_NOT_VISIBLE",
            "ELEMENT_DISABLED",
        }
        assert page.evaluate("window.wrong===true || window.original===true") is False


def test_duplicate_names_keep_exact_identity(live):
    browser, page = live
    page.evaluate(
        "document.body.innerHTML='<button onclick=window.first=true>Duplicate</button><button onclick=window.second=true>Duplicate</button>'"
    )
    snapshot = browser.snapshot()
    ids = [a["id"] for a in snapshot["actions"] if a["label"] == "Duplicate"]
    assert len(ids) == 2
    result = browser.click(ids[1], snapshot["generation"])
    assert result["success"]
    assert page.evaluate("window.second===true && window.first!==true")


def test_focus_preparation_mutation_is_rejected(live):
    browser, page = live
    page.evaluate(
        "document.body.innerHTML='<label>Name<input></label>';document.querySelector('input').onfocus=function(){this.outerHTML='<input id=replacement>'}"
    )
    snapshot = browser.snapshot()
    result = browser.fill(target(snapshot, "Name"), "sensitive", snapshot["generation"])
    assert result["error"]["code"] == "STALE_ACTION_ID"
    assert page.evaluate("document.querySelector('#replacement').value") == ""


def test_hostile_main_world_cannot_replace_isolated_primitives(live):
    browser, page = live
    page.evaluate(
        "HTMLElement.prototype.click=function(){window.wrong=true}; window.MutationObserver=class {observe(){} takeRecords(){return []} disconnect(){}}"
    )
    snapshot = browser.snapshot()
    result = browser.click(target(snapshot, "Update"), snapshot["generation"])
    assert result["success"]
    assert page.evaluate("window.wrong===true") is False
    assert "Changed by JavaScript" in result["markdown"]


def test_navigation_invalidates_world(live, site):
    browser, page = live
    snapshot = browser.snapshot()
    page.goto(site + "/other")
    result = browser.click(target(snapshot, "Update"), snapshot["generation"])
    assert result["error"]["code"] == "PAGE_NAVIGATED"


def test_cross_engine_generation_rejected(live, site):
    browser, _ = live
    snapshot = browser.snapshot()
    other = AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    )
    try:
        fresh = other.fetch(site + "/form", force_fidelity=True)
        assert fresh["success"]
        result = other.click(target(snapshot, "Update"), snapshot["generation"])
        assert result["error"]["code"] == "STALE_ACTION_ID"
    finally:
        other.close()
