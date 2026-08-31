import pytest

from mtg_proxy.config import load_config
from mtg_proxy.layout.a4 import CardRect, compute_grid
from mtg_proxy.layout.duplex import back_cells, flip_rect


def test_flip_long_edge_portrait_horizontal_mirror():
    cfg = load_config()
    # retrato: long edge vertical -> espelho horizontal
    r = CardRect(100, 200, 178.58, 249.45)
    out = flip_rect(r, 595.28, 841.89, "long_edge", "portrait")
    assert out.x == pytest.approx(595.28 - 100 - 178.58)
    assert out.y == pytest.approx(200)
    assert out.w == r.w and out.h == r.h


def test_flip_short_edge_portrait_vertical_mirror():
    cfg = load_config()
    r = CardRect(100, 200, 178.58, 249.45)
    out = flip_rect(r, 595.28, 841.89, "short_edge", "portrait")
    assert out.x == pytest.approx(100)
    assert out.y == pytest.approx(841.89 - 200 - 249.45)


def test_flip_long_edge_landscape_vertical_mirror():
    # paisagem: long edge horizontal -> espelho vertical
    r = CardRect(100, 200, 249.45, 178.58)
    out = flip_rect(r, 841.89, 595.28, "long_edge", "landscape")
    assert out.x == pytest.approx(100)
    assert out.y == pytest.approx(595.28 - 200 - 178.58)


def test_flip_short_edge_landscape_horizontal_mirror():
    r = CardRect(100, 200, 249.45, 178.58)
    out = flip_rect(r, 841.89, 595.28, "short_edge", "landscape")
    assert out.x == pytest.approx(841.89 - 100 - 249.45)
    assert out.y == pytest.approx(200)


def test_back_aligns_behind_front_long_edge_portrait():
    # aplica o flip físico (espelho horizontal) no resultado e deve voltar
    # à posição original da frente
    W, H = 595.28, 841.89
    r = CardRect(100, 200, 178.58, 249.45)
    back = flip_rect(r, W, H, "long_edge", "portrait")
    # flip físico novamente (mesmo eixo) deve restaurar
    restored = flip_rect(back, W, H, "long_edge", "portrait")
    assert restored.x == pytest.approx(r.x)
    assert restored.y == pytest.approx(r.y)


def test_back_cells_3x3_long_edge_portrait_mirrors_columns():
    cfg = load_config()
    layout = compute_grid(cfg)  # 3x3
    backs = back_cells(layout, cfg)
    # coluna 0 (esquerda) deve ir para coluna 2 (direita)
    left = layout.cells[0]      # linha 0, col 0
    right = layout.cells[2]     # linha 0, col 2
    assert backs[0].x == pytest.approx(right.x)
    assert backs[2].x == pytest.approx(left.x)
    # mesma linha (y) preservada no long edge
    assert backs[0].y == pytest.approx(left.y)


def test_back_cells_3x3_short_edge_portrait_mirrors_rows():
    cfg = load_config()
    cfg.duplex.flip = "short_edge"
    layout = compute_grid(cfg)
    backs = back_cells(layout, cfg)
    # linha de baixo (índice 0) deve ir para linha de cima (índice 6 na grade 3x3)
    bottom = layout.cells[0]
    top = layout.cells[6]
    assert backs[0].y == pytest.approx(top.y)
    assert backs[6].y == pytest.approx(bottom.y)
