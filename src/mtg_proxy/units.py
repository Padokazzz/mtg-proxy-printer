"""Conversões entre unidades físicas e pontos/pixels."""

MM_PER_INCH = 25.4
PT_PER_INCH = 72.0


def mm_to_pt(mm: float) -> float:
    """Milímetros -> pontos (1 pt = 1/72 inch, 1 inch = 25.4 mm)."""
    return mm / MM_PER_INCH * PT_PER_INCH


def mm_to_px(mm: float, dpi: float) -> float:
    """Milímetros -> pixels numa dada resolução (DPI)."""
    return mm / MM_PER_INCH * dpi


def pt_to_mm(pt: float) -> float:
    return pt / PT_PER_INCH * MM_PER_INCH


def px_to_mm(px: float, dpi: float) -> float:
    return px / dpi * MM_PER_INCH
