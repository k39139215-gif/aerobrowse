"""Real native CDP/controller/browser regressions; no Python browser delegation."""

import json
import os
import select
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import psutil
import pytest
from playwright.sync_api import sync_playwright

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(sys.platform != "linux", reason="native Linux namespace"),
]


@pytest.fixture
def native():
    binary = os.environ.get("AEROBROWSE_NATIVE_BINARY")
    if not binary and os.environ.get("AEROBROWSE_NATIVE_REQUIRED") == "1":
        pytest.fail("required compiled native executable is missing")
    if not binary:
        pytest.skip("native browser job supplies compiled executable")
    with sync_playwright() as playwright:
        browser = playwright.chromium.executable_path
    process = subprocess.Popen(
        [binary, "native-session"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={
            **os.environ,
            "AEROBROWSE_CHROMIUM": browser,
            "AEROBROWSE_NATIVE_ALLOW_NETWORKS": "127.0.0.1/32",
        },
    )

    class Client:
        serial = 0

        def call(self, operation, **arguments):
            self.serial += 1
            process.stdin.write(
                json.dumps({"id": self.serial, "operation": operation, **arguments})
                + "\n"
            )
            process.stdin.flush()
            ready, _, _ = select.select([process.stdout], [], [], 40)
            assert ready, "native operation exceeded its bounded reply deadline"
            line = process.stdout.readline()
            assert line, (
                process.poll(),
                process.stderr.read() if process.poll() is not None else "closed",
            )
            result = json.loads(line)
            assert result["id"] == self.serial
            return result

        def action(self, page, label, operation, **arguments):
            target = next(a for a in page["actions"] if a["label"] == label)
            return self.call(
                operation,
                action_id=target["id"],
                generation=page["generation"],
                **arguments,
            )

    client = Client()
    client.process = process
    yield client
    if process.poll() is None:
        process.stdin.close()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            pytest.fail("native session did not clean up on EOF")


def test_native_navigation_exact_actions_and_injection(native, site):
    page = native.call("navigate", url=site + "/form")
    assert page["success"], page
    original = page
    value = '";globalThis.injected=true;// 世界'
    page = native.action(page, "Name", "fill", value=value)
    assert page["success"], page
    stale = native.action(original, "Name", "fill", value="wrong")
    assert stale["error"]["code"] == "STALE_ACTION_ID"
    page = native.action(page, "Choice", "select", value="b")
    assert page["success"], page
    page = native.action(page, "Agree", "check", value=True)
    assert page["success"]
    assert next(a for a in page["actions"] if a["label"] == "Agree")["checked"]
    page = native.action(page, "Update", "click")
    assert page["success"] and "Changed by JavaScript" in page["markdown"], page
    assert value not in json.dumps(page)
    screenshot = native.call("screenshot")
    assert screenshot["success"] and screenshot["mime_type"] == "image/png"


def test_native_blocks_redirect_and_private_destination(native, site):
    for url in [
        "http://127.0.0.2",
        "http://169.254.169.254",
        "http://[::1]",
        site + "/redirect",
    ]:
        result = native.call("navigate", url=url)
        assert not result["success"], result
        assert result["error"]["code"] == "BLOCKED_DESTINATION", result


def test_native_mount_network_boundary_and_cleanup(native, site):
    page = native.call("navigate", url=site + "/form")
    assert page["success"], page
    controller = psutil.Process(native.process.pid)
    children = controller.children(recursive=True)
    chromium = [
        p
        for p in children
        if "chrome" in p.name().lower() or "chromium" in p.name().lower()
    ]
    assert chromium
    host_net = os.readlink("/proc/self/ns/net")
    for child in chromium:
        root = Path("/proc") / str(child.pid)
        assert os.readlink(root / "ns/net") != host_net
        assert not (root / "root/tmp").exists()
        assert (root / "root/workspace/tmp").is_dir()
        assert not (root / "root/etc/shadow").exists()
    assert native.call("close")["success"]
    deadline = time.monotonic() + 5
    while controller.children(recursive=True) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not controller.children(recursive=True)


@pytest.fixture
def native_site():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/loop"):
                self.send_response(302)
                self.send_header("Location", "/loop")
                self.end_headers()
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "/form")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"""<html><head><title>Native</title></head><body>
            <label>Name<input id=name></label><button onclick="document.querySelector('#result').textContent=window.injected?'INJECTED':document.querySelector('#name').value">Read</button><p id=result>Initial</p>
            <button onclick="document.querySelector('#name').outerHTML='<label>Replacement<input></label>'">Replace</button>
            <script>setTimeout(()=>{const button=document.createElement('button');button.textContent='Late';document.body.append(button)},500)</script>
            </body></html>""")

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)


def test_native_values_are_data_and_dynamic_nodes_invalidate(native, native_site):
    page = native.call("navigate", url=native_site + "/form")
    assert page["success"], page
    payload = '";window.injected=true;// 世界'
    page = native.action(page, "Name", "fill", value=payload)
    assert page["success"], page
    page = native.action(page, "Read", "click")
    assert page["success"] and payload in page["markdown"]
    assert "INJECTED" not in page["markdown"]
    before = page
    time.sleep(0.7)
    stale = native.action(before, "Name", "fill", value="wrong")
    assert stale["error"]["code"] == "STALE_ACTION_ID", stale
    page = native.call("snapshot")
    assert any(a["label"] == "Late" for a in page["actions"])
    original = page
    page = native.action(page, "Replace", "click")
    assert page["success"]
    assert (
        native.action(original, "Name", "fill", value="wrong")["error"]["code"]
        == "STALE_ACTION_ID"
    )


def test_native_valid_redirect_and_loop_limit(native, native_site):
    page = native.call("navigate", url=native_site + "/redirect")
    assert page["success"] and page["url"].endswith("/form"), page
    result = native.call("navigate", url=native_site + "/loop")
    assert result["error"]["code"] == "TOO_MANY_REDIRECTS", result


def test_native_controller_death_reaps_browser(native, site):
    page = native.call("navigate", url=site + "/form")
    assert page["success"], page
    children = psutil.Process(native.process.pid).children(recursive=True)
    assert children
    groups = {
        line.split(":", 2)[2].strip()
        for child in children
        for line in Path(f"/proc/{child.pid}/cgroup").read_text().splitlines()
        if "aero-native-" in line
    }
    assert len(groups) == 1
    native.process.kill()
    native.process.wait(timeout=5)
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        alive = [
            p for p in children if p.is_running() and p.status() != psutil.STATUS_ZOMBIE
        ]
        if not alive:
            break
        time.sleep(0.05)
    assert not alive, [(p.pid, p.name()) for p in alive]
    for group in groups:
        path = Path("/sys/fs/cgroup") / group.lstrip("/")
        while path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not path.exists(), "native cgroup leaked after controller death"


def test_native_tabs_history_and_discovery_wait(native, native_site):
    first = native.call("navigate", url=native_site + "/form")
    assert first["success"], first
    waited = native.call("wait", name="Late", role="button", timeout_ms=2000)
    assert waited["success"] and waited["wait"]["matched_action_ids"], waited
    second = native.call("navigate", url=native_site + "/other")
    assert second["success"], second
    back = native.call("back")
    assert back["success"] and back["url"].endswith("/form"), back
    forward = native.call("forward")
    assert forward["success"] and forward["url"].endswith("/other"), forward
    tab = native.call("new_tab", url=native_site + "/form")
    assert tab["success"] and tab["tab_id"] != first["tab_id"], tab
    listing = native.call("tabs")
    assert listing["success"] and len(listing["tabs"]) == 2
    switched = native.call("switch_tab", tab_id=first["tab_id"])
    assert switched["success"] and switched["url"].endswith("/other"), switched
    closed = native.call("close_tab", tab_id=tab["tab_id"])
    assert closed["success"]
    assert len(native.call("tabs")["tabs"]) == 1
    assert (
        native.call("switch_tab", tab_id="foreign")["error"]["code"] == "TAB_NOT_FOUND"
    )
