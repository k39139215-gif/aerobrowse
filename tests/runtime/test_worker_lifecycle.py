"""Real worker processes: lifecycle and cleanup assertions do not mock the worker."""

import asyncio
import os

import psutil

from aerobrowse.runtime import ProcessWorker, ResourcePool, WorkerState
from aerobrowse.sessions import SessionManager


def test_worker_state_and_pid_reaped():
    pool = ResourcePool()
    worker = ProcessWorker(pool)
    assert worker.state == WorkerState.CREATED
    try:
        result = worker.call("snapshot", (), {})
        assert result["error"]["code"] == "NO_ACTIVE_PAGE"
        assert worker.state == WorkerState.READY
        pid = worker.pid
        assert pid != os.getpid() and psutil.pid_exists(pid)
        directory = worker.directory.name
    finally:
        worker.terminate()
        pool.close()
    assert worker.state == WorkerState.TERMINATED
    assert not psutil.pid_exists(pid)
    assert not os.path.exists(directory)


def test_repeated_sessions_release_processes_and_slots():
    async def run():
        manager = SessionManager(max_sessions=1)
        processes = []
        for _ in range(5):
            sid = await manager.create("owner")
            result = await manager.call("owner", sid, "snapshot")
            assert result["error"]["code"] == "NO_ACTIVE_PAGE"
            processes.append(psutil.Process(manager._sessions[sid].worker.pid))
            assert (await manager.close("owner", sid))["success"]
            assert manager.active_sessions == 0
        await manager.close_all()
        assert not any(process.is_running() for process in processes)

    asyncio.run(run())


def test_idle_session_is_reaped_without_new_requests():
    async def run():
        manager = SessionManager(idle_timeout=0.05)
        sid = await manager.create("owner")
        await asyncio.sleep(0.2)
        assert manager.active_sessions == 0
        assert sid not in manager._sessions
        await manager.close_all()

    asyncio.run(run())


def test_terminated_created_worker_cannot_later_launch():
    pool = ResourcePool()
    worker = ProcessWorker(pool)
    worker.terminate()
    try:
        import pytest

        from aerobrowse.errors import AeroError

        with pytest.raises(AeroError) as error:
            worker.call("snapshot", (), {})
        assert error.value.code == "WORKER_CRASHED"
        assert worker.process is None
    finally:
        pool.close()


def test_closed_manager_cannot_reopen_without_resource_controls():
    import pytest

    from aerobrowse.errors import AeroError

    async def run():
        manager = SessionManager()
        await manager.close_all()
        with pytest.raises(AeroError) as error:
            await manager.create("owner")
        assert error.value.code == "RUNTIME_CLOSED"

    asyncio.run(run())


def test_pool_cannot_create_workers_after_shutdown():
    import pytest

    from aerobrowse.errors import AeroError

    pool = ResourcePool()
    pool.close()
    with pytest.raises(AeroError) as error:
        pool.session()
    assert error.value.code == "RUNTIME_CLOSED"
