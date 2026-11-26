import asyncio

import psutil
import pytest

from aerobrowse.runtime import ResourceLimits
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


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux", reason="Required Linux supervised Chromium"
)
def test_supervised_browser_navigation_actions_and_cleanup(site):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=256),
        )
        sid = await manager.create("owner")
        try:
            result = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            group = manager._sessions[sid].worker.group
            counters = {
                name: (group.path / name).read_text()
                for name in (
                    "memory.events",
                    "pids.events",
                    "pids.current",
                    "memory.current",
                )
            }
            assert result.get("success"), {"result": result, "quota_counters": counters}
            aid = next(a["id"] for a in result["actions"] if a["label"] == "Name")
            result = await manager.call(
                "owner", sid, "fill", aid, "Ada", result["generation"]
            )
            assert result.get("success"), result
            assert (await manager.close("owner", sid))["success"]
            assert manager.active_sessions == 0
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux", reason="Linux Chromium task exhaustion"
)
def test_low_task_budget_fails_explicitly_and_releases_slot(site):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=16),
        )
        sid = await manager.create("owner")
        try:
            result = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            assert result["error"]["code"] == "WORKER_RESOURCE_LIMIT", result
            assert manager.active_sessions == 0
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="Linux live browser descendant crashes",
)
@pytest.mark.parametrize("target", ["browser", "renderer"])
def test_live_browser_crash_releases_tree_and_recovers(site, target):
    async def run():
        manager = SessionManager(
            max_sessions=1,
            allow_networks=("127.0.0.1/32",),
            resource_limits=ResourceLimits(processes=256),
        )
        sid = await manager.create("owner")
        descendants = []
        try:
            snapshot = await manager.call(
                "owner", sid, "navigate", site + "/form", force_fidelity=True
            )
            assert snapshot.get("success"), snapshot
            worker = psutil.Process(manager._sessions[sid].worker.pid)
            descendants = worker.children(recursive=True)
            chromes = [p for p in descendants if p.name() in ("chrome", "chromium")]
            selected = (
                [p for p in chromes if "--type=renderer" in p.cmdline()]
                if target == "renderer"
                else [
                    next(
                        p
                        for p in chromes
                        if not any(a.startswith("--type=") for a in p.cmdline())
                    )
                ]
            )
            # Chromium can prestart a spare renderer; terminate every session renderer
            # so this test cannot accidentally kill only the spare process.
            assert selected
            for process in selected:
                try:
                    process.kill()
                except psutil.NoSuchProcess:
                    pass
            await asyncio.sleep(0.1)
            manager.request_timeout = 3
            aid = next(a["id"] for a in snapshot["actions"] if a["label"] == "Name")
            result = await manager.call(
                "owner",
                sid,
                "fill",
                aid,
                "must not target another page",
                snapshot["generation"],
            )
            assert not result.get("success"), result
            assert result["error"]["code"] in {
                "STALE_ACTION_ID",
                "PAGE_NAVIGATED",
                "NO_ACTIVE_PAGE",
                "WORKER_CRASHED",
                "SNAPSHOT_FAILED",
                "TIMEOUT",
            }, result
            if sid in manager._sessions:
                assert (await manager.close("owner", sid))["success"]
            assert manager.active_sessions == 0
            for process in descendants:
                try:
                    assert process.status() == psutil.STATUS_ZOMBIE, (
                        process.pid,
                        process.name(),
                        process.status(),
                    )
                except psutil.NoSuchProcess:
                    pass
            manager.request_timeout = 45
            replacement = await manager.create("owner")
            fresh = await manager.call(
                "owner", replacement, "navigate", site + "/form", force_fidelity=True
            )
            assert fresh.get("success"), fresh
            assert fresh["generation"] != snapshot["generation"]
        finally:
            await manager.close_all()

    asyncio.run(run())


@pytest.mark.browser
@pytest.mark.skipif(
    __import__("sys").platform != "linux",
    reason="Linux independent guardian parent death",
)
def test_linux_parent_death_kills_worker_and_cgroup():
    import json
    import subprocess
    import sys
    import time

    code = """import json,sys
from aerobrowse.runtime import ResourcePool,ProcessWorker
pool=ResourcePool();worker=ProcessWorker(pool)
worker.call('snapshot',(),{})
print(json.dumps({'pid':worker.pid,'guardian':worker.guardian.pid,'directory':worker.directory.name,'group':str(worker.group.path)}),flush=True)
sys.stdin.readline()
"""
    with subprocess.Popen(
        [sys.executable, "-c", code],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    ) as parent:
        receipt = json.loads(parent.stdout.readline())
        worker = psutil.Process(receipt["pid"])
        parent.kill()
        parent.wait(timeout=5)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                live = worker.is_running() and worker.status() != psutil.STATUS_ZOMBIE
            except psutil.NoSuchProcess:
                live = False
            if (
                not live
                and not __import__("pathlib").Path(receipt["directory"]).exists()
                and not __import__("pathlib").Path(receipt["group"]).exists()
            ):
                break
            time.sleep(0.05)
        assert not live
        assert not __import__("pathlib").Path(receipt["directory"]).exists()
        assert not __import__("pathlib").Path(receipt["group"]).exists()
