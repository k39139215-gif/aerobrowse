"""Actual Chromium/host canary tests; no mocked validator is used."""

import urllib.request

import pytest
from conftest import save_receipt

pytestmark = pytest.mark.browser

ATTACKS = {
    "fetch": "u => fetch(u).catch(()=>null)",
    "xhr": "u => new Promise(r=>{const x=new XMLHttpRequest();x.open('GET',u);x.onload=x.onerror=()=>r();x.send()})",
    "image": "u => new Promise(r=>{let e=new Image();e.onload=e.onerror=()=>r();e.src=u;document.body.append(e)})",
    "css": "u => {let e=document.createElement('link');e.rel='stylesheet';e.href=u;document.head.append(e)}",
    "iframe": "u => {let e=document.createElement('iframe');e.src=u;document.body.append(e)}",
    "websocket": "u => {let w=new WebSocket(u.replace('http:','ws:'));w.onerror=()=>{};setTimeout(()=>w.close(),100)}",
    "worker": "u => {const source='fetch('+JSON.stringify(u)+').catch(()=>null)';new Worker(URL.createObjectURL(new Blob([source],{type:'text/javascript'})))}",
    "serviceworker": "u => navigator.serviceWorker.register(u).catch(()=>null)",
    "popup": "u => window.open(u,'_blank')",
    "download": "u => {let a=document.createElement('a');a.href=u;a.download='attack';document.body.append(a);a.click()}",
    "webrtc": "u => {let p=new RTCPeerConnection({iceServers:[{urls:'stun:'+new URL(u).hostname+':3478'}]});p.createDataChannel('x');p.createOffer().then(o=>p.setLocalDescription(o));setTimeout(()=>p.close(),200)}",
}


@pytest.mark.parametrize("mechanism", list(ATTACKS))
def test_prohibited_browser_egress_hits_no_canary(attack_lab, mechanism):
    lab = attack_lab
    # Positive control proves canary is reachable from the broker's host.
    with urllib.request.urlopen(
        lab["forbidden"] + "/positive-control", timeout=2
    ) as response:
        assert response.status == 200
    lab["received"].clear()
    snapshot = lab["browser"].fetch(lab["allowed"])
    assert snapshot["success"], snapshot
    page = lab["browser"]._fidelity.current_page
    page.evaluate(ATTACKS[mechanism], lab["forbidden"] + "/" + mechanism)
    page.wait_for_timeout(350)
    assert lab["received"] == []
    assert len(page.context.pages) == 1
    save_receipt(
        "egress-" + mechanism,
        {
            "mechanism": mechanism,
            "canary_received": lab["received"],
            "positive_control": True,
        },
    )


def test_direct_egress_without_playwright_route_is_blocked(attack_lab):
    lab = attack_lab
    assert lab["browser"].fetch(lab["allowed"])["success"]
    context = lab["browser"]._fidelity.current_context
    context.unroute("**/*")
    result = context.pages[0].evaluate(
        "u=>fetch(u).then(()=>false).catch(()=>true)", lab["forbidden"] + "/direct"
    )
    assert result is True
    assert lab["received"] == []
    save_receipt(
        "route-bypass", {"fetch_failed": result, "canary_received": lab["received"]}
    )


def test_navigation_redirect_cannot_reach_canary(attack_lab):
    lab = attack_lab
    result = lab["browser"].fetch(lab["allowed"] + "/redirect")
    assert not result["success"]
    assert result["error"]["code"] == "BLOCKED_DESTINATION"
    assert lab["received"] == []


def test_direct_webrtc_udp_sees_no_canary(attack_lab):
    import socket
    import time

    lab = attack_lab
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as positive:
        positive.sendto(b"positive-control", lab["udp"])
    deadline = time.monotonic() + 2
    while not lab["datagrams"] and time.monotonic() < deadline:
        time.sleep(0.01)
    assert lab["datagrams"]
    lab["datagrams"].clear()
    assert lab["browser"].fetch(lab["allowed"])["success"]
    page = lab["browser"]._fidelity.current_page
    page.context.unroute("**/*")
    page.evaluate(
        """port=>{let p=new RTCPeerConnection({iceServers:[{urls:'stun:127.0.0.2:'+port}]});p.createDataChannel('x');p.createOffer().then(o=>p.setLocalDescription(o));globalThis.attackPeer=p}""",
        lab["udp"][1],
    )
    page.wait_for_timeout(1000)
    page.evaluate("attackPeer.close()")
    assert lab["datagrams"] == []
    save_receipt(
        "webrtc-udp",
        {
            "positive_control": True,
            "udp_datagrams": lab["datagrams"],
            "routing_removed": True,
        },
    )
