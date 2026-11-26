"""Real native CDP/controller/browser regressions; no Python browser delegation."""

import json
import os
import select
import subprocess
import sys
import time
from pathlib import Path

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
