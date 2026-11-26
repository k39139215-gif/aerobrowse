import pytest

from aerobrowse import TurboEngine


def test_default_transport_rejects_loopback(site):
    result = TurboEngine().fetch(site)
    assert not result["success"]
    assert result["error"]["code"] == "BLOCKED_DESTINATION"


import socket

from aerobrowse.errors import AeroError
from aerobrowse.security import Limits, NetworkPolicy, SafeTransport


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://169.254.169.254",
        "http://[::1]",
        "http://[fc00::1]",
        "http://[fe80::1]",
        "http://[::]",
        "http://224.0.0.1",
        "http://0.0.0.0",
        "http://240.0.0.1",
        "http://[::ffff:127.0.0.1]",
        "http://[64:ff9b::7f00:1]",
        "http://localhost",
        "http://foo.localhost",
        "http://service.internal",
        "file:///etc/passwd",
        "data:text/html,x",
        "javascript:alert(1)",
        "http://2130706433",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://127.1",
        "http://user:secret@example.com",
        "http://[fe80::1%25eth0]",
        "http://example.com\\@127.0.0.1",
        "http://example.com\n",
        "https://example.com:99999",
    ],
)
def test_policy_rejects_unsafe_urls(url):
    with pytest.raises(AeroError):
        NetworkPolicy().validate(url)


def test_explicit_allowlist_and_redirect_revalidation(site):
    policy = NetworkPolicy(allow_networks=("127.0.0.1/32",))
    assert SafeTransport(policy).request(site).status == 200
    with pytest.raises(AeroError, match="Destination is not permitted"):
        SafeTransport(policy).request(site + "/redirect")


def test_mixed_dns_answer_fails_closed(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 80)),
        ],
    )
    with pytest.raises(AeroError) as error:
        NetworkPolicy().validate("https://safe.example")
    assert error.value.code == "BLOCKED_DESTINATION"


def test_pin_does_not_resolve_again_during_connection(site, monkeypatch):
    # Synthetic DNS at the trust boundary, actual TCP server/response underneath.
    calls = []

    def dns(*args):
        calls.append(args)
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("127.0.0.1" if len(calls) == 1 else "169.254.169.254", 80),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    port = site.rsplit(":", 1)[1]
    response = SafeTransport(NetworkPolicy(allow_networks=("127.0.0.1/32",))).request(
        f"http://pin.example:{port}/"
    )
    assert b"Private service secret" in response.body
    assert len(calls) == 1


def test_length_and_response_limits(site):
    with pytest.raises(AeroError) as error:
        NetworkPolicy().validate("https://example.com/" + "x" * 8192)
    assert error.value.code == "INVALID_URL"
    policy = NetworkPolicy(
        allow_networks=("127.0.0.1/32",), limits=Limits(response_bytes=8)
    )
    with pytest.raises(AeroError) as error:
        SafeTransport(policy).request(site)
    assert error.value.code == "RESPONSE_TOO_LARGE"


def test_header_secrets_are_not_forwarded(site, monkeypatch):
    from aerobrowse.security import _PinnedConnection

    captured = []
    original = _PinnedConnection.request

    def capture(self, method, url, body=None, headers=None):
        captured.append(headers)
        return original(self, method, url, body=body, headers=headers)

    monkeypatch.setattr(_PinnedConnection, "request", capture)
    SafeTransport(NetworkPolicy(allow_networks=("127.0.0.1/32",))).request(
        site, headers={"Authorization": "secret", "Cookie": "session=secret"}
    )
    assert all(k.lower() not in {"authorization", "cookie"} for k in captured[0])


from aerobrowse.fidelity import FidelityEngine


def test_browser_refuses_unisolated_host_network():
    import sys

    if sys.platform == "linux":
        pytest.skip("Linux namespace launch is covered by integration job")
    engine = FidelityEngine()
    try:
        result = engine.navigate("https://example.com")
        assert not result["success"]
        assert result["error"]["code"] == "NETWORK_ISOLATION_UNAVAILABLE"
        assert engine.browser is None
    finally:
        engine.close()


def test_redirect_count_and_request_deadline(site):
    policy = NetworkPolicy(allow_networks=("127.0.0.1/32",), limits=Limits(redirects=2))
    with pytest.raises(AeroError) as error:
        SafeTransport(policy).request(site + "/loop")
    assert error.value.code == "TOO_MANY_REDIRECTS"
    policy = NetworkPolicy(
        allow_networks=("127.0.0.1/32",), limits=Limits(timeout=0.05)
    )
    with pytest.raises(AeroError) as error:
        SafeTransport(policy).request(site + "/slow")
    assert error.value.code == "TIMEOUT"
