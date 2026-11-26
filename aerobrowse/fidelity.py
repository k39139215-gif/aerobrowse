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
from aerobrowse.cdp_broker import install as install_broker
from aerobrowse.errors import AeroError
from aerobrowse.isolation import IsolatedLauncher
from aerobrowse.pruner import SemanticPruner
from aerobrowse.security import NetworkPolicy, SafeTransport
from aerobrowse.tokens import measure_output

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
        self._tabs: dict[str, Any] = {}
        self._brokers: dict[Any, Any] = {}
        self._creating_page = False
        self._pending_pages: list[Any] = []
        self.max_tabs = 8

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
                self.current_context.route_web_socket("**/*", lambda ws: ws.close())
                self.current_context.on("page", self._new_page)
                self.current_page = self._open_page()
            except (AeroError, PlaywrightError):
                self.close()
                raise
        if self.current_page is None or self.current_page.is_closed():
            self.current_page = self._open_page()
        return self.current_page

    def _new_page(self, page: Any) -> None:
        # Only explicit API-created blank tabs are admitted. Page-created popups
        # remain denied even when the context already owns multiple tabs.
        if not self._creating_page or page.opener() is not None:
            page.close()
        else:
            self._pending_pages.append(page)

    def _open_page(self) -> Any:
        if len(self._tabs) >= self.max_tabs:
            raise AeroError("TAB_LIMIT", "Maximum browser tabs reached")
        self._creating_page = True
        try:
            page = self.current_context.new_page()
            self._brokers[page] = install_broker(
                page, self._broker, self._broker_failed
            )
        except PlaywrightError:
            pending, self._pending_pages = self._pending_pages, []
            for candidate in pending:
                if not candidate.is_closed():
                    candidate.close()
            raise
        finally:
            self._creating_page = False
        # A concurrent noopener popup can also have no opener. Only the exact
        # page returned by the explicit context call is admitted into the map.
        pending, self._pending_pages = self._pending_pages, []
        for candidate in pending:
            if candidate != page and not candidate.is_closed():
                candidate.close()
        if page.is_closed():
            raise AeroError("TAB_FAILED", "Browser rejected the new tab")
        tab_id = uuid.uuid4().hex
        self._tabs[tab_id] = page
        page.on("close", lambda closed_page: self._tab_closed(tab_id, closed_page))
        return page

    def _tab_closed(self, tab_id: str, page: Any) -> None:
        self._brokers.pop(page, None)
        self._tabs.pop(tab_id, None)
        if page == self.current_page:
            self._invalidate()
            self.current_page = None

    def _tab(self, tab_id: str) -> Any:
        if not isinstance(tab_id, str) or not re.fullmatch(r"[0-9a-f]{32}", tab_id):
            raise AeroError("INVALID_TAB_ID", "Use an opaque tab ID from browser_tabs")
        page = self._tabs.get(tab_id)
        if page is None or page.is_closed():
            raise AeroError("TAB_NOT_FOUND", "Tab does not exist in this session")
        return page

    def _active_tab_id(self) -> str | None:
        return next(
            (key for key, page in self._tabs.items() if page == self.current_page), None
        )

    def tabs(self) -> dict[str, Any]:
        return {
            "success": True,
            "engine": "fidelity",
            "active_tab_id": self._active_tab_id(),
            "tabs": [
                {"tab_id": key, "url": page.url, "active": page == self.current_page}
                for key, page in self._tabs.items()
                if not page.is_closed()
            ],
            "max_tabs": self.max_tabs,
        }

    def new_tab(self, url: str) -> dict[str, Any]:
        try:
            # Reject disallowed destinations before allocating any browser resources.
            self.policy.validate(url)
            if not self.browser:
                self._ensure_page()
            else:
                page = self._open_page()
                self._invalidate()
                self.current_page = page
            return self.navigate(url)
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return AeroError("TAB_FAILED", "Could not create browser tab").result()

    def switch_tab(self, tab_id: str) -> dict[str, Any]:
        try:
            page = self._tab(tab_id)
            self._invalidate()
            self.current_page = page
            return self.snapshot()
        except AeroError as exc:
            return exc.result()

    def close_tab(self, tab_id: str) -> dict[str, Any]:
        try:
            page = self._tab(tab_id)
            self._invalidate()
            page.close()
            if self.current_page is None and self._tabs:
                self.current_page = next(iter(self._tabs.values()))
            if self.current_page is not None:
                result = self.snapshot()
                result["closed_tab_id"] = tab_id
                return result
            return {**self.tabs(), "closed_tab_id": tab_id, "tab_id": None, "url": None}
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return AeroError("TAB_FAILED", "Could not close browser tab").result()

    def _history(self, direction: str) -> dict[str, Any]:
        try:
            if not self.current_page or self.current_page.is_closed():
                raise AeroError("NO_ACTIVE_PAGE", "Navigate before using history")
            page = self._ensure_page()
            self._invalidate()
            self._network_error = None
            self._redirects = 0
            # CDP distinguishes same-document history from an absent entry;
            # Playwright returns None for both cases.
            client = self.current_context.new_cdp_session(page)
            try:
                history = client.send("Page.getNavigationHistory")
            finally:
                client.detach()
            target = history["currentIndex"] + (-1 if direction == "back" else 1)
            if not 0 <= target < len(history["entries"]):
                raise AeroError(
                    "HISTORY_UNAVAILABLE", "No history entry in this direction"
                )
            self.policy.validate(history["entries"][target]["url"])
            if direction == "back":
                page.go_back(wait_until="domcontentloaded", timeout=20000)
            else:
                page.go_forward(wait_until="domcontentloaded", timeout=20000)
            if self._network_error:
                raise self._network_error
            return self.snapshot()
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return (
                self._network_error
                or AeroError("NAVIGATION_FAILED", "History navigation failed")
            ).result()

    def back(self) -> dict[str, Any]:
        return self._history("back")

    def forward(self) -> dict[str, Any]:
        return self._history("forward")

    def reload(self) -> dict[str, Any]:
        try:
            if not self.current_page or self.current_page.is_closed():
                raise AeroError("NO_ACTIVE_PAGE", "Navigate before reloading")
            self._invalidate()
            self._network_error = None
            self._redirects = 0
            self.current_page.reload(wait_until="domcontentloaded", timeout=20000)
            if self._network_error:
                raise self._network_error
            return self.snapshot()
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            self._invalidate()
            return AeroError(
                "NAVIGATION_FAILED", "Reload failed; request a fresh snapshot"
            ).result()

    def _broker_failed(self, error: AeroError) -> None:
        self._network_error = error

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
            response = self.transport._browser_request(
                request.url,
                method=request.method,
                # The abbreviated headers property omits security-sensitive cookies.
                # Chromium computes credentials per destination, including redirects.
                headers=request.all_headers(),
                body=request.post_data_buffer or b"",
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
            if response.set_cookies:
                # Playwright's HAR router uses this representation for repeated
                # Set-Cookie fields. Chromium, rather than a host-side jar, applies
                # HttpOnly, domain/path, Secure, SameSite and expiry restrictions.
                headers["set-cookie"] = "\n".join(response.set_cookies)
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
            if not live["url"].startswith(("http://", "https://")):
                raise AeroError(
                    "NAVIGATION_FAILED", "Browser has no supported live HTTP document"
                )
            if self._network_error:
                raise self._network_error
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
                tab_id=self._active_tab_id(),
            )
            parsed.update(measure_output(parsed))
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
        self,
        action_id: str | None = None,
        generation: str | None = None,
        timeout_ms: int = 5000,
        *,
        name: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        """Validate an existing ID, or discover an enabled control by exact name."""
        try:
            roles = {
                "button",
                "link",
                "textbox",
                "checkbox",
                "radio",
                "combobox",
                "switch",
                "menuitem",
            }
            if (
                type(timeout_ms) is not int
                or not 1 <= timeout_ms <= 30000
                or (name is None and (action_id is None or role is not None))
                or (
                    name is not None
                    and (
                        not isinstance(name, str)
                        or not name.strip()
                        or len(name) > 512
                        or action_id is not None
                        or generation is not None
                    )
                )
                or (
                    role is not None
                    and (not isinstance(role, str) or role not in roles)
                )
            ):
                raise AeroError(
                    "INVALID_ARGUMENT",
                    "Provide an action ID or bounded exact accessible name",
                )
            if name is None:
                return self.perform("wait", str(action_id), generation=generation)
            if not self.current_page or self.current_page.is_closed():
                raise AeroError("NO_ACTIVE_PAGE", "Navigate before waiting")
            page = self._ensure_page()
            session = page.context.new_cdp_session(page)
            try:
                document = session.send("Page.getFrameTree")["frameTree"]["frame"]
                identity = (document["id"], document.get("loaderId"))
                deadline = time.monotonic() + timeout_ms / 1000
                while True:
                    frame = session.send("Page.getFrameTree")["frameTree"]["frame"]
                    if (frame["id"], frame.get("loaderId")) != identity:
                        self._invalidate()
                        raise AeroError(
                            "PAGE_NAVIGATED",
                            "Document changed during wait; request a fresh snapshot",
                        )
                    snapshot = self.snapshot()
                    if not snapshot.get("success"):
                        return snapshot
                    frame = session.send("Page.getFrameTree")["frameTree"]["frame"]
                    if (frame["id"], frame.get("loaderId")) != identity:
                        self._invalidate()
                        raise AeroError(
                            "PAGE_NAVIGATED",
                            "Document changed during wait; request a fresh snapshot",
                        )
                    matches = [
                        a["id"]
                        for a in snapshot["actions"]
                        if a["accessible_name"] == name
                        and a["executable"]
                        and (role is None or a["role"] == role)
                    ]
                    if matches:
                        snapshot["wait"] = {"matched_action_ids": matches}
                        snapshot.update(measure_output(snapshot))
                        return snapshot
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AeroError(
                            "WAIT_TIMEOUT",
                            "No matching enabled control appeared before the deadline",
                        )
                    page.wait_for_timeout(min(50, remaining * 1000))
            finally:
                try:
                    session.detach()
                except PlaywrightError:
                    log.debug("wait_context_closed")
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            self._invalidate()
            return AeroError(
                "PAGE_NAVIGATED", "Document changed or browser terminated during wait"
            ).result()

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
        self._tabs.clear()
        self._brokers.clear()
        self._pending_pages.clear()
        self.launcher.close()
