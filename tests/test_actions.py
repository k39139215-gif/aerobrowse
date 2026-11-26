import pytest
from aerobrowse.fidelity import FidelityEngine

def test_action_ids_never_accept_selector_fallback():
    engine = FidelityEngine()
    for value in ['button', '1', '1\"] ; alert(1)', '', '../secret']:
        result = engine.click(value)
        assert result['error']['code'] == 'INVALID_ACTION_ID'
        assert engine.browser is None

def test_stale_generation_fails_before_browser_creation():
    engine = FidelityEngine()
    result = engine.click('a'*32+':1', generation='b'*32)
    assert result['error']['code'] == 'STALE_ACTION_ID'
    assert engine.browser is None
