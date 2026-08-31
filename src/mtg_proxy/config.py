import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass
class ScryfallConfig:
    user_agent: str
    timeout_seconds: float
    max_retries: int
    request_delay_seconds: float


@dataclass
class CardsConfig:
    default_language: str
    fallback_language: str
    preferred_image: str
    prefer_black_border: bool = True


@dataclass
class PrintConfig:
    paper: str
    card_width_mm: float
    card_height_mm: float
    dpi_reference: int


@dataclass
class PageConfig:
    width_mm: float
    height_mm: float
    margin_mm: float
    gap_mm: float
    orientation: str


@dataclass
class BleedConfig:
    enabled: bool
    size_mm: float


@dataclass
class CutMarksConfig:
    enabled: bool
    length_mm: float
    offset_mm: float
    card_outline: bool = True
    card_outline_mm: float = 0.5


@dataclass
class DuplexConfig:
    enabled: bool
    flip: str


@dataclass
class OutputConfig:
    directory: str
    cache_directory: str
    generate_combined_pdf: bool
    generate_front_pdf: bool
    generate_back_pdf: bool


@dataclass
class AppConfig:
    scryfall: ScryfallConfig
    cards: CardsConfig
    print: PrintConfig
    page: PageConfig
    bleed: BleedConfig
    cut_marks: CutMarksConfig
    duplex: DuplexConfig
    output: OutputConfig

    @property
    def output_dir(self) -> Path:
        return Path(self.output.directory)

    @property
    def cache_dir(self) -> Path:
        raw = self.output.cache_directory
        p = Path(raw)
        if p.is_absolute():
            return p
        if getattr(sys, "frozen", False):
            local = os.environ.get("LOCALAPPDATA")
            base = Path(local) if local else (Path.home() / "AppData" / "Local")
            return base / "MTGProxy" / raw
        return Path.cwd() / raw


DEFAULT_CONFIG: Dict[str, Any] = {
    "scryfall": {
        "user_agent": "MTG-Proxy-Printer/1.0 (personal-use)",
        "timeout_seconds": 15,
        "max_retries": 3,
        "request_delay_seconds": 0.1,
    },
    "cards": {
        "default_language": "pt",
        "fallback_language": "en",
        "preferred_image": "png",
        "prefer_black_border": True,
    },
    "print": {
        "paper": "A4",
        "card_width_mm": 63,
        "card_height_mm": 88,
        "dpi_reference": 300,
    },
    "page": {
        "width_mm": 210,
        "height_mm": 297,
        "margin_mm": 5,
        "gap_mm": 2,
        "orientation": "portrait",
    },
    "bleed": {"enabled": False, "size_mm": 0},
    "cut_marks": {"enabled": True, "length_mm": 2, "offset_mm": 1, "card_outline": True, "card_outline_mm": 0.5},
    "duplex": {"enabled": True, "flip": "long_edge"},
    "output": {
        "directory": "saida",
        "cache_directory": "cartas",
        "generate_combined_pdf": True,
        "generate_front_pdf": True,
        "generate_back_pdf": True,
    },
}


def _deep_merge(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: Optional[str] = None) -> AppConfig:
    """Carrega a configuração de um YAML, mesclando com os padrões.

    Se o arquivo não existir, usa somente os padrões.
    """
    raw: Dict[str, Any] = DEFAULT_CONFIG
    if path:
        config_path = Path(path)
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as fh:
                user_data = yaml.safe_load(fh) or {}
            raw = _deep_merge(DEFAULT_CONFIG, user_data)
        else:
            raise FileNotFoundError(
                f"Arquivo de configuração não encontrado: {config_path}"
            )

    return AppConfig(
        scryfall=ScryfallConfig(**raw["scryfall"]),
        cards=CardsConfig(**raw["cards"]),
        print=PrintConfig(**raw["print"]),
        page=PageConfig(**raw["page"]),
        bleed=BleedConfig(**raw["bleed"]),
        cut_marks=CutMarksConfig(**raw["cut_marks"]),
        duplex=DuplexConfig(**raw["duplex"]),
        output=OutputConfig(**raw["output"]),
    )
