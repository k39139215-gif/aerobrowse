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
