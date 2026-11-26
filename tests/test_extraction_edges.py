"""Semantic relationships and complete-output token accounting regressions."""

import json

import pytest
import tiktoken

from aerobrowse.errors import AeroError
from aerobrowse.pruner import SemanticPruner
from aerobrowse.security import Limits


def test_ordered_and_nested_lists_keep_order_and_depth():
    result = SemanticPruner().prune(
        '<ol start="3"><li>First<ul><li>Nested</li></ul></li>'
        '<li value="7">Last</li></ol><ol reversed><li>A</li><li>B</li></ol>'
    )
    assert "3. First\n  - Nested" in result["markdown"]
    assert "7. Last" in result["markdown"]
    assert "2. A\n1. B" in result["markdown"]


def test_nested_table_parent_and_explicit_headers_remain_unambiguous():
    result = SemanticPruner().prune(
        '<table><caption>Outer</caption><tr><th id="total" scope="col">Total</th></tr>'
        '<tr><td headers="total" rowspan="2">42<table><caption>Inner</caption>'
        '<tr><th id="total">Detail</th><td headers="total">9</td></tr></table>'
        "</td></tr></table>"
    )
    outer, inner = result["tables"]
    assert outer["parent_table"] is None
    assert inner["parent_table"] == 0
    assert inner["parent_cell"] == {"row": 1, "column": 0}
    outer_cell = outer["rows"][1][0]
    assert outer_cell["text"] == "42"
    assert outer_cell["nested_tables"] == [1]
    assert outer_cell["rowspan"] == "2"
    assert outer_cell["resolved_headers"] == [{"id": "total", "text": "Total"}]
    assert inner["rows"][0][1]["resolved_headers"] == [
        {"id": "total", "text": "Detail"}
    ]
    assert len(outer["rows"]) == 2


def test_wrapped_labels_and_image_link_names_are_preserved_without_values():
    result = SemanticPruner().prune(
        '<label>Account <input value="SECRET"></label>'
        "<label>Choice <select><option>First</option></select></label>"
        '<a href="/report"><img alt="Report" src="/chart.png"></a>'
        '<label for="notes">Notes</label><textarea id="notes">PRIVATE</textarea>',
        "https://example.org/",
    )
    assert [item["accessible_name"] for item in result["actions"]] == [
        "Account",
        "Choice",
        "Report",
        "Notes",
    ]
    assert "SECRET" not in json.dumps(result)
    assert "PRIVATE" not in json.dumps(result)


@pytest.mark.parametrize(
    "html",
    ["", "<html><body></body></html>", "<!DOCTYPE html><html><body></body></html>"],
)
def test_empty_documents_report_no_meaningful_content(html):
    result = SemanticPruner().prune(html)
    assert result["markdown"] == ""
    assert result["actions"] == []
    assert result["quality"]["empty_content"]


def test_repeated_multilingual_content_is_not_deduplicated():
    result = SemanticPruner().prune(
        '<p dir="rtl">رصيد ١٢٣</p><p dir="rtl">رصيد ١٢٣</p>'
        "<ol start=invalid><li value=999999999999999999999>Alpha</li><li>Beta</li></ol>"
    )
    assert result["markdown"].count("رصيد ١٢٣") == 2
    assert "1. Alpha\n2. Beta" in result["markdown"]


def test_malformed_multilingual_rtl_content_and_embeds_are_explicit():
    result = SemanticPruner().prune(
        '<main dir="rtl"><h1>مرحبا 中文</h1><p>שלום κόσμε<p>第二段'
        '<iframe title="Finance" src="https://user:pass@embed.example/chart?key=SECRET#fragment">'
        '</iframe><iframe title="Inline" srcdoc="PRIVATE"></iframe></main>'
    )
    assert all(
        word in result["markdown"]
        for word in ("مرحبا", "中文", "שלום", "κόσμε", "第二段")
    )
    assert "https://embed.example/chart" in result["markdown"]
    assert "SECRET" not in json.dumps(result)
    assert "PRIVATE" not in json.dumps(result)
    assert result["quality"]["embedded_content_inaccessible"] == 2


@pytest.mark.parametrize(
    ("limits", "html", "code"),
    [
        (Limits(response_bytes=3), "世界", "HTML_TOO_LARGE"),
        (Limits(html_nodes=3), "<p>A</p><p>B</p>", "HTML_LIMIT_EXCEEDED"),
        (
            Limits(html_depth=3),
            "<div><div><div><p>A</p></div></div></div>",
            "HTML_LIMIT_EXCEEDED",
        ),
    ],
)
def test_extraction_limits_fail_explicitly(limits, html, code):
    with pytest.raises(AeroError) as error:
        SemanticPruner(limits=limits).prune(html)
    assert error.value.code == code


@pytest.mark.parametrize("tokenizer", ["cl100k_base", "o200k_base", "p50k_base"])
def test_full_output_measurement_includes_action_and_table_metadata(tokenizer):
    from aerobrowse.tokens import measure_output

    result = SemanticPruner(tokenizer=tokenizer).prune(
        "<button>Go</button><table><tr><td>世界</td></tr></table>"
    )
    metric = result["serialized_output"]
    content = {
        key: value for key, value in result.items() if key != "serialized_output"
    }
    serialized = json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert metric["tokens"] == len(
        tiktoken.get_encoding(tokenizer).encode(serialized, disallowed_special=())
    )
    assert metric["bytes"] == len(serialized.encode("utf-8"))
    assert metric["tokens"] > result["extracted_tokens"]
    assert metric["reduction_pct"] == round(
        (1 - metric["tokens"] / result["original_tokens"]) * 100, 2
    )
    assert measure_output(result) == {"serialized_output": metric}
    result["actions"] = []
    assert measure_output(result)["serialized_output"]["tokens"] < metric["tokens"]


def test_full_output_measurement_rejects_non_json_data():
    from aerobrowse.tokens import measure_output

    with pytest.raises(AeroError) as error:
        measure_output({"original_tokens": 1, "object": object()})
    assert error.value.code == "OUTPUT_SERIALIZATION_ERROR"


def test_tokenizer_special_text_is_counted_as_content():
    result = SemanticPruner().prune("<p>&lt;|endoftext|&gt;你好</p>")
    assert "<|endoftext|>你好" == result["markdown"]
    assert result["serialized_output"]["tokens"] > 0


def test_scoped_table_headers_follow_spans_without_nested_leaks():
    result = SemanticPruner().prune(
        '<table><thead><tr><th rowspan="2">Account</th><th colspan="2" scope="colgroup">Balance</th></tr>'
        '<tr><th scope="col">Debit</th><th scope="col">Credit</th></tr></thead>'
        '<tbody><tr><th scope="row">Cash</th><td>42</td><td>0</td></tr>'
        '<tr><th scope="row">Bank</th><td>7<table><tr><th>Nested</th><td>9</td></tr></table></td><td>1</td></tr></tbody></table>'
    )
    outer, inner = result["tables"]
    assert [h["text"] for h in outer["rows"][2][1]["inferred_headers"]] == [
        "Balance",
        "Debit",
        "Cash",
    ]
    assert [h["text"] for h in outer["rows"][3][2]["inferred_headers"]] == [
        "Balance",
        "Credit",
        "Bank",
    ]
    assert "Nested" not in str(outer["rows"][3][1]["inferred_headers"])
    assert [h["text"] for h in inner["rows"][0][1]["inferred_headers"]] == ["Nested"]


def test_document_language_direction_and_landmarks_are_preserved():
    result = SemanticPruner().prune(
        '<html lang="ar" dir="rtl"><body><nav aria-label="القائمة">Menu</nav><main><h1>مرحبا</h1><p lang="he" dir="rtl">שלום</p></main></body></html>'
    )
    assert result["document"] == {"language": "ar", "direction": "rtl"}
    assert result["landmarks"] == [
        {"role": "navigation", "label": "القائمة"},
        {"role": "main", "label": ""},
    ]
    assert result["language_regions"] == [
        {"language": "he", "direction": "rtl", "text": "שלום"}
    ]


def test_scoped_rowgroups_do_not_leak_between_table_sections():
    result = SemanticPruner().prune(
        '<table><tbody><tr><th scope="rowgroup">North</th><td>1</td></tr><tr><td>Second</td><td>2</td></tr></tbody><tbody><tr><th scope="rowgroup">South</th><td>3</td></tr></tbody></table>'
    )
    rows = result["tables"][0]["rows"]
    assert [h["text"] for h in rows[1][1]["inferred_headers"]] == ["North"]
    assert [h["text"] for h in rows[2][1]["inferred_headers"]] == ["South"]


def test_semantic_metadata_limit_is_explicit_and_bounded():
    result = SemanticPruner().prune(
        "<main>" + '<p lang="ar">مرحبا</p>' * 300 + "</main>"
    )
    assert len(result["language_regions"]) == 256
    assert (
        "semantic_metadata_truncated" in result["quality"]["missing_content_indicators"]
    )
