"""Bounded static retrieval through a DNS-pinned network transport."""
import time
from typing import Any
from bs4 import BeautifulSoup
from aerobrowse.errors import AeroError
from aerobrowse.pruner import SemanticPruner
from aerobrowse.security import Limits, NetworkPolicy, SafeTransport

class TurboEngine:
    def __init__(self, timeout: int = 12, *, policy: NetworkPolicy | None = None):
        self.policy = policy or NetworkPolicy(limits=Limits(timeout=timeout))
        self.transport = SafeTransport(self.policy)
        self.pruner = SemanticPruner()

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        start = time.monotonic()
        try:
            response = self.transport.request(url, headers=headers)
            html = response.body.decode('utf-8', errors='replace')
            result = self.pruner.prune(html, base_url=response.url)
            result.update(success=response.status < 400, status_code=response.status,
                          url=response.url, engine='turbo', needs_fidelity=self._detect_spa_fallback(html))
            for action in result['actions']:
                action['executable'] = False
            if response.status >= 400:
                result['error'] = {'code': 'HTTP_ERROR', 'message': 'Server returned an error status'}
        except AeroError as exc:
            result = exc.result()
            result.update(engine='turbo', needs_fidelity=False, status_code=0)
        result['elapsed_ms'] = round((time.monotonic() - start) * 1000, 2)
        return result

    def _detect_spa_fallback(self, html: str) -> bool:
        soup = BeautifulSoup(html, 'html.parser')
        explicit = any(text in soup.get_text(' ', strip=True).lower() for text in
                       ('you need to enable javascript', 'please enable javascript', 'please enable js'))
        for node in soup(['script', 'style', 'noscript']):
            node.decompose()
        text = soup.get_text(' ', strip=True)
        shell = soup.select_one('#root, #app, #__next, [ng-version], [data-v-app]')
        return explicit or bool(shell is not None and len(text.split()) < 30)

    def close(self) -> None:
        """Transport owns no persistent sockets or cookie state."""
