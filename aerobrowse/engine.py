"""Hybrid page state. Static action candidates never execute against a different DOM."""

import uuid
from threading import RLock
from typing import Any, Self

from aerobrowse.errors import AeroError
from aerobrowse.fidelity import FidelityEngine
from aerobrowse.security import NetworkPolicy
from aerobrowse.turbo import TurboEngine


class AeroBrowser:
    def __init__(
        self, default_mode: str = "auto", *, policy: NetworkPolicy | None = None
    ):
        if default_mode not in {"auto", "turbo", "fidelity"}:
            raise ValueError("default_mode must be auto, turbo or fidelity")
        self.default_mode = default_mode
        self.policy = policy or NetworkPolicy()
        self.turbo = TurboEngine(policy=self.policy)
        self._fidelity: FidelityEngine | None = None
        self.current_url: str | None = None
        self.active_engine: str | None = None
        self.session_id = uuid.uuid4().hex
        self._snapshot: dict[str, Any] | None = None
        self._lock = RLock()

    def _get_fidelity(self) -> FidelityEngine:
        if self._fidelity is None:
            self._fidelity = FidelityEngine(policy=self.policy)
        return self._fidelity

    def _remember(self, result: dict[str, Any]) -> dict[str, Any]:
        result["session_id"] = self.session_id
        if result.get("success"):
            self.current_url = result["url"]
            self.active_engine = result["engine"]
            self._snapshot = result
        return result

    def fetch(self, url: str, force_fidelity: bool = False) -> dict[str, Any]:
        with self._lock:
            # Failed navigation invalidates previous state rather than exposing it as current.
            self.current_url, self.active_engine, self._snapshot = None, None, None
            if force_fidelity or self.default_mode == "fidelity":
                return self._remember(self._get_fidelity().navigate(url))
            result = self.turbo.fetch(url)
            if (
                result.get("success")
                and result.get("needs_fidelity")
                and self.default_mode == "auto"
            ):
                return self._remember(self._get_fidelity().navigate(result["url"]))
            return self._remember(result)

    def _interactive(self) -> dict[str, Any] | None:
        if not self.current_url:
            return AeroError(
                "NO_ACTIVE_PAGE", "Navigate before performing actions"
            ).result()
        if self.active_engine != "fidelity":
            result = self._remember(self._get_fidelity().navigate(self.current_url))
            if result.get("success"):
                # Deliberate resnapshot handshake: callers must select a live action.
                result = dict(result)
                result.update(
                    success=False,
                    error={
                        "code": "STALE_ACTION_ID",
                        "message": "Page synchronized to Chromium; use the returned live action IDs",
                    },
                    synchronized=True,
                )
            return result
        return None

    def perform(
        self,
        operation: str,
        action_id: str,
        value: Any = None,
        generation: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            synchronization = self._interactive()
            if synchronization is not None:
                return synchronization
            return self._remember(
                self._get_fidelity().perform(operation, action_id, value, generation)
            )

    def click(self, action_id: str, generation: str | None = None) -> dict[str, Any]:
        return self.perform("click", action_id, generation=generation)

    def fill(
        self, action_id: str, text: str, generation: str | None = None
    ) -> dict[str, Any]:
        return self.perform("fill", action_id, text, generation)

    def select(
        self, action_id: str, value: str, generation: str | None = None
    ) -> dict[str, Any]:
        return self.perform("select", action_id, value, generation)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if self.active_engine == "turbo" and self._snapshot:
                return dict(self._snapshot)
            if self.active_engine == "fidelity":
                return self._remember(self._get_fidelity().snapshot())
            return AeroError(
                "NO_ACTIVE_PAGE", "Navigate before requesting a snapshot"
            ).result()

    def scroll(self, x: int = 0, y: int = 600) -> dict[str, Any]:
        with self._lock:
            sync = self._interactive()
            return (
                sync
                if sync is not None
                else self._remember(self._get_fidelity().scroll(x, y))
            )

    def wait(
        self, action_id: str, generation: str | None = None, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        with self._lock:
            sync = self._interactive()
            return (
                sync
                if sync is not None
                else self._remember(
                    self._get_fidelity().wait(action_id, generation, timeout_ms)
                )
            )

    def screenshot(self) -> bytes:
        with self._lock:
            sync = self._interactive()
            if sync is not None:
                error = sync.get("error", {})
                raise AeroError(
                    error.get("code", "STALE_ACTION_ID"),
                    error.get("message", "Refresh snapshot"),
                )
            return self._get_fidelity().screenshot()

    def close(self) -> None:
        with self._lock:
            if self._fidelity:
                self._fidelity.close()
                self._fidelity = None
            self.turbo.close()
            self.current_url, self.active_engine, self._snapshot = None, None, None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
