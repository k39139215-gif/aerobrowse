"""Owned browser sessions. A dedicated thread preserves sync Playwright affinity."""

import asyncio
import json
import logging
import secrets
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from aerobrowse.engine import AeroBrowser
from aerobrowse.errors import AeroError

log = logging.getLogger("aerobrowse.requests")


@dataclass
class Session:
    owner: str
    worker: ThreadPoolExecutor
    browser: AeroBrowser | None = None
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)
    closed: bool = False


class SessionManager:
    def __init__(
        self,
        max_sessions: int = 8,
        idle_timeout: float = 300,
        request_timeout: float = 45,
    ):
        if (
            not 1 <= max_sessions <= 64
            or not 0 < idle_timeout <= 3600
            or not 0 < request_timeout <= 120
        ):
            raise ValueError("Invalid session limits")
        self.max_sessions, self.idle_timeout, self.request_timeout = (
            max_sessions,
            idle_timeout,
            request_timeout,
        )
        self._sessions: dict[str, Session] = {}
        self.metrics: dict[str, int] = {
            "requests": 0,
            "failures": 0,
            "cancelled": 0,
            "timeouts": 0,
        }

    @property
    def active_sessions(self) -> int:
        return len(self._sessions)

    async def create(self, owner: str) -> str:
        if not owner:
            raise AeroError(
                "SESSION_OWNER_REQUIRED", "Transport session identity is required"
            )
        await self.expire()
        if self.active_sessions >= self.max_sessions:
            raise AeroError("SESSION_LIMIT", "Maximum browser sessions reached")
        sid = secrets.token_urlsafe(32)
        self._sessions[sid] = Session(
            owner, ThreadPoolExecutor(max_workers=1, thread_name_prefix="aero-session")
        )
        return sid

    def _owned(self, owner: str, sid: str) -> Session:
        session = self._sessions.get(sid)
        if (
            not session
            or session.closed
            or not secrets.compare_digest(session.owner, owner)
        ):
            raise AeroError(
                "SESSION_NOT_FOUND",
                "Session does not exist or is not owned by this client",
            )
        return session

    async def call(
        self, owner: str, sid: str, operation: str, *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        request_id, start = uuid.uuid4().hex, time.monotonic()
        result: dict[str, Any]
        try:
            session = self._owned(owner, sid)
            if time.monotonic() - session.last_used > self.idle_timeout:
                await self.close(owner, sid)
                raise AeroError("SESSION_EXPIRED", "Session expired")
            # Bounded queue: waiting calls time out before entering the single worker.
            async with asyncio.timeout(self.request_timeout):
                async with session.lock:
                    self._owned(owner, sid)
                    session.last_used = time.monotonic()
                    loop = asyncio.get_running_loop()

                    def execute() -> dict[str, Any]:
                        if session.browser is None:
                            session.browser = AeroBrowser()
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
                            raise AeroError(
                                "UNSUPPORTED_OPERATION", "Unknown browser operation"
                            )
                        value = getattr(session.browser, methods[operation])(
                            *args, **kwargs
                        )
                        if operation == "screenshot":
                            import base64

                            return {
                                "success": True,
                                "mime_type": "image/png",
                                "data": base64.b64encode(value).decode(),
                            }
                        return value

                    future = loop.run_in_executor(session.worker, execute)
                    result = await asyncio.shield(future)
                    session.last_used = time.monotonic()
        except AeroError as exc:
            result = exc.result()
        except TimeoutError:
            self.metrics["timeouts"] += 1
            await self.close(owner, sid)
            result = AeroError(
                "TIMEOUT", "Request timed out; session was closed"
            ).result()
        except asyncio.CancelledError:
            self.metrics["cancelled"] += 1
            await self.close(owner, sid)
            raise
        except Exception:  # noqa: BLE001 - untrusted protocol boundary with safe serialization
            # Protocol boundary: fixed message; no raw exception strings, paths or values.
            log.error(
                json.dumps(
                    {
                        "request_id": request_id,
                        "operation": operation,
                        "error_code": "INTERNAL_ERROR",
                    }
                )
            )
            await self.close(owner, sid)
            result = AeroError("INTERNAL_ERROR", "Browser request failed").result()
        result.update(request_id=request_id, session_id=sid)
        self.metrics["requests"] += 1
        if not result.get("success"):
            self.metrics["failures"] += 1
        log.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "session_id": sid,
                    "operation": operation,
                    "engine": result.get("engine"),
                    "duration_ms": round((time.monotonic() - start) * 1000, 2),
                    "outcome": "success" if result.get("success") else "error",
                    "error_code": result.get("error", {}).get("code"),
                }
            )
        )
        return result

    async def close(self, owner: str, sid: str) -> dict[str, Any]:
        try:
            session = self._owned(owner, sid)
        except AeroError as exc:
            return exc.result()
        session.closed = True
        self._sessions.pop(sid, None)

        def cleanup() -> None:
            if session.browser:
                session.browser.close()
                session.browser = None

        future = asyncio.get_running_loop().run_in_executor(session.worker, cleanup)
        # Cleanup queues behind any cancelled operation; do not shut down its thread mid-browser call.
        try:
            await asyncio.wait_for(asyncio.shield(future), timeout=self.request_timeout)
        except TimeoutError:
            log.error(
                json.dumps(
                    {
                        "session_id": sid,
                        "operation": "close",
                        "error_code": "CLEANUP_PENDING",
                    }
                )
            )
        finally:
            session.worker.shutdown(wait=False, cancel_futures=False)
        return {"success": True, "session_id": sid}

    async def expire(self) -> None:
        for sid, session in list(self._sessions.items()):
            if (
                not session.lock.locked()
                and time.monotonic() - session.last_used > self.idle_timeout
            ):
                await self.close(session.owner, sid)

    async def close_all(self) -> None:
        await asyncio.gather(
            *(self.close(s.owner, sid) for sid, s in list(self._sessions.items()))
        )
