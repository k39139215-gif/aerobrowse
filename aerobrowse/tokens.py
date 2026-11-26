"""Tokenizer metrics; never substitute character division after tokenizer failure."""
from importlib.metadata import version
from functools import lru_cache
from typing import Any
import tiktoken
from aerobrowse.errors import AeroError

@lru_cache(maxsize=4)
def encoding(name: str) -> Any:
    if name not in {'cl100k_base','o200k_base','p50k_base'}:
        raise AeroError('TOKENIZER_ERROR','Unsupported tokenizer')
    try:
        return tiktoken.get_encoding(name)
    except Exception as exc:
        raise AeroError('TOKENIZER_ERROR','Tokenizer could not be initialized') from exc

def measure(original: str, extracted: str, tokenizer: str = 'cl100k_base') -> dict[str,Any]:
    try:
        enc = encoding(tokenizer)
        before = len(enc.encode(original,disallowed_special=()))
        after = len(enc.encode(extracted,disallowed_special=()))
        reduction = round((1-after/before)*100,2) if before else 0.0
        return {'original_tokens':before,'extracted_tokens':after,'token_reduction_pct':reduction,
                'reduction_pct':reduction,'tokenizer':{'library':'tiktoken','version':version('tiktoken'),'name':tokenizer}}
    except AeroError:
        raise
    except Exception as exc:
        raise AeroError('TOKENIZER_ERROR','Token measurement failed') from exc
