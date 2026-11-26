"""Fail-closed Linux browser sandbox. Host broker and CDP stay outside the sandbox."""

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from aerobrowse.errors import AeroError


class IsolatedLauncher:
    def __init__(self):
        self.directory: tempfile.TemporaryDirectory | None = None

    @staticmethod
    def command(browser: str, *, preserve_cdp: bool = True) -> list[str]:
        bwrap = shutil.which("bwrap")
        executable = Path(browser).resolve(strict=True)
        if sys.platform != "linux" or not bwrap:
            raise AeroError(
                "NETWORK_ISOLATION_UNAVAILABLE",
                "Fidelity requires Linux bubblewrap namespaces",
            )
        command = [
            bwrap,
            "--unshare-user",
            "--uid",
            "0",
            "--gid",
            "0",
            "--unshare-net",
            "--unshare-pid",
            "--unshare-ipc",
            "--unshare-uts",
            "--die-with-parent",
            "--new-session",
            "--cap-drop",
            "ALL",
            "--clearenv",
            "--setenv",
            "HOME",
            "/home/browser",
            "--setenv",
            "PATH",
            "/nonexistent",
            "--setenv",
            "LANG",
            "C.UTF-8",
            "--proc",
            "/proc",
            "--dev",
            "/dev",
            "--tmpfs",
            "/tmp",
            "--tmpfs",
            "/run",
            "--tmpfs",
            "/home",
            "--dir",
            "/home/browser",
            "--chdir",
            "/tmp",
        ]
        # System runtime data only. Never bind host /, /home, /run, /tmp, /proc or environment.
        for directory in (
            "/lib",
            "/lib64",
            "/usr/lib",
            "/usr/lib64",
            "/usr/share/fonts",
            "/usr/share/fontconfig",
            "/usr/share/glib-2.0",
            "/etc/fonts",
            "/etc/ssl/certs",
        ):
            if Path(directory).exists():
                command.extend(["--ro-bind", directory, directory])
        if Path("/etc/ld.so.cache").exists():
            command.extend(["--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache"])
        # Exact installed browser distribution; a caller must not choose an unrelated host directory.
        command.extend(["--ro-bind", str(executable.parent), str(executable.parent)])
        if preserve_cdp:
            # Chromium's remote-debugging-pipe uses descriptors 3 and 4; no TCP proxy is exposed.
            command.extend(["--preserve-fds", "2"])
        return command + ["--", str(executable)]

    def create(self, browser: str) -> str:
        try:
            command = self.command(browser)
            # Probe actual primitives and mount layout using the installed browser, not host Python.
            probe = self.command(browser, preserve_cdp=False) + ["--version"]
            result = subprocess.run(probe, capture_output=True, timeout=10, check=False)
            if result.returncode != 0:
                raise AeroError(
                    "NETWORK_ISOLATION_UNAVAILABLE",
                    "Host denies required browser sandbox",
                )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AeroError(
                "NETWORK_ISOLATION_UNAVAILABLE",
                "Browser sandbox could not be established",
            ) from exc
        self.directory = tempfile.TemporaryDirectory(prefix="aero-launch-")
        launcher = Path(self.directory.name) / "chromium"
        launcher.write_text("#!/bin/sh\nexec " + shlex.join(command) + ' "$@"\n')
        os.chmod(launcher, 0o700)
        return str(launcher)

    def close(self) -> None:
        if self.directory:
            self.directory.cleanup()
            self.directory = None
