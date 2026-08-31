import logging
import time
from typing import Any, Dict, List, Optional

import requests

from ..config import ScryfallConfig

logger = logging.getLogger("mtg_proxy")


class ScryfallError(Exception):
    """Erro genérico ao falar com a Scryfall."""


class ScryfallRateLimitError(ScryfallError):
    """Erro após esgotar retries com HTTP 429."""


class ScryfallServerError(ScryfallError):
    """Erro após esgotar retries com HTTP 5xx."""


class ScryfallClient:
    """Cliente HTTP responsável para a API da Scryfall.

    - envia User-Agent e Accept descritivos;
    - respeita timeout, retries e delay entre requisições;
    - trata HTTP 429 (usando Retry-After) e 5xx.
    """

    BASE_URL = "https://api.scryfall.com"

    def __init__(self, config: ScryfallConfig):
        self.timeout = config.timeout_seconds
        self.max_retries = config.max_retries
        self.delay = config.request_delay_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": config.user_agent,
                "Accept": "application/json",
            }
        )

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
            except requests.Timeout:
                if attempt > self.max_retries:
                    raise ScryfallError(f"Timeout ao acessar {url}") from None
                logger.warning(f"[WARN] Timeout em {url}; tentativa {attempt}/{self.max_retries}")
                time.sleep(self.delay * attempt)
                continue

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", self.delay))
                if attempt > self.max_retries:
                    raise ScryfallRateLimitError(
                        "Limite de requisições da Scryfall excedido (HTTP 429)."
                    )
                logger.warning(f"[WARN] HTTP 429; aguardando {retry_after:.1f}s")
                time.sleep(retry_after)
                continue

            if resp.status_code >= 500:
                if attempt > self.max_retries:
                    raise ScryfallServerError(f"Erro {resp.status_code} da Scryfall em {url}")
                logger.warning(
                    f"[WARN] HTTP {resp.status_code}; tentativa {attempt}/{self.max_retries}"
                )
                time.sleep(self.delay * attempt)
                continue

            try:
                resp.raise_for_status()
            except requests.HTTPError as exc:
                raise ScryfallError(f"HTTP {resp.status_code} em {url}: {exc}") from exc
            if self.delay:
                time.sleep(self.delay)
            return resp

    def get_json(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        resp = self._request("GET", f"{self.BASE_URL}{path}", params=params)
        return resp.json()

    def get_collection(self, identifiers: List[Dict[str, str]]) -> Dict[str, Any]:
        """Consulta em lote via /cards/collection (POST)."""
        resp = self._request(
            "POST",
            f"{self.BASE_URL}/cards/collection",
            json={"identifiers": identifiers},
        )
        return resp.json()

    def search(self, query: str, unique: str = "prints") -> Dict[str, Any]:
        return self.get_json("/cards/search", params={"q": query, "unique": unique})

    def download_image(self, url: str) -> bytes:
        attempt = 0
        while True:
            attempt += 1
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except requests.Timeout:
                if attempt > self.max_retries:
                    raise ScryfallError(f"Timeout baixando imagem {url}") from None
                time.sleep(self.delay * attempt)
                continue
            resp.raise_for_status()
            return resp.content
