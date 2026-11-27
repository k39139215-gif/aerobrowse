"""Controlled cookie login through the real isolated Chromium broker."""

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from urllib.parse import urlencode

import pytest

from aerobrowse.engine import AeroBrowser
from aerobrowse.security import NetworkPolicy

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        sys.platform != "linux", reason="requires isolated Linux Chromium"
    ),
]

COOKIE_SECRET = "fixture-session-secret"
PASSWORD = "fixture-password-secret"


@pytest.fixture
def login_lab():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            cookies = self.headers.get("Cookie", "")
            received.append((self.server.server_address[0], self.path, cookies))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            if self.path == "/logout":
                self.send_header("Set-Cookie", "session=; Max-Age=0; HttpOnly; Path=/")
            self.end_headers()
            if self.path == "/login":
                self.wfile.write(
                    b'<h1>Sign in</h1><form method="post" action="/login">'
                    b'<label>Password<input type="password" name="login_secret"></label>'
                    b'<button type="submit">Sign in</button></form>'
                )
            elif self.path == "/account" and f"session={COOKIE_SECRET}" in cookies:
                self.wfile.write(b"<h1>Authenticated account</h1>")
            else:
                self.wfile.write(b"<h1>Public page</h1>")

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if body != urlencode({"login_secret": PASSWORD}).encode():
                self.send_response(403)
                self.end_headers()
                return
            self.send_response(303)
            self.send_header("Location", "/account")
            self.send_header(
                "Set-Cookie",
                f"session={COOKIE_SECRET}; HttpOnly; SameSite=Strict; Path=/",
            )
            self.send_header("Set-Cookie", "private=path-scoped; Path=/private")
            # A response may not assign cookies to an unrelated host.
            self.send_header(
                "Set-Cookie", "foreign=must-not-exist; Domain=127.0.0.2; Path=/"
            )
            self.end_headers()

        def log_message(self, *args):
            return

    servers = [
        ThreadingHTTPServer((host, 0), Handler) for host in ("127.0.0.1", "127.0.0.2")
    ]
    threads = [Thread(target=server.serve_forever, daemon=True) for server in servers]
    for thread in threads:
        thread.start()
    browser = AeroBrowser(
        default_mode="fidelity",
        policy=NetworkPolicy(allow_networks=("127.0.0.1/32", "127.0.0.2/32")),
    )
    trace = []
    engine = browser._get_fidelity()
    original_broker = engine._broker

    def traced(route):
        from urllib.parse import urlsplit

        trace.append(
            (
                route.request.method,
                urlsplit(route.request.url).path,
                route.request.resource_type,
            )
        )
        return original_broker(route)

    engine._broker = traced
    try:
        yield (
            browser,
            [f"http://{s.server_address[0]}:{s.server_port}" for s in servers],
            received,
        )
    finally:
        print("OWNED_ROUTE_TRACE", trace)
        browser.close()
        for server in servers:
            server.shutdown()
            server.server_close()
        for thread in threads:
            thread.join(timeout=5)


def sign_in(browser, url):
    result = browser.fetch(url + "/login", force_fidelity=True)
    assert result["success"], result
    password = next(a for a in result["actions"] if a["input_type"] == "password")
    filled = browser.fill(password["id"], PASSWORD, result["generation"])
    assert filled["success"], filled
    assert PASSWORD not in json.dumps(filled)
    submit = next(a for a in filled["actions"] if a["tag"] == "button")
    clicked = browser.click(submit["id"], filled["generation"])
    page = browser._fidelity.current_page
    assert clicked.get("success"), clicked
    assert not page.url.startswith("chrome-error:"), (clicked.get("error"), page.url)
    page.wait_for_url(url + "/account")
    result = browser.snapshot()
    assert result["success"], (clicked, result)
    assert "Authenticated account" in result["markdown"]
    assert COOKIE_SECRET not in json.dumps(result)
    return page


def test_login_redirect_cookie_scopes_logout_and_secret_redaction(login_lab, caplog):
    browser, (url, _), received = login_lab
    page = sign_in(browser, url)
    assert COOKIE_SECRET not in page.evaluate("document.cookie")
    # Both Set-Cookie fields must survive the 303; Chromium applies the path rule.
    result = browser.fetch(url + "/private/details")
    assert result["success"], result
    private_cookies = next(
        cookies for _, path, cookies in reversed(received) if path == "/private/details"
    )
    assert "private=path-scoped" in private_cookies
    assert f"session={COOKIE_SECRET}" in private_cookies
    result = browser.fetch(url + "/public")
    assert result["success"], result
    public_cookies = next(
        cookies for _, path, cookies in reversed(received) if path == "/public"
    )
    assert "private=" not in public_cookies
    result = browser.fetch(url + "/logout")
    assert result["success"], result
    result = browser.fetch(url + "/account")
    assert "Authenticated account" not in result["markdown"]
    assert COOKIE_SECRET not in caplog.text
    assert PASSWORD not in caplog.text


def test_host_only_cookie_and_foreign_domain_cookie_do_not_cross_hosts(login_lab):
    browser, (url, foreign), received = login_lab
    sign_in(browser, url)
    result = browser.fetch(foreign + "/account")
    assert result["success"], result
    assert "Authenticated account" not in result["markdown"]
    foreign_requests = [cookies for host, _, cookies in received if host == "127.0.0.2"]
    assert foreign_requests and all(not cookies for cookies in foreign_requests)
    result = browser.fetch(url + "/account")
    assert result["success"]
    # First cross-site Strict-cookie navigation may be anonymous. A same-origin
    # reload must still find the original session in that context.
    result = browser.fetch(url + "/account")
    assert "Authenticated account" in result["markdown"]


def test_new_context_has_no_cookie_from_logged_in_context(login_lab):
    browser, (url, _), received = login_lab
    sign_in(browser, url)
    engine = browser._fidelity
    isolated = engine.browser.new_context(
        service_workers="block", accept_downloads=False
    )
    try:
        isolated.route("**/*", engine._broker)
        isolated.route_web_socket("**/*", lambda ws: ws.close())
        page = isolated.new_page()
        page.goto(url + "/account")
        assert "Authenticated account" not in page.text_content("body")
        assert received[-1][2] == ""
    finally:
        isolated.close()
    assert "Authenticated account" in browser.fetch(url + "/account")["markdown"]


def test_fetch_credentials_omit_cannot_acquire_cookie_from_host_broker(login_lab):
    browser, (url, _), received = login_lab
    page = sign_in(browser, url)
    public = page.evaluate(
        "async () => (await fetch('/account', {credentials:'omit'})).text()"
    )
    assert "Authenticated account" not in public
    assert received[-1][2] == ""
    private = page.evaluate(
        "async () => (await fetch('/account', {credentials:'include'})).text()"
    )
    assert "Authenticated account" in private
    assert f"session={COOKIE_SECRET}" in received[-1][2]
