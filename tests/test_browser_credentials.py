"""Real HTTP broker regressions; fixture credentials never leave the fixture."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

import pytest

from aerobrowse.errors import AeroError
from aerobrowse.security import NetworkPolicy, SafeTransport


@pytest.fixture
def credential_site():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            received.append(dict(self.headers))
            self.send_response(
                302 if self.path in {"/redirect", "/blocked-redirect"} else 200
            )
            if self.path == "/oversized-cookie":
                self.send_header("Set-Cookie", "oversized=" + "x" * 16385)
                self.end_headers()
                return
            if self.path == "/folded-cookie":
                self.send_header("Set-Cookie", "folded=value\r\n injected=second")
                self.end_headers()
                return
            if self.path == "/redirect":
                self.send_header("Location", "/destination")
            if self.path == "/blocked-redirect":
                self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.send_header(
                "Set-Cookie", "session=fixture; HttpOnly; SameSite=Strict; Path=/"
            )
            self.send_header("Set-Cookie", "scoped=second; Path=/private")
            self.end_headers()
            self.wfile.write(b"<h1>Fixture</h1>")

        def log_message(self, *args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", received
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def transport():
    return SafeTransport(NetworkPolicy(allow_networks=("127.0.0.1/32",)))


def test_public_transport_does_not_retain_or_forward_credentials(credential_site):
    url, received = credential_site
    response = transport().request(
        url, headers={"Cookie": "session=fixture", "Authorization": "Bearer fixture"}
    )
    assert not any(k.lower() in {"cookie", "authorization"} for k in received[0])
    assert "set-cookie" not in response.headers
    assert not response.set_cookies


def test_browser_transport_preserves_repeated_cookies_only_for_browser(credential_site):
    url, received = credential_site
    response = transport()._browser_request(
        url,
        headers={
            "Cookie": "session=fixture",
            "Origin": url,
            "Authorization": "Bearer must-not-forward",
            "Host": "169.254.169.254",
            "Proxy-Authorization": "must-not-forward",
        },
    )
    assert received[0]["Cookie"] == "session=fixture"
    assert received[0]["Origin"] == url
    assert received[0]["Host"] == url.removeprefix("http://")
    assert "Authorization" not in received[0]
    assert "Proxy-Authorization" not in received[0]
    assert response.set_cookies == (
        "session=fixture; HttpOnly; SameSite=Strict; Path=/",
        "scoped=second; Path=/private",
    )
    assert "fixture" not in repr(response)
    assert "set-cookie" not in response.headers


def test_browser_transport_never_follows_redirect_with_cookie(credential_site):
    url, received = credential_site
    response = transport()._browser_request(
        url + "/redirect", headers={"Cookie": "secret=x"}
    )
    assert response.status == 302
    assert response.headers["location"] == url + "/destination"
    assert len(received) == 1
    assert len(response.set_cookies) == 2


def test_browser_cookie_header_injection_fails_before_connection(credential_site):
    url, received = credential_site
    with pytest.raises(AeroError) as error:
        transport()._browser_request(url, headers={"Cookie": "x=y\r\nHost: evil"})
    assert error.value.code == "INVALID_REQUEST"
    assert received == []


def test_browser_transport_retains_network_restrictions():
    with pytest.raises(AeroError) as error:
        SafeTransport()._browser_request(
            "http://169.254.169.254", headers={"Cookie": "x=y"}
        )
    assert error.value.code == "BLOCKED_DESTINATION"


def test_browser_rejects_metadata_redirect_before_returning_cookies(credential_site):
    url, received = credential_site
    with pytest.raises(AeroError) as error:
        transport()._browser_request(
            url + "/blocked-redirect", headers={"Cookie": "x=y"}
        )
    assert error.value.code == "BLOCKED_DESTINATION"
    assert len(received) == 1


@pytest.mark.parametrize("path", ["/oversized-cookie", "/folded-cookie"])
def test_browser_rejects_unbounded_or_folded_cookie_responses(credential_site, path):
    url, received = credential_site
    with pytest.raises(AeroError) as error:
        transport()._browser_request(url + path)
    assert error.value.code == "INVALID_RESPONSE"
    assert len(received) == 1
