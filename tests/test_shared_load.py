import asyncio

from benchmarks.agent.shared_load import run


def test_shared_load_uses_real_workers_bounded_queue_and_cleanup():
    result = asyncio.run(
        run(sessions_count=2, rounds=2, browser=False, aggregate_processes=512)
    )
    assert result["completed_operations"] == 8
    assert result["successful_operations"] == 8
    assert result["overload_rejections"] == 2
    assert result["foreign_session_rejected"]
    assert result["capacity_rejected"]
    assert result["active_sessions_after_cleanup"] == 0
    assert all(row["worker_reaped"] for row in result["sessions"])
    assert all(row["completed"] == 4 for row in result["sessions"])
    assert result["telemetry"]["requests"] >= 8
    assert all(row["success"] for row in result["operations"])
    assert result["duration_seconds"] > 0
