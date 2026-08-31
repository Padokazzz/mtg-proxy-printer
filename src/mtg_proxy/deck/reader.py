import logging
import re
from typing import List, Optional, Tuple

from ..models import CardRequest

logger = logging.getLogger("mtg_proxy")

# Cabeçalho: "Nome da Carta x4" ou "Nome da Carta X4"
_QUANTITY_X_RE = re.compile(r"^(?P<name>.*?)\s+x(?P<qty>\d+)$", re.IGNORECASE)
# Cabeçalho: "Nome da Carta 4x" ou "Nome da Carta 2X"
_QUANTITY_TRAIL_RE = re.compile(r"^(?P<name>.*?)\s+(?P<qty>\d+)[xX]$")
# Quantidade à esquerda (formato de exportação de deck): "1 Sol Ring", "6 Island",
# "35x Mountain" (com ou sem 'x' após o número)
_LEADING_QTY_RE = re.compile(r"^(\d+)\s*[xX]?\s+(.*)$")
# Opção chave=valor: "set=FDN" ou "cn=192"
_OPTION_RE = re.compile(r"^(?P<key>[A-Za-z_]+)=(?P<value>.*)$")
# Cabeçalho de seção (formato Commander): "COMMANDER", "LANDS (36)", "RAMP (6)"
_HEADER_RE = re.compile(r"^[A-Z0-9\s\(\)/\-]+$")


class DeckParseError(ValueError):
    """Erro de parsing de uma linha específica do deck."""


def _is_section_header(line: str) -> bool:
    """Linha em MAIÚSCULAS sem letras minúsculas (cabeçalho de seção)."""
    if line[0].isdigit():
        return False
    if not _HEADER_RE.fullmatch(line):
        return False
    return any(c.isalpha() for c in line)


def parse_deck(text: str, default_language: Optional[str] = None) -> Tuple[List[CardRequest], List[str]]:
    """Faz o parse do conteúdo de um deck.txt.

    Aceita dois estilos de linha de carta:
    - "Nome da Carta" / "Nome da Carta x4" (quantidade à direita);
    - "1 Nome da Carta" / "6 Island" / "35x Mountain" (quantidade à esquerda,
      exportação de deck; o 'x' após o número é opcional).

    Cartas duplas (MDFC) usam "//": "Riverglide Pathway // Lavaglide Pathway".
    Linhas vazias, comentários (#) e cabeçalhos de seção (TUDO MAIÚSCULAS) são
    ignorados. Opções continuam via "|": "Nome | pt | set=FDN | cn=192".
    """
    text = text.replace("\ufeff", "")
    requests: List[CardRequest] = []
    errors: List[str] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if _is_section_header(line):
            continue
        try:
            req = _parse_line(line, default_language)
            requests.append(req)
        except DeckParseError as exc:
            errors.append(f"Linha {lineno}: {exc}")

    return requests, errors


def _parse_line(line: str, default_language: Optional[str]) -> CardRequest:
    segments = [seg.strip() for seg in line.split("|")]
    head = segments[0]

    lead_match = _LEADING_QTY_RE.match(head)
    if lead_match:
        name = lead_match.group(2).strip()
        quantity = int(lead_match.group(1))
    else:
        qty_match = _QUANTITY_X_RE.match(head) or _QUANTITY_TRAIL_RE.match(head)
        if qty_match:
            name = qty_match.group("name").strip()
            quantity = int(qty_match.group("qty"))
        else:
            name = head.strip()
            quantity = 1

    if not name:
        raise DeckParseError("nome da carta vazio")
    if quantity < 1:
        raise DeckParseError(f"quantidade inválida: {quantity}")

    language = default_language
    set_code: Optional[str] = None
    collector_number: Optional[str] = None

    for option in segments[1:]:
        if not option:
            continue
        opt_match = _OPTION_RE.match(option)
        if opt_match:
            key = opt_match.group("key").lower()
            value = opt_match.group("value").strip()
            if key == "set":
                if not value:
                    raise DeckParseError("set vazio")
                set_code = value
            elif key in ("cn", "collector"):
                if not value:
                    raise DeckParseError("número de colecionador vazio")
                collector_number = value
            else:
                raise DeckParseError(f"opção desconhecida: {key}")
        else:
            # Sem '=', tratamos como código de idioma (ex.: pt, en).
            if len(option) > 3 or not option.isalpha():
                raise DeckParseError(f"opção inválida: {option}")
            language = option.lower()

    return CardRequest(
        name=name,
        quantity=quantity,
        language=language,
        set_code=set_code,
        collector_number=collector_number,
    )
