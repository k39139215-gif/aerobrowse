"""The browser writes only inside a namespace-owned workspace."""

import sys

from aerobrowse.isolation import IsolatedLauncher


def test_launcher_uses_private_workspace_without_host_temp(monkeypatch, tmp_path):
    browser = tmp_path / "chromium"
    browser.touch()
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(
        "aerobrowse.isolation.shutil.which", lambda name: "/usr/bin/bwrap"
    )
    command = IsolatedLauncher.command(str(browser))
    assert "/tmp" not in command
    assert command[command.index("--chdir") + 1] == "/workspace"
    assert "TMPDIR" in command
    assert command[command.index("TMPDIR") + 1] == "/workspace/tmp"
    workspace = command.index("/workspace")
    assert command[workspace - 1] == "--tmpfs"
    assert command.count("/workspace/tmp") == 2
    assert not any(
        command[i + 1] == "/workspace"
        for i, item in enumerate(command[:-1])
        if item in {"--bind", "--ro-bind"}
    )
