"""Hybrid page state. Static action candidates never execute against a different DOM."""

import uuid
from threading import RLock
from typing import Any, Self

from aerobrowse.errors import AeroError
from aerobrowse.fidelity import FidelityEngine
from aerobrowse.security import NetworkPolicy
from aerobrowse.tokens import measure_output
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
        if not result.get("success") and self._fidelity is not None:
            result.setdefault("tab_id", self._fidelity._active_tab_id())
            result.setdefault("url", self.current_url)
            result.setdefault("generation", self._fidelity.generation or None)
            result["recovery"] = self.capabilities()["recovery"].get(
                result.get("error", {}).get("code"),
                "Inspect capabilities or navigate to an owned page",
            )
        if result.get("success"):
            self.current_url = result["url"]
            self.active_engine = result["engine"]
            self._snapshot = result
        result.update(measure_output(result))
        return result

    def fetch(self, url: str, force_fidelity: bool = False) -> dict[str, Any]:
        with self._lock:
            # Failed navigation invalidates previous state rather than exposing it as current.
            self.current_url, self.active_engine, self._snapshot = None, None, None
            if (
                force_fidelity
                or self.default_mode == "fidelity"
                or (self._fidelity is not None and self._fidelity.tabs()["tabs"])
            ):
                # After escalation, navigation stays in the active live tab.
                # Returning to stateless HTTP would discard its cookies/history
                # and advertise a different page from the visible tab map.
                return self._remember(self._get_fidelity().navigate(url))
            result = self.turbo.fetch(url)
            if (
                result.get("success")
                and result.get("needs_fidelity")
                and self.default_mode == "auto"
            ):
                fallback = self._get_fidelity().navigate(result["url"])
                fallback["fallback_reason"] = "dynamic_content"
                return self._remember(fallback)
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
        self,
        action_id: str | None = None,
        generation: str | None = None,
        timeout_ms: int = 5000,
        *,
        name: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            sync = self._interactive()
            return (
                sync
                if sync is not None
                else self._remember(
                    self._get_fidelity().wait(
                        action_id, generation, timeout_ms, name=name, role=role
                    )
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

    def tabs(self) -> dict[str, Any]:
        with self._lock:
            return {**self._get_fidelity().tabs(), "session_id": self.session_id}

    def new_tab(self, url: str) -> dict[str, Any]:
        with self._lock:
            fidelity = self._get_fidelity()
            try:
                self.policy.validate(url)
            except AeroError as exc:
                return exc.result()
            if len(fidelity.tabs()["tabs"]) >= fidelity.max_tabs:
                return AeroError("TAB_LIMIT", "Maximum browser tabs reached").result()
            if self.active_engine == "turbo" and self.current_url:
                synchronized = fidelity.navigate(self.current_url)
                if not synchronized.get("success"):
                    return synchronized
                self._remember(synchronized)
            result = fidelity.new_tab(url)
            if not result.get("success") and fidelity.current_page is not None:
                # A failed tab navigation must never leave a previous snapshot
                # advertised as the current live document.
                self.current_url, self.active_engine, self._snapshot = None, None, None
            return self._remember(result)

    def switch_tab(self, tab_id: str) -> dict[str, Any]:
        with self._lock:
            return self._remember(self._get_fidelity().switch_tab(tab_id))

    def close_tab(self, tab_id: str) -> dict[str, Any]:
        with self._lock:
            result = self._get_fidelity().close_tab(tab_id)
            if result.get("success") and result.get("tab_id") is None:
                self.current_url, self.active_engine, self._snapshot = None, None, None
                return {**result, "session_id": self.session_id}
            return self._remember(result)

    def _history(self, direction: str) -> dict[str, Any]:
        with self._lock:
            if self.active_engine != "fidelity":
                return AeroError(
                    "NO_ACTIVE_PAGE", "History requires an active Chromium tab"
                ).result()
            result = getattr(self._get_fidelity(), direction)()
            if (
                not result.get("success")
                and result.get("error", {}).get("code") != "HISTORY_UNAVAILABLE"
            ):
                self.current_url, self.active_engine, self._snapshot = None, None, None
            return self._remember(result)

    def back(self) -> dict[str, Any]:
        return self._history("back")

    def forward(self) -> dict[str, Any]:
        return self._history("forward")

    def reload(self) -> dict[str, Any]:
        with self._lock:
            if self.active_engine == "turbo" and self.current_url:
                return self.fetch(self.current_url)
            if self._fidelity is None:
                return AeroError("NO_ACTIVE_PAGE", "Navigate before reloading").result()
            return self._remember(self._fidelity.reload())

    @staticmethod
    def capabilities() -> dict[str, Any]:
        return {
            "success": True,
            "operations": [
                "navigate",
                "snapshot",
                "click",
                "fill",
                "select",
                "check",
                "press",
                "scroll",
                "wait",
                "screenshot",
                "tabs",
                "new_tab",
                "switch_tab",
                "close_tab",
                "back",
                "forward",
                "reload",
                "close",
            ],
            "max_tabs": 8,
            "input_mode": "synthetic_dom",
            "wait_semantics": "Existing ID validates identity immediately; name/role waits for an enabled control and returns fresh IDs without execution",
            "keyboard_semantics": "Synthetic keydown/keyup; Enter on text input submits owning form if not prevented; no physical default navigation",
            "keys": [
                "Enter",
                "Escape",
                "ArrowUp",
                "ArrowDown",
                "ArrowLeft",
                "ArrowRight",
                "Home",
                "End",
            ],
            "cookies": "ephemeral context-scoped; shared only within owning session",
            "unsupported": [
                "trusted physical input",
                "file uploads",
                "downloads",
                "WebSocket",
                "service workers",
                "HTTP Authorization",
            ],
            "recovery": {
                "STALE_ACTION_ID": "Request browser_snapshot and choose a new action; IDs are never remapped",
                "TAB_NOT_FOUND": "List owned tabs and select a returned tab ID",
                "TIMEOUT": "Worker and session are retired; create a new session and log in again",
                "PAGE_NAVIGATED": "Request browser_snapshot; navigate again if no active page",
            },
        }

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
