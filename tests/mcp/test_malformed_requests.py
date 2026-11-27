import pytest


@pytest.mark.parametrize(
    "frame,code",
    [
        (b"{\n", -32700),
        (b"\xff\n", -32700),
        (b'[{"jsonrpc":"2.0","id":2,"method":"ping"}]\n', -32600),
        (b'{"jsonrpc":"1.0","id":2,"method":"ping"}\n', -32600),
        (b'{"jsonrpc":"2.0","id":true,"method":"ping"}\n', -32600),
        (b'{"jsonrpc":"2.0","id":2.3,"method":"ping"}\n', -32600),
        (b'{"jsonrpc":"2.0","method":"tools/list"}\n', -32600),
        (b'{"jsonrpc":"2.0","id":2,"method":"unknown"}\n', -32601),
        (b'{"jsonrpc":"2.0","id":2,"method":"ping","unexpected":"secret"}\n', -32600),
        (b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":[]}\n', -32600),
        (b'{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{}}\n', -32602),
    ],
)
def test_bad_frames_fail_without_leaking_input_and_next_request_works(
    peer, frame, code
):
    peer.raw(frame)
    response = peer.receive()
    assert response["error"]["code"] == code
    assert "secret" not in str(response)
    peer.initialize()
    peer.send({"jsonrpc": "2.0", "id": 90, "method": "ping"})
    assert peer.receive() == {"jsonrpc": "2.0", "id": 90, "result": {}}


def test_unknown_notification_is_ignored(peer):
    peer.initialize()
    peer.send(
        {"jsonrpc": "2.0", "method": "notifications/future-extension", "params": {}}
    )
    peer.send({"jsonrpc": "2.0", "id": 3, "method": "ping"})
    assert peer.receive()["id"] == 3
