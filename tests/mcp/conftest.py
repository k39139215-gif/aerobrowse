"""Real subprocess/stdin harness; no fake SDK or browser transport."""

import json
import queue
import subprocess
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path

import pytest


class Peer:
    def __init__(self):
        self.files = ExitStack()
        self.stderr = self.files.enter_context(tempfile.TemporaryFile())
        self.process = subprocess.Popen(
            [sys.executable, "-m", "aerobrowse.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.stderr,
            cwd=Path(__file__).resolve().parents[2],
        )
        self.output = queue.Queue()

        def read():
            for line in self.process.stdout:
                self.output.put(json.loads(line))

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def raw(self, value):
        self.process.stdin.write(value)
        self.process.stdin.flush()

    def send(self, message):
        self.raw(json.dumps(message).encode("utf-8") + b"\n")

    def receive(self):
        try:
            return self.output.get(timeout=20)
        except queue.Empty:
            self.stderr.seek(0)
            raise AssertionError(
                f"MCP response timeout; exit={self.process.poll()}; stderr={self.stderr.read().decode(errors='replace')}"
            ) from None

    def initialize(self):
        self.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "adversarial-test", "version": "1"},
                },
            }
        )
        response = self.receive()
        assert response["id"] == 1 and "result" in response
        self.send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def close(self):
        if self.process.poll() is None:
            if not self.process.stdin.closed:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.reader.join(timeout=1)
        self.process.stdout.close()
        self.files.close()


@pytest.fixture
def peer():
    peer = Peer()
    try:
        yield peer
    finally:
        peer.close()
