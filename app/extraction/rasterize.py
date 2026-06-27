"""Render PDF pages to PNG bytes using PyMuPDF (no system deps)."""

from pathlib import Path

import fitz  # PyMuPDF

from app.config import settings


def page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count


def render_page(pdf_path: Path, page_index: int, max_px: int | None = None) -> bytes:
    """Render a single 0-based page to PNG bytes, longest edge ~= max_px."""
    max_px = max_px or settings.rasterize_max_px
    with fitz.open(pdf_path) as doc:
        page = doc.load_page(page_index)
        longest_pt = max(page.rect.width, page.rect.height)
        zoom = max_px / longest_pt if longest_pt else 1.0
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
        return pix.tobytes("png")


def render_page_cached(pdf_path: Path, page_index: int, cache_dir: Path) -> bytes:
    """Render with an on-disk PNG cache so re-runs don't re-rasterize."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"page_{page_index:04d}.png"
    if cached.exists():
        return cached.read_bytes()
    data = render_page(pdf_path, page_index)
    cached.write_bytes(data)
    return data
