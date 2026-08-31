import logging
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

from ..config import AppConfig
from ..models import ResolvedCard
from ..units import mm_to_px
from ..util import slugify

logger = logging.getLogger("mtg_proxy")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageProcessor:
    """Prepara a imagem para o tamanho físico da carta preservando a resolução real.

    - aplica crop central mínimo para a proporção exata 63:88 (sem distorção);
    - NÃO faz upscale: a imagem nativa da Scryfall é mantida pixel a pixel,
      garantindo a "qualidade da carta real" (1:1 na impressão);
    - normaliza alpha;
    - cacheia o recorte para não reprocessar.
    """

    def __init__(self, config: AppConfig):
        self.config = config
        self.print_cfg = config.print
        self.processed_dir = config.cache_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def target_px(self) -> tuple[int, int]:
        dpi = self.print_cfg.dpi_reference
        width = round(mm_to_px(self.print_cfg.card_width_mm, dpi))
        height = round(mm_to_px(self.print_cfg.card_height_mm, dpi))
        return width, height

    def _target_ratio(self) -> float:
        return self.print_cfg.card_width_mm / self.print_cfg.card_height_mm

    def _processed_path(self, rc: ResolvedCard) -> Path:
        name = (
            f"{slugify(rc.name)}__{rc.language}__{rc.set_code}"
            f"__{rc.collector_number}__native.png"
        )
        return self.processed_dir / name

    @staticmethod
    def _is_valid(path: Path, target_ratio: float) -> bool:
        if not path.exists():
            return False
        try:
            data = path.read_bytes()
        except OSError:
            return False
        if not data.startswith(_PNG_SIGNATURE):
            return False
        try:
            with Image.open(path) as img:
                w, h = img.size
                if w <= 0 or h <= 0:
                    return False
                return abs((w / h) - target_ratio) < 1e-3
        except Exception:
            return False

    @staticmethod
    def _normalize(img: Image.Image) -> Image.Image:
        if img.mode in ("RGBA", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1])
            return background
        if img.mode != "RGB":
            return img.convert("RGB")
        return img

    @staticmethod
    def _crop_to_ratio(img: Image.Image, ratio: float) -> Image.Image:
        cw, ch = img.size
        src_ratio = cw / ch
        if src_ratio > ratio:
            new_w = int(round(ch * ratio))
            x = (cw - new_w) // 2
            box = (x, 0, x + new_w, ch)
        else:
            new_h = int(round(cw / ratio))
            y = (ch - new_h) // 2
            box = (0, y, cw, y + new_h)
        return img.crop(box)

    def process(self, rc: ResolvedCard) -> Path:
        if rc.image_path is None:
            raise ValueError(f"Imagem de {rc.name} ainda não foi baixada.")
        src = Path(rc.image_path)
        if not src.exists():
            raise FileNotFoundError(f"Arquivo de imagem ausente: {src}")

        out = self._processed_path(rc)
        ratio = self._target_ratio()
        if self._is_valid(out, ratio):
            logger.info(f"Processada (cache): {rc.name}")
            return out

        logger.info(f"Processando: {rc.name} (recorte nativo 63x88mm)")
        with Image.open(src) as img:
            img = self._normalize(img)
            img = self._crop_to_ratio(img, ratio)
            img.save(out, "PNG")
        return out

    def process_raw(self, src: Path, key: str = "cardback") -> Path:
        """Recorta uma imagem arbitrária (ex.: verso fornecido pelo usuário) para a proporção."""
        src = Path(src)
        if not src.exists():
            raise FileNotFoundError(f"Arquivo de imagem ausente: {src}")
        out = self.processed_dir / f"{key}__native.png"
        ratio = self._target_ratio()
        if (
            out.exists()
            and self._is_valid(out, ratio)
            and out.stat().st_mtime >= src.stat().st_mtime
        ):
            logger.info(f"Processada (cache): {key}")
            return out
        logger.info(f"Processando imagem externa: {key} ({src.name})")
        with Image.open(src) as img:
            img = self._normalize(img)
            img = self._crop_to_ratio(img, ratio)
            img.save(out, "PNG")
        return out

    def make_card_back(self) -> Path:
        """Gera um verso estilizado (inspirado no verso da Magic) em resolução nativa.

        A Scryfall não disponibiliza a arte oficial do verso; este placeholder é
        desenhado localmente. Para usar a arte real, basta colocar um arquivo
        `cardback.png` no diretório de cache (cartas/) que ele será usado.
        """
        out = self.processed_dir / "cardback__native.png"
        ratio = self._target_ratio()
        if self._is_valid(out, ratio):
            return out

        w, h = self.target_px()
        navy = (20, 30, 52)
        beige = (214, 198, 156)
        img = Image.new("RGB", (w, h), navy)
        d = ImageDraw.Draw(img)

        m = max(10, int(w * 0.03))
        d.rectangle([m, m, w - m, h - m], outline=beige, width=max(4, int(w * 0.012)))
        m2 = m + max(8, int(w * 0.02))
        d.rectangle([m2, m2, w - m2, h - m2], outline=beige, width=max(2, int(w * 0.006)))

        cx, cy = w // 2, h // 2
        rx, ry = int(w * 0.30), int(h * 0.21)
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=beige, width=max(3, int(w * 0.01)))
        d.ellipse(
            [cx - rx + 10, cy - ry + 10, cx + rx - 10, cy + ry - 10],
            outline=beige,
            width=max(1, int(w * 0.004)),
        )

        font = self._load_font(int(h * 0.085))
        d.text((cx, cy - int(h * 0.05)), "MAGIC", font=font, fill=beige, anchor="mm")
        font_small = self._load_font(int(h * 0.03))
        d.text((cx, cy + int(h * 0.05)), "THE GATHERING", font=font_small, fill=beige, anchor="mm")

        img.save(out, "PNG")
        return out

    @staticmethod
    def _load_font(size: int):
        candidates = [
            "C:/Windows/Fonts/times.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, size)
            except (OSError, IOError):
                continue
        return ImageFont.load_default()
