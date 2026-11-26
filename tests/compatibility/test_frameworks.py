"""Built framework fixtures; use a single permitted loopback for the fixture server."""

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        sys.platform != "linux", reason="requires isolated Linux browser"
    ),
]
ROOT = Path(__file__).parent


@contextmanager
def server(framework):
    if framework != "nextjs":
        directory = ROOT / framework / "dist"
        assert (directory / "app.js").is_file(), (
            "Build fixtures with npm ci --ignore-scripts && npm run build"
        )
        handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
        httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{httpd.server_port}"
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join()
        return
    assert (ROOT / "nextjs" / ".next" / "BUILD_ID").is_file(), (
        "Build real Next fixture before test"
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    process = subprocess.Popen(
        [
            "node",
            str(ROOT / "node_modules" / "next" / "dist" / "bin" / "next"),
            "start",
            str(ROOT / "nextjs"),
            "-p",
            str(port),
            "-H",
            "127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env={**os.environ, "NEXT_TELEMETRY_DISABLED": "1"},
    )
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    break
            if process.poll() is not None:
                raise AssertionError(process.stderr.read().decode())
            time.sleep(0.1)
        else:
            raise AssertionError("Next startup timed out")
        yield f"http://127.0.0.1:{port}"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        process.stderr.close()


def action(snapshot, name):
    return next(a["id"] for a in snapshot["actions"] if a["label"] == name)


def stable(browser):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        snapshot = browser.snapshot()
        if (
            snapshot.get("success")
            and "Important compatibility content" in snapshot["markdown"]
        ):
            return snapshot
        browser._fidelity.current_page.wait_for_timeout(50)
    raise AssertionError(snapshot)


@pytest.mark.parametrize("framework", ["react", "vue", "angular", "nextjs"])
def test_framework_controlled_state_and_targets(framework):
    with (
        server(framework) as url,
        AeroBrowser(
            default_mode="fidelity",
            policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
        ) as browser,
    ):
        result = browser.fetch(url, force_fidelity=True)
        assert result.get("success"), result
        snapshot = stable(browser)
        assert "Important compatibility content" in snapshot["markdown"]
        assert not any(a["label"] == "Hidden action" for a in snapshot["actions"])
        assert next(a for a in snapshot["actions"] if a["label"] == "Disabled action")[
            "disabled"
        ]
        snapshot = browser.fill(action(snapshot, "Name"), "Ada", snapshot["generation"])
        assert snapshot.get("success"), snapshot
        snapshot = stable(browser)
        assert "Name state: Ada" in snapshot["markdown"]
        snapshot = browser.select(
            action(snapshot, "Choice"), "b", snapshot["generation"]
        )
        assert snapshot.get("success"), snapshot
        snapshot = stable(browser)
        assert "choice state: b" in snapshot["markdown"]
        old = action(snapshot, "Increment")
        snapshot = browser.click(old, snapshot["generation"])
        assert snapshot.get("success"), snapshot
        snapshot = stable(browser)
        assert "count: 1" in snapshot["markdown"]
        stale = browser.click(old)
        assert stale["error"]["code"] == "STALE_ACTION_ID"
        snapshot = browser.click(
            action(snapshot, "Toggle dialog"), snapshot["generation"]
        )
        assert snapshot.get("success"), snapshot
        snapshot = stable(browser)
        assert "Dialog content" in snapshot["markdown"]
        snapshot = browser.click(
            action(snapshot, "Close dialog"), snapshot["generation"]
        )
        assert snapshot.get("success"), snapshot
        snapshot = stable(browser)
        snapshot = browser.click(
            action(snapshot, "Details route"), snapshot["generation"]
        )
        assert snapshot.get("success"), snapshot
        assert "details" in snapshot["url"]
