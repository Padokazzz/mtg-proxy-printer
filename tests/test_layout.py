import pytest

from mtg_proxy.config import load_config
from mtg_proxy.layout.a4 import (
    CardRect,
    compute_grid,
    page_size_pt,
    paginate,
)
from mtg_proxy.layout.cut_marks import cut_marks_for_cell, cut_marks_for_page
from mtg_proxy.units import mm_to_pt


def test_page_size_portrait():
    cfg = load_config()
    w, h = page_size_pt(cfg)
    assert w == pytest.approx(mm_to_pt(210))
    assert h == pytest.approx(mm_to_pt(297))


def test_page_size_landscape_swaps():
    cfg = load_config()
    cfg.page.orientation = "landscape"
    w, h = page_size_pt(cfg)
    assert w == pytest.approx(mm_to_pt(297))
    assert h == pytest.approx(mm_to_pt(210))


def test_grid_portrait_fits_3x3():
    cfg = load_config()
    layout = compute_grid(cfg)
    # A4 retrato com margem 5mm e gap 2mm comporta 3x3 = 9 cartas
    assert layout.cols == 3
    assert layout.rows == 3
    assert layout.cards_per_page == 9
    assert len(layout.cells) == 9


def test_grid_landscape_changes_count():
    cfg = load_config()
    cfg.page.orientation = "landscape"
    layout = compute_grid(cfg)
    assert layout.cols == 4
    assert layout.rows == 2
    assert layout.cards_per_page == 8


def test_cells_within_page_bounds():
    cfg = load_config()
    layout = compute_grid(cfg)
    margin = mm_to_pt(cfg.page.margin_mm)
    eps = 1e-6
    for cell in layout.cells:
        assert cell.x >= margin - eps
        assert cell.y >= margin - eps
        assert cell.x + cell.w <= layout.page_w - margin + eps
        assert cell.y + cell.h <= layout.page_h - margin + eps


def test_cell_spacing_is_card_plus_gap():
    cfg = load_config()
    layout = compute_grid(cfg)
    cw = mm_to_pt(cfg.print.card_width_mm)
    ch = mm_to_pt(cfg.print.card_height_mm)
    g = mm_to_pt(cfg.page.gap_mm)
    cells = layout.cells
    # primeira linha: colunas adjacentes
    top_row = [c for c in cells if abs(c.y - cells[0].y) < 1e-6]
    top_row.sort(key=lambda c: c.x)
    for i in range(1, len(top_row)):
        assert top_row[i].x - (top_row[i - 1].x + cw) == pytest.approx(g, abs=1e-6)


def test_paginate_splits_correctly():
    items = list(range(20))
    pages = paginate(items, 9)
    assert len(pages) == 3
    assert [len(p) for p in pages] == [9, 9, 2]


def test_cut_marks_outside_card_and_count():
    cfg = load_config()
    length = mm_to_pt(cfg.cut_marks.length_mm)
    offset = mm_to_pt(cfg.cut_marks.offset_mm)
    cell = CardRect(100, 100, 178.58, 249.45)
    marks = cut_marks_for_cell(cell, length, offset)
    assert len(marks) == 8  # 2 por canto
    xL, yB, w, h = cell.x, cell.y, cell.w, cell.h
    yT = yB + h
    # marca horizontal do canto superior esquerdo está acima da carta
    hx1, hy1, hx2, hy2 = marks[0]
    assert hy1 == pytest.approx(yT + offset)
    # marca vertical do canto superior esquerdo está à esquerda da carta
    vx1, vy1, vx2, vy2 = marks[1]
    assert vx1 == pytest.approx(xL - offset)


def test_cut_marks_disabled():
    cfg = load_config()
    cfg.cut_marks.enabled = False
    layout = compute_grid(cfg)
    assert cut_marks_for_page(layout.cells, cfg) == []


def test_cut_marks_enabled_count():
    cfg = load_config()
    layout = compute_grid(cfg)
    marks = cut_marks_for_page(layout.cells, cfg)
    assert len(marks) == 9 * 8  # 8 por carta
