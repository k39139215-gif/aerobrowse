"""Isolated-world action map: validation and DOM activation occur in one renderer task.

Actions are synthetic DOM operations. They never substitute an ordinal/selector and
are deliberately unavailable for sites requiring trusted physical input.
"""

import json
from importlib.resources import files
from typing import Any

from aerobrowse.errors import AeroError

# Page scripts cannot access this isolated execution context or replace its builtins.
INSTALL = files("aerobrowse").joinpath("action_runtime.js").read_text(encoding="utf-8")


class ActionContext:
    """Own one CDP isolated context. Values are always JSON serialized."""

    def __init__(self, page: Any):
        self.page = page
        self.session = page.context.new_cdp_session(page)
        frame = self.session.send("Page.getFrameTree")["frameTree"]["frame"]["id"]
        self.context_id = self.session.send(
            "Page.createIsolatedWorld",
            {"frameId": frame, "worldName": "AeroBrowse actions"},
        )["executionContextId"]
        self._evaluate("globalThis.__aeroState = " + INSTALL + "; true")

    def _evaluate(self, expression: str) -> Any:
        result = self.session.send(
            "Runtime.evaluate",
            {
                "expression": expression,
                "contextId": self.context_id,
                "returnByValue": True,
            },
        )
        if result.get("exceptionDetails"):
            raise AeroError(
                "ACTION_CONTEXT_FAILED", "Isolated browser action context failed"
            )
        return result.get("result", {}).get("value")

    def snapshot(self, generation: str, html_limit: int = 5_000_000) -> dict[str, Any]:
        return self._evaluate(
            "globalThis.__aeroState.snapshot("
            + json.dumps(generation)
            + ","
            + str(html_limit)
            + ")"
        )

    def perform(
        self, action_id: str, generation: str, operation: str, value: Any
    ) -> dict[str, Any]:
        arguments = json.dumps(
            {
                "id": action_id,
                "generation": generation,
                "operation": operation,
                "value": value,
            }
        )
        return self._evaluate("globalThis.__aeroState.perform(" + arguments + ")")

    def close(self) -> None:
        try:
            self._evaluate("globalThis.__aeroState.dispose();true")
        finally:
            self.session.detach()
