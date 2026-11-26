import asyncio

import pytest


def test_sessions_require_owner_and_capability():
    from aerobrowse.sessions import SessionManager

    async def run():
        manager = SessionManager(max_sessions=2)
        sid = await manager.create("client-a")
        denied = await manager.call("client-b", sid, "snapshot")
        assert denied["error"]["code"] == "SESSION_NOT_FOUND"
        own = await manager.call("client-a", sid, "snapshot")
        assert own["error"]["code"] == "NO_ACTIVE_PAGE"
        await manager.close_all()
        assert manager.active_sessions == 0

    asyncio.run(run())


def test_capacity_and_concurrent_snapshots():
    from aerobrowse.sessions import SessionManager

    async def run():
        manager = SessionManager(max_sessions=1)
        sid = await manager.create("client-a")
        from aerobrowse.errors import AeroError

        with pytest.raises(AeroError) as error:
            await manager.create("client-b")
        assert error.value.code == "SESSION_LIMIT"
        results = await asyncio.gather(
            *(manager.call("client-a", sid, "snapshot") for _ in range(5))
        )
        assert all(r["error"]["code"] == "NO_ACTIVE_PAGE" for r in results)
        await manager.close_all()

    asyncio.run(run())


def test_retiring_worker_remains_capacity_accounted():
    from threading import Event

    from aerobrowse.errors import AeroError
    from aerobrowse.sessions import SessionManager

    async def run():
        manager = SessionManager(max_sessions=1, request_timeout=0.02)
        sid = await manager.create("owner")
        release = Event()
        worker = manager._sessions[sid].worker
        blocker = asyncio.get_running_loop().run_in_executor(worker, release.wait, 1)
        try:
            result = await manager.close("owner", sid)
            assert result["error"]["code"] == "CLEANUP_PENDING"
            assert manager.active_sessions == 1
            with pytest.raises(AeroError) as error:
                await manager.create("next")
            assert error.value.code == "SESSION_LIMIT"
        finally:
            release.set()
            await blocker
            for _ in range(20):
                if manager.active_sessions == 0:
                    break
                await asyncio.sleep(0.01)
        assert manager.active_sessions == 0

    asyncio.run(run())


def test_bounded_session_queue():
    from aerobrowse.sessions import SessionManager

    async def run():
        manager = SessionManager(max_sessions=1)
        sid = await manager.create("owner")
        session = manager._sessions[sid]
        await session.lock.acquire()
        tasks = [
            asyncio.create_task(manager.call("owner", sid, "snapshot"))
            for _ in range(17)
        ]
        await asyncio.sleep(0.02)
        session.lock.release()
        results = await asyncio.gather(*tasks)
        assert (
            sum(r.get("error", {}).get("code") == "SESSION_BUSY" for r in results) == 1
        )
        await manager.close_all()

    asyncio.run(run())
