import pytest

from aerobrowse.fidelity import FidelityEngine


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"name": ""},
        {"name": "x" * 513},
        {"name": "Ready", "role": "invalid"},
        {"name": "Ready", "timeout_ms": True},
        {"name": "Ready", "timeout_ms": 0},
        {"name": "Ready", "timeout_ms": 30001},
        {"name": "Ready", "action_id": "f" * 32 + ":1"},
        {"name": "Ready", "generation": "f" * 32},
    ],
)
def test_invalid_wait_fails_before_browser_startup(kwargs):
    engine = FidelityEngine()
    result = engine.wait(**kwargs)
    assert result["error"]["code"] == "INVALID_ARGUMENT", result
    assert engine.browser is None
