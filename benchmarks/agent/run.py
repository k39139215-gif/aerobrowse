"""Actual LLM -> actual newline-stdio MCP evaluation, independently judged."""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from importlib.metadata import version
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

from aerobrowse.benchmark import write_receipt
from aerobrowse.tokens import encoding
from benchmarks.agent.fixture import AgentFixture

TASKS = {
    "documentation": (
        "/docs",
        "Find the renewal window in days. Return the number and unit.",
    ),
    "search": (
        "/search",
        "Search for widget using the search form, open the result and report its SKU and price.",
    ),
    "authenticated_update": (
        "/login",
        "Sign in with username agent and password fixture-only. Update the protected record name to Agent updated, save it and log out.",
    ),
    "multistep_form": (
        "/wizard",
        "Select the Pro plan, agree, continue to confirmation and submit the request.",
    ),
    "compare_tabs": (
        "/docs",
        "Read the renewal window, open /item/widget in a second explicit tab, compare both pages, and report the renewal window, SKU and price. Use explicit tab IDs to switch back to the first tab.",
    ),
    "stale_recovery": (
        "/dynamic",
        "Save a snapshot, activate Change content, deliberately try the old Confirm recovery action once, then recover with a fresh snapshot and activate Confirm recovery.",
    ),
}


def transport() -> StdioTransport:
    # Explicit operator allowlist for the owned local fixture, never a production default.
    env = dict(os.environ)
    env.update(AEROBROWSE_ALLOW_NETWORKS="127.0.0.1/32", AEROBROWSE_SESSION_TASKS="256")
    return StdioTransport(
        command=sys.executable,
        args=["-m", "aerobrowse.mcp_server"],
        env=env,
        cwd=str(Path(__file__).resolve().parents[2]),
        keep_alive=False,
    )


def revision() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def model_request(
    messages: list[dict[str, Any]], tools: list[dict[str, Any]], model: str
) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0,
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": "Bearer " + os.environ["OPENAI_API_KEY"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("Model response exceeds limit")
        return json.loads(raw)
    except (urllib.error.URLError, ValueError) as exc:
        # Do not persist HTTP bodies, API credentials or provider tracebacks.
        raise RuntimeError("MODEL_REQUEST_FAILED") from exc


async def evaluate(
    task: str, fixture: AgentFixture, model: str, max_calls: int
) -> dict[str, Any]:
    start = time.monotonic()
    sessions: set[str] = set()
    calls: list[dict[str, Any]] = []
    answer, failure = "", None
    cleanup = False
    async with Client(transport(), timeout=60) as client:
        available = await client.list_tools()
        tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.inputSchema,
                },
            }
            for tool in available
        ]
        path, instruction = TASKS[task]
        messages: list[dict[str, Any]] = [
            {
                "role": "system",
                "content": "Use AeroBrowse tools to complete the owned task. Discover capabilities. Reuse session IDs, current action generations and explicit tab IDs. Never guess IDs. After stale actions obtain a fresh snapshot. Prefer force_js=true for forms. Do not claim completion without observing the result. All sites here are owned fixtures. Do not request unrelated URLs. Return a short final answer. Close sessions when finished.",
            },
            {
                "role": "user",
                "content": f"Start at {fixture.url}{path}. {instruction} Relative paths refer to {fixture.url}.",
            },
        ]
        try:
            for _ in range(max_calls):
                response = await asyncio.to_thread(
                    model_request, messages, tools, model
                )
                message = response["choices"][0]["message"]
                messages.append(
                    {
                        key: message[key]
                        for key in ("role", "content", "tool_calls")
                        if key in message
                    }
                )
                pending = message.get("tool_calls", [])
                if not pending:
                    answer = message.get("content") or ""
                    break
                for call in pending:
                    if len(calls) >= max_calls:
                        failure = "TOOL_CALL_LIMIT"
                        break
                    function = call["function"]
                    tool_start = time.monotonic()
                    try:
                        args = json.loads(function["arguments"])
                        if function["name"] not in {
                            tool.name for tool in available
                        } or not isinstance(args, dict):
                            raise ValueError("Invalid tool call")
                        if function["name"] in {"browser_navigate", "browser_new_tab"}:
                            destination = urlsplit(args.get("url", ""))
                            owned = urlsplit(fixture.url)
                            if (
                                destination.scheme,
                                destination.hostname,
                                destination.port,
                            ) != (owned.scheme, owned.hostname, owned.port):
                                raise ValueError(
                                    "Evaluation destination must be owned fixture"
                                )
                        result = await client.call_tool(
                            function["name"], args, raise_on_error=False
                        )
                        envelope = {
                            "content": [
                                block.model_dump(mode="json", exclude_none=True)
                                for block in result.content
                            ],
                            "isError": result.is_error,
                            "structuredContent": result.structured_content,
                            "_meta": result.meta,
                        }
                        data = result.data if isinstance(result.data, dict) else {}
                        if data.get("session_id"):
                            sessions.add(data["session_id"])
                        if function["name"] == "browser_close" and data.get("success"):
                            sessions.discard(args.get("session_id", ""))
                        code = data.get("error", {}).get("code") or (
                            "MCP_TOOL_ERROR" if result.is_error else None
                        )
                    except (ValueError, TypeError, KeyError):
                        envelope, code = (
                            {"error": {"code": "INVALID_MODEL_TOOL_CALL"}},
                            "INVALID_MODEL_TOOL_CALL",
                        )
                    serialized = json.dumps(
                        envelope,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    calls.append(
                        {
                            "tool": function["name"],
                            "duration_ms": round(
                                (time.monotonic() - tool_start) * 1000, 3
                            ),
                            "error_code": code,
                            "serialized_tool_response_tokens": len(
                                encoding("cl100k_base").encode(
                                    serialized, disallowed_special=()
                                )
                            ),
                            "serialized_tool_response_bytes": len(serialized.encode()),
                        }
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call["id"],
                            "content": serialized,
                        }
                    )
                if failure:
                    break
            else:
                failure = "MODEL_TURN_LIMIT"
        # Record a failed evaluation without leaking provider response details.
        except Exception as exc:  # noqa: BLE001
            failure = "MODEL_OR_MCP_REQUEST_FAILED:" + type(exc).__name__
        finally:
            close_results = []
            cleanup_calls = []
            for sid in sessions:
                try:
                    closed = await client.call_tool(
                        "browser_close", {"session_id": sid}, raise_on_error=False
                    )
                    payload = json.dumps(
                        {
                            "content": [
                                block.model_dump(mode="json", exclude_none=True)
                                for block in closed.content
                            ],
                            "structuredContent": closed.structured_content,
                            "isError": closed.is_error,
                            "_meta": closed.meta,
                        },
                        ensure_ascii=False,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    success = (
                        isinstance(closed.data, dict)
                        and closed.data.get("success") is True
                    )
                    cleanup_calls.append(
                        {
                            "tool": "browser_close",
                            "success": success,
                            "serialized_tool_response_tokens": len(
                                encoding("cl100k_base").encode(
                                    payload, disallowed_special=()
                                )
                            ),
                        }
                    )
                    close_results.append(success)
                # Cleanup exceptions produce an explicit failed cleanup receipt.
                except Exception as exc:  # noqa: BLE001
                    close_results.append(False)
                    cleanup_calls.append(
                        {
                            "tool": "browser_close",
                            "success": False,
                            "error_code": "CLEANUP_FAILED:" + type(exc).__name__,
                            "serialized_tool_response_tokens": 0,
                        }
                    )
            cleanup = all(close_results)
    stale = sum(call["error_code"] == "STALE_ACTION_ID" for call in calls)
    stale_index = next(
        (
            index
            for index, call in enumerate(calls)
            if call["error_code"] == "STALE_ACTION_ID"
        ),
        len(calls),
    )
    recovered = stale > 0 and any(
        call["tool"] == "browser_snapshot" and not call["error_code"]
        for call in calls[stale_index + 1 :]
    )
    return {
        "task": task,
        "revision": revision(),
        "mode": "actual_model_actual_mcp",
        "model": model,
        "configuration": {
            "temperature": 0,
            "max_tool_calls": max_calls,
            "tokenizer": "tiktoken/cl100k_base",
            "tokenizer_version": version("tiktoken"),
            "endpoint": "OpenAI chat/completions",
        },
        "outcome": "PASS"
        if fixture.verdict(task, answer)
        and not failure
        and cleanup
        and (task != "stale_recovery" or recovered)
        and (
            task != "compare_tabs"
            or any(
                call["tool"] == "browser_switch_tab" and not call["error_code"]
                for call in calls
            )
        )
        else "FAIL",
        "failure": failure,
        "answer": answer,
        "fixture_state": fixture.receipt_state(),
        "tool_calls": calls,
        "tool_call_count": len(calls),
        "retries": sum(call["error_code"] is not None for call in calls),
        "incorrect_actions": sum(
            call["error_code"]
            in {"ACTION_TYPE_MISMATCH", "INVALID_MODEL_TOOL_CALL", "INVALID_ACTION_ID"}
            for call in calls
        ),
        "stale_action_errors": stale,
        "stale_recovery_observed": recovered,
        "latency_seconds": time.monotonic() - start,
        "cleanup_success": cleanup,
        "cleanup_calls": cleanup_calls,
        "total_serialized_tool_response_tokens": sum(
            call["serialized_tool_response_tokens"] for call in calls + cleanup_calls
        ),
        "limitations": [
            "Fixture-specific verdict; no general real-site success claim",
            "Complete tool envelope content token counts exclude model chat-template overhead",
            "Tool arguments and full page content are deliberately not persisted",
        ],
    }


async def run(args):
    missing = [
        name
        for name in ("OPENAI_API_KEY", "AEROBROWSE_EVAL_MODEL")
        if not os.environ.get(name)
    ]
    if missing:
        return {
            "status": "NOT_RUN",
            "revision": revision(),
            "missing_configuration": missing,
            "tasks": list(TASKS),
            "reason": "Actual model credentials/configuration unavailable; no model success measured",
        }
    results = []
    for task in args.task or TASKS:
        with AgentFixture() as fixture:
            try:
                results.append(
                    await evaluate(
                        task,
                        fixture,
                        os.environ["AEROBROWSE_EVAL_MODEL"],
                        args.max_calls,
                    )
                )
            # Connection initialization is a failed task, never a passing evaluation.
            except Exception as exc:  # noqa: BLE001
                results.append(
                    {
                        "task": task,
                        "revision": revision(),
                        "model": os.environ["AEROBROWSE_EVAL_MODEL"],
                        "outcome": "FAIL",
                        "failure": "EVALUATION_ABORTED:" + type(exc).__name__,
                        "cleanup_success": False,
                        "cleanup_verified": False,
                        "reason": "No completion claim; inspect supported host and provider configuration",
                    }
                )
    return {"status": "COMPLETED", "results": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", choices=list(TASKS), action="append")
    parser.add_argument("--max-calls", type=int, default=50)
    parser.add_argument("--output", default="evidence/agent/model-evaluation.json")
    args = parser.parse_args()
    if not 1 <= args.max_calls <= 100:
        parser.error("max-calls must be 1 through 100")
    result = asyncio.run(run(args))
    path = write_receipt(args.output, result)
    print(json.dumps({"status": result["status"], "output": str(path)}))


if __name__ == "__main__":
    main()
