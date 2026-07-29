"""Convert text-based export artifacts into readable PDF documents."""

from __future__ import annotations

import io
import json
import re
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

_PDF_FONT = "STSong-Light"
_FONT_REGISTERED = False

_ACCENT = colors.HexColor("#1F4E79")
_MUTED = colors.HexColor("#555555")
_CODE_COLOR = colors.HexColor("#0B5CAD")

_TITLE_STYLE = ParagraphStyle(
    "title",
    fontName=_PDF_FONT,
    fontSize=19,
    leading=24,
    textColor=_ACCENT,
    spaceBefore=0,
    spaceAfter=10,
)
_HEADING2_STYLE = ParagraphStyle(
    "heading2",
    fontName=_PDF_FONT,
    fontSize=14,
    leading=18,
    textColor=_ACCENT,
    spaceBefore=14,
    spaceAfter=6,
)
_HEADING3_STYLE = ParagraphStyle(
    "heading3",
    fontName=_PDF_FONT,
    fontSize=12,
    leading=16,
    textColor=_MUTED,
    spaceBefore=10,
    spaceAfter=4,
)
_BODY_STYLE = ParagraphStyle(
    "body",
    fontName=_PDF_FONT,
    fontSize=10,
    leading=15,
    spaceAfter=3,
)

_BOLD_PATTERN = re.compile(r"\*\*(.+?)\*\*")
_ITALIC_PATTERN = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")
_CODE_PATTERN = re.compile(r"`([^`]+?)`")
_BULLET_PATTERN = re.compile(r"^(\s*)[-*]\s+(.*)$")
_ORDERED_PATTERN = re.compile(r"^(\s*)(\d+)[.)]\s+(.*)$")


def _ensure_font() -> None:
    global _FONT_REGISTERED
    if not _FONT_REGISTERED:
        pdfmetrics.registerFont(UnicodeCIDFont(_PDF_FONT))
        _FONT_REGISTERED = True


def _inline_markup(text: str) -> str:
    """Escape text and convert Markdown inline markup to Paragraph tags."""
    rendered = escape(text)
    rendered = _BOLD_PATTERN.sub(r"<b>\1</b>", rendered)
    rendered = _ITALIC_PATTERN.sub(r"<i>\1</i>", rendered)
    rendered = _CODE_PATTERN.sub(r'<font color="#0B5CAD">\1</font>', rendered)
    return rendered or "&nbsp;"


def _list_style(indent_level: int) -> ParagraphStyle:
    return ParagraphStyle(
        f"list-{indent_level}",
        parent=_BODY_STYLE,
        leftIndent=14 + indent_level * 12,
        bulletIndent=4 + indent_level * 12,
        spaceAfter=2,
    )


def _markdown_story(text: str) -> list[Any]:
    story: list[Any] = []
    pending_space = False
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            pending_space = True
            continue
        if pending_space and story:
            story.append(Spacer(1, 4))
        pending_space = False
        if line.startswith("# "):
            story.append(Paragraph(_inline_markup(line[2:].strip()), _TITLE_STYLE))
            story.append(
                HRFlowable(width="100%", thickness=0.8, color=_ACCENT, spaceAfter=8)
            )
            continue
        if line.startswith("## "):
            story.append(
                Paragraph(_inline_markup(line[3:].strip()), _HEADING2_STYLE)
            )
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.4,
                    color=colors.HexColor("#C9D6E4"),
                    spaceAfter=4,
                )
            )
            continue
        if line.startswith("### "):
            story.append(
                Paragraph(_inline_markup(line[4:].strip()), _HEADING3_STYLE)
            )
            continue
        bullet_match = _BULLET_PATTERN.match(raw_line)
        if bullet_match:
            indent_level = min(len(bullet_match.group(1)) // 2, 4)
            story.append(
                Paragraph(
                    _inline_markup(bullet_match.group(2)),
                    _list_style(indent_level),
                    bulletText="•",
                )
            )
            continue
        ordered_match = _ORDERED_PATTERN.match(raw_line)
        if ordered_match:
            indent_level = min(len(ordered_match.group(1)) // 2, 4)
            story.append(
                Paragraph(
                    _inline_markup(ordered_match.group(3)),
                    _list_style(indent_level),
                    bulletText=f"{ordered_match.group(2)}.",
                )
            )
            continue
        story.append(Paragraph(_inline_markup(line), _BODY_STYLE))
    return story


def _label(key: str) -> str:
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", key).replace("_", " ")
    return spaced[:1].upper() + spaced[1:]


def _json_lines(value: Any, key: str | None, depth: int) -> list[str]:
    """Flatten a JSON value into readable Markdown-style lines."""
    indent = "  " * max(depth - 2, 0)
    if isinstance(value, dict):
        lines: list[str] = []
        if key is not None:
            if depth == 1:
                lines.append(f"## {_label(key)}")
            elif depth == 2:
                lines.append(f"### {_label(key)}")
            else:
                lines.append(f"{indent}- **{_label(key)}**")
        for child_key, child in value.items():
            lines.extend(_json_lines(child, child_key, depth + 1))
        return lines
    if isinstance(value, list):
        lines = []
        if key is not None:
            if depth == 1:
                lines.append(f"## {_label(key)}")
            elif depth == 2:
                lines.append(f"### {_label(key)}")
            else:
                lines.append(f"{indent}- **{_label(key)}**")
        if not value:
            lines.append(f"{indent}  - None recorded")
            return lines
        for index, child in enumerate(value, start=1):
            if isinstance(child, (dict, list)):
                lines.append(f"{indent}  - Item {index}")
                lines.extend(_json_lines(child, None, depth + 2))
            else:
                lines.append(f"{indent}  - {_scalar(child)}")
        return lines
    label = f"**{_label(key)}:** " if key is not None else ""
    return [f"{indent}- {label}{_scalar(value)}"]


def _scalar(value: Any) -> str:
    if value is None:
        return "Not available"
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return str(value)


def json_to_readable_text(payload: str, title: str) -> str:
    """Convert a structured-analysis JSON payload into readable Markdown."""
    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, TypeError):
        return payload
    lines = [f"# {title}", ""]
    if isinstance(data, dict):
        for child_key, child in data.items():
            lines.extend(_json_lines(child, child_key, 1))
            lines.append("")
    else:
        lines.extend(_json_lines(data, None, 1))
    return "\n".join(lines)


def text_to_pdf_bytes(text: str, title: str) -> bytes:
    """Render plain text or Markdown-style text into a readable PDF."""
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
    story = _markdown_story(text)
    if not story:
        story.append(Paragraph("&nbsp;", _BODY_STYLE))
    document.build(story)
    return buffer.getvalue()


def as_pdf_artifact(artifact: dict[str, str]) -> dict[str, str | bytes]:
    """Return a readable PDF version of a text or JSON export artifact."""
    base_name, _, extension = artifact["fileName"].rpartition(".")
    base_name = base_name or artifact["fileName"]
    content = artifact["content"]
    title = _label(base_name.replace("-", " "))
    if extension.lower() == "json":
        content = json_to_readable_text(content, title)
    return {
        "fileName": f"{base_name}.pdf",
        "mimeType": "application/pdf",
        "content": text_to_pdf_bytes(content, title),
    }
