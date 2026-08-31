import logging
from pathlib import Path
from typing import List, Tuple

from reportlab.pdfgen import canvas

from ..config import AppConfig
from ..layout.a4 import CardRect, PageLayout, compute_grid, paginate, page_size_pt
from ..layout.cut_marks import cut_marks_for_cells
from ..layout.duplex import back_cells
from ..units import mm_to_pt
from ..models import ResolvedCard

logger = logging.getLogger("mtg_proxy")

Page = List[Tuple[CardRect, str]]


class PdfGenerator:
    """Gera o PDF de impressão usando ReportLab com escala física real."""

    def __init__(self, config: AppConfig):
        self.config = config

    def build_front_pages(self, cards: List[ResolvedCard]) -> Tuple[PageLayout, List[Page]]:
        layout = compute_grid(self.config)
        raw_pages = paginate(cards, layout.cards_per_page)
        pages: List[Page] = []
        for page_cards in raw_pages:
            page: Page = []
            for i, card in enumerate(page_cards):
                page.append((layout.cells[i], card.image_path or ""))
            pages.append(page)
        return layout, pages

    def build_back_pages(
        self, front_pages: List[Page], layout: PageLayout, back_image_path: str
    ) -> List[Page]:
        if not self.config.duplex.enabled:
            return []
        backs = back_cells(layout, self.config)
        result: List[Page] = []
        for page in front_pages:
            back_page: Page = []
            for i in range(len(page)):
                back_page.append((backs[i], back_image_path))
            result.append(back_page)
        return result

    def _draw_page(self, c: canvas.Canvas, layout: PageLayout, page: Page) -> None:
        occupied: List[CardRect] = []
        for rect, image_path in page:
            if image_path:
                c.drawImage(
                    str(image_path),
                    rect.x,
                    rect.y,
                    width=rect.w,
                    height=rect.h,
                    preserveAspectRatio=False,
                    mask="auto",
                )
            if self.config.cut_marks.card_outline:
                c.setStrokeColorRGB(0, 0, 0)
                c.setLineWidth(mm_to_pt(self.config.cut_marks.card_outline_mm))
                c.rect(rect.x, rect.y, rect.w, rect.h, stroke=1, fill=0)
            occupied.append(rect)

        for x1, y1, x2, y2 in cut_marks_for_cells(occupied, self.config):
            c.line(x1, y1, x2, y2)

    def write_pages(self, pages: List[Page], out_path: Path, layout: PageLayout) -> None:
        c = canvas.Canvas(str(out_path), pagesize=(layout.page_w, layout.page_h))
        for page in pages:
            self._draw_page(c, layout, page)
            c.showPage()
        c.save()
        logger.info(f"PDF criado: {out_path} ({len(pages)} página(s))")

    def write(self, cards: List[ResolvedCard], out_path: Path) -> None:
        """Gera apenas as páginas da frente (compatibilidade)."""
        layout, pages = self.build_front_pages(cards)
        self.write_pages(pages, out_path, layout)

    def _draw_label(self, c: canvas.Canvas, rect: CardRect, label: str, header: str) -> None:
        c.rect(rect.x, rect.y, rect.w, rect.h)
        font_size = mm_to_pt(20)
        c.setFont("Helvetica-Bold", font_size)
        cx = rect.x + rect.w / 2
        cy = rect.y + rect.h / 2 - font_size / 2
        c.drawCentredString(cx, cy, label)
        c.setFont("Helvetica", mm_to_pt(6))
        c.drawString(rect.x, rect.y + rect.h + mm_to_pt(1), header)

    def write_duplex_test(self, out_path: Path) -> None:
        """Gera página de teste de alinhamento (frente + verso com A-I)."""
        layout = compute_grid(self.config)
        labels = [chr(ord("A") + i) for i in range(layout.cards_per_page)]
        c = canvas.Canvas(str(out_path), pagesize=(layout.page_w, layout.page_h))

        # Frente
        for i, rect in enumerate(layout.cells):
            if i >= len(labels):
                break
            self._draw_label(c, rect, labels[i], "FRENTE")
        c.showPage()

        # Verso (posições transformadas pelo flip)
        backs = back_cells(layout, self.config)
        for i, rect in enumerate(backs):
            if i >= len(labels):
                break
            self._draw_label(c, rect, labels[i], "VERSO")
        c.showPage()

        c.save()
        logger.info(f"Teste de duplex criado: {out_path}")

    def write_scale_test(self, out_path: Path) -> None:
        """Gera página com um quadrado de 50 mm para conferência física."""
        pw, ph = page_size_pt(self.config)
        c = canvas.Canvas(str(out_path), pagesize=(pw, ph))
        size = mm_to_pt(50)
        margin = mm_to_pt(20)
        c.rect(margin, margin, size, size)
        c.setFont("Helvetica-Bold", mm_to_pt(11))
        c.drawString(margin, margin + size + mm_to_pt(6), "QUADRADO DE 50 MM")
        c.setFont("Helvetica", mm_to_pt(9))
        c.drawString(
            margin,
            margin - mm_to_pt(10),
            "Imprima em 100% de escala (sem 'ajustar à página') e meça com uma régua.",
        )
        c.save()
        logger.info(f"Teste de escala criado: {out_path}")
