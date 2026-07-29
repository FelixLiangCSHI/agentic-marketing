"""Convert text-based export artifacts into PDF documents."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_PDF_FONT = "STSong-Light"
_FONT_REGISTERED = False


def _ensure_font() -> None:
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(_PDF_FONT))
        _FONT_REGISTERED = True


def _line_style(line: str) -> ParagraphStyle:
    if line.startswith("# "):
        return ParagraphStyle(
            "heading1", fontName=_PDF_FONT, fontSize=16, leading=20, spaceAfter=6
        )
    if line.startswith("## "):
        return ParagraphStyle(
            "heading2", fontName=_PDF_FONT, fontSize=13, leading=17, spaceAfter=5
        )
    if line.startswith("### "):
        return ParagraphStyle(
            "heading3", fontName=_PDF_FONT, fontSize=11, leading=15, spaceAfter=4
        )
    return ParagraphStyle("body", fontName=_PDF_FONT, fontSize=9, leading=13)


def _paragraph_text(line: str) -> str:
    stripped = line.lstrip("#").strip() if line.startswith("#") else line
    text = escape(stripped).replace("  ", "&nbsp;&nbsp;")
    return text or "&nbsp;"


def text_to_pdf_bytes(text: str, title: str) -> bytes:
    """Render plain text or Markdown-style text into a simple PDF document."""
    _ensure_font()
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )
    story: list[Paragraph | Spacer] = []
    for line in text.splitlines():
        if line.strip():
            story.append(Paragraph(_paragraph_text(line), _line_style(line)))
        else:
            story.append(Spacer(1, 4))
    if not story:
        story.append(Paragraph("&nbsp;", _line_style("")))
    document.build(story)
    return buffer.getvalue()


def as_pdf_artifact(artifact: dict[str, str]) -> dict[str, str | bytes]:
    """Return a PDF version of a text export artifact."""
    base_name = artifact["fileName"].rsplit(".", 1)[0]
    file_name = f"{base_name}.pdf"
    return {
        "fileName": file_name,
        "mimeType": "application/pdf",
        "content": text_to_pdf_bytes(artifact["content"], base_name),
    }
