from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class CardRequest:
    """Pedido de uma carta parsed do deck.txt (antes de consultar a Scryfall)."""

    name: str
    quantity: int = 1
    language: Optional[str] = None
    set_code: Optional[str] = None
    collector_number: Optional[str] = None

    def key(self) -> str:
        """Identificador estável para deduplicação/agrupamento de imagem."""
        return "|".join(
            str(v) for v in (self.name, self.language, self.set_code, self.collector_number)
        )


@dataclass
class ResolvedCard:
    """Carta já resolvida contra a Scryfall: impressão escolhida + URL da imagem."""

    request: CardRequest
    scryfall_id: str
    name: str
    language: str
    set_code: str
    set_name: str
    collector_number: str
    released_at: str
    image_url: Optional[str]
    fallback_used: bool = False
    image_path: Optional[Path] = None
    border_color: Optional[str] = None

    def cache_key(self) -> str:
        return f"{self.name}|{self.language}|{self.set_code}|{self.collector_number}"


class CardNotFoundError(Exception):
    """Levantada quando a Scryfall não retorna nenhuma impressão para o pedido."""

    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Carta não encontrada: {name}")

