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
