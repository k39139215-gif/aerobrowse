from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest


@pytest.fixture
def site():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/loop":
                self.send_response(302)
                self.send_header("Location", "/loop")
                self.end_headers()
                return
            if self.path == "/slow":
                import time

                time.sleep(0.2)
                self.send_response(200)
                self.end_headers()
                return
            if self.path == "/form":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"""<html><head><title>Form fixture</title></head><body><label>Name<input name=name></label><label>Choice<select><option value=a>A</option><option value=b>B</option></select></label><label>Agree<input type=checkbox></label><button onclick="document.querySelector('p').textContent='Changed by JavaScript'">Update</button><p>Original</p></body></html>"""
                )
                return
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
                self.end_headers()
                return
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h1>Private service secret</h1>")

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join()
