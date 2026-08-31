import argparse
import copy
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .cache import ImageCache
from .config import AppConfig, load_config
from .deck import parse_deck
from .images.processor import ImageProcessor
from .models import CardRequest, CardNotFoundError, ResolvedCard
from .pdf import PdfGenerator
from .scryfall import ScryfallClient, ScryfallError, resolve

logger = logging.getLogger("mtg_proxy")

LOG_FORMAT = "[%(levelname)s] %(message)s"


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format=LOG_FORMAT,
        stream=sys.stderr,
    )


def _resource(name: str) -> Optional[Path]:
    """Localiza um arquivo de recurso (ex.: back.png) no dev ou dentro do exe."""
    candidates: List[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / name)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass) / name)
    candidates.append(Path.cwd() / name)
    candidates.append(Path(__file__).resolve().parent.parent.parent / name)
    for c in candidates:
        if c.is_file():
            return c
    return None


def _read_deck(path: str) -> str:
    deck_path = Path(path)
    if not deck_path.exists():
        raise FileNotFoundError(f"Arquivo deck não encontrado: {deck_path}")
    return deck_path.read_text(encoding="utf-8-sig")


def _expand_requests(requests: List[CardRequest]) -> List[CardRequest]:
    """Expande quantidades em múltiplas referências (mesma imagem reutilizada)."""
    expanded: List[CardRequest] = []
    for req in requests:
        for _ in range(req.quantity):
            expanded.append(req)
    return expanded


def cmd_check(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        text = _read_deck(args.deck)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 2

    requests, errors = parse_deck(text, default_language=config.cards.default_language)

    total_cards = sum(req.quantity for req in requests)
    unique_names = {req.name for req in requests}

    logger.info(f"Lendo {args.deck}")
    logger.info(f"Cartas únicas encontradas: {len(unique_names)}")
    logger.info(f"Total de cartas (com quantidades): {total_cards}")

    if requests:
        logger.info("Resumo:")
        for req in requests:
            extras = []
            if req.language:
                extras.append(f"lang={req.language}")
            if req.set_code:
                extras.append(f"set={req.set_code}")
            if req.collector_number:
                extras.append(f"cn={req.collector_number}")
            suffix = f" ({', '.join(extras)})" if extras else ""
            logger.info(f"  {req.quantity}x {req.name}{suffix}")

    if errors:
        logger.warning(f"{len(errors)} linha(s) com problema:")
        for err in errors:
            logger.warning(f"  {err}")
        return 1

    logger.info("Validação concluída sem erros.")
    return 0


def _make_client(config: AppConfig) -> ScryfallClient:
    return ScryfallClient(config.scryfall)


def _fetch_card_back(config: AppConfig) -> "Optional[Path]":
    """Prepara a imagem do verso para as páginas de duplex.

    Prioriza um `cardback.png` no cache do usuário, depois `back.png`/`cardback.png`
    na raiz do projeto ou junto ao executável; caso contrário gera um verso
    estilizado localmente (a Scryfall não serve a arte oficial).
    """
    try:
        processor = ImageProcessor(config)
        user_back = config.cache_dir / "cardback.png"
        if user_back.exists():
            return processor.process_raw(user_back, "cardback")
        for name in ("back.png", "cardback.png"):
            res = _resource(name)
            if res:
                return processor.process_raw(res, "cardback")
        return processor.make_card_back()
    except Exception as exc:
        logger.error(f"Falha ao preparar o verso ({exc}); gerando só frentes.")
        return None


def _resolve_and_cache(
    requests: List[CardRequest], config: AppConfig, progress=None, cancel=None
) -> tuple[dict, List[str], int]:
    """Resolve pedidos únicos contra a Scryfall e baixa/cacheia as imagens."""
    client = _make_client(config)
    cache = ImageCache(config, client)

    unique: dict[str, CardRequest] = {}
    for req in requests:
        unique.setdefault(req.key(), req)

    resolved: dict[str, ResolvedCard] = {}
    not_found: List[str] = []
    fallback_count = 0
    total_unique = len(unique)

    for i, req in enumerate(unique.values(), 1):
        if cancel and cancel.is_set():
            raise InterruptedError("Geração cancelada pelo usuário.")
        key = req.key()
        sel_sig = f"{config.cards.preferred_image}:{config.cards.prefer_black_border}"
        cache_key = f"{key}|{sel_sig}"
        cached = cache.get_resolved(cache_key)
        if cached and cached.get("image_url"):
            rc = _resolved_from_cache(req, cached)
            try:
                rc.image_path = cache.get(rc)
            except Exception:
                cached = None
            if cached is not None and rc.image_path is not None:
                resolved[key] = rc
                if rc.fallback_used:
                    fallback_count += 1
                continue

        try:
            rc = resolve(req, client, config)
        except CardNotFoundError:
            not_found.append(req.name)
            continue
        except ScryfallError as exc:
            logger.error(f"Erro ao consultar a Scryfall para '{req.name}': {exc}")
            not_found.append(req.name)
            continue
        if rc.fallback_used:
            fallback_count += 1
        try:
            rc.image_path = cache.get(rc)
        except Exception as exc:  # imagem indisponível corrompe só esta carta
            logger.error(f"Falha ao obter imagem de {rc.name}: {exc}")
            not_found.append(rc.name)
            continue
        cache.put_resolved(
            cache_key,
            {
                "scryfall_id": rc.scryfall_id,
                "name": rc.name,
                "language": rc.language,
                "set_code": rc.set_code,
                "set_name": rc.set_name,
                "collector_number": rc.collector_number,
                "released_at": rc.released_at,
                "image_url": rc.image_url,
                "fallback_used": rc.fallback_used,
                "border_color": rc.border_color,
            },
        )
        resolved[key] = rc
        if progress:
            progress(i, total_unique)

    return resolved, not_found, fallback_count


def _resolved_from_cache(
    req: CardRequest, data: Dict[str, Any]
) -> "ResolvedCard":
    return ResolvedCard(
        request=req,
        scryfall_id=data["scryfall_id"],
        name=data["name"],
        language=data["language"],
        set_code=data["set_code"],
        set_name=data["set_name"],
        collector_number=data["collector_number"],
        released_at=data["released_at"],
        image_url=data.get("image_url"),
        fallback_used=data.get("fallback_used", False),
        border_color=data.get("border_color"),
    )


def _expand_for_pdf(
    requests: List[CardRequest], resolved: dict, config: AppConfig, progress=None,
    cancel=None, on_card=None,
) -> tuple[List[ResolvedCard], List[str]]:
    """Expande quantidades e processa as imagens para o tamanho de impressão."""
    processor = ImageProcessor(config)
    cards_for_pdf: List[ResolvedCard] = []
    not_found: List[str] = []
    resolvable = [r for r in requests if resolved.get(r.key()) is not None]
    total_steps = len(resolvable)

    for i, req in enumerate(resolvable, 1):
        if cancel and cancel.is_set():
            raise InterruptedError("Geração cancelada pelo usuário.")
        rc = resolved[req.key()]
        try:
            rc.image_path = processor.process(rc)
        except Exception as exc:
            logger.error(f"Falha ao processar imagem de {rc.name}: {exc}")
            not_found.append(rc.name)
            continue
        for _ in range(req.quantity):
            cards_for_pdf.append(rc)
        if on_card:
            on_card(rc.name, str(rc.image_path))
        if progress:
            progress(i, total_steps)

    return cards_for_pdf, not_found


def cmd_download(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        text = _read_deck(args.deck)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 2

    requests, parse_errors = parse_deck(
        text, default_language=config.cards.default_language
    )
    for err in parse_errors:
        logger.warning(f"  {err}")

    resolved, not_found, fallback_count = _resolve_and_cache(requests, config)

    total_cards = sum(req.quantity for req in requests)
    logger.info("---- Resumo ----")
    logger.info(f"Cartas solicitadas: {total_cards}")
    logger.info(f"Pedidos únicos: {len(requests)}")
    logger.info(f"Encontradas: {len(resolved)}")
    logger.info(f"Fallback de idioma: {fallback_count}")
    logger.info(f"Não encontradas: {len(not_found)}")
    for name in not_found:
        logger.error(f"[ERRO] Carta não encontrada: {name}")

    return 0 if not not_found else 1


def _phase_progress(on_progress, phase):
    def _cb(done: int, total: int) -> None:
        if on_progress:
            on_progress(done, total, phase)

    return _cb


def run_generate(
    deck_text: str,
    config: AppConfig,
    output_dir,
    *,
    on_progress=None,
    cancel=None,
    on_card=None,
    deck_name=None,
) -> dict:
    """Gera os PDFs a partir de um deck em texto.

    `on_progress(done, total, phase)` é chamado durante a resolução e o
    processamento de imagens; `phase` é "Resolvendo" ou "Processando".
    Retorna um dicionário de estatísticas (requested, found, fallback,
    not_found, pages, cards_per_page, duplex).
    """
    requests, parse_errors = parse_deck(
        deck_text, default_language=config.cards.default_language
    )
    for err in parse_errors:
        logger.warning(f"  {err}")

    if not requests:
        raise ValueError("O deck está vazio ou não contém cartas válidas.")

    resolved, not_found, fallback_count = _resolve_and_cache(
        requests, config, progress=_phase_progress(on_progress, "Resolvendo"), cancel=cancel
    )
    cards_for_pdf, proc_errors = _expand_for_pdf(
        requests, resolved, config, progress=_phase_progress(on_progress, "Processando"),
        cancel=cancel, on_card=on_card,
    )
    not_found.extend(proc_errors)

    if not cards_for_pdf:
        raise RuntimeError("Nenhuma carta disponível para gerar o PDF.")

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    base = Path(deck_name).stem if deck_name else "deck"

    generator = PdfGenerator(config)
    layout, front_pages = generator.build_front_pages(cards_for_pdf)

    back_pages: list = []
    if config.duplex.enabled:
        back_path = _fetch_card_back(config)
        if back_path:
            back_pages = generator.build_back_pages(front_pages, layout, str(back_path))

    if config.output.generate_front_pdf:
        generator.write_pages(front_pages, output_dir / f"{base}-frente.pdf", layout)
    if config.output.generate_back_pdf and back_pages:
        generator.write_pages(back_pages, output_dir / f"{base}-verso.pdf", layout)

    if config.output.generate_combined_pdf:
        if back_pages:
            combined = []
            for fp, bp in zip(front_pages, back_pages):
                combined.append(fp)
                combined.append(bp)
        else:
            combined = front_pages
        generator.write_pages(combined, output_dir / f"{base}-impressao.pdf", layout)

    total_pages = len(front_pages) + len(back_pages)
    stats = {
        "requested": sum(req.quantity for req in requests),
        "found": len(resolved),
        "fallback": fallback_count,
        "not_found": not_found,
        "not_found_names": not_found,
        "pages": total_pages,
        "cards_per_page": layout.cards_per_page,
        "card_w": config.print.card_width_mm,
        "card_h": config.print.card_height_mm,
        "paper": config.print.paper,
        "duplex": config.duplex.enabled,
        "flip": config.duplex.flip,
        "output_base": base,
        "pdf_path": str(output_dir / f"{base}-impressao.pdf"),
    }
    return stats


def cmd_generate(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        text = _read_deck(args.deck)
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 2

    output_dir = Path(args.output) if args.output else config.output_dir
    try:
        stats = run_generate(text, config, output_dir, deck_name=args.deck)
    except (ValueError, RuntimeError) as exc:
        logger.error(str(exc))
        return 1

    logger.info("---- Resumo ----")
    logger.info(f"Cartas no PDF: {stats['requested']}")
    logger.info(f"Fallback de idioma: {stats['fallback']}")
    logger.info(f"Não encontradas: {len(stats['not_found'])}")
    for name in stats["not_found"]:
        logger.error(f"[ERRO] Carta não encontrada: {name}")

    return 0 if not stats["not_found"] else 1


def configure_mode(config: AppConfig, mode: str) -> AppConfig:
    """Retorna uma cópia da config ajustada para o modo de geração.

    mode="duplex" -> frentes + versos (PDF combinado frente/verso).
    mode="front"  -> somente frentes (PDF combinado só frente).
    """
    cfg = copy.deepcopy(config)
    if mode == "front":
        cfg.duplex.enabled = False
        cfg.output.generate_front_pdf = True
        cfg.output.generate_back_pdf = False
        cfg.output.generate_combined_pdf = False
    else:  # "duplex"
        cfg.duplex.enabled = True
        cfg.output.generate_front_pdf = False
        cfg.output.generate_back_pdf = False
        cfg.output.generate_combined_pdf = True
    return cfg


def launch_gui(config: AppConfig, deck_path: Optional[str] = None,
               output_dir: Optional[str] = None) -> int:
    from .gui.app import run

    run(config, deck_path=deck_path, output_dir=output_dir)
    return 0


def cmd_duplex_test(args: argparse.Namespace, config: AppConfig) -> int:
    output_dir = Path(args.output) if args.output else config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generator = PdfGenerator(config)
    generator.write_duplex_test(output_dir / "duplex-test.pdf")
    return 0


def cmd_scale_test(args: argparse.Namespace, config: AppConfig) -> int:
    output_dir = Path(args.output) if args.output else config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    generator = PdfGenerator(config)
    generator.write_scale_test(output_dir / "scale-test.pdf")
    return 0


def cmd_not_implemented(phase: str, feature: str) -> int:
    logger.warning(
        f"'{feature}' será implementado na {phase}. "
        f"Fase 1 inclui apenas o parser do deck e o comando 'check'."
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mtg_proxy",
        description="Gera PDF de proxies de Magic a partir de uma lista (Scryfall).",
    )
    parser.add_argument("--config", default="config.yaml", help="Caminho do config.yaml")
    parser.add_argument("--verbose", action="store_true", help="Logs em nível DEBUG")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Validar deck.txt sem gerar PDF")
    check.add_argument("--deck", default="deck.txt")

    generate = sub.add_parser("generate", help="Gerar o PDF de impressão")
    generate.add_argument("--deck", default="deck.txt")
    generate.add_argument("--output", default=None)

    gui = sub.add_parser("gui", help="Abrir a interface gráfica (PySide6)")
    gui.add_argument("--deck", default=None, help="Deck pré-carregado")
    gui.add_argument("--output", default=None, help="Pasta de saída padrão")

    download = sub.add_parser("download", help="Baixar/cachear imagens")
    download.add_argument("--deck", default="deck.txt")

    duplex = sub.add_parser("duplex-test", help="Gerar página de teste de alinhamento")
    duplex.add_argument("--output", default=None)

    scale = sub.add_parser("scale-test", help="Gerar página de teste de escala (50 mm)")
    scale.add_argument("--output", default=None)

    return parser


def _resolve_config_path(arg: str) -> Optional[str]:
    """Localiza o config.yaml, considerando o executável congelado (PyInstaller)."""
    candidates = [arg]
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).parent
        candidates.append(str(base / arg))
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(str(Path(meipass) / arg))
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    _setup_logging(args.verbose)

    try:
        config = load_config(_resolve_config_path(args.config))
    except FileNotFoundError as exc:
        logger.error(str(exc))
        return 2

    command = args.command
    if command == "check":
        return cmd_check(args, config)
    if command == "generate":
        return cmd_generate(args, config)
    if command == "gui":
        return launch_gui(config, deck_path=args.deck, output_dir=args.output)
    if command == "download":
        return cmd_download(args, config)
    if command == "duplex-test":
        return cmd_duplex_test(args, config)
    if command == "scale-test":
        return cmd_scale_test(args, config)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
