"""Process-owned browser workers, bounded JSON IPC, and kernel resource controls.

Cgroups require an operator-delegated empty v2 subtree. No sudo, controller
relaxation, or unconfined Chromium fallback is performed by this module.
"""

from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from aerobrowse.errors import AeroError

log = logging.getLogger(__name__)

MAX_FRAME = 8 * 1024 * 1024


class WorkerState(StrEnum):
    CREATED = "CREATED"
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    STOPPING = "STOPPING"
    TERMINATED = "TERMINATED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class ResourceLimits:
    memory_bytes: int = 1024 * 1024 * 1024
    global_memory_bytes: int = 4 * 1024 * 1024 * 1024
    cpu_percent: int = 100
    global_cpu_percent: int = 200
    processes: int = 64
    global_processes: int = 256
    startup_seconds: float = 15
    lifetime_seconds: float = 1800

    def __post_init__(self) -> None:
        if not (64 * 1024 * 1024 <= self.memory_bytes <= self.global_memory_bytes):
            raise ValueError("Invalid memory quota")
        if not (1 <= self.cpu_percent <= self.global_cpu_percent <= 10000):
            raise ValueError("Invalid CPU quota")
        if not (1 <= self.processes <= self.global_processes <= 4096):
            raise ValueError("Invalid process quota")
        if not (0 < self.startup_seconds <= 120 and 0 < self.lifetime_seconds <= 86400):
            raise ValueError("Invalid runtime timeout")


class Cgroup:
    def __init__(self, path: Path, memory: int, cpu: int, processes: int):
        self.path = path
        try:
            path.mkdir()
            for name, value in {
                "memory.max": str(memory),
                "memory.swap.max": "0",
                "pids.max": str(processes),
                "cpu.max": f"{cpu * 1000} 100000",
            }.items():
                (path / name).write_text(value, encoding="ascii")
        except OSError as exc:
            self.close()
            raise AeroError(
                "RESOURCE_ISOLATION_UNAVAILABLE",
                "Delegated cgroup controls are unavailable",
            ) from exc

    def attach(self, pid: int) -> None:
        (self.path / "cgroup.procs").write_text(str(pid), encoding="ascii")

    def kill(self) -> None:
        target = self.path / "cgroup.kill"
        if target.exists():
            target.write_text("1", encoding="ascii")

    def close(self) -> None:
        try:
            if self.path.exists() and (self.path / "cgroup.events").exists():
                deadline = time.monotonic() + 5
                while (
                    "populated 1" in (self.path / "cgroup.events").read_text()
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.01)
            self.path.rmdir()
        except FileNotFoundError:
            return
        except OSError as exc:
            raise AeroError(
                "CLEANUP_FAILED", "Cgroup resources remain allocated"
            ) from exc


class WindowsJob:
    """Nested kill-on-close jobs. Handles are never inherited by workers."""

    def __init__(self, memory: int, cpu: int, processes: int):
        from ctypes import wintypes

        self.api = cast(Any, ctypes).WinDLL("kernel32", use_last_error=True)
        self.api.CreateJobObjectW.restype = wintypes.HANDLE
        self.api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        self.api.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        self.api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        self.api.QueryInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.c_void_p,
        ]
        self.api.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.api.CreateJobObjectW(None, None)

        class Basic(ctypes.Structure):
            _fields_ = [
                ("process_time", ctypes.c_int64),
                ("job_time", ctypes.c_int64),
                ("flags", wintypes.DWORD),
                ("min_ws", ctypes.c_size_t),
                ("max_ws", ctypes.c_size_t),
                ("active", wintypes.DWORD),
                ("affinity", ctypes.c_size_t),
                ("priority", wintypes.DWORD),
                ("scheduling", wintypes.DWORD),
            ]

        class IO(ctypes.Structure):
            _fields_ = [
                (name, ctypes.c_uint64)
                for name in (
                    "read_ops",
                    "write_ops",
                    "other_ops",
                    "read_bytes",
                    "write_bytes",
                    "other_bytes",
                )
            ]

        class Extended(ctypes.Structure):
            _fields_ = [
                ("basic", Basic),
                ("io", IO),
                ("process_memory", ctypes.c_size_t),
                ("job_memory", ctypes.c_size_t),
                ("peak_process", ctypes.c_size_t),
                ("peak_job", ctypes.c_size_t),
            ]

        limits = Extended()
        limits.basic.flags = (
            0x2000 | 0x200 | 0x8
        )  # kill on close, job memory, active process count
        limits.basic.active = processes
        limits.job_memory = memory
        if not self.handle or not self.api.SetInformationJobObject(
            self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        ):
            self.close()
            raise AeroError(
                "RESOURCE_ISOLATION_UNAVAILABLE", "Windows job limits unavailable"
            )

        class CPU(ctypes.Structure):
            _fields_ = [("flags", wintypes.DWORD), ("rate", wintypes.DWORD)]

        quota = CPU(1 | 4, min(10000, max(1, int(cpu * 100 / (os.cpu_count() or 1)))))
        if not self.api.SetInformationJobObject(
            self.handle, 15, ctypes.byref(quota), ctypes.sizeof(quota)
        ):
            self.close()
            raise AeroError(
                "RESOURCE_ISOLATION_UNAVAILABLE", "Windows CPU limits unavailable"
            )

    def attach(self, process: subprocess.Popen) -> None:
        if not self.api.AssignProcessToJobObject(
            self.handle, int(cast(Any, process)._handle)
        ):
            raise AeroError(
                "RESOURCE_ISOLATION_UNAVAILABLE", "Worker could not enter job"
            )

    def kill(self) -> None:
        if self.handle:
            if not self.api.TerminateJobObject(self.handle, 1):
                raise AeroError(
                    "WORKER_TERMINATION_FAILED", "Windows job termination failed"
                )
            self.wait_empty()

    def wait_empty(self) -> None:
        from ctypes import wintypes

        class Accounting(ctypes.Structure):
            _fields_ = [
                ("user", ctypes.c_int64),
                ("kernel", ctypes.c_int64),
                ("period_user", ctypes.c_int64),
                ("period_kernel", ctypes.c_int64),
                ("faults", wintypes.DWORD),
                ("total", wintypes.DWORD),
                ("active", wintypes.DWORD),
                ("terminated", wintypes.DWORD),
            ]

        deadline = time.monotonic() + 5
        while True:
            value = Accounting()
            if not self.api.QueryInformationJobObject(
                self.handle, 1, ctypes.byref(value), ctypes.sizeof(value), None
            ):
                raise AeroError(
                    "WORKER_TERMINATION_FAILED", "Windows job accounting failed"
                )
            if value.active == 0:
                return
            if time.monotonic() >= deadline:
                raise AeroError(
                    "WORKER_TERMINATION_FAILED", "Windows job descendants remain alive"
                )
            time.sleep(0.01)

    def close(self) -> None:
        if getattr(self, "handle", None):
            self.api.CloseHandle(self.handle)
            self.handle = None


class ResourcePool:
    def __init__(
        self,
        limits: ResourceLimits | None = None,
        *,
        allow_networks: tuple[str, ...] = (),
    ):
        self.limits = limits or ResourceLimits()
        self.allow_networks = allow_networks
        self.group: Cgroup | WindowsJob | None = None
        self.path: Path | None = None
        self.closed = False
        if sys.platform == "win32":
            self.group = WindowsJob(
                self.limits.global_memory_bytes,
                self.limits.global_cpu_percent,
                self.limits.global_processes,
            )
        elif sys.platform == "linux" and os.environ.get("AEROBROWSE_CGROUP_ROOT"):
            root = Path(os.environ["AEROBROWSE_CGROUP_ROOT"]).resolve(strict=True)
            if not (root / "cgroup.controllers").is_file():
                raise AeroError(
                    "RESOURCE_ISOLATION_UNAVAILABLE",
                    "A delegated cgroup v2 root is required",
                )
            self.path = root / f"aero-{os.getpid()}-{uuid.uuid4().hex}"
            self.group = Cgroup(
                self.path,
                self.limits.global_memory_bytes,
                self.limits.global_cpu_percent,
                self.limits.global_processes,
            )
            try:
                (self.path / "cgroup.subtree_control").write_text(
                    "+cpu +memory +pids", encoding="ascii"
                )
            except OSError as exc:
                self.close()
                raise AeroError(
                    "RESOURCE_ISOLATION_UNAVAILABLE",
                    "Cgroup controllers are not delegated",
                ) from exc

    @property
    def enforced(self) -> bool:
        return self.group is not None

    def session(self) -> Cgroup | WindowsJob | None:
        if self.closed:
            raise AeroError("RUNTIME_CLOSED", "Resource pool has been closed")
        q = self.limits
        if isinstance(self.group, WindowsJob):
            return WindowsJob(q.memory_bytes, q.cpu_percent, q.processes)
        if self.path:
            return Cgroup(
                self.path / uuid.uuid4().hex, q.memory_bytes, q.cpu_percent, q.processes
            )
        return None

    def close(self) -> None:
        self.closed = True
        if self.group:
            self.group.kill()
            self.group.close()
            self.group = None


def _frame_read(stream: Any) -> dict[str, Any]:
    raw = stream.readline(MAX_FRAME + 1)
    if not raw or len(raw) > MAX_FRAME or not raw.endswith(b"\n"):
        raise AeroError(
            "WORKER_PROTOCOL_ERROR", "Worker response is missing or exceeds its limit"
        )
    try:
        result = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise AeroError("WORKER_PROTOCOL_ERROR", "Invalid worker response") from exc
    if not isinstance(result, dict):
        raise AeroError("WORKER_PROTOCOL_ERROR", "Invalid worker response")
    return result


def _frame_write(stream: Any, value: dict[str, Any]) -> None:
    raw = json.dumps(value, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    if len(raw) > MAX_FRAME:
        raise AeroError("RESPONSE_TOO_LARGE", "Worker message exceeds limit")
    stream.write(raw)
    stream.flush()


class ProcessWorker:
    def __init__(self, pool: ResourcePool):
        self.pool = pool
        self.state = WorkerState.CREATED
        self.process: subprocess.Popen | None = None
        self.group: Cgroup | WindowsJob | None = None
        self._lock = threading.Lock()
        self.started = 0.0
        self.worker_pid: int | None = None
        self.guardian: subprocess.Popen | None = None
        self.guardian_pipe: int | None = None
        self._termination = threading.Lock()
        self._stopped = False
        self.directory: tempfile.TemporaryDirectory | None = None

    @property
    def pid(self) -> int | None:
        return self.worker_pid or (self.process.pid if self.process else None)

    def start(self) -> None:
        if self.state != WorkerState.CREATED:
            return
        self.state = WorkerState.STARTING
        try:
            with self._termination:
                if self._stopped:
                    raise AeroError(
                        "WORKER_STOPPED", "Worker was stopped during startup"
                    )
                self._launch()
            process = self.process
            if process is None:
                raise AeroError("WORKER_START_FAILED", "Worker launch failed")
            timer = threading.Timer(self.pool.limits.startup_seconds, self.terminate)
            timer.start()
            try:
                _frame_write(
                    process.stdin,
                    {
                        "quotas": self.pool.enforced,
                        "allow_networks": self.pool.allow_networks,
                    },
                )
                ready = _frame_read(process.stdout)
            finally:
                timer.cancel()
            if self._stopped or ready.get("state") != "READY":
                raise AeroError("WORKER_START_FAILED", "Browser worker did not start")
            self.worker_pid = ready["pid"]
            self.started = time.monotonic()
            self.state = WorkerState.READY
        except BaseException:
            self.terminate()
            self.state = WorkerState.FAILED
            raise

    def _launch(self) -> None:
        self.group = self.pool.session()
        options: dict[str, Any] = (
            {"start_new_session": True}
            if os.name != "nt"
            else {"creationflags": cast(Any, subprocess).CREATE_NEW_PROCESS_GROUP}
        )
        self.directory = tempfile.TemporaryDirectory(prefix="aero-worker-")
        safe_env = {
            key: value
            for key, value in os.environ.items()
            if key
            in {
                "PATH",
                "SYSTEMROOT",
                "WINDIR",
                "COMSPEC",
                "PATHEXT",
                "LANG",
                "LC_ALL",
                "PLAYWRIGHT_BROWSERS_PATH",
                "AEROBROWSE_CGROUP_ROOT",
            }
        }
        safe_env.update(
            TEMP=self.directory.name,
            TMP=self.directory.name,
            TMPDIR=self.directory.name,
            PYTHONIOENCODING="utf-8",
        )
        # Chromium storage is ephemeral; the trusted worker does not inherit API tokens/cookies.
        self.process = subprocess.Popen(
            [sys.executable, "-m", "aerobrowse.runtime", "--worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            bufsize=0,
            env=safe_env,
            **options,
        )
        if isinstance(self.pool.group, WindowsJob):
            self.pool.group.attach(self.process)
        if isinstance(self.group, WindowsJob):
            self.group.attach(self.process)
        elif self.group:
            self.group.attach(self.process.pid)
        if sys.platform == "linux":
            read_fd, self.guardian_pipe = os.pipe()
            temp_path = Path(self.directory.name)
            cleanup_fd = os.open(
                temp_path.parent, os.O_RDONLY | cast(Any, os).O_DIRECTORY
            )
            group_parent_fd = (
                os.open(self.group.path.parent, os.O_RDONLY | cast(Any, os).O_DIRECTORY)
                if isinstance(self.group, Cgroup)
                else -1
            )
            guardian_fds = (read_fd, cleanup_fd) + (
                (group_parent_fd,) if group_parent_fd >= 0 else ()
            )
            try:
                self.guardian = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "aerobrowse.runtime",
                        "--guardian",
                        str(read_fd),
                        str(self.process.pid),
                        str(cleanup_fd),
                        temp_path.name,
                        str(group_parent_fd),
                        self.group.path.name if isinstance(self.group, Cgroup) else "",
                    ],
                    pass_fds=guardian_fds,
                    start_new_session=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=safe_env,
                )
            finally:
                for descriptor in guardian_fds:
                    os.close(descriptor)

    def call(
        self, operation: str, args: tuple[Any, ...], kwargs: dict[str, Any]
    ) -> dict[str, Any]:
        with self._lock:
            self.start()
            if not self.process or self.process.poll() is not None:
                self.state = WorkerState.FAILED
                raise AeroError("WORKER_CRASHED", "Browser worker terminated")
            self.state = WorkerState.BUSY
            request_id = uuid.uuid4().hex
            try:
                _frame_write(
                    self.process.stdin,
                    {
                        "id": request_id,
                        "operation": operation,
                        "args": args,
                        "kwargs": kwargs,
                    },
                )
                response = _frame_read(self.process.stdout)
                if response.get("id") != request_id or not isinstance(
                    response.get("result"), dict
                ):
                    raise AeroError(
                        "WORKER_PROTOCOL_ERROR", "Worker correlation failed"
                    )
                self.state = WorkerState.READY
                return response["result"]
            except (BrokenPipeError, OSError) as exc:
                self.state = WorkerState.FAILED
                raise AeroError("WORKER_CRASHED", "Browser worker terminated") from exc

    def terminate(self) -> None:
        self._stopped = True
        with self._termination:
            self._terminate()

    def _terminate(self) -> None:
        self.state = WorkerState.STOPPING
        process = self.process
        if self.group:
            self.group.kill()
        if process:
            if process.poll() is None:
                if os.name != "nt":
                    try:
                        cast(Any, os).killpg(process.pid, 9)
                    except ProcessLookupError:
                        pass
                else:
                    process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired as exc:
                self.state = WorkerState.FAILED
                raise AeroError(
                    "WORKER_TERMINATION_FAILED", "Worker termination did not complete"
                ) from exc
            if os.name == "nt":
                cast(Any, process)._handle.Close()
            if self.worker_pid:
                import psutil

                try:
                    psutil.Process(self.worker_pid).wait(timeout=5)
                except psutil.NoSuchProcess:
                    pass
                except psutil.TimeoutExpired as exc:
                    raise AeroError(
                        "WORKER_TERMINATION_FAILED", "Worker exit was not confirmed"
                    ) from exc
            for stream in (process.stdin, process.stdout):
                if stream:
                    stream.close()
        if self.guardian_pipe is not None:
            os.close(self.guardian_pipe)
            self.guardian_pipe = None
        if self.guardian:
            if self.guardian.wait(timeout=6) != 0:
                raise AeroError("CLEANUP_FAILED", "Worker guardian cleanup failed")
            self.guardian = None
        if self.group:
            self.group.close()
            self.group = None
        if self.directory:
            self.directory.cleanup()
            self.directory = None
        self.state = WorkerState.TERMINATED


def _execute(
    browser: Any, operation: str, args: list[Any], kwargs: dict[str, Any], quotas: bool
) -> dict[str, Any]:
    methods = {
        "navigate": "fetch",
        "snapshot": "snapshot",
        "click": "click",
        "fill": "fill",
        "select": "select",
        "scroll": "scroll",
        "wait": "wait",
        "screenshot": "screenshot",
        "perform": "perform",
    }
    if operation not in methods:
        raise AeroError("UNSUPPORTED_OPERATION", "Unknown browser operation")
    if not quotas and operation not in {"navigate", "snapshot"}:
        raise AeroError(
            "RESOURCE_ISOLATION_UNAVAILABLE",
            "Browser actions require enforced aggregate quotas",
        )
    if not quotas and kwargs.get("force_fidelity"):
        raise AeroError(
            "RESOURCE_ISOLATION_UNAVAILABLE",
            "Fidelity requires enforced aggregate quotas",
        )
    value = getattr(browser, methods[operation])(*args, **kwargs)
    if not quotas and isinstance(value, dict) and value.get("needs_fidelity"):
        raise AeroError(
            "RESOURCE_ISOLATION_UNAVAILABLE",
            "Dynamic content requires a quota-controlled browser worker",
        )
    if operation == "screenshot":
        return {
            "success": True,
            "mime_type": "image/png",
            "data": base64.b64encode(value).decode(),
        }
    return value


def _worker_main() -> None:
    # Linux process session is created before any descendant exists by Popen.
    if sys.platform == "linux":
        parent = os.getppid()
        libc = ctypes.CDLL(None, use_errno=True)
        if libc.prctl(1, 9, 0, 0, 0) != 0 or os.getppid() != parent:
            raise SystemExit(70)
    command = _frame_read(sys.stdin.buffer)
    quotas = command.get("quotas") is True
    from aerobrowse.engine import AeroBrowser
    from aerobrowse.security import NetworkPolicy

    browser = AeroBrowser(
        default_mode="auto" if quotas else "turbo",
        policy=NetworkPolicy(allow_networks=tuple(command.get("allow_networks", ()))),
    )
    _frame_write(
        sys.stdout.buffer, {"state": "READY", "pid": os.getpid(), "quotas": quotas}
    )
    try:
        while True:
            request = _frame_read(sys.stdin.buffer)
            try:
                value = _execute(
                    browser,
                    request["operation"],
                    request["args"],
                    request["kwargs"],
                    quotas,
                )
            except AeroError as exc:
                value = exc.result()
            except (OSError, ValueError, TypeError, RuntimeError):
                log.error(
                    "worker_operation_failed",
                    extra={"error_code": "WORKER_OPERATION_FAILED"},
                )
                value = AeroError(
                    "WORKER_OPERATION_FAILED", "Browser operation failed"
                ).result()
            _frame_write(sys.stdout.buffer, {"id": request.get("id"), "result": value})
    finally:
        browser.close()


def _guardian_cleanup(
    parent_fd: int, name: str, group_parent_fd: int, group_name: str
) -> None:
    # Never accept a filesystem path from argv. Only generated basenames relative
    # to inherited directory descriptors are permitted; rmtree's fd API rejects symlinks.
    if not re.fullmatch(r"aero-worker-[a-z0-9_]{8}", name):
        raise ValueError("Invalid guardian directory identifier")
    if group_parent_fd >= 0:
        if not re.fullmatch(r"[0-9a-f]{32}", group_name):
            raise ValueError("Invalid guardian cgroup identifier")
        try:
            descriptor = os.open(
                group_name,
                os.O_RDONLY | cast(Any, os).O_DIRECTORY | cast(Any, os).O_NOFOLLOW,
                dir_fd=group_parent_fd,
            )
            try:
                kill_fd = os.open(
                    "cgroup.kill",
                    os.O_WRONLY | cast(Any, os).O_NOFOLLOW,
                    dir_fd=descriptor,
                )
                try:
                    os.write(kill_fd, b"1")
                finally:
                    os.close(kill_fd)
            finally:
                os.close(descriptor)
            deadline = time.monotonic() + 5
            while True:
                try:
                    os.rmdir(group_name, dir_fd=group_parent_fd)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(0.01)
        except FileNotFoundError:
            pass
    try:
        shutil.rmtree(name, dir_fd=parent_fd)
    except FileNotFoundError:
        pass


def _guardian_main() -> None:
    read_fd, group_pid = int(sys.argv[2]), int(sys.argv[3])
    try:
        while os.read(read_fd, 1):
            pass
    finally:
        os.close(read_fd)
    try:
        cast(Any, os).killpg(group_pid, 9)
    except ProcessLookupError:
        pass
    parent_fd, group_parent_fd = int(sys.argv[4]), int(sys.argv[6])
    try:
        _guardian_cleanup(parent_fd, sys.argv[5], group_parent_fd, sys.argv[7])
    finally:
        os.close(parent_fd)
        if group_parent_fd >= 0:
            os.close(group_parent_fd)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--guardian":
        _guardian_main()
    else:
        _worker_main()
