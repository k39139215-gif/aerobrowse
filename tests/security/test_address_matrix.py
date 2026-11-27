"""Conservative address policy regression matrix; these are validation tests, not OS isolation proof."""

import pytest

from aerobrowse.errors import AeroError
from aerobrowse.security import NetworkPolicy


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://[::1]",
        "http://[::ffff:127.0.0.1]",
        "http://169.254.169.254/latest/meta-data",
        "http://[fe80::1]",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.1.1",
        "http://[fc00::1]",
        "http://0.0.0.0",
        "http://224.0.0.1",
        "http://240.0.0.1",
        "http://[::]",
        "http://2130706433",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://127.1",
        "http://127.000.000.001",
        "http://%31%32%37.0.0.1",
        "http://localhost.",
        "http://metadata.google.internal",
        "http://service.local",
        "file:///etc/passwd",
        "data:text/html,test",
        "javascript:alert(1)",
        "http://[fe80::1%25eth0]",
        "http://１２７.０.０.１",
        "http://127。0。0。1",
    ],
)
def test_non_public_and_ambiguous_hostnames_are_denied(url):
    policy = NetworkPolicy()
    with pytest.raises(AeroError):
        policy.validate(url)


@pytest.mark.parametrize(
    "address",
    ["::ffff:8.8.8.8", "64:ff9b::808:808", "2002:0808:0808::1", "2001:db8::1"],
)
def test_transition_ranges_fail_closed_even_with_allowlist(address):
    policy = NetworkPolicy(allow_networks=("::/0",))
    with pytest.raises(AeroError) as caught:
        policy.check_address(address)
    assert caught.value.code == "BLOCKED_DESTINATION"
