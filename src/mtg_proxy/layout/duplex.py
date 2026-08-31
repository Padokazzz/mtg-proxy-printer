from dataclasses import dataclass
from typing import List, Tuple

from ..config import AppConfig
from .a4 import CardRect, PageLayout, compute_grid, paginate


def flip_rect(
    rect: CardRect,
    page_w: float,
    page_h: float,
    flip: str,
    orientation: str,
) -> CardRect:
    """Calcula a posição da carta no VERSO para alinhar atrás da frente.

    Modela o flip físico de 180° sobre o eixo central da folha:
    - long_edge: espelha no eixo perpendicular à borda longa;
    - short_edge: espelha no eixo perpendicular à borda curta.
    A orientação define qual borda é longa/curta.
    """
    x, y, w, h = rect.x, rect.y, rect.w, rect.h
    portrait = orientation == "portrait"

    if flip == "long_edge":
        mirror_horizontal = portrait
    else:  # short_edge
        mirror_horizontal = not portrait

    if mirror_horizontal:
        return CardRect(page_w - x - w, y, w, h)
    return CardRect(x, page_h - y - h, w, h)


def back_cells(layout: PageLayout, config: AppConfig) -> List[CardRect]:
    """Posições do verso, na mesma ordem das células da frente."""
    return [
        flip_rect(c, layout.page_w, layout.page_h, config.duplex.flip, config.page.orientation)
        for c in layout.cells
    ]


def build_back_pages(
    front_pages: List[List], layout: PageLayout, config: AppConfig
) -> List[List[Tuple[CardRect, object]]]:
    """Para cada página da frente, monta a página do verso.

    Cada carta i da frente vai para a posição `back_cells[i]`, garantindo
    que o verso caia exatamente atrás da frente após o flip da impressora.
    """
    backs = back_cells(layout, config)
    result: List[List[Tuple[CardRect, object]]] = []
    for page in front_pages:
        back_page: List[Tuple[CardRect, object]] = []
        for i, (_rect, card) in enumerate(page):
            back_page.append((backs[i], card))
        result.append(back_page)
    return result
