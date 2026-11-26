"""Run the same destination-rejection contract against the real native binary."""

import json
import os
import subprocess

import pytest

from aerobrowse import TurboEngine

BLOCKED = [
    "http://127.0.0.1",
    "http://10.1.1.1",
    "http://172.16.1.1",
    "http://192.168.1.1",
    "http://169.254.169.254",
    "http://[::1]",
    "http://[fc00::1]",
    "http://[fe80::1]",
    "http://[::ffff:127.0.0.1]",
    "http://0.0.0.0",
    "http://224.0.0.1",
    "http://localhost",
    "http://svc.internal",
    "file:///etc/passwd",
    "javascript:alert(1)",
    "data:text/html,x",
    "http://user:secret@example.com",
]


@pytest.mark.native_contract
@pytest.mark.parametrize("url", BLOCKED)
def test_both_native_and_python_reject_destination(url):
    binary = os.environ.get("AEROBROWSE_NATIVE_BINARY")
    if not binary:
        pytest.skip(
            "native_contract requires AEROBROWSE_NATIVE_BINARY; run in Rust CI job"
        )
    native = subprocess.run(
        [binary, "fetch", url], capture_output=True, text=True, timeout=20, check=False
    )
    assert native.returncode != 0
    response = json.loads(native.stdout)
    assert response["success"] is False
    assert response["error"]["code"].split(":", 1)[0] in {
        "BLOCKED_DESTINATION",
        "INVALID_URL",
    }
    python = TurboEngine().fetch(url)
    assert python["success"] is False
    assert python["error"]["code"] in {"BLOCKED_DESTINATION", "INVALID_URL"}


@pytest.mark.native_contract
def test_native_browser_cannot_silently_fall_back_to_unrestricted_runtime():
    binary = os.environ.get("AEROBROWSE_NATIVE_BINARY")
    if not binary:
        pytest.skip(
            "native_contract requires AEROBROWSE_NATIVE_BINARY; run in Rust CI job"
        )
    result = subprocess.run(
        [binary, "fetch", "https://example.com", "--fidelity"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode != 0
    assert json.loads(result.stdout)["error"]["code"].startswith(
        "NETWORK_ISOLATION_UNAVAILABLE"
    )
