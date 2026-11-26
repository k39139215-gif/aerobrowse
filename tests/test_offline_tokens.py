import subprocess
import sys

import pytest


@pytest.mark.parametrize("name", ["cl100k_base", "o200k_base", "p50k_base"])
def test_tokenizer_initializes_without_network_or_cache(name, tmp_path):
    code = """
import socket,sys
from aerobrowse.tokens import encoding

def denied(*args, **kwargs):
    raise AssertionError("Tokenizer attempted network access")

socket.socket = denied
enc = encoding(sys.argv[1])
assert len(enc.encode("مرحبا 世界 hello")) > 0
"""
    import os

    result = subprocess.run(
        [sys.executable, "-c", code, name],
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "TIKTOKEN_CACHE_DIR": str(tmp_path / "empty")},
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "empty").exists()


def test_bundled_vocab_checksum_failure_is_explicit(tmp_path, monkeypatch):
    import aerobrowse.tokens as tokens
    from aerobrowse.errors import AeroError
    import json

    root = tmp_path / "token_data"
    root.mkdir()
    (root / "manifest.json").write_text(
        json.dumps({"cl100k_base": {"sha256": "invalid"}})
    )
    (root / "cl100k_base.tiktoken.gz").write_bytes(b"tampered")
    monkeypatch.setattr(tokens, "files", lambda package: tmp_path)
    tokens.encoding.cache_clear()
    try:
        with pytest.raises(AeroError) as caught:
            tokens.encoding("cl100k_base")
        assert caught.value.code == "TOKENIZER_ERROR"
    finally:
        tokens.encoding.cache_clear()
