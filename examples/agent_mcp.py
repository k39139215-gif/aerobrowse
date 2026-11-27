"""Complete deterministic task against the actual AeroBrowse stdio MCP process."""

from benchmarks.agent.fixture import AgentFixture
from benchmarks.agent.workflows import MCPBrowser, login_update_logout


def main():
    with AgentFixture() as fixture:
        browser = MCPBrowser()
        try:
            login_update_logout(browser, fixture)
            print(
                {
                    "task": "authenticated_update",
                    "independent_verdict": fixture.verdict("authenticated_update", ""),
                }
            )
        finally:
            browser.close()


if __name__ == "__main__":
    main()
