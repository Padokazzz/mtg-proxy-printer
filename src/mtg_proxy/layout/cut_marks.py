from typing import List, Tuple

from ..config import AppConfig
from ..units import mm_to_pt
from .a4 import CardRect


def cut_marks_for_cell(
    rect: CardRect, length_pt: float, offset_pt: float
) -> List[Tuple[float, float, float, float]]:
    """Gera 8 segmentos de marca de corte ao redor de uma carta.

    Coordenadas em pontos, origem no canto inferior esquerdo (padrão PDF).
    As marcas ficam fora da área da carta, com `offset_pt` de afastamento.
    """
    xL, yB, w, h = rect.x, rect.y, rect.w, rect.h
    xR = xL + w
    yT = yB + h
    L = length_pt
    o = offset_pt

    return [
        # Canto superior esquerdo
        (xL, yT + o, xL + L, yT + o),
        (xL - o, yT, xL - o, yT - L),
        # Canto superior direito
        (xR - L, yT + o, xR, yT + o),
        (xR + o, yT, xR + o, yT - L),
        # Canto inferior esquerdo
        (xL, yB - o, xL + L, yB - o),
        (xL - o, yB, xL - o, yB + L),
        # Canto inferior direito
        (xR - L, yB - o, xR, yB - o),
        (xR + o, yB, xR + o, yB + L),
    ]


def cut_marks_for_cells(
    cells: List[CardRect], config: AppConfig
) -> List[Tuple[float, float, float, float]]:
    if not config.cut_marks.enabled:
        return []
    length = mm_to_pt(config.cut_marks.length_mm)
    offset = mm_to_pt(config.cut_marks.offset_mm)
    marks: List[Tuple[float, float, float, float]] = []
    for cell in cells:
        marks.extend(cut_marks_for_cell(cell, length, offset))
    return marks


def cut_marks_for_page(
    cells: List[CardRect], config: AppConfig
) -> List[Tuple[float, float, float, float]]:
    return cut_marks_for_cells(cells, config)
