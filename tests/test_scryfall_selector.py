from mtg_proxy.models import CardRequest, ResolvedCard
from mtg_proxy.scryfall.selector import _fetch_prints, _select, resolve


class FakeClient:
    BASE_URL = "https://api.scryfall.com"

    def __init__(self, canonical, prints):
        self.canonical = canonical
        self.prints = prints

    def get_json(self, path, params=None):
        if path == "/cards/named":
            return self.canonical
        if "cards/search" in path:
            return {"data": self.prints, "next_page": None}
        raise AssertionError(f"path inesperado: {path}")

    def download_image(self, url):
        return b"png-bytes"


def _card(name, lang, set_, cn, released, image=True, full_art=False,
          border_color=None, frame_effects=None, illustration_id=None):
    return {
        "id": f"{name}-{set_}-{cn}",
        "name": name,
        "lang": lang,
        "set": set_,
        "set_name": set_.upper(),
        "collector_number": cn,
        "released_at": released,
        "full_art": full_art,
        "border_color": border_color,
        "frame_effects": frame_effects or [],
        "illustration_id": illustration_id,
        "image_uris": {"png": f"http://img/{set_}/{cn}.png"} if image else None,
    }


def _canonical(name):
    return {
        "name": name,
        "prints_search_uri": "https://api.scryfall.com/cards/search?q=oracleid:1",
    }


def test_select_prefers_image_and_most_recent():
    cards = [
        _card("Bolt", "en", "m19", "1", "2018-01-01", image=False),
        _card("Bolt", "en", "fdn", "99", "2024-01-01", image=True),
        _card("Bolt", "en", "2x2", "50", "2023-01-01", image=True),
    ]
    chosen = _select(cards, "png", {})
    assert chosen["set"] == "fdn"


def test_select_without_image_falls_back():
    cards = [_card("Bolt", "en", "m19", "1", "2018-01-01", image=False)]
    chosen = _select(cards, "png", {})
    assert chosen["set"] == "m19"


def test_resolve_prefers_standard_art_over_full_art():
    name = "Sol Ring"
    prints = [
        _card(name, "en", "msc", "211", "2023-01-01", full_art=True),
        _card(name, "en", "sld", "2783", "2024-01-01", full_art=True),
        _card(name, "en", "cmm", "337", "2020-01-01", full_art=False),
    ]
    client = FakeClient(_canonical(name), prints)
    cfg = _cfg()
    rc = resolve(CardRequest(name=name), client, cfg)
    assert isinstance(rc, ResolvedCard)
    assert rc.set_code == "cmm"
    assert rc.image_url.endswith("cmm/337.png")


def test_resolve_uses_fallback_language():
    name = "Carta Exotica"
    prints = [
        _card(name, "pt", "fdn", "10", "2024-01-01", full_art=False),
        _card(name, "en", "fdn", "11", "2024-01-01", full_art=False),
    ]
    client = FakeClient(_canonical(name), prints)
    cfg = _cfg(default="pt", fallback="en")
    rc = resolve(CardRequest(name=name), client, cfg)
    assert rc.language == "pt"
    assert rc.fallback_used is False


def test_resolve_uses_english_when_pt_missing():
    name = "So Ingles"
    prints = [
        _card(name, "en", "fdn", "5", "2024-01-01", full_art=False),
    ]
    client = FakeClient(_canonical(name), prints)
    cfg = _cfg(default="pt", fallback="en")
    rc = resolve(CardRequest(name=name), client, cfg)
    assert rc.language == "en"
    assert rc.fallback_used is True


def test_resolve_honors_set_code_even_if_full_art():
    name = "So Set"
    prints = [
        _card(name, "en", "cmm", "1", "2020-01-01", full_art=False),
        _card(name, "en", "xxx", "9", "2024-01-01", full_art=True),
    ]
    client = FakeClient(_canonical(name), prints)
    cfg = _cfg()
    rc = resolve(CardRequest(name=name, set_code="xxx"), client, cfg)
    assert rc.set_code == "xxx"  # set explícito tem prioridade


def test_resolve_not_found_raises():
    from mtg_proxy.models import CardNotFoundError

    name = "Inexistente"
    client = FakeClient(_canonical(name), [])
    cfg = _cfg()
    try:
        resolve(CardRequest(name=name), client, cfg)
        assert False, "esperado CardNotFoundError"
    except CardNotFoundError:
        pass


def test_fetch_prints_follows_pagination():
    pages = [
        {"data": [_card("A", "en", "a", "1", "2020")], "next_page": "https://api.scryfall.com/cards/search?page=2"},
        {"data": [_card("A", "en", "b", "2", "2021")], "next_page": None},
    ]

    class PagedClient:
        BASE_URL = "https://api.scryfall.com"

        def __init__(self):
            self.i = 0

        def get_json(self, path, params=None):
            data = pages[self.i]
            self.i += 1
            return data

    result = _fetch_prints(PagedClient(), "https://api.scryfall.com/cards/search?page=1")
    assert len(result) == 2


def test_resolve_prefers_recent_standard_art():
    name = "Recente"
    prints = [
        _card(name, "en", "old", "1", "2010-01-01", full_art=False),
        _card(name, "en", "mid", "2", "2018-01-01", full_art=False),
        _card(name, "en", "new", "3", "2024-01-01", full_art=True),  # full art
    ]
    client = FakeClient(_canonical(name), prints)
    rc = resolve(CardRequest(name=name), client, _cfg())
    assert rc.set_code == "mid"  # 2018, padrão e mais recente >= 2015


def test_resolve_uses_oldest_when_no_recent():
    name = "So Velha"
    prints = [
        _card(name, "en", "a", "1", "2008-01-01", full_art=False),
        _card(name, "en", "b", "2", "2012-01-01", full_art=False),
    ]
    client = FakeClient(_canonical(name), prints)
    rc = resolve(CardRequest(name=name), client, _cfg())
    assert rc.set_code == "a"  # mais antiga, pois nenhuma é >= 2015


def test_resolve_prefers_recent_art_over_old_art_reprint():
    name = "Nova Arte"
    # todas padrão; a mais recente (recent/2026) reusa arte clássica (oldart, 1993),
    # mas existe uma impressão mais antiga (past/2020) com arte nova (newart).
    prints = [
        _card(name, "en", "recent", "1", "2026-01-01", full_art=False,
              border_color="black", illustration_id="oldart"),
        _card(name, "en", "past", "2", "2020-01-01", full_art=False,
              border_color="black", illustration_id="newart"),
        _card(name, "en", "classic", "3", "1993-01-01", full_art=False,
              border_color="black", illustration_id="oldart"),
    ]
    client = FakeClient(_canonical(name), prints)
    rc = resolve(CardRequest(name=name), client, _cfg())
    assert rc.set_code == "past"  # arte nova (estreia 2020 >= 2015)


def _cfg(default="en", fallback="en"):
    class Cards:
        default_language = default
        fallback_language = fallback
        preferred_image = "png"
        prefer_black_border = True

    class Cfg:
        cards = Cards()

    return Cfg()
