"""Inspect real browser descendants rather than trusting launcher arguments."""

import os
import tempfile
from pathlib import Path

import psutil
import pytest
from conftest import save_receipt

pytestmark = pytest.mark.browser


def test_browser_descendants_have_private_network_and_mounts(attack_lab):
    lab = attack_lab
    assert lab["browser"].fetch(lab["allowed"])["success"]
    host_net = os.readlink("/proc/self/ns/net")
    host_mnt = os.readlink("/proc/self/ns/mnt")
    processes = []
    for process in psutil.Process().children(recursive=True):
        try:
            executable = process.name().lower()
            if not ("chrome" in executable or "chromium" in executable):
                continue
            root = Path("/proc") / str(process.pid)
            network = os.readlink(root / "ns/net")
            mount = os.readlink(root / "ns/mnt")
            assert network != host_net, (process.pid, process.cmdline())
            assert mount != host_mnt
            assert (root / "root/home/browser").is_dir()
            assert not (root / "root" / str(Path.home()).lstrip("/")).exists()
            assert not (root / "root/etc/shadow").exists()
            processes.append(
                {
                    "pid": process.pid,
                    "name": executable,
                    "network_namespace": network,
                    "mount_namespace": mount,
                    "command": process.cmdline(),
                }
            )
        except psutil.NoSuchProcess:
            continue
    assert len(processes) >= 3, processes
    assert any("--type=renderer" in " ".join(p["command"]) for p in processes)
    assert len({p["network_namespace"] for p in processes}) == 1
    save_receipt(
        "namespace-processes",
        {"host_net": host_net, "host_mount": host_mnt, "processes": processes},
    )


def test_browser_cannot_read_host_secret_or_environment(attack_lab):
    lab = attack_lab
    with tempfile.NamedTemporaryFile(
        prefix="aero-host-secret-", delete=False
    ) as stream:
        stream.write(b"CONTROLLED_HOST_SECRET")
        secret = Path(stream.name)
    try:
        assert lab["browser"].fetch(lab["allowed"])["success"]
        for process in psutil.Process().children(recursive=True):
            try:
                if not (
                    "chrome" in process.name().lower()
                    or "chromium" in process.name().lower()
                ):
                    continue
                root = Path("/proc") / str(process.pid) / "root"
                assert not (root / str(secret).lstrip("/")).exists()
                assert "AEROBROWSE_TEST_HOST_SECRET" not in process.environ()
            except psutil.NoSuchProcess:
                continue
    finally:
        secret.unlink()
