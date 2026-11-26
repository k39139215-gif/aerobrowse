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
