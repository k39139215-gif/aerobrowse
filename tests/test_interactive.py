import pytest
from aerobrowse.fidelity import FidelityEngine


def test_fidelity_engine_navigation():
    fidelity = FidelityEngine(headless=True)
    res = fidelity.navigate("https://example.com")
    assert res["success"] is True
    assert "Example Domain" in res["title"]
    assert res["engine"] == "fidelity"
    assert len(res["actions"]) >= 1
    fidelity.close()
