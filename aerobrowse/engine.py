"""
AeroBrowse Unified Hybrid Engine
Orchestrates Turbo (sub-50ms) and Fidelity (100% Blink compatibility)
with zero-overhead session pooling.
"""

from typing import Dict, Any, Optional
from aerobrowse.turbo import TurboEngine
from aerobrowse.fidelity import FidelityEngine


class AeroBrowser:
    """
    Main entry point for AeroBrowse.
    Automatically selects the optimal engine (Turbo vs Fidelity)
    based on page requirements and agent intent.
    """

    def __init__(self, default_mode: str = "auto"):
        self.default_mode = default_mode
        self.turbo = TurboEngine()
        self._fidelity: Optional[FidelityEngine] = None

    def _get_fidelity(self) -> FidelityEngine:
        if not self._fidelity:
            self._fidelity = FidelityEngine()
        return self._fidelity

    def fetch(self, url: str, force_fidelity: bool = False) -> Dict[str, Any]:
        """Fetches page content, parses markdown, and extracts actionable elements."""
        if force_fidelity or self.default_mode == "fidelity":
            fidelity = self._get_fidelity()
            return fidelity.navigate(url)

        # 1. Try Turbo Engine First (FastPath)
        res = self.turbo.fetch(url)

        # 2. If page is an empty client-side SPA or failed, fall back to Fidelity Engine
        if res.get("needs_fidelity") or not res.get("success"):
            fidelity = self._get_fidelity()
            return fidelity.navigate(url)

        return res

    def click(self, action_id: str) -> Dict[str, Any]:
        """Clicks an element by action ID on the active page."""
        return self._get_fidelity().click(action_id)

    def fill(self, action_id: str, text: str) -> Dict[str, Any]:
        """Fills an input field by action ID on the active page."""
        return self._get_fidelity().fill(action_id, text)

    def screenshot(self) -> bytes:
        """Captures a screenshot of the active page."""
        return self._get_fidelity().screenshot()

    def snapshot(self) -> Dict[str, Any]:
        """Returns the current page snapshot."""
        return self._get_fidelity().snapshot()

    def close(self):
        if self._fidelity:
            self._fidelity.close()
            self._fidelity = None
