import sys
import time

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(sys.platform != "linux", reason="isolated Chromium"),
]


def test_wait_discovers_late_control_without_executing_it(site):
    with AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        old = browser.fetch(site + "/form")
        page = browser._fidelity.current_page
        page.evaluate(
            "setTimeout(()=>{const b=document.createElement('button');b.textContent='Late action';b.disabled=true;b.onclick=()=>window.__clicked=true;document.body.append(b);setTimeout(()=>b.disabled=false,150)},100)"
        )
        ready = browser.wait(name="Late action", role="button", timeout_ms=3000)
        assert ready["success"], ready
        assert ready["generation"] != old["generation"]
        assert ready["wait"]["matched_action_ids"] == [
            next(a["id"] for a in ready["actions"] if a["label"] == "Late action")
        ]
        assert page.evaluate("window.__clicked || false") is False
        stale = browser.click(old["actions"][0]["id"], old["generation"])
        assert stale["error"]["code"] == "STALE_ACTION_ID"
        start = time.monotonic()
        absent = browser.wait(name="Never appears", timeout_ms=150)
        assert absent["error"]["code"] == "WAIT_TIMEOUT", absent
        assert 0.1 <= time.monotonic() - start < 3
        assert browser.snapshot()["success"]


def test_wait_cannot_succeed_on_another_document(site):
    with AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        browser.fetch(site + "/form")
        page = browser._fidelity.current_page
        page.evaluate("setTimeout(()=>location.href='/',100)")
        result = browser.wait(name="Never appears", timeout_ms=1000)
        assert result["error"]["code"] == "PAGE_NAVIGATED", result
