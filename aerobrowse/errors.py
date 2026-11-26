"""Safe, stable public errors."""
from typing import Any

class AeroError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message

    def result(self) -> dict[str, Any]:
        return {'success': False, 'error': {'code': self.code, 'message': self.message},
                'markdown': '', 'actions': [], 'title': '', 'original_chars': 0,
                'pruned_chars': 0, 'reduction_pct': None}
