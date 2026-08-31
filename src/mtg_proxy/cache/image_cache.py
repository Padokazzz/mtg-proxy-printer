import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from ..config import AppConfig
from ..models import ResolvedCard
from ..scryfall.client import ScryfallClient
from ..util import slugify

logger = logging.getLogger("mtg_proxy")

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class ImageCache:
    """Cache local de imagens baixadas da Scryfall.

    - evita baixar imagens já existentes;
    - reutiliza o mesmo arquivo para cópias da mesma carta;
    - registra metadados em cache.json;
    - detecta arquivos corrompidos e re-download.
    """

    def __init__(self, config: AppConfig, client: ScryfallClient):
        self.dir = config.cache_dir
        self.client = client
        self.dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self.dir / "cache.json"
        self.index: Dict[str, Any] = self._load_index()
        self._resolved_path = self.dir / "resolved.json"
        self.resolved: Dict[str, Any] = self._load_resolved()

    def _load_index(self) -> Dict[str, Any]:
        if self._index_path.exists():
            try:
                return json.loads(self._index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                logger.warning(f"cache.json corrompido ({exc}); recriando")
                return {}
        return {}

    def _save_index(self) -> None:
        self._index_path.write_text(
            json.dumps(self.index, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _load_resolved(self) -> Dict[str, Any]:
        if self._resolved_path.exists():
            try:
                return json.loads(self._resolved_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save_resolved(self) -> None:
        self._resolved_path.write_text(
            json.dumps(self.resolved, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def get_resolved(self, key: str) -> Optional[Dict[str, Any]]:
        return self.resolved.get(key)

    def put_resolved(self, key: str, data: Dict[str, Any]) -> None:
        self.resolved[key] = data
        self._save_resolved()

    def _filename(self, rc: ResolvedCard) -> str:
        return (
            f"{slugify(rc.name)}__{rc.language}__{rc.set_code}"
            f"__{rc.collector_number}.png"
        )

    @staticmethod
    def _is_valid_image(path: Path) -> bool:
        try:
            data = path.read_bytes()
        except OSError:
            return False
        if not data:
            return False
        return data.startswith(_PNG_SIGNATURE)

    def get(self, rc: ResolvedCard) -> Path:
        filename = self._filename(rc)
        path = self.dir / filename
        key = rc.cache_key()

        if path.exists() and self._is_valid_image(path) and key in self.index:
            logger.info(f"Cache encontrado: {rc.name} ({rc.language}, {rc.set_code})")
            return path

        if path.exists() and not self._is_valid_image(path):
            logger.warning(f"Imagem corrompida detectada; baixando novamente: {filename}")

        if not rc.image_url:
            raise ValueError(
                f"Não há URL de imagem disponível para {rc.name} "
                f"({rc.language}, {rc.set_code})."
            )

        logger.info(f"Download: {rc.name} ({rc.language}, {rc.set_code})")
        data = self.client.download_image(rc.image_url)
        path.write_bytes(data)
        self.index[key] = {
            "name": rc.name,
            "language": rc.language,
            "set_code": rc.set_code,
            "collector_number": rc.collector_number,
            "scryfall_id": rc.scryfall_id,
            "image_url": rc.image_url,
            "filename": filename,
        }
        self._save_index()
        return path
