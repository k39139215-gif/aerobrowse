"""Tokenizer metrics; never substitute character division after tokenizer failure."""

import json
from collections.abc import Mapping
from functools import lru_cache
from importlib.metadata import version
from typing import Any

import tiktoken

from aerobrowse.errors import AeroError


@lru_cache(maxsize=4)
def encoding(name: str) -> Any:
    if name not in {"cl100k_base", "o200k_base", "p50k_base"}:
        raise AeroError("TOKENIZER_ERROR", "Unsupported tokenizer")
    try:
        return tiktoken.get_encoding(name)
    except Exception as exc:
        raise AeroError(
            "TOKENIZER_ERROR", "Tokenizer could not be initialized"
        ) from exc


def measure(
    original: str, extracted: str, tokenizer: str = "cl100k_base"
) -> dict[str, Any]:
    try:
        enc = encoding(tokenizer)
        before = len(enc.encode(original, disallowed_special=()))
        after = len(enc.encode(extracted, disallowed_special=()))
        reduction = round((1 - after / before) * 100, 2) if before else 0.0
        return {
            "original_tokens": before,
            "extracted_tokens": after,
            "token_reduction_pct": reduction,
            "reduction_pct": reduction,
            "tokenizer": {
                "library": "tiktoken",
                "version": version("tiktoken"),
                "name": tokenizer,
            },
        }
    except AeroError:
        raise
    except Exception as exc:
        raise AeroError("TOKENIZER_ERROR", "Token measurement failed") from exc


def measure_output(output: Mapping[str, Any]) -> dict[str, Any]:
    """Measure canonical JSON, excluding only this measurement to avoid recursion.

    Call again after adding envelope fields or replacing live actions. This reports
    content serialization cost, not MCP framing or a model's chat-template overhead.
    Existing extracted_tokens remains the Markdown-only metric for compatibility.
    """
    try:
        serialized = json.dumps(
            {key: value for key, value in output.items() if key != "serialized_output"},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError) as exc:
        raise AeroError(
            "OUTPUT_SERIALIZATION_ERROR", "Snapshot cannot be serialized as JSON"
        ) from exc
    tokenizer = output.get("tokenizer", {}).get("name", "cl100k_base")
    try:
        count = len(encoding(tokenizer).encode(serialized, disallowed_special=()))
        before = output.get("original_tokens", 0)
        return {
            "serialized_output": {
                "tokens": count,
                "bytes": len(serialized.encode("utf-8")),
                "reduction_pct": round((1 - count / before) * 100, 2)
                if before
                else 0.0,
                "serialization": "json;ensure_ascii=false;sort_keys=true;compact=true",
                "excluded_fields": ["serialized_output"],
            }
        }
    except AeroError:
        raise
    except Exception as exc:
        raise AeroError("TOKENIZER_ERROR", "Token measurement failed") from exc
