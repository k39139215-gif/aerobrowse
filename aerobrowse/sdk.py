"""Public synchronous SDK: one owned, bounded process worker per browser."""

import base64
import threading
import time
import uuid
from typing import Any, Self

from aerobrowse.errors import AeroError
from aerobrowse.runtime import ProcessWorker, ResourceLimits, ResourcePool
from aerobrowse.security import NetworkPolicy
from aerobrowse.tokens import measure_output


class AeroBrowser:
    def __init__(
        self,
        default_mode: str = "auto",
        *,
        policy: NetworkPolicy | None = None,
        resource_limits: ResourceLimits | None = None,
        request_timeout: float = 45,
    ):
        if default_mode not in {"auto", "turbo", "fidelity"}:
            raise ValueError("default_mode must be auto, turbo or fidelity")
        if not 0 < request_timeout <= 120:
            raise ValueError("request_timeout must be between zero and 120 seconds")
        self.default_mode = default_mode
        self.policy = policy or NetworkPolicy()
        self.session_id = uuid.uuid4().hex
        self.current_url: str | None = None
        self.active_engine: str | None = None
        self.tab_id: str | None = None
        self.request_timeout = request_timeout
        self._pool = ResourcePool(
            resource_limits or ResourceLimits.from_environment(),
            allow_networks=tuple(str(n) for n in self.policy.allow_networks),
            network_limits=self.policy.limits,
            default_mode=default_mode,
        )
        self._worker = ProcessWorker(self._pool)
        self._lock = threading.RLock()
        self._closed = False
        self._created = time.monotonic()

    def _call(self, operation: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        with self._lock:
            if self._closed:
                return AeroError("RUNTIME_CLOSED", "Browser has been closed").result()
            if not self._pool.enforced and (
                self.default_mode == "fidelity" or kwargs.get("force_fidelity")
            ):
                return AeroError(
                    "RESOURCE_ISOLATION_UNAVAILABLE",
                    "Fidelity requires enforced aggregate quotas",
                ).result()
            remaining = self._pool.limits.lifetime_seconds - (
                time.monotonic() - self._created
            )
            if remaining <= 0:
                self.close()
                return AeroError(
                    "SESSION_EXPIRED", "Session lifetime exceeded; create a new browser"
                ).result()
            expired = threading.Event()

            def timeout() -> None:
                expired.set()
                self._worker.terminate()

            timer = threading.Timer(min(self.request_timeout, remaining), timeout)
            timer.daemon = True
            timer.start()
            try:
                result = self._worker.call(operation, args, kwargs)
            except AeroError as exc:
                result = exc.result()
                if exc.code.startswith("WORKER_"):
                    self.close()
            except (OSError, ValueError):
                self.close()
                result = AeroError(
                    "WORKER_CRASHED",
                    "Browser worker disconnected; create a new browser",
                ).result()
            finally:
                timer.cancel()
                timer.join()
            if expired.is_set():
                self.close()
                result = AeroError(
                    "TIMEOUT", "Request timed out; worker was terminated"
                ).result()
            result["session_id"] = self.session_id
            if result.get("success"):
                self.current_url = result.get("url", self.current_url)
                self.active_engine = result.get("engine", self.active_engine)
                self.tab_id = result.get("tab_id", self.tab_id)
            result.update(measure_output(result))
            return result

    def fetch(self, url: str, force_fidelity: bool = False) -> dict[str, Any]:
        self.current_url, self.active_engine = None, None
        return self._call("navigate", url, force_fidelity=force_fidelity)

    def snapshot(self) -> dict[str, Any]:
        return self._call("snapshot")

    def perform(
        self,
        operation: str,
        action_id: str,
        value: Any = None,
        generation: str | None = None,
    ) -> dict[str, Any]:
        return self._call("perform", operation, action_id, value, generation)

    def click(self, action_id: str, generation: str | None = None) -> dict[str, Any]:
        return self._call("click", action_id, generation=generation)

    def fill(
        self, action_id: str, text: str, generation: str | None = None
    ) -> dict[str, Any]:
        return self._call("fill", action_id, text, generation=generation)

    def select(
        self, action_id: str, value: str, generation: str | None = None
    ) -> dict[str, Any]:
        return self._call("select", action_id, value, generation=generation)

    def scroll(self, x: int = 0, y: int = 600) -> dict[str, Any]:
        return self._call("scroll", x, y)

    def wait(
        self, action_id: str, generation: str | None = None, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        return self._call("wait", action_id, generation, timeout_ms)

    def screenshot(self) -> bytes:
        result = self._call("screenshot")
        if not result.get("success"):
            error = result["error"]
            raise AeroError(error["code"], error["message"])
        return base64.b64decode(result["data"], validate=True)

    def tabs(self) -> dict[str, Any]:
        return self._call("tabs")

    def new_tab(self, url: str) -> dict[str, Any]:
        return self._call("new_tab", url)

    def switch_tab(self, tab_id: str) -> dict[str, Any]:
        return self._call("switch_tab", tab_id)

    def close_tab(self, tab_id: str) -> dict[str, Any]:
        return self._call("close_tab", tab_id)

    def back(self) -> dict[str, Any]:
        return self._call("back")

    def forward(self) -> dict[str, Any]:
        return self._call("forward")

    def reload(self) -> dict[str, Any]:
        return self._call("reload")

    def capabilities(self) -> dict[str, Any]:
        return self._call("capabilities")

    def check(
        self, action_id: str, checked: bool, generation: str | None = None
    ) -> dict[str, Any]:
        return self.perform("check", action_id, checked, generation)

    def press(
        self, action_id: str, key: str, generation: str | None = None
    ) -> dict[str, Any]:
        return self.perform("press", action_id, key, generation)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            try:
                self._worker.terminate()
            finally:
                self._pool.close()
                self.current_url, self.active_engine, self.tab_id = None, None, None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
