"""Chromium lifecycle with mandatory OS network isolation and host HTTP broker."""

import hashlib
import logging
import re
import sys
import time
import uuid
from typing import Any

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from aerobrowse.errors import AeroError
from aerobrowse.isolation import IsolatedLauncher
from aerobrowse.pruner import SemanticPruner
from aerobrowse.security import NetworkPolicy, SafeTransport

log = logging.getLogger(__name__)

# One extraction rule set; host retains actual ElementHandles, never ordinal selectors.
EXTRACT = r"""() => Array.from(document.querySelectorAll(
 'a[href],button,input:not([type="hidden"]),textarea,select,summary,[role="button"],[role="link"],[role="textbox"],[role="checkbox"],[role="combobox"],[role="radio"],[role="switch"],[role="menuitem"],[contenteditable="true"]'
)).filter(el => {
 const s=getComputedStyle(el);
 return el.isConnected && el.getClientRects().length && s.display!=='none' && s.visibility!=='hidden'
   && !el.closest('[hidden],[inert],[aria-hidden="true"]');
})"""
METADATA = r"""el => {
 const labelIds=(el.getAttribute('aria-labelledby')||'').split(/\s+/).filter(Boolean);
 const referenced=labelIds.map(id=>document.getElementById(id)?.textContent||'').join(' ');
 const labels=Array.from(el.labels||[]).map(l=>{const copy=l.cloneNode(true); copy.querySelectorAll('input,textarea,select,button').forEach(n=>n.remove()); return copy.textContent;}).join(' ');
 const tag=el.tagName.toLowerCase(), type=el.getAttribute('type')||'';
 const label=(el.getAttribute('aria-label')||referenced||labels||el.textContent||el.getAttribute('alt')||el.getAttribute('title')||el.getAttribute('placeholder')||'').trim();
 const role=el.getAttribute('role')||({a:'link',button:'button',textarea:'textbox',select:'combobox',summary:'button'}[tag])||(tag==='input'?(type==='checkbox'?'checkbox':type==='radio'?'radio':'textbox'):'');
 return {tag,element_type:tag,label,accessible_name:label,role,input_type:type,
 disabled:el.matches(':disabled')||el.getAttribute('aria-disabled')==='true',visible:true,
 value:null,checked:typeof el.checked==='boolean'?el.checked:null,
 href:el.getAttribute('href')||'',name:el.getAttribute('name')||'',
 attributes:{required:el.hasAttribute('required'),readonly:el.hasAttribute('readonly'),multiple:el.hasAttribute('multiple')}};
}"""


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
        self._actions: dict[str, tuple[Any, dict[str, Any]]] = {}
        self._digest = ""
        self._url = ""
        self._network_error: AeroError | None = None
        self._redirects = 0

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
        for handle, _ in self._actions.values():
            try:
                handle.dispose()
            except PlaywrightError:
                log.debug("action_disposal_after_navigation")
        self._actions.clear()
        self.generation = ""
        self._digest = ""

    def snapshot(self, elapsed_ms: float = 0.0) -> dict[str, Any]:
        try:
            if not self.current_page or self.current_page.is_closed():
                raise AeroError(
                    "NO_ACTIVE_PAGE", "Navigate before requesting a snapshot"
                )
            page = self._ensure_page()
            self._invalidate()
            html = page.content()
            if len(html.encode("utf-8")) > self.policy.limits.response_bytes:
                raise AeroError("HTML_TOO_LARGE", "Rendered document exceeds limit")
            parsed = self.pruner.prune(html, base_url=page.url)
            self.generation = uuid.uuid4().hex
            array = page.evaluate_handle(EXTRACT)
            properties = array.get_properties()
            actions: list[dict[str, Any]] = []
            try:
                for key, handle in properties.items():
                    element = handle.as_element()
                    if not key.isdigit() or element is None:
                        handle.dispose()
                        continue
                    metadata = element.evaluate(METADATA)
                    aid = f"{self.generation}:{len(actions) + 1}"
                    metadata.update(
                        id=aid,
                        generation=self.generation,
                        executable=not metadata["disabled"],
                    )
                    self._actions[aid] = (element, metadata)
                    actions.append(metadata)
            finally:
                array.dispose()
            self._url = page.url
            self._digest = hashlib.sha256(page.content().encode()).hexdigest()
            parsed.update(
                success=True,
                url=page.url,
                engine="fidelity",
                actions=actions,
                generation=self.generation,
                elapsed_ms=round(elapsed_ms, 2),
            )
            return parsed
        except AeroError as exc:
            return {**exc.result(), "engine": "fidelity"}
        except PlaywrightError:
            self._invalidate()
            return AeroError("SNAPSHOT_FAILED", "Browser snapshot failed").result()

    def _element(self, action_id: str, generation: str | None) -> Any:
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
        if action_id not in self._actions or not action_id.startswith(
            self.generation + ":"
        ):
            raise AeroError("STALE_ACTION_ID", "Action ID is no longer active")
        page = self._ensure_page()
        handle, metadata = self._actions[action_id]
        changed = (
            page.url != self._url
            or hashlib.sha256(page.content().encode()).hexdigest() != self._digest
        )
        if (
            changed
            or not handle.evaluate("el => el.isConnected")
            or not handle.is_visible()
        ):
            raise AeroError("STALE_ACTION_ID", "DOM changed; request a new snapshot")
        if handle.is_disabled() or metadata["disabled"]:
            raise AeroError("DISABLED_ACTION", "Element is disabled")
        return handle

    def perform(
        self,
        operation: str,
        action_id: str,
        value: Any = None,
        generation: str | None = None,
    ) -> dict[str, Any]:
        try:
            element = self._element(action_id, generation)
            if (
                isinstance(value, str)
                and len(value.encode()) > self.policy.limits.body_bytes
            ):
                raise AeroError("REQUEST_TOO_LARGE", "Action value exceeds limit")
            if operation == "click":
                element.click(timeout=5000)
            elif operation == "fill":
                if not isinstance(value, str):
                    raise AeroError("INVALID_ARGUMENT", "Fill requires a string")
                element.fill(value, timeout=5000)
            elif operation == "select":
                element.select_option(value=value, timeout=5000)
            elif operation == "check":
                if not isinstance(value, bool):
                    raise AeroError("INVALID_ARGUMENT", "Check requires a boolean")
                element.set_checked(value, timeout=5000)
            elif operation == "press":
                if (
                    not isinstance(value, str)
                    or len(value) > 64
                    or not re.fullmatch(r"[A-Za-z0-9+_-]+", value)
                ):
                    raise AeroError("INVALID_ARGUMENT", "Invalid keyboard key")
                element.press(value, timeout=5000)
            else:
                raise AeroError("UNSUPPORTED_OPERATION", "Operation is not implemented")
            return self.snapshot()
        except AeroError as exc:
            return exc.result()
        except PlaywrightError:
            return AeroError(
                "ACTION_FAILED", "Browser action failed; inspect a new snapshot"
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
            self._element(action_id, generation).wait_for_element_state(
                "visible", timeout=timeout_ms
            )
            return self.snapshot()
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
