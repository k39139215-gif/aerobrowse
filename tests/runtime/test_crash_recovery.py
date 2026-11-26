import asyncio

import psutil
import pytest

from aerobrowse.sessions import SessionManager


def test_worker_crash_retires_slot_and_allows_new_session():
    async def run():
        manager = SessionManager(max_sessions=1)
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        process = manager._sessions[sid].worker.process
        psutil.Process(manager._sessions[sid].worker.pid).kill()
        process.wait(timeout=5)
        result = await manager.call("owner", sid, "snapshot")
        assert result["error"]["code"] == "WORKER_CRASHED"
        assert manager.active_sessions == 0
        replacement = await manager.create("owner")
        assert (await manager.call("owner", replacement, "snapshot"))["error"][
            "code"
        ] == "NO_ACTIVE_PAGE"
        await manager.close_all()

    asyncio.run(run())


def test_slow_network_worker_is_killed_on_timeout(site):
    async def run():
        manager = SessionManager(max_sessions=1, allow_networks=("127.0.0.1/32",))
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        pid = manager._sessions[sid].worker.pid
        manager.request_timeout = 0.03
        result = await manager.call("owner", sid, "navigate", site + "/slow")
        assert result["error"]["code"] == "TIMEOUT"
        assert not psutil.pid_exists(pid)
        assert manager.active_sessions == 0
        await manager.close_all()

    asyncio.run(run())


def test_cancelled_network_call_terminates_worker(site):
    async def run():
        manager = SessionManager(allow_networks=("127.0.0.1/32",))
        sid = await manager.create("owner")
        await manager.call("owner", sid, "snapshot")
        pid = manager._sessions[sid].worker.pid
        task = asyncio.create_task(
            manager.call("owner", sid, "navigate", site + "/slow")
        )
        await asyncio.sleep(0.03)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not psutil.pid_exists(pid)
        assert manager.active_sessions == 0
        await manager.close_all()

    asyncio.run(run())


@pytest.mark.skipif(
    __import__("sys").platform not in {"win32", "linux"},
    reason="Kernel job or Linux guardian parent death",
)
def test_parent_death_closes_job_and_kills_worker():
    import json
    import subprocess
    import sys
    import time

    parent = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import json,sys;from aerobrowse.runtime import ResourcePool,ProcessWorker;p=ResourcePool();w=ProcessWorker(p);w.call('snapshot',(),{});print(json.dumps({'pid':w.pid}),flush=True);sys.stdin.readline()",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        worker = json.loads(parent.stdout.readline())["pid"]
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 5
        while psutil.pid_exists(worker) and time.monotonic() < deadline:
            time.sleep(0.02)
        assert not psutil.pid_exists(worker)
    finally:
        if parent.poll() is None:
            parent.kill()
            parent.wait(timeout=5)
        parent.stdin.close()
        parent.stdout.close()
