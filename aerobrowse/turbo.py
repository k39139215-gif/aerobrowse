"""
AeroBrowse Turbo Engine — Blazing-Fast Lightweight Client
Uses curl_cffi with full Chrome TLS/JA3 impersonation.
Under 6MB RAM, sub-100ms latency, zero Chromium processes spawned.
"""

import time
from typing import Dict, Any, Optional
from curl_cffi import requests
from aerobrowse.pruner import SemanticPruner


class TurboEngine:
    """
    Tier-1 Engine for text, documentation, articles, search results, and static/SSR web pages.
    """

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.pruner = SemanticPruner()

    def fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        start_time = time.time()
        
        default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        if headers:
            default_headers.update(headers)

        try:
            resp = requests.get(
                url,
                headers=default_headers,
                impersonate="chrome124",
                timeout=self.timeout,
                allow_redirects=True
            )
            elapsed_ms = round((time.time() - start_time) * 1000, 1)

            html = resp.text
            status_code = resp.status_code

            # Check if page is an empty client-side SPA that requires a full JS engine
            needs_js = self._detect_spa_fallback(html)

            # Prune and optimize
            parsed = self.pruner.prune(html, base_url=str(resp.url))

            return {
                "success": status_code < 400,
                "status_code": status_code,
                "url": str(resp.url),
                "title": parsed["title"],
                "markdown": parsed["markdown"],
                "actions": parsed["actions"],
                "reduction_pct": parsed["reduction_pct"],
                "original_chars": parsed["original_chars"],
                "pruned_chars": parsed["pruned_chars"],
                "elapsed_ms": elapsed_ms,
                "engine": "turbo",
                "needs_fidelity": needs_js
            }

        except Exception as e:
            elapsed_ms = round((time.time() - start_time) * 1000, 1)
            return {
                "success": False,
                "status_code": 0,
                "url": url,
                "title": "Fetch Failed",
                "markdown": f"Error loading URL: {str(e)}",
                "actions": [],
                "reduction_pct": 0.0,
                "original_chars": 0,
                "pruned_chars": 0,
                "elapsed_ms": elapsed_ms,
                "engine": "turbo",
                "needs_fidelity": True
            }

    def _detect_spa_fallback(self, html: str) -> bool:
        """Determines if the page is an empty SPA shell that needs full JavaScript execution."""
        lower = html.lower()
        if "you need to enable javascript" in lower:
            return True
        if "please enable js" in lower:
            return True
        # If body contains virtually no text and only root divs
        if len(html) < 2000 and ('id="root"' in html or 'id="app"' in html or '__next' in html):
            return True
        return False
