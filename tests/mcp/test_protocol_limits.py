import json

import pytest

from aerobrowse.mcp_transport import FrameError, TransportLimits, decode_frame


@pytest.mark.parametrize(
    "payload",
    [
        b"{",
        b"\xff",
        b"[]",
        b"NaN",
        b'{"a":1,"a":2}',
        b'{"a":"\\ud800"}',
        b'{"a":' + b"[" * 40 + b"0" + b"]" * 40 + b"}",
        json.dumps({"a": "x" * 65537}).encode(),
        json.dumps({"a": list(range(2049))}).encode(),
    ],
    ids=[
        "truncated-json",
        "invalid-utf8",
        "non-object",
        "non-finite-number",
        "duplicate-key",
        "lone-surrogate",
        "excessive-nesting",
        "oversized-string",
        "oversized-array",
    ],
)
def test_shape_limits_precede_sdk(payload):
    with pytest.raises(FrameError):
        decode_frame(payload, TransportLimits())


def test_oversized_unterminated_frame_is_rejected_and_connection_closed(peer):
    peer.raw(b"x" * 131073)
    response = peer.receive()
    assert response["error"]["message"] == "MCP frame limit exceeded"
    peer.process.wait(timeout=10)
    assert peer.process.returncode == 0


def test_multiple_frames_in_one_write_remain_correlated(peer):
    peer.initialize()
    messages = [{"jsonrpc": "2.0", "id": i, "method": "ping"} for i in range(10, 30)]
    peer.raw(b"".join(json.dumps(m).encode() + b"\n" for m in messages))
    responses = [peer.receive() for _ in messages]
    assert {r["id"] for r in responses} == set(range(10, 30))
    assert all("result" in r for r in responses)


def test_duplicate_active_request_ids_close_without_ambiguous_response(peer):
    peer.initialize()
    request = {
        "jsonrpc": "2.0",
        "id": 44,
        "method": "tools/call",
        "params": {
            "name": "browser_navigate",
            "arguments": {"url": "http://127.0.0.1"},
        },
    }
    peer.raw((json.dumps(request) + "\n" + json.dumps(request) + "\n").encode())
    peer.process.wait(timeout=15)
    assert peer.process.returncode == 0
    ids = []
    while not peer.output.empty():
        ids.append(peer.output.get()["id"])
    assert ids.count(44) <= 1


def test_partial_frame_deadline_closes_connection(peer):
    import time

    peer.raw(b"{")
    # Keep delivering bytes; the deadline must cover the whole frame, not inactivity.
    for _ in range(4):
        time.sleep(2.5)
        if peer.process.poll() is None:
            try:
                peer.raw(b" ")
            except (BrokenPipeError, OSError):
                break
    response = peer.receive()
    assert response["error"]["message"] == "MCP partial frame deadline exceeded"
    peer.process.wait(timeout=10)
    assert peer.process.returncode == 0


def test_nonfinite_exponent_is_rejected():
    with pytest.raises(FrameError):
        decode_frame(b'{"n":1e999}', TransportLimits())


def test_unread_output_pipe_closes_server_with_bounded_deadline():
    import subprocess
    import sys
    from pathlib import Path

    process = subprocess.Popen(
        [sys.executable, "-m", "aerobrowse.mcp_server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        cwd=Path(__file__).resolve().parents[2],
    )
    try:
        initialize = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "blocked-output", "version": "1"},
            },
        }
        process.stdin.write(json.dumps(initialize).encode() + b"\n")
        process.stdin.flush()
        assert json.loads(process.stdout.readline())["id"] == 1
        messages = [{"jsonrpc": "2.0", "method": "notifications/initialized"}]
        messages.extend(
            {"jsonrpc": "2.0", "id": i, "method": "tools/list"} for i in range(10, 30)
        )
        process.stdin.write(
            b"".join(json.dumps(message).encode() + b"\n" for message in messages)
        )
        process.stdin.flush()
        # Deliberately leave stdout unread while the server fills the real OS pipe.
        process.wait(timeout=20)
        assert process.returncode == 0
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
        process.stdin.close()
        process.stdout.close()


def test_oversized_integer_is_bounded_error_and_pipe_recovers(peer):
    peer.initialize()
    peer.raw(b'{"jsonrpc":"2.0","id":' + b"9" * 5000 + b',"method":"ping"}\n')
    response = peer.receive()
    assert response["error"]["code"] == -32700, response
    peer.send({"jsonrpc": "2.0", "id": 901, "method": "ping"})
    assert peer.receive() == {"jsonrpc": "2.0", "id": 901, "result": {}}


@pytest.mark.parametrize("digits", [129, 5000])
def test_integer_limit_independent_of_interpreter_settings(digits):
    with pytest.raises(FrameError) as error:
        decode_frame(b'{"number":' + b"9" * digits + b"}", TransportLimits())
    assert error.value.code == -32700
