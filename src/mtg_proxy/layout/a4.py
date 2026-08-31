from dataclasses import dataclass
from typing import List, Tuple

from ..config import AppConfig
from ..units import mm_to_pt


@dataclass
class CardRect:
    x: float
    y: float
    w: float
    h: float


@dataclass
class PageLayout:
    page_w: float
    page_h: float
    cols: int
    rows: int
    cards_per_page: int
    cells: List[CardRect]


def page_size_pt(config: AppConfig) -> Tuple[float, float]:
    """Tamanho da página em pontos, aplicando a orientação."""
    w = mm_to_pt(config.page.width_mm)
    h = mm_to_pt(config.page.height_mm)
    if config.page.orientation == "landscape":
        return h, w
    return w, h


def compute_grid(config: AppConfig) -> PageLayout:
    """Calcula a grade de cartas que cabe em uma página A4.

    A grade é centralizada nas margens. O número de cartas é derivado
    automaticamente de margem, espaçamento e tamanho físico da carta.
    """
    pw, ph = page_size_pt(config)
    cw = mm_to_pt(config.print.card_width_mm)
    ch = mm_to_pt(config.print.card_height_mm)
    m = mm_to_pt(config.page.margin_mm)
    g = mm_to_pt(config.page.gap_mm)

    usable_w = pw - 2 * m
    usable_h = ph - 2 * m

    cols = int((usable_w + g) // (cw + g))
    rows = int((usable_h + g) // (ch + g))
    cols = max(cols, 1)
    rows = max(rows, 1)

    grid_w = cols * cw + (cols - 1) * g
    grid_h = rows * ch + (rows - 1) * g

    start_x = m + (usable_w - grid_w) / 2
    start_y = m + (usable_h - grid_h) / 2

    cells: List[CardRect] = []
    for r in range(rows):
        for c in range(cols):
            x = start_x + c * (cw + g)
            y = start_y + r * (ch + g)
            cells.append(CardRect(x, y, cw, ch))

    return PageLayout(pw, ph, cols, rows, cols * rows, cells)


def paginate(items: List, cards_per_page: int) -> List[List]:
    """Divide uma lista de itens em páginas de no máximo `cards_per_page`."""
    pages: List[List] = []
    for i in range(0, len(items), cards_per_page):
        pages.append(items[i : i + cards_per_page])
    return pages
