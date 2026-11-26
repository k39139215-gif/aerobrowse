"""Linux namespace launcher; Chromium receives only stdio/CDP pipe descriptors."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from aerobrowse.errors import AeroError


class IsolatedLauncher:
    def __init__(self):
        self.directory: tempfile.TemporaryDirectory | None = None

    def create(self, browser: str) -> str:
        unshare = shutil.which("unshare")
        if sys.platform != "linux" or not unshare:
            raise AeroError(
                "NETWORK_ISOLATION_UNAVAILABLE",
                "Fidelity requires Linux user/network namespace isolation",
            )
        # Test the exact namespace primitives. Do not provide an unsafe fallback.
        try:
            result = subprocess.run(
                [
                    unshare,
                    "--user",
                    "--map-root-user",
                    "--net",
                    "--",
                    sys.executable,
                    "-c",
                    "import socket; assert socket.if_nameindex() == [(1, 'lo')]",
                ],
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise AeroError(
                "NETWORK_ISOLATION_UNAVAILABLE",
                "Network isolation could not be established",
            ) from exc
        if result.returncode != 0:
            raise AeroError(
                "NETWORK_ISOLATION_UNAVAILABLE",
                "Host denies required namespace isolation",
            )
        self.directory = tempfile.TemporaryDirectory(prefix="aero-launch-")
        launcher = Path(self.directory.name) / "chromium"
        import shlex

        # Absolute, discovered paths only; no caller-provided shell fragments.
        launcher.write_text(
            "#!/bin/sh\nexec "
            + shlex.join([unshare, "--user", "--map-root-user", "--net", "--", browser])
            + ' "$@"\n'
        )
        os.chmod(launcher, 0o700)
        return str(launcher)

    def close(self) -> None:
        if self.directory:
            self.directory.cleanup()
            self.directory = None
