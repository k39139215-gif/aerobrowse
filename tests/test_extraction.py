"""Bounded semantic extraction and live action metadata contract."""
import pytest
from aerobrowse import SemanticPruner
from aerobrowse.errors import AeroError

def test_iframe_and_table_relations_survive():
    result = SemanticPruner().prune('<main><h2>العربية 中文</h2><iframe src="https://embed.example" title="Report"></iframe><table><tr><th id="h" scope="col">Total</th></tr><tr><td headers="h">₹42</td></tr></table></main>')
    assert 'Report' in result['markdown']
    assert result['tables'][0]['rows'][1][0]['headers'] == ['h']
    assert result['quality']['embedded_content_inaccessible'] == 1

def test_safe_values_and_hidden_elements():
    result = SemanticPruner().prune('<input type="password" value="SECRET"><input hidden value="HIDDEN"><input type="hidden" value="TOKEN"><button disabled>Stop</button>')
    assert 'SECRET' not in str(result)
    assert 'HIDDEN' not in str(result)
    assert 'TOKEN' not in str(result)
    assert all(a['input_type'] != 'hidden' for a in result['actions'])
    assert all(not a['executable'] for a in result['actions'])

def test_token_metrics_are_not_character_estimates():
    result = SemanticPruner().prune('<h1>Hello 世界</h1>')
    import tiktoken
    assert result['original_tokens'] == len(tiktoken.get_encoding('cl100k_base').encode('<h1>Hello 世界</h1>'))
    assert result['tokenizer']['name'] == 'cl100k_base'
    assert result['tokenizer']['version']
    assert result['reduction_pct'] == result['token_reduction_pct']

def test_deep_html_fails_explicitly():
    with pytest.raises(AeroError) as error:
        SemanticPruner().prune('<div>' * 200 + 'text' + '</div>' * 200)
    assert error.value.code == 'HTML_LIMIT_EXCEEDED'
