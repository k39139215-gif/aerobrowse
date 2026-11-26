"""Actual local connection observations under policy, redirects and rebinding."""

import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aerobrowse.errors import AeroError
from aerobrowse.security import NetworkPolicy, SafeTransport


def test_mixed_dns_and_changing_redirect_answers_cannot_reach_private_canary(
    monkeypatch,
):
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(302 if self.path == "/start" else 200)
            if self.path == "/start":
                self.send_header(
                    "Location",
                    "http://target.example:" + str(self.server.server_port) + "/secret",
                )
            self.end_headers()

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    calls = []

    def resolver(host, port, *args):
        calls.append(host)
        addresses = (
            ["127.0.0.1"] if host == "entry.example" else ["127.0.0.1", "10.0.0.1"]
        )
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (a, port)) for a in addresses
        ]

    monkeypatch.setattr(socket, "getaddrinfo", resolver)
    try:
        with pytest.raises(AeroError) as caught:
            SafeTransport(NetworkPolicy(allow_networks=("127.0.0.1/32",))).request(
                "http://entry.example:" + str(server.server_port) + "/start"
            )
        assert caught.value.code == "BLOCKED_DESTINATION"
        assert hits == ["/start"]
        assert calls == ["entry.example", "target.example"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_destination_headers_cannot_override_pinned_target(site):
    response = SafeTransport(NetworkPolicy(allow_networks=("127.0.0.1/32",))).request(
        site,
        headers={
            "Host": "169.254.169.254",
            "Forwarded": "host=metadata.google.internal",
            "Proxy-Authorization": "secret",
        },
    )
    assert response.status == 200
