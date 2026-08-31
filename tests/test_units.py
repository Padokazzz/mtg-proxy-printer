import pytest

from mtg_proxy.units import mm_to_pt, mm_to_px, pt_to_mm


def test_mm_to_pt_card_width():
    # 63 mm -> ~178.58 pt
    assert mm_to_pt(63) == pytest.approx(178.58, abs=0.01)


def test_mm_to_pt_card_height():
    assert mm_to_pt(88) == pytest.approx(249.45, abs=0.01)


def test_mm_to_pt_a4():
    assert mm_to_pt(210) == pytest.approx(595.28, abs=0.01)
    assert mm_to_pt(297) == pytest.approx(841.89, abs=0.01)


def test_mm_to_px():
    assert mm_to_px(63, 300) == pytest.approx(744.09, abs=0.01)
    assert mm_to_px(88, 300) == pytest.approx(1039.37, abs=0.01)


def test_pt_to_mm_roundtrip():
    assert pt_to_mm(mm_to_pt(63)) == pytest.approx(63, abs=1e-6)
