import pytest

from aerobrowse.benchmark import write_receipt


@pytest.mark.parametrize(
    "path",
    [
        "../secret.json",
        "evidence/../secret.json",
        "other/output.json",
        "/tmp/output.json",
    ],
)
def test_benchmark_output_cannot_escape_evidence(tmp_path, monkeypatch, path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        write_receipt(path, {})
    assert not (tmp_path / "secret.json").exists()


def test_benchmark_does_not_overwrite_existing_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = write_receipt("evidence/result.json", {"success": True})
    before = result.read_text()
    with pytest.raises(FileExistsError):
        write_receipt("evidence/result.json", {"success": False})
    assert result.read_text() == before


@pytest.mark.parametrize(
    "module", ["extraction_quality", "shared_load", "concurrency", "run"]
)
def test_agent_receipt_entrypoints_use_confined_exclusive_writer(
    tmp_path, monkeypatch, module
):
    import importlib

    target = importlib.import_module("benchmarks.agent." + module)
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError):
        target.write_receipt("../escape.json", {"success": True})
    assert not (tmp_path.parent / "escape.json").exists()
