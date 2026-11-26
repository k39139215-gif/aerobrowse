def test_invalid_session_and_arguments_are_safe_tool_errors(peer):
    peer.initialize()
    peer.send(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "browser_snapshot", "arguments": {"session_id": "bad"}},
        }
    )
    response = peer.receive()
    assert response["id"] == 2
    assert response["result"]["isError"] is True
    assert "Traceback" not in str(response)


def test_concurrent_tool_responses_keep_request_and_session_identity(peer):
    peer.initialize()
    for request_id in range(10, 18):
        peer.send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": "browser_navigate",
                    "arguments": {"url": "http://127.0.0.1"},
                },
            }
        )
    responses = [peer.receive() for _ in range(8)]
    assert {r["id"] for r in responses} == set(range(10, 18))
    sessions = []
    for response in responses:
        data = response["result"]["structuredContent"]
        assert data["error"]["code"] == "BLOCKED_DESTINATION"
        sessions.append(data["session_id"])
    assert len(set(sessions)) == 8
    for index, sid in enumerate(sessions):
        peer.send(
            {
                "jsonrpc": "2.0",
                "id": 100 + index,
                "method": "tools/call",
                "params": {"name": "browser_close", "arguments": {"session_id": sid}},
            }
        )
    assert all(
        peer.receive()["result"]["structuredContent"]["success"] for _ in sessions
    )


def test_request_cancellation_and_malformed_frame_do_not_break_other_requests(peer):
    peer.initialize()
    peer.send(
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {
                "name": "browser_navigate",
                "arguments": {"url": "http://127.0.0.1"},
            },
        }
    )
    peer.send(
        {
            "jsonrpc": "2.0",
            "method": "notifications/cancelled",
            "params": {"requestId": 30, "reason": "test"},
        }
    )
    peer.raw(b"{\n")
    peer.send({"jsonrpc": "2.0", "id": 31, "method": "ping"})
    replies = [peer.receive() for _ in range(3)]
    assert len([r for r in replies if r.get("id") == 30]) == 1
    assert any(r.get("id") == 31 and "result" in r for r in replies)
    assert any(r.get("error", {}).get("code") == -32700 for r in replies)


def test_disconnect_closes_session_worker_processes(peer):
    import time

    import psutil

    peer.initialize()
    peer.send(
        {
            "jsonrpc": "2.0",
            "id": 40,
            "method": "tools/call",
            "params": {
                "name": "browser_navigate",
                "arguments": {"url": "http://127.0.0.1"},
            },
        }
    )
    response = peer.receive()
    assert (
        response["result"]["structuredContent"]["error"]["code"]
        == "BLOCKED_DESTINATION"
    )
    children = psutil.Process(peer.process.pid).children(recursive=True)
    assert children
    peer.process.stdin.close()
    peer.process.wait(timeout=15)
    assert peer.process.returncode == 0
    deadline = time.monotonic() + 5
    while any(child.is_running() for child in children) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not any(child.is_running() for child in children)
