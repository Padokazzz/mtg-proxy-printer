from typing import Any, Dict, List, Optional


def _first_face(card: Dict[str, Any]) -> Dict[str, Any]:
    """Cartas double-faced armazenam image_uris em card_faces[0]."""
    faces = card.get("card_faces")
    if faces:
        return faces[0]
    return card


def image_url_for(card: Dict[str, Any], preferred: str = "png") -> Optional[str]:
    """Retorna a URL da imagem da frente, priorizando `preferred` (png/large)."""
    face = _first_face(card)
    uris = face.get("image_uris") or card.get("image_uris")
    if not uris:
        return None
    return uris.get(preferred) or uris.get("large") or uris.get("png")


def normalize(card: Dict[str, Any], preferred: str = "png") -> Dict[str, Any]:
    """Extrai os campos relevantes de um objeto de carta da Scryfall."""
    return {
        "scryfall_id": card.get("id", ""),
        "name": card.get("name", ""),
        "lang": card.get("lang", ""),
        "set": card.get("set", ""),
        "set_name": card.get("set_name", ""),
        "collector_number": str(card.get("collector_number", "")),
        "released_at": card.get("released_at", ""),
        "image_url": image_url_for(card, preferred),
        "border_color": card.get("border_color", ""),
    }


def collect_prints(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Retorna as impressões contidas em uma página de resposta de busca."""
    return list(payload.get("data", []))
