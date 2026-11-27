import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar

from benchmarks.agent.fixture import AgentFixture


def test_fixture_judges_persisted_state_not_completion_claim():
    with AgentFixture() as fixture:
        assert not fixture.verdict("authenticated_update", "success")
        jar = CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
        for path, values in [
            ("/login", {"username": "agent", "password": "fixture-only"}),
            ("/record", {"name": "Agent updated"}),
            ("/logout", {}),
        ]:
            with opener.open(
                fixture.url + path, urllib.parse.urlencode(values).encode(), timeout=5
            ) as response:
                assert response.status == 200
        assert fixture.verdict("authenticated_update", "")
        assert fixture.receipt_state()["active_logins"] == 0
        assert not fixture.verdict("multistep_form", "submitted")
        with opener.open(
            fixture.url + "/wizard", b"plan=pro&agree=on", timeout=5
        ) as response:
            assert b"Confirm Pro plan" in response.read()
        with opener.open(
            fixture.url + "/wizard/confirm", b"plan=pro&agree=yes", timeout=5
        ) as response:
            assert b"Request submitted" in response.read()
        assert fixture.verdict("multistep_form", "")


def test_fixture_html_and_wrong_password():
    with AgentFixture() as fixture:
        with urllib.request.urlopen(fixture.url + "/docs", timeout=5) as response:
            assert b"17 days" in response.read()
        try:
            urllib.request.urlopen(
                fixture.url + "/login", b"username=agent&password=wrong", timeout=5
            )
        except urllib.error.HTTPError as error:
            assert error.code == 403
        else:
            raise AssertionError("Invalid credentials accepted")
        assert fixture.receipt_state()["logins"] == 0
