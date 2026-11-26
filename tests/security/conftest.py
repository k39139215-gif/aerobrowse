"""Real host canaries. Only fixture address .1 is allowlisted; .2 must see no traffic."""

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy


@pytest.fixture
def attack_lab(monkeypatch):
    monkeypatch.setenv("AEROBROWSE_TEST_HOST_SECRET", "CONTROLLED_ENV_SECRET")
    received = []
    datagrams = []
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.bind(("127.0.0.2", 0))
    udp.settimeout(0.1)
    udp_stop = threading.Event()

    def record_udp():
        while not udp_stop.is_set():
            try:
                packet, peer = udp.recvfrom(4096)
                datagrams.append({"bytes": len(packet), "peer": peer[0]})
            except TimeoutError:
                continue

    udp_thread = threading.Thread(target=record_udp, daemon=True)
    udp_thread.start()

    class Canary(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append({"path": self.path, "method": "GET"})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"CANARY_PRIVATE_SECRET")

        def do_POST(self):
            received.append({"path": self.path, "method": "POST"})
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            return

    canary = ThreadingHTTPServer(("127.0.0.2", 0), Canary)
    forbidden = f"http://127.0.0.2:{canary.server_port}"

    class Fixture(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/redirect"):
                self.send_response(302)
                self.send_header("Location", forbidden + "/redirect-canary")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<html><title>Attack fixture</title><body><h1>Permitted fixture</h1></body></html>"
            )

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threads = [
        threading.Thread(target=s.serve_forever, daemon=True) for s in (server, canary)
    ]
    for t in threads:
        t.start()
    browser = AeroBrowser(
        default_mode="fidelity", policy=NetworkPolicy(allow_networks=("127.0.0.1/32",))
    )
    lab = {
        "browser": browser,
        "allowed": f"http://127.0.0.1:{server.server_port}",
        "forbidden": forbidden,
        "received": received,
        "udp": udp.getsockname(),
        "datagrams": datagrams,
    }
    try:
        yield lab
    finally:
        browser.close()
        udp_stop.set()
        udp_thread.join(timeout=2)
        udp.close()
        for s in (server, canary):
            s.shutdown()
            s.server_close()
        for t in threads:
            t.join(timeout=5)


def save_receipt(name, evidence):
    from pathlib import Path

    root = Path("evidence/phase2/runtime")
    root.mkdir(parents=True, exist_ok=True)
    destination = root / (name + ".json")
    # Test evidence includes only controlled fixture addresses, no user data.
    destination.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
