"""Chromium lifecycle with mandatory OS network isolation and host HTTP broker."""

import logging
import re
import sys
import time
import uuid
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from aerobrowse.actions import ActionContext
from aerobrowse.errors import AeroError
from aerobrowse.isolation import IsolatedLauncher
from aerobrowse.pruner import SemanticPruner
from aerobrowse.security import NetworkPolicy, SafeTransport

log = logging.getLogger(__name__)


class FidelityEngine:
    def __init__(
        self,
        headless: bool = True,
        block_heavy_resources: bool = False,
        *,
        policy: NetworkPolicy | None = None,
    ):
        self.policy = policy or NetworkPolicy()
        self.transport = SafeTransport(self.policy)
        self.headless, self.block_heavy = headless, block_heavy_resources
        self.playwright: Any = None
        self.browser: Any = None
        self.current_context: Any = None
        self.current_page: Any = None
        self.launcher = IsolatedLauncher()
        self.pruner = SemanticPruner()
        self.generation = ""
        self._network_error: AeroError | None = None
        self._redirects = 0
        self._action_context: ActionContext | None = None

    def _ensure_page(self) -> Any:
        if self.browser and not self.browser.is_connected():
            self.close()
            raise AeroError(
                "BROWSER_CRASHED",
                "Browser terminated; navigate to recreate the session",
            )
        if not self.browser:
            try:
                if sys.platform != "linux":
                    raise AeroError(
                        "NETWORK_ISOLATION_UNAVAILABLE",
                        "Fidelity requires Linux network namespaces",
                    )
                self.playwright = sync_playwright().start()
                launcher = self.launcher.create(
                    self.playwright.chromium.executable_path
                )
                self.browser = self.playwright.chromium.launch(
                    executable_path=launcher,
                    headless=self.headless,
                    timeout=15000,
                    args=[
                        "--disable-background-networking",
                        "--disable-extensions",
                        "--disable-quic",
                        "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                    ],
                )
                self.current_context = self.browser.new_context(
                    accept_downloads=False,
                    service_workers="block",
                    viewport={"width": 1280, "height": 800},
                )
                self.current_context.set_default_timeout(5000)
                self.current_context.route("**/*", self._broker)
                self.current_context.route_web_socket("**/*", lambda ws: ws.close())
                self.current_context.on("page", self._new_page)
                self.current_page = self.current_context.new_page()
            except (AeroError, PlaywrightError):
                self.close()
                raise
        return self.current_page

    def _new_page(self, page: Any) -> None:
        # Popups are denied; a single active tab is the implemented contract.
        if self.current_page is not None and page != self.current_page:
            page.close()

    def _broker(self, route: Any) -> None:
        try:
            request = route.request
            if request.redirected_from:
                self._redirects += 1
                if self._redirects > self.policy.limits.redirects:
                    raise AeroError(
                        "TOO_MANY_REDIRECTS", "Browser redirect limit exceeded"
                    )
            if self.block_heavy and request.resource_type in {"image", "media", "font"}:
                route.abort("blockedbyclient")
                return
            response = self.transport.request(
                request.url,
                method=request.method,
                headers=request.headers,
                body=request.post_data_buffer or b"",
                follow_redirects=False,
            )
            headers = {
                k: v
                for k, v in response.headers.items()
                if k
                not in {
                    "content-length",
                    "transfer-encoding",
                    "connection",
                    "content-encoding",
                    "set-cookie",
                }
            }
            route.fulfill(status=response.status, headers=headers, body=response.body)
        except AeroError as exc:
            self._network_error = exc
            route.abort("blockedbyclient")
        except PlaywrightError:
            log.warning(
                "broker_route_closed", extra={"error_code": "BROWSER_ROUTE_CLOSED"}
            )

    def navigate(
        self, url: str, wait_until: str = "domcontentloaded", timeout_ms: int = 20000
    ) -> dict[str, Any]:
        start = time.monotonic()
        try:
            if (
                wait_until not in {"commit", "domcontentloaded", "load", "networkidle"}
                or not 1 <= timeout_ms <= 30000
            ):
                raise AeroError(
                    "INVALID_ARGUMENT", "Invalid navigation wait or timeout"
                )
            self.policy.validate(url)
            self._invalidate()
            self._network_error = None
            self._redirects = 0
            page = self._ensure_page()
            page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            if self._network_error:
                raise self._network_error
            return self.snapshot(elapsed_ms=(time.monotonic() - start) * 1000)
        except AeroError as exc:
            return {**exc.result(), "engine": "fidelity"}
        except PlaywrightError:
            error = self._network_error or AeroError(
                "NAVIGATION_FAILED", "Browser navigation failed"
            )
            log.warning("navigation_failed", extra={"error_code": error.code})
            return {**error.result(), "engine": "fidelity"}

    def _invalidate(self) -> None:
        self.generation = ""
        if self._action_context is not None:
            try:
                self._action_context.close()
            except PlaywrightError:
                log.debug("action_context_close_after_navigation")
            self._action_context = None

    def snapshot(self, elapsed_ms: float = 0.0) -> dict[str, Any]:
        try:
            if not self.current_page or self.current_page.is_closed():
                raise AeroError(
                    "NO_ACTIVE_PAGE", "Navigate before requesting a snapshot"
                )
            page = self._ensure_page()
            self._invalidate()
            self._action_context = ActionContext(page)
            self.generation = uuid.uuid4().hex
            live = self._action_context.snapshot(
                self.generation, self.policy.limits.response_bytes
            )
            if live.get("error"):
                self._invalidate()
                raise AeroError("HTML_TOO_LARGE", "Rendered document exceeds limit")
            html = live["html"]
            if len(html.encode("utf-8")) > self.policy.limits.response_bytes:
                self._invalidate()
                raise AeroError("HTML_TOO_LARGE", "Rendered document exceeds limit")
            parsed = self.pruner.prune(html, base_url=live["url"])
            parsed.update(
                success=True,
                url=live["url"],
                engine="fidelity",
                actions=live["actions"],
                generation=self.generation,
                elapsed_ms=round(elapsed_ms, 2),
                input_mode="synthetic_dom",
            )
            return parsed
        except AeroError as exc:
            return {**exc.result(), "engine": "fidelity"}
        except PlaywrightError:
            self._invalidate()
            return AeroError("SNAPSHOT_FAILED", "Browser snapshot failed").result()

    def _validate_action(self, action_id: str, generation: str | None) -> None:
        if not isinstance(action_id, str) or not re.fullmatch(
            r"[0-9a-f]{32}:[1-9][0-9]{0,5}", action_id
        ):
            raise AeroError(
                "INVALID_ACTION_ID", "Use an action ID returned by the active snapshot"
            )
        if generation is not None and generation != self.generation:
            raise AeroError(
                "STALE_ACTION_ID", "Snapshot generation is no longer active"
            )
        if not action_id.startswith(self.generation + ":"):
            raise AeroError("STALE_ACTION_ID", "Action ID is no longer active")

    def perform(
        self,
        operation: str,
        action_id: str,
        value: Any = None,
        generation: str | None = None,
    ) -> dict[str, Any]:
        try:
            self._validate_action(action_id, generation)
            self._ensure_page()
            if (
                isinstance(value, str)
                and len(value.encode()) > self.policy.limits.body_bytes
            ):
                raise AeroError("REQUEST_TOO_LARGE", "Action value exceeds limit")
            if operation in {"fill", "select", "press"} and not isinstance(value, str):
                raise AeroError("INVALID_ARGUMENT", "Action requires a string")
            if operation == "check" and not isinstance(value, bool):
                raise AeroError("INVALID_ARGUMENT", "Check requires a boolean")
            if self._action_context is None:
                raise AeroError("STALE_ACTION_ID", "Request a current snapshot")
            result = self._action_context.perform(
                action_id, generation or self.generation, operation, value
            )
            if not result.get("success"):
                return result
            return self.snapshot()
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            self._invalidate()
            return AeroError(
                "PAGE_NAVIGATED", "Browser document changed or terminated during action"
            ).result()

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

    def scroll(self, x: int = 0, y: int = 600) -> dict[str, Any]:
        try:
            if (
                not isinstance(x, int)
                or not isinstance(y, int)
                or max(abs(x), abs(y)) > 10000
            ):
                raise AeroError("INVALID_ARGUMENT", "Scroll distance exceeds limit")
            if not self.current_page:
                raise AeroError("NO_ACTIVE_PAGE", "Navigate before scrolling")
            self._ensure_page().evaluate("([x,y]) => window.scrollBy(x,y)", [x, y])
            return self.snapshot()
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return AeroError("ACTION_FAILED", "Scroll failed").result()

    def wait(
        self, action_id: str, generation: str | None = None, timeout_ms: int = 5000
    ) -> dict[str, Any]:
        try:
            if not 1 <= timeout_ms <= 30000:
                raise AeroError("INVALID_ARGUMENT", "Wait timeout exceeds limit")
            return self.perform("wait", action_id, generation=generation)
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return AeroError("TIMEOUT", "Element wait timed out").result()

    def screenshot(self) -> bytes:
        if not self.current_page:
            raise AeroError("NO_ACTIVE_PAGE", "Navigate before taking a screenshot")
        image = self._ensure_page().screenshot(
            type="png", full_page=False, timeout=5000
        )
        if len(image) > self.policy.limits.response_bytes:
            raise AeroError("RESPONSE_TOO_LARGE", "Screenshot exceeds limit")
        return image

    def close(self) -> None:
        self._invalidate()
        for name in ("current_context", "browser", "playwright"):
            resource = getattr(self, name)
            setattr(self, name, None)
            if resource:
                try:
                    resource.stop() if name == "playwright" else resource.close()
                except PlaywrightError:
                    log.warning(
                        "browser_cleanup_failed", extra={"error_code": "CLEANUP_FAILED"}
                    )
        self.current_page = None
        self.launcher.close()
