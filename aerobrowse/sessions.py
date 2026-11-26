"""Owned sessions with serialized, killable process workers and bounded admission."""

import asyncio
import json
import logging
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from aerobrowse.errors import AeroError
from aerobrowse.runtime import ProcessWorker, ResourceLimits, ResourcePool

log = logging.getLogger("aerobrowse.requests")


@dataclass
class Session:
    owner: str
    worker: ProcessWorker
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    last_used: float = field(default_factory=time.monotonic)
    created: float = field(default_factory=time.monotonic)
    closed: bool = False
    pending: int = 0


class SessionManager:
    def __init__(
        self,
        max_sessions: int = 8,
        idle_timeout: float = 300,
        request_timeout: float = 45,
        *,
        resource_limits: ResourceLimits | None = None,
        allow_networks: tuple[str, ...] = (),
    ):
        if (
            not 1 <= max_sessions <= 64
            or not 0 < idle_timeout <= 3600
            or not 0 < request_timeout <= 120
        ):
            raise ValueError("Invalid session limits")
        self.max_sessions = max_sessions
        self.idle_timeout = idle_timeout
        self.request_timeout = request_timeout
        self.pool = ResourcePool(resource_limits, allow_networks=allow_networks)
        self._sessions: dict[str, Session] = {}
        self._retiring: dict[str, Session] = {}
        self._reaper: asyncio.Task | None = None
        self.metrics = {"requests": 0, "failures": 0, "cancelled": 0, "timeouts": 0}

    @property
    def active_sessions(self) -> int:
        return len(self._sessions) + len(self._retiring)

    async def create(self, owner: str) -> str:
        if not owner:
            raise AeroError(
                "SESSION_OWNER_REQUIRED", "Transport session identity is required"
            )
        await self.expire()
        if self.active_sessions >= self.max_sessions:
            raise AeroError("SESSION_LIMIT", "Maximum browser sessions reached")
        sid = secrets.token_urlsafe(32)
        self._sessions[sid] = Session(owner, ProcessWorker(self.pool))
        if self._reaper is None or self._reaper.done():
            self._reaper = asyncio.create_task(self._reap())
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
        admitted: Session | None = None
        try:
            session = self._owned(owner, sid)
            if self._expired(session):
                await self.close(owner, sid)
                raise AeroError("SESSION_EXPIRED", "Session expired")
            if session.pending >= 16:
                raise AeroError("SESSION_BUSY", "Session request queue is full")
            session.pending += 1
            admitted = session
            async with asyncio.timeout(self.request_timeout), session.lock:
                self._owned(owner, sid)
                session.last_used = time.monotonic()
                remaining_lifetime = self.pool.limits.lifetime_seconds - (
                    time.monotonic() - session.created
                )
                async with asyncio.timeout(remaining_lifetime):
                    result = await asyncio.to_thread(
                        session.worker.call, operation, args, kwargs
                    )
                session.last_used = time.monotonic()
        except AeroError as exc:
            result = exc.result()
            if exc.code.startswith("WORKER_"):
                await self.close(owner, sid)
        except TimeoutError:
            self.metrics["timeouts"] += 1
            await self.close(owner, sid)
            result = AeroError(
                "TIMEOUT", "Request timed out; worker was terminated"
            ).result()
        except asyncio.CancelledError:
            self.metrics["cancelled"] += 1
            await self.close(owner, sid)
            raise
        except Exception:
            log.exception(
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
        finally:
            if admitted is not None:
                admitted.pending -= 1
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

    def _expired(self, session: Session) -> bool:
        now = time.monotonic()
        return (
            now - session.last_used > self.idle_timeout
            or now - session.created > self.pool.limits.lifetime_seconds
        )

    async def close(self, owner: str, sid: str) -> dict[str, Any]:
        try:
            session = self._owned(owner, sid)
        except AeroError as exc:
            return exc.result()
        session.closed = True
        self._sessions.pop(sid)
        self._retiring[sid] = session
        cleanup = asyncio.create_task(asyncio.to_thread(session.worker.terminate))

        def completed(task: asyncio.Task) -> None:
            if not task.cancelled() and task.exception() is None:
                self._retiring.pop(sid, None)

        cleanup.add_done_callback(completed)
        try:
            # Shield kernel termination from caller cancellation; retain slot until completion.
            await asyncio.shield(cleanup)
        except (AeroError, OSError):
            log.error(
                json.dumps(
                    {
                        "session_id": sid,
                        "operation": "close",
                        "error_code": "CLEANUP_FAILED",
                    }
                )
            )
            return AeroError(
                "CLEANUP_FAILED", "Worker termination could not be verified"
            ).result()
        self._retiring.pop(sid, None)
        return {"success": True, "session_id": sid}

    async def expire(self) -> None:
        for sid, session in list(self._sessions.items()):
            if not session.lock.locked() and self._expired(session):
                await self.close(session.owner, sid)

    async def _reap(self) -> None:
        while self._sessions:
            await asyncio.sleep(
                min(1, self.idle_timeout, self.pool.limits.lifetime_seconds)
            )
            await self.expire()

    async def close_all(self) -> None:
        if self._reaper and self._reaper is not asyncio.current_task():
            self._reaper.cancel()
            try:
                await self._reaper
            except asyncio.CancelledError:
                log.debug("session_reaper_stopped")
        await asyncio.gather(
            *(
                self.close(session.owner, sid)
                for sid, session in list(self._sessions.items())
            )
        )
        if not self._retiring:
            self.pool.close()
