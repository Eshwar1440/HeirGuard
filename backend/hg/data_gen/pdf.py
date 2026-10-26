"""reportlab helpers for specimen forms.

Every page gets a diagonal "SPECIMEN - HYPOTHETICAL DATA" watermark. Pages are
written uncompressed and with ``invariant=1`` so output is reproducible and the
watermark text can be checked in tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from reportlab.lib.colors import Color, black
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

WATERMARK = "SPECIMEN - HYPOTHETICAL DATA"
FOOTER = "Hypothetical specimen generated for a concept prototype. Not a real form or record."

PAGE_W, PAGE_H = letter
MARGIN = 54
CONTENT_W = PAGE_W - 2 * MARGIN
ROW_H = 38

INK = Color(0.12, 0.16, 0.22)
MUTED = Color(0.38, 0.42, 0.48)
RULE = Color(0.70, 0.73, 0.77)
STAMP_RED = Color(0.78, 0.10, 0.10)
WATERMARK_GRAY = Color(0.55, 0.55, 0.55, alpha=0.22)


class FormCanvas:
    """A page-at-a-time form writer with a moving cursor ``y``."""

    def __init__(self, path: Path, form_id: str, total_pages: int, title: str):
        self.c = canvas.Canvas(str(path), pagesize=letter, invariant=1, pageCompression=0)
        self.c.setTitle(f"{title} (specimen)")
        self.c.setAuthor("HeritageGuard synthetic data generator")
        self.form_id = form_id
        self.total_pages = total_pages
        self.page = 1
        self.y = PAGE_H - MARGIN

    # --- Blocks --------------------------------------------------------------

    def header(self, title: str, issuer: str) -> None:
        c = self.c
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 8)
        c.drawString(MARGIN, self.y, issuer.upper())
        c.drawRightString(PAGE_W - MARGIN, self.y, self.form_id)
        self.y -= 26
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 18)
        c.drawString(MARGIN, self.y, title)
        self.y -= 10
        c.setStrokeColor(INK)
        c.setLineWidth(1.2)
        c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 22

    def section(self, text: str) -> None:
        c = self.c
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 10.5)
        c.drawString(MARGIN, self.y, text)
        self.y -= 6
        c.setStrokeColor(RULE)
        c.setLineWidth(0.6)
        c.line(MARGIN, self.y, PAGE_W - MARGIN, self.y)
        self.y -= 16

    def paragraph(self, text: str, size: float = 9.5, font: str = "Helvetica") -> None:
        c = self.c
        c.setFillColor(INK)
        c.setFont(font, size)
        for line in simpleSplit(text, font, size, CONTENT_W):
            c.drawString(MARGIN, self.y, line)
            self.y -= size + 4
        self.y -= 8

    def fields(self, items: list[tuple[str, str, bool]]) -> None:
        """Labeled boxes. Each item is ``(label, value, wide)``; narrow items pair up."""
        row: list[tuple[str, str]] = []
        for label, value, wide in items:
            if wide:
                if row:
                    self._field_row(row)
                    row = []
                self._field_row([(label, value)])
            else:
                row.append((label, value))
                if len(row) == 2:
                    self._field_row(row)
                    row = []
        if row:
            self._field_row(row)
        self.y -= 6

    def _field_row(self, row: list[tuple[str, str]]) -> None:
        c = self.c
        gap = 12
        width = (CONTENT_W - gap * (2 - 1)) / 2 if len(row) == 2 else CONTENT_W
        x = MARGIN
        for label, value in row:
            c.setStrokeColor(RULE)
            c.setLineWidth(0.6)
            c.rect(x, self.y - ROW_H + 10, width, ROW_H - 4, stroke=1, fill=0)
            c.setFillColor(MUTED)
            c.setFont("Helvetica", 7)
            c.drawString(x + 5, self.y - 1, label.upper())
            c.setFillColor(black)
            c.setFont("Courier-Bold", 10.5)
            c.drawString(x + 5, self.y - 19, value)
            x += width + gap
        self.y -= ROW_H + 2

    def signature(self, label: str, signed_name: Optional[str], date_label: str, date_value: str) -> None:
        c = self.c
        self.y -= 18
        line_w = CONTENT_W * 0.6
        if signed_name:
            c.setFillColor(Color(0.05, 0.15, 0.45))
            c.setFont("Times-Italic", 15)
            c.drawString(MARGIN + 6, self.y + 4, signed_name)
        c.setStrokeColor(INK)
        c.setLineWidth(0.8)
        c.line(MARGIN, self.y, MARGIN + line_w, self.y)
        date_x = MARGIN + line_w + 24
        c.setFillColor(black)
        c.setFont("Courier-Bold", 10.5)
        c.drawString(date_x + 4, self.y + 4, date_value)
        c.line(date_x, self.y, PAGE_W - MARGIN, self.y)
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(MARGIN, self.y - 10, label.upper())
        c.drawString(date_x, self.y - 10, date_label.upper())
        self.y -= 34

    def seal(self, lines: list[str]) -> None:
        """Text block standing in for a registrar's certification and raised seal."""
        c = self.c
        cx, cy, r = PAGE_W - MARGIN - 60, self.y - 50, 46
        c.setStrokeColor(INK)
        c.setLineWidth(1.4)
        c.circle(cx, cy, r, stroke=1, fill=0)
        c.circle(cx, cy, r - 6, stroke=1, fill=0)
        c.setFillColor(INK)
        c.setFont("Helvetica-Bold", 7)
        c.drawCentredString(cx, cy + 4, "OFFICIAL SEAL")
        c.drawCentredString(cx, cy - 6, "OF THE REGISTRAR")
        text_y = self.y - 14
        for i, line in enumerate(lines):
            c.setFont("Helvetica-Bold" if i == 0 else "Helvetica", 10 if i == 0 else 8.5)
            c.drawString(MARGIN, text_y, line)
            text_y -= 14
        self.y -= 112

    def stamp(self, text: str) -> None:
        """A red rubber-stamp style marker, e.g. COPY - NOT CERTIFIED."""
        c = self.c
        c.saveState()
        c.translate(PAGE_W - MARGIN - 130, self.y - 40)
        c.rotate(-8)
        c.setStrokeColor(STAMP_RED)
        c.setFillColor(STAMP_RED)
        c.setLineWidth(2.2)
        c.rect(-110, -18, 220, 40, stroke=1, fill=0)
        c.setFont("Helvetica-Bold", 16)
        c.drawCentredString(0, -4, text)
        c.restoreState()
        self.y -= 90

    # --- Pages ---------------------------------------------------------------

    def end_page(self) -> None:
        c = self.c
        c.setFillColor(MUTED)
        c.setFont("Helvetica", 7)
        c.drawString(MARGIN, 30, FOOTER)
        c.drawRightString(PAGE_W - MARGIN, 30, f"Page {self.page} of {self.total_pages}")
        self._watermark()
        c.showPage()
        self.page += 1
        self.y = PAGE_H - MARGIN

    def _watermark(self) -> None:
        c = self.c
        c.saveState()
        c.translate(PAGE_W / 2, PAGE_H / 2)
        c.rotate(45)
        c.setFillColor(WATERMARK_GRAY)
        c.setFont("Helvetica-Bold", 40)
        c.drawCentredString(0, 0, WATERMARK)
        c.restoreState()

    def save(self) -> None:
        if self.page - 1 != self.total_pages:
            raise ValueError(f"{self.form_id}: wrote {self.page - 1} pages, expected {self.total_pages}")
        self.c.save()


__all__ = ["FormCanvas", "WATERMARK"]
