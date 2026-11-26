"""Complete deterministic login/update/logout through the public supervised SDK."""

from aerobrowse import AeroBrowser
from aerobrowse.runtime import ResourceLimits
from aerobrowse.security import NetworkPolicy
from benchmarks.agent.fixture import AgentFixture
from benchmarks.agent.workflows import login_update_logout


def main():
    with (
        AgentFixture() as fixture,
        AeroBrowser(
            default_mode="fidelity",
            policy=NetworkPolicy(allow_networks=("127.0.0.1/32",)),
            resource_limits=ResourceLimits(processes=256),
        ) as browser,
    ):
        login_update_logout(browser, fixture)
        print(
            {
                "task": "authenticated_update",
                "independent_verdict": fixture.verdict("authenticated_update", ""),
                "state": fixture.receipt_state(),
            }
        )


if __name__ == "__main__":
    main()
