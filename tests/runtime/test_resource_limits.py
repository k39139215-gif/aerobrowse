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


@pytest.mark.skipif(sys.platform != "linux", reason="Linux cgroup hard limit test")
def test_delegated_kernel_limits_are_installed():
    import os

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.skip("Delegated kernel quota test requires AEROBROWSE_CGROUP_ROOT")
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


@pytest.mark.skipif(
    sys.platform != "linux", reason="Linux kernel cgroup memory enforcement"
)
def test_linux_kernel_rejects_excess_memory():
    import os
    import subprocess

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.skip("Delegated kernel quota test requires AEROBROWSE_CGROUP_ROOT")
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


@pytest.mark.skipif(sys.platform != "linux", reason="Linux kernel cgroup process cap")
def test_linux_kernel_denies_excess_child_process():
    import os
    import subprocess

    if "AEROBROWSE_CGROUP_ROOT" not in os.environ:
        pytest.skip("Delegated kernel quota test requires AEROBROWSE_CGROUP_ROOT")
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
