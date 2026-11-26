"""Bounded operator telemetry. No request inputs or session IDs become metric labels."""

import json
import logging
import math
import threading
from collections import Counter
from collections.abc import Iterable
from typing import Any

import psutil

OPERATIONS = frozenset(
    {
        "navigate",
        "snapshot",
        "click",
        "fill",
        "select",
        "scroll",
        "wait",
        "screenshot",
        "perform",
        "tabs",
        "new_tab",
        "switch_tab",
        "close_tab",
        "back",
        "forward",
        "reload",
        "capabilities",
    }
)
ACTIONS = frozenset({"click", "fill", "select", "scroll", "wait", "perform"})
EXTRACTION_ERRORS = frozenset(
    {
        "HTML_TOO_LARGE",
        "HTML_LIMIT_EXCEEDED",
        "SNAPSHOT_FAILED",
        "ACTION_CONTEXT_FAILED",
        "TOKENIZER_ERROR",
        "OUTPUT_SERIALIZATION_ERROR",
    }
)
CRASHES = frozenset({"WORKER_CRASHED", "BROWSER_CRASHED"})
BUCKETS = (1, 5, 10, 25, 50, 100, 250, 500, 1000, 5000, 30000, 120000)
log = logging.getLogger("aerobrowse.requests")


def operation_label(operation: str) -> str:
    return operation if operation in OPERATIONS else "unknown"


def request_log(
    request_id: str,
    session_id: str,
    operation: str,
    result: dict[str, Any],
    duration_ms: float,
) -> None:
    log.info(
        json.dumps(
            {
                "request_id": request_id,
                "session_id": session_id,
                "operation": operation_label(operation),
                "engine": result.get("engine")
                if result.get("engine") in {"turbo", "fidelity"}
                else None,
                "duration_ms": round(duration_ms, 3),
                "outcome": "success" if result.get("success") else "error",
                "error_code": result.get("error", {}).get("code"),
            }
        )
    )


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counts: Counter[str] = Counter()
        self._operations: Counter[str] = Counter()
        self._latency_count = 0
        self._latency_sum = 0.0
        self._latency_max = 0.0
        self._buckets = [0] * len(BUCKETS)
        self._rss_max = 0
        self._rss_samples = 0
        self._rss_incomplete = 0

    def observe(
        self, operation: str, result: dict[str, Any], duration_ms: float
    ) -> None:
        label = operation_label(operation)
        duration_ms = max(0.0, duration_ms) if math.isfinite(duration_ms) else 0.0
        success = bool(result.get("success"))
        code = result.get("error", {}).get("code")
        with self._lock:
            self._counts["requests"] += 1
            self._counts["failures"] += not success
            self._operations[label] += 1
            self._counts["navigation_requests"] += label == "navigate"
            self._counts["navigation_successes"] += label == "navigate" and success
            self._counts["action_requests"] += label in ACTIONS
            self._counts["action_successes"] += label in ACTIONS and success
            self._counts["fallbacks"] += bool(
                result.get("synchronized") or result.get("fallback_reason")
            )
            self._counts["extraction_failures"] += code in EXTRACTION_ERRORS
            self._counts["browser_crashes"] += code in CRASHES
            self._counts["timeouts"] += code == "TIMEOUT"
            self._counts["wait_timeouts"] += code == "WAIT_TIMEOUT"
            self._counts["cancelled"] += code == "CANCELLED"
            self._latency_count += 1
            self._latency_sum += duration_ms
            self._latency_max = max(self._latency_max, duration_ms)
            for i, bound in enumerate(BUCKETS):
                self._buckets[i] += duration_ms <= bound

    def sample_memory(self, pids: Iterable[int | None]) -> None:
        seen: set[int] = set()
        rss = 0
        incomplete = False
        for pid in pids:
            if not pid:
                continue
            try:
                parent = psutil.Process(pid)
                processes = [parent, *parent.children(recursive=True)]
            except psutil.Error:
                incomplete = True
                continue
            for process in processes:
                if process.pid in seen:
                    continue
                seen.add(process.pid)
                try:
                    rss += process.memory_info().rss
                except psutil.Error:
                    incomplete = True
        with self._lock:
            self._rss_max = max(self._rss_max, rss)
            self._rss_samples += 1
            self._rss_incomplete += incomplete

    def snapshot(self, active_sessions: int) -> dict[str, Any]:
        with self._lock:
            counts = {
                key: self._counts[key]
                for key in (
                    "requests",
                    "failures",
                    "navigation_requests",
                    "navigation_successes",
                    "action_requests",
                    "action_successes",
                    "fallbacks",
                    "extraction_failures",
                    "browser_crashes",
                    "timeouts",
                    "wait_timeouts",
                    "cancelled",
                )
            }
            return {
                **counts,
                "active_sessions": active_sessions,
                "average_latency_ms": self._latency_sum / self._latency_count
                if self._latency_count
                else None,
                "navigation_success_rate": counts["navigation_successes"]
                / counts["navigation_requests"]
                if counts["navigation_requests"]
                else None,
                "action_success_rate": counts["action_successes"]
                / counts["action_requests"]
                if counts["action_requests"]
                else None,
                "fallback_rate": counts["fallbacks"]
                / (counts["navigation_requests"] + counts["action_requests"])
                if counts["navigation_requests"] + counts["action_requests"]
                else None,
                "operations": dict(sorted(self._operations.items())),
                "latency_ms": {
                    "count": self._latency_count,
                    "sum": self._latency_sum,
                    "max": self._latency_max,
                    "average": self._latency_sum / self._latency_count
                    if self._latency_count
                    else None,
                    "cumulative_buckets": {
                        str(bound): n for bound, n in zip(BUCKETS, self._buckets)
                    },
                },
                "sampled_peak_tree_rss_bytes": self._rss_max,
                "memory_samples": self._rss_samples,
                "incomplete_memory_samples": self._rss_incomplete,
                "memory_scope": "Owned worker trees sampled at request completion/export; includes shared mappings; excludes exited processes; not exact peak",
            }

    def prometheus(self, active_sessions: int) -> str:
        data = self.snapshot(active_sessions)
        lines = []
        for key in (
            "requests",
            "failures",
            "fallbacks",
            "extraction_failures",
            "browser_crashes",
            "timeouts",
            "wait_timeouts",
            "cancelled",
        ):
            lines.extend(
                [
                    f"# TYPE aerobrowse_{key}_total counter",
                    f"aerobrowse_{key}_total {data[key]}",
                ]
            )
        for key in (
            "active_sessions",
            "sampled_peak_tree_rss_bytes",
            "memory_samples",
            "incomplete_memory_samples",
        ):
            lines.extend(
                [f"# TYPE aerobrowse_{key} gauge", f"aerobrowse_{key} {data[key]}"]
            )
        for key in ("navigation_success_rate", "action_success_rate", "fallback_rate"):
            if data[key] is not None:
                lines.append(f"aerobrowse_{key} {data[key]}")
        lines.append("# TYPE aerobrowse_request_duration_ms histogram")
        for bound, count in data["latency_ms"]["cumulative_buckets"].items():
            lines.append(
                f'aerobrowse_request_duration_ms_bucket{{le="{bound}"}} {count}'
            )
        lines.extend(
            [
                f'aerobrowse_request_duration_ms_bucket{{le="+Inf"}} {data["latency_ms"]["count"]}',
                f"aerobrowse_request_duration_ms_sum {data['latency_ms']['sum']}",
                f"aerobrowse_request_duration_ms_count {data['latency_ms']['count']}",
            ]
        )
        return "\n".join(lines) + "\n"
