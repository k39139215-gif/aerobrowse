import asyncio
import json
import logging

from aerobrowse import AeroBrowser
from aerobrowse.security import NetworkPolicy
from aerobrowse.sessions import SessionManager


def test_sdk_records_safe_request_context_and_bounded_metrics(site, caplog):
    with caplog.at_level(logging.INFO, logger="aerobrowse.requests"):
        with AeroBrowser(
            default_mode="turbo", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
        ) as browser:
            denied = browser.fetch("http://127.0.0.2/PRIVATE-VALUE?token=DO-NOT-LOG")
            page = browser.fetch(site)
            assert denied["request_id"] != page["request_id"]
            metrics = browser.metrics_snapshot()
            assert metrics["requests"] == 2
            assert metrics["failures"] == 1
            assert metrics["navigation_success_rate"] == 0.5
            assert metrics["latency_ms"]["count"] == 2
            assert metrics["active_sessions"] == 1
            assert metrics["sampled_peak_tree_rss_bytes"] > 0
            assert "aerobrowse_requests_total 2" in browser.metrics_prometheus()
        assert browser.metrics_snapshot()["active_sessions"] == 0
    logs = [
        json.loads(r.message) for r in caplog.records if r.name == "aerobrowse.requests"
    ]
    assert all(
        {
            "request_id",
            "session_id",
            "engine",
            "operation",
            "duration_ms",
            "outcome",
            "error_code",
        }
        <= row.keys()
        for row in logs
    )
    assert "DO-NOT-LOG" not in str(logs)
    assert "PRIVATE-VALUE" not in str(logs)


def test_manager_metrics_aggregate_real_workers_and_hide_untrusted_labels():
    async def run():
        manager = SessionManager()
        try:
            sid = await manager.create("owner")
            await manager.call("owner", sid, "navigate", "http://127.0.0.1")
            await manager.call("foreign-owner", sid, "snapshot")
            await manager.call("owner", sid, "arbitrary-user-secret")
            value = manager.metrics_snapshot()
            assert value["requests"] == 3
            assert value["failures"] == 3
            assert value["active_sessions"] == 1
            assert "arbitrary-user-secret" not in json.dumps(value)
            assert "foreign-owner" not in manager.metrics_prometheus()
        finally:
            await manager.close_all()
        assert manager.metrics_snapshot()["active_sessions"] == 0

    asyncio.run(run())


def test_closed_sdk_calls_still_have_request_ids_and_metrics():
    browser = AeroBrowser(default_mode="turbo")
    browser.close()
    result = browser.snapshot()
    assert result["error"]["code"] == "RUNTIME_CLOSED"
    assert result["request_id"]
    assert browser.metrics_snapshot()["requests"] == 1


def test_telemetry_label_cardinality_and_histogram_are_bounded():
    from aerobrowse.observability import Metrics

    metrics = Metrics()
    for i in range(1000):
        metrics.observe(
            "secret-" + str(i),
            {"success": False, "error": {"code": "SECRET"}},
            float(i),
        )
    value = metrics.snapshot(0)
    assert value["operations"] == {"unknown": 1000}
    assert len(value["latency_ms"]["cumulative_buckets"]) == 12
    assert value["latency_ms"]["sum"] == sum(range(1000))
    assert "SECRET" not in metrics.prometheus(0)
    assert 'le="+Inf"} 1000' in metrics.prometheus(0)


def test_handoff_rate_uses_all_navigation_and_action_opportunities():
    from aerobrowse.observability import Metrics

    metrics = Metrics()
    metrics.observe("navigate", {"success": True}, 1)
    for _ in range(3):
        metrics.observe("click", {"success": False, "synchronized": True}, 2)
    assert metrics.snapshot(0)["fallback_rate"] == 0.75
