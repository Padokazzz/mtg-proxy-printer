import logging
from typing import Any, Dict, List, Optional

from ..config import AppConfig
from ..models import CardRequest, CardNotFoundError, ResolvedCard
from .client import ScryfallClient, ScryfallError
from .parser import image_url_for, normalize

logger = logging.getLogger("mtg_proxy")


def _fetch_prints(client: ScryfallClient, uri: str) -> List[Dict[str, Any]]:
    """Segue a prints_search_uri (com paginação) e retorna todas as impressões."""
    prints: List[Dict[str, Any]] = []
    url: Optional[str] = uri
    while url:
        path = url.replace(client.BASE_URL, "")
        data = client.get_json(path)
        prints.extend(data.get("data", []))
        url = data.get("next_page")
    return prints


_SPECIAL_FRAME_EFFECTS = {"showcase", "extendedart", "inverted", "fullart"}

RECENCY_THRESHOLD = "2015-01-01"


def _is_standard_art(card: Dict[str, Any]) -> bool:
    """Arte padrão: moldura comum (preta/branca) e sem efeitos especiais."""
    if card.get("full_art"):
        return False
    if card.get("border_color") not in ("black", "white"):
        return False
    fx = set(card.get("frame_effects") or [])
    if fx & _SPECIAL_FRAME_EFFECTS:
        return False
    return True


def _art_debut(prints: List[Dict[str, Any]]) -> Dict[str, str]:
    """Data de estreia (mais antiga) de cada illustration_id entre todas as impressões."""
    debut: Dict[str, str] = {}
    for p in prints:
        ill = p.get("illustration_id")
        if not ill:
            continue
        d = p.get("released_at") or ""
        if ill not in debut or d < debut[ill]:
            debut[ill] = d
    return debut


def _art_date(p: Dict[str, Any], debut: Dict[str, str]) -> str:
    ill = p.get("illustration_id")
    if ill and ill in debut:
        return debut[ill]
    return p.get("released_at") or ""


def _select(
    prints: List[Dict[str, Any]], preferred: str, debut: Dict[str, str]
) -> Optional[Dict[str, Any]]:
    """Escolhe deterministicamente a melhor impressão.

    Prioridade: imagem disponível > arte mais recente (estreia do illustration_id) >
    impressão mais recente (released_at) > set/collector_number como desempate.
    """
    with_image = [p for p in prints if image_url_for(p, preferred)]
    pool = with_image if with_image else prints
    if not pool:
        return None

    if preferred:
        matches = [p for p in pool if p.get("set") == preferred]
        if matches:
            pool = matches

    def sort_key(p: Dict[str, Any]):
        return (
            _art_date(p, debut),
            p.get("released_at", ""),
            p.get("set", ""),
            str(p.get("collector_number", "")),
        )

    return sorted(pool, key=sort_key, reverse=True)[0]


def resolve(request: CardRequest, client: ScryfallClient, config: AppConfig) -> ResolvedCard:
    """Resolve um CardRequest para uma impressão concreta da Scryfall.

    Estratégia (conforme prioridade do projeto):
    1. busca todas as impressões via prints_search_uri;
    2. aplica set_code / collector_number quando informados;
    3. filtra pelo idioma alvo (default), com fallback;
    4. prefere arte padrão (full_art=False) quando houver opção;
    5. escolhe a mais recente com imagem.
    """
    target = request.language or config.cards.default_language
    fallback = config.cards.fallback_language
    preferred = config.cards.preferred_image

    try:
        canonical = client.get_json("/cards/named", params={"exact": request.name})
    except ScryfallError:
        raise CardNotFoundError(request.name)

    prints_uri = canonical.get("prints_search_uri")
    if not prints_uri:
        raise CardNotFoundError(request.name)

    all_prints = _fetch_prints(client, prints_uri)
    if not all_prints:
        raise CardNotFoundError(request.name)

    candidates = all_prints
    if request.set_code:
        candidates = [p for p in candidates if p.get("set", "").lower() == request.set_code.lower()]
    if request.collector_number is not None:
        candidates = [
            p for p in candidates
            if str(p.get("collector_number", "")) == str(request.collector_number)
        ]

    lang_cands = [p for p in candidates if p.get("lang") == target]
    fallback_used = False
    if lang_cands:
        pool = lang_cands
    elif fallback and fallback != target:
        fb = [p for p in candidates if p.get("lang") == fallback]
        pool = fb if fb else candidates
        fallback_used = True
    else:
        pool = candidates

    if not pool:
        raise CardNotFoundError(request.name)

    # Arte padrão tem prioridade sobre full art / efeitos especiais (quando houver escolha).
    non_full_art = [p for p in pool if not p.get("full_art")]
    if non_full_art:
        pool = non_full_art

    standard = [p for p in pool if _is_standard_art(p)]
    if standard:
        pool = standard

    # Moldura preta tem prioridade sobre a recência da arte: evita que a moldura
    # branca "suma" no papel branco na impressão. Só descarta a preferência quando
    # não houver nenhuma opção de moldura preta disponível.
    if config.cards.prefer_black_border:
        black_pool = [p for p in pool if p.get("border_color") == "black"]
        if black_pool:
            pool = black_pool

    # Recência da ARTE: prioriza impressões cuja arte estreou a partir de 2015
    # (evita reprints recentes que reusam arte clássica). Se nenhuma arte for
    # recente, cai para a impressão mais recente; se também não houver, a mais antiga.
    debut = _art_debut(all_prints)
    recent_art = [p for p in pool if _art_date(p, debut) >= RECENCY_THRESHOLD]
    if recent_art:
        pool = recent_art
    else:
        recent = [p for p in pool if (p.get("released_at") or "") >= RECENCY_THRESHOLD]
        if recent:
            pool = recent
        else:
            oldest = min(pool, key=lambda p: p.get("released_at") or "0000-00-00")
            pool = [oldest]

    chosen = _select(pool, preferred, debut)
    if chosen is None:
        raise CardNotFoundError(request.name)

    norm = normalize(chosen, preferred)
    logger.info(
        f"Resolvida: {norm['name']} | lang={norm['lang']} | "
        f"set={norm['set']} | cn={norm['collector_number']}"
        + (" | full_art" if chosen.get("full_art") else "")
        + (f" | borda={chosen.get('border_color')}" if chosen.get("border_color") else "")
    )
    if fallback_used:
        logger.debug("  (fallback de idioma: idioma alvo indisponível)")

    return ResolvedCard(
        request=request,
        scryfall_id=norm["scryfall_id"],
        name=norm["name"],
        language=norm["lang"],
        set_code=norm["set"],
        set_name=norm["set_name"],
        collector_number=norm["collector_number"],
        released_at=norm["released_at"],
        image_url=norm["image_url"],
        fallback_used=fallback_used,
        border_color=norm["border_color"] or None,
    )
