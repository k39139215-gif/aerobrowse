import io
import sys

import pytest

from aerobrowse.errors import AeroError
from aerobrowse.runtime import (
    MAX_FRAME,
    ProcessWorker,
    ResourceLimits,
    ResourcePool,
    _frame_read,
)


def test_frame_bound_before_json_parse():
    with pytest.raises(AeroError) as error:
        _frame_read(io.BytesIO(b"X" * (MAX_FRAME + 1)))
    assert error.value.code == "WORKER_PROTOCOL_ERROR"


def test_resource_configuration_rejects_invalid_limits():
    with pytest.raises(ValueError):
        ResourceLimits(memory_bytes=1)


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux delegated cgroup capability check"
)
def test_no_cgroup_browser_action_fails_closed(monkeypatch):
    monkeypatch.delenv("AEROBROWSE_CGROUP_ROOT", raising=False)
    pool = ResourcePool()
    worker = ProcessWorker(pool)
    try:
        result = worker.call(
            "navigate", ("https://example.com",), {"force_fidelity": True}
        )
        assert result["error"]["code"] == "RESOURCE_ISOLATION_UNAVAILABLE"
    finally:
        worker.terminate()
        pool.close()


@pytest.mark.browser
@pytest.mark.skipif(sys.platform != "linux", reason="Linux cgroup hard limit test")
def test_delegated_kernel_limits_are_installed():
    import os

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.fail("Required Linux quota test requires AEROBROWSE_CGROUP_ROOT")
    pool = ResourcePool(ResourceLimits(memory_bytes=256 * 1024 * 1024, processes=4))
    group = pool.session()
    try:
        assert (group.path / "memory.max").read_text().strip() == str(256 * 1024 * 1024)
        assert (group.path / "pids.max").read_text().strip() == "4"
        assert (group.path / "cpu.max").read_text().strip() == "100000 100000"
    finally:
        group.close()
        pool.close()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows Job Object hard memory denial"
)
def test_windows_kernel_rejects_excess_memory():
    import subprocess

    pool = ResourcePool(ResourceLimits(memory_bytes=128 * 1024 * 1024))
    group = pool.session()
    process = subprocess.Popen(
        [
            getattr(sys, "_base_executable", sys.executable),
            "-c",
            "import sys;sys.stdin.readline();\ntry:\n x=bytearray(512*1024*1024);print('UNEXPECTED',flush=True)\nexcept MemoryError:\n print('DENIED',flush=True)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        group.attach(process)
        output, _ = process.communicate("go\n", timeout=10)
        assert process.returncode == 0
        assert output.strip() == "DENIED"
    finally:
        group.kill()
        group.close()
        pool.close()


@pytest.mark.skipif(
    sys.platform != "win32", reason="Windows Job Object active-process hard cap"
)
def test_windows_kernel_denies_excess_child_process():
    import subprocess

    pool = ResourcePool(ResourceLimits(processes=1))
    group = pool.session()
    process = subprocess.Popen(
        [
            getattr(sys, "_base_executable", sys.executable),
            "-c",
            "import subprocess,sys;sys.stdin.readline();\ntry:\n subprocess.run([sys.executable,'-c','pass'],check=True);print('UNEXPECTED',flush=True)\nexcept OSError:\n print('DENIED',flush=True)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        group.attach(process)
        output, _ = process.communicate("go\n", timeout=10)
        assert process.returncode == 0
        assert output.strip() == "DENIED"
    finally:
        group.kill()
        group.close()
        pool.close()


@pytest.mark.browser
@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux kernel cgroup memory enforcement"
)
def test_linux_kernel_rejects_excess_memory():
    import os
    import subprocess

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.fail("Required Linux quota test requires AEROBROWSE_CGROUP_ROOT")
    pool = ResourcePool(ResourceLimits(memory_bytes=64 * 1024 * 1024))
    group = pool.session()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys;sys.stdin.readline();x=bytearray(256*1024*1024);print('UNEXPECTED',flush=True)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        group.attach(process.pid)
        output, _ = process.communicate("go\n", timeout=10)
        assert process.returncode != 0
        assert "UNEXPECTED" not in output
        assert (
            int(
                dict(
                    line.split()
                    for line in (group.path / "memory.events").read_text().splitlines()
                )["oom_kill"]
            )
            >= 1
        )
    finally:
        group.kill()
        group.close()
        pool.close()


@pytest.mark.browser
@pytest.mark.skipif(sys.platform != "linux", reason="Linux kernel cgroup process cap")
def test_linux_kernel_denies_excess_child_process():
    import os
    import subprocess

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.fail("Required Linux quota test requires AEROBROWSE_CGROUP_ROOT")
    pool = ResourcePool(ResourceLimits(processes=1))
    group = pool.session()
    process = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import subprocess,sys;sys.stdin.readline();\ntry:\n subprocess.run([sys.executable,'-c','pass'],check=True);print('UNEXPECTED',flush=True)\nexcept OSError:\n print('DENIED',flush=True)",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        group.attach(process.pid)
        output, _ = process.communicate("go\n", timeout=10)
        assert process.returncode == 0
        assert output.strip() == "DENIED"
        assert (
            int(
                dict(
                    line.split()
                    for line in (group.path / "pids.events").read_text().splitlines()
                )["max"]
            )
            >= 1
        )
    finally:
        group.kill()
        group.close()
        pool.close()


def test_worker_ipc_preserves_frame_across_partial_writes():
    import json

    from aerobrowse.runtime import _frame_write

    class PartialWriter:
        def __init__(self):
            self.data = bytearray()
            self.flushed = False

        def write(self, data):
            amount = min(7, len(data))
            self.data.extend(data[:amount])
            return amount

        def flush(self):
            self.flushed = True

    stream = PartialWriter()
    payload = {
        "id": "request",
        "result": {
            "unicode": "ÃƒÆ’Ã¢â€žÂ¢ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã‹Å“Ãƒâ€šÃ‚Â±ÃƒÆ’Ã‹Å“Ãƒâ€šÃ‚Â­ÃƒÆ’Ã‹Å“Ãƒâ€šÃ‚Â¨ÃƒÆ’Ã‹Å“Ãƒâ€šÃ‚Â§",
            "data": "x" * 10000,
        },
    }
    _frame_write(stream, payload)
    assert bytes(stream.data).endswith(b"\n")
    assert json.loads(stream.data) == payload
    assert stream.flushed


def test_worker_ipc_zero_write_fails_closed():
    from aerobrowse.runtime import _frame_write

    class Closed:
        def write(self, data):
            return 0

    with pytest.raises(AeroError) as caught:
        _frame_write(Closed(), {"id": "request"})
    assert caught.value.code == "WORKER_PROTOCOL_ERROR"


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux no-delegation capability rejection"
)
def test_positional_fidelity_cannot_bypass_missing_kernel_quota(monkeypatch, site):
    monkeypatch.delenv("AEROBROWSE_CGROUP_ROOT", raising=False)
    pool = ResourcePool()
    worker = ProcessWorker(pool)
    try:
        result = worker.call("navigate", (site + "/form", True), {})
        assert result["error"]["code"] == "RESOURCE_ISOLATION_UNAVAILABLE", result
    finally:
        worker.terminate()
        pool.close()


@pytest.mark.parametrize(
    "raw",
    [
        "0",
        "-1",
        "257",
        "4096",
        "1.0",
        " 256",
        "256 ",
        "",
        "abc",
        "999999999999999999999",
    ],
)
def test_operator_task_budget_rejects_invalid_or_aggregate_bypass(monkeypatch, raw):
    monkeypatch.setenv("AEROBROWSE_SESSION_TASKS", raw)
    with pytest.raises(AeroError) as error:
        ResourceLimits.from_environment()
    assert error.value.code == "INVALID_RUNTIME_CONFIG"


def test_operator_task_budget_keeps_defaults_and_aggregate_ceiling(monkeypatch):
    monkeypatch.delenv("AEROBROWSE_SESSION_TASKS", raising=False)
    assert ResourceLimits.from_environment().processes == 64
    monkeypatch.setenv("AEROBROWSE_SESSION_TASKS", "256")
    configured = ResourceLimits.from_environment()
    assert configured.processes == configured.global_processes == 256
    assert configured.global_memory_bytes == ResourceLimits().global_memory_bytes


def test_cgroup_resource_diagnostics_include_aggregate_limits(tmp_path):
    from aerobrowse.runtime import Cgroup

    root = tmp_path / "pool"
    child = root / "worker"
    child.mkdir(parents=True)
    for group, exhausted in [(root, True), (child, False)]:
        (group / "pids.events").write_text("max " + ("1" if exhausted else "0") + "\n")
        (group / "memory.events").write_text("max 0\noom 0\noom_kill 0\n")
    pool = Cgroup.__new__(Cgroup)
    pool.path = root
    session = Cgroup.__new__(Cgroup)
    session.path = child
    assert pool.resource_events()["pids_max"] == 1
    assert session.resource_events()["pids_max"] == 0
    (root / "memory.events").write_text("max 3\noom 1\noom_kill 1\n")
    assert pool.resource_events()["oom_kill"] == 1
