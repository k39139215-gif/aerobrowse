import os

import psutil

from aerobrowse import AeroBrowser


def test_public_sdk_owns_real_worker_and_cleans_it():
    browser = AeroBrowser(default_mode="turbo")
    result = browser.fetch("http://127.0.0.1")
    assert result["error"]["code"] == "BLOCKED_DESTINATION"
    assert result["session_id"] == browser.session_id
    pid = browser._worker.pid
    assert pid != os.getpid() and psutil.pid_exists(pid)
    directory = browser._worker.directory.name
    browser.close()
    assert not psutil.pid_exists(pid)
    assert not os.path.exists(directory)
    assert browser.snapshot()["error"]["code"] == "RUNTIME_CLOSED"


def test_public_sdk_has_bounded_request_timeout():
    import pytest

    with pytest.raises(ValueError):
        AeroBrowser(request_timeout=0)


def test_public_sdk_timeout_retires_actual_worker():
    browser = AeroBrowser(default_mode="turbo", request_timeout=0.001)
    result = browser.snapshot()
    assert result["error"]["code"] == "TIMEOUT", result
    assert browser._closed
    assert browser._worker.process is None or browser._worker.process.poll() is not None
    assert browser.snapshot()["error"]["code"] == "RUNTIME_CLOSED"


def test_public_sdk_retains_explicit_network_policy(site):
    from aerobrowse.security import NetworkPolicy

    with AeroBrowser(
        default_mode="turbo", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    ) as browser:
        result = browser.fetch(site)
        assert result["success"], result
        assert "Private service secret" in result["markdown"]
        assert result["serialized_output"]["tokens"] > result["extracted_tokens"]


def test_sdk_session_lifetime_cannot_be_extended_by_calls():
    import time

    from aerobrowse.runtime import ResourceLimits

    browser = AeroBrowser(
        default_mode="turbo", resource_limits=ResourceLimits(lifetime_seconds=0.01)
    )
    time.sleep(0.02)
    result = browser.snapshot()
    assert result["error"]["code"] == "SESSION_EXPIRED"
    assert browser._worker.process is None
    assert browser._closed
