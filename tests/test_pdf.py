import re

import pytest
from pathlib import Path

from PIL import Image

from mtg_proxy.config import load_config
from mtg_proxy.models import CardRequest, ResolvedCard
from mtg_proxy.pdf.generator import PdfGenerator


def _make_card(name, image_path):
    return ResolvedCard(
        request=CardRequest(name=name),
        scryfall_id="id",
        name=name,
        language="pt",
        set_code="x",
        set_name="X",
        collector_number="1",
        released_at="2020",
        image_url="",
        image_path=image_path,
    )


def _write_img(path: Path, color):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (744, 1039), color).save(path, "PNG")


def test_pdf_generated_has_correct_page_count(tmp_path):
    cfg = load_config()
    img = tmp_path / "c.png"
    _write_img(img, (200, 100, 50))
    # 10 cartas -> 2 páginas (9 + 1)
    cards = [_make_card(f"C{i}", img) for i in range(10)]
    out = tmp_path / "deck.pdf"
    PdfGenerator(cfg).write(cards, out)

    assert out.exists()
    data = out.read_bytes()
    assert data.startswith(b"%PDF")
    # "/Type /Page" excluindo o nó pai "/Type /Pages"
    assert len(re.findall(rb"/Type /Page(?!s)", data)) == 2


def test_pdf_page_is_a4_portrait(tmp_path):
    cfg = load_config()
    img = tmp_path / "c.png"
    _write_img(img, (10, 20, 30))
    cards = [_make_card("C1", img)]
    out = tmp_path / "deck.pdf"
    PdfGenerator(cfg).write(cards, out)
    data = out.read_bytes()
    # MediaBox A4 retrato (aprox. 595.28 x 841.89)
    assert b"595.2" in data
    assert b"841.8" in data


def test_pdf_landscape_swaps_mediabox(tmp_path):
    cfg = load_config()
    cfg.page.orientation = "landscape"
    img = tmp_path / "c.png"
    _write_img(img, (10, 20, 30))
    cards = [_make_card("C1", img)]
    out = tmp_path / "deck.pdf"
    PdfGenerator(cfg).write(cards, out)
    data = out.read_bytes()
    # Em paisagem, largura e altura trocadas
    assert b"841.8" in data
    assert b"595.2" in data


def test_back_pages_use_card_back_image(tmp_path):
    cfg = load_config()
    cfg.duplex.enabled = True
    img = tmp_path / "c.png"
    _write_img(img, (10, 20, 30))
    gen = PdfGenerator(cfg)
    layout, front = gen.build_front_pages([_make_card("C1", img)])
    back = gen.build_back_pages(front, layout, "verso.png")
    assert len(back) == len(front)
    # toda célula do verso usa a imagem de verso, nas posições espelhadas
    assert back[0][0][1] == "verso.png"
    assert back[0][0][0] != front[0][0][0]  # posição espelhada


def test_card_back_generated_natively(tmp_path):
    cfg = load_config()
    cfg.output.cache_directory = str(tmp_path)
    from mtg_proxy.images.processor import ImageProcessor

    out = ImageProcessor(cfg).make_card_back()
    assert out.exists()
    from PIL import Image

    with Image.open(out) as img:
        w, h = img.size
        assert abs((w / h) - (63 / 88)) < 1e-3

