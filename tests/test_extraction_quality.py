from benchmarks.agent.extraction_quality import run


def test_owned_quality_corpus_reports_real_recall_and_complete_tokens():
    result = run()
    assert len(result["cases"]) >= 10
    assert result["missing_requirements"] == 0
    assert result["checked_requirements"] >= 30
    assert result["recall"] == 1.0
    for row in result["cases"]:
        assert row["missing"] == []
        assert row["tokenizer"]["version"]
        assert row["complete_json_tokens"] > row["markdown_tokens"]
        assert row["checked_requirements"] > 0
