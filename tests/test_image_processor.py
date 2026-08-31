from pathlib import Path

from PIL import Image

from mtg_proxy.config import load_config
from mtg_proxy.images.processor import ImageProcessor
from mtg_proxy.models import CardRequest, ResolvedCard


def _make_rc(name="Sol Ring", lang="en", set_="cmm", cn="337", image_path=None):
    return ResolvedCard(
        request=CardRequest(name=name),
        scryfall_id="id1",
        name=name,
        language=lang,
        set_code=set_,
        set_name=set_.upper(),
        collector_number=cn,
        released_at="2020-01-01",
        image_url="http://img/x.png",
        image_path=image_path,
    )


def _write_png(path: Path, size, color=(255, 0, 0)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, color).save(path, "PNG")


def test_processor_target_px(tmp_path):
    cfg = load_config()
    proc = ImageProcessor(cfg)
    w, h = proc.target_px()
    # 63mm e 88mm a 300dpi
    assert (w, h) == (744, 1039)


def test_processor_crops_to_ratio_without_upscale(tmp_path):
    cfg = load_config()
    cfg.output.cache_directory = str(tmp_path)
    src = tmp_path / "orig.png"
    # imagem com proporção levemente diferente (mais larga)
    _write_png(src, (800, 1100), color=(10, 20, 30))
    rc = _make_rc(image_path=str(src))

    proc = ImageProcessor(cfg)
    out1 = proc.process(rc)
    assert out1.exists()

    with Image.open(out1) as img:
        w, h = img.size
        # não faz upscale: largura não pode exceder a da fonte
        assert w <= 800
        assert abs((w / h) - (63 / 88)) < 1e-3

    # segunda chamada deve reutilizar o cache (mesmo conteúdo)
    out2 = proc.process(rc)
    assert out1 == out2


def test_processor_handles_alpha(tmp_path):
    cfg = load_config()
    cfg.output.cache_directory = str(tmp_path)
    src = tmp_path / "alpha.png"
    src.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (745, 1040), (0, 255, 0, 128)).save(src, "PNG")
    rc = _make_rc(image_path=str(src))
    proc = ImageProcessor(cfg)
    out = proc.process(rc)
    with Image.open(out) as img:
        assert img.mode == "RGB"
        w, h = img.size
        assert abs((w / h) - (63 / 88)) < 1e-3


def test_processor_preserves_aspect_no_distortion(tmp_path):
    cfg = load_config()
    cfg.output.cache_directory = str(tmp_path)
    src = tmp_path / "tall.png"
    _write_png(src, (700, 1100))  # mais alta que 63:88
    rc = _make_rc(image_path=str(src))
    proc = ImageProcessor(cfg)
    out = proc.process(rc)
    with Image.open(out) as img:
        w, h = img.size
        assert w <= 700  # sem upscale
        assert abs((w / h) - (63 / 88)) < 1e-3
