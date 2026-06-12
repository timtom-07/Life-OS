#!/usr/bin/env python3
"""
build_news_pdf.py — rendert data/news.json in eine schoene 1-2-Seiten-PDF
(data/news-latest.pdf) im Life-OS-Look.

Aufruf (vom Repo-Root oder von ueberall):
    python tools/build_news_pdf.py

Single source of truth: news.json. Die PDF wird IMMER aus news.json erzeugt,
damit Webseite und PDF denselben Inhalt zeigen. Sauberer Textfluss (reportlab
Platypus) -> es ueberschneidet sich nichts, egal wie lang die Texte sind.

Schriften liegen in tools/fonts/ (Fraunces, Manrope, JetBrains Mono). Fehlt eine,
greift automatisch eine Standard-Schrift, das Skript laeuft also immer.

Abhaengigkeit:  pip install reportlab
"""

import json
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.lib.styles import ParagraphStyle

# ---------------------------------------------------------------- Pfade
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
FONTS = os.path.join(HERE, "fonts")
NEWS_JSON = os.path.join(DATA, "news.json")
OUT_PDF = os.path.join(DATA, "news-latest.pdf")

# ---------------------------------------------------------------- Farben (Life-OS-CI)
BG     = HexColor("#F4EFE6")
INK    = HexColor("#2A2622")
SOFT   = HexColor("#5A5048")
MUTE   = HexColor("#9A8E80")
ACCENT = HexColor("#9C4221")
LINE   = HexColor("#E2D9CC")
CARD   = HexColor("#FBF6EE")


# ---------------------------------------------------------------- Schriften
def _reg(name, filename):
    path = os.path.join(FONTS, filename)
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont(name, path))
            return name
        except Exception:
            return None
    return None


SERIF       = _reg("Fraunces", "Fraunces-Regular.ttf") or "Times-Roman"
SERIF_TITLE = _reg("FrauncesBlack", "Fraunces-Black.ttf") or _reg("FrauncesSB", "Fraunces-SemiBold.ttf") or "Times-Bold"
SANS        = _reg("Manrope", "Manrope-Regular.ttf") or "Helvetica"
SANS_SB     = _reg("ManropeSB", "Manrope-SemiBold.ttf") or "Helvetica-Bold"
MONO        = _reg("JBMono", "JetBrainsMono-Regular.ttf") or "Courier"


# ---------------------------------------------------------------- Styles
styles = {
    "kicker": ParagraphStyle("kicker", fontName=MONO, fontSize=8, textColor=ACCENT,
                             leading=11, spaceAfter=6),
    "title": ParagraphStyle("title", fontName=SERIF_TITLE, fontSize=30, textColor=INK,
                            leading=34, spaceAfter=3),
    "subtitle": ParagraphStyle("subtitle", fontName=SANS, fontSize=11, textColor=SOFT,
                               leading=15),
    "sec_kicker": ParagraphStyle("sec_kicker", fontName=MONO, fontSize=8.5, textColor=ACCENT,
                                 leading=12, spaceAfter=4),
    "body": ParagraphStyle("body", fontName=SANS, fontSize=10.5, textColor=INK,
                           leading=15.5),
    "change": ParagraphStyle("change", fontName=SANS, fontSize=9, textColor=SOFT,
                             leading=13, spaceBefore=5),
    "box_title": ParagraphStyle("box_title", fontName=MONO, fontSize=8, textColor=ACCENT,
                                leading=11, spaceAfter=6),
    "box_item": ParagraphStyle("box_item", fontName=SANS, fontSize=9.5, textColor=SOFT,
                               leading=14, spaceAfter=3),
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# ---------------------------------------------------------------- Seitenhintergrund + Footer
def _decorate(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 1.5 * cm, w - doc.rightMargin, 1.5 * cm)
    canvas.setFont(MONO, 7)
    canvas.setFillColor(MUTE)
    canvas.drawString(doc.leftMargin, 1.15 * cm, doc._gen_label)
    canvas.drawRightString(w - doc.rightMargin, 1.15 * cm, "Seite %d" % doc.page)
    canvas.restoreState()


# ---------------------------------------------------------------- Bau
def build(news):
    story = []
    label = news.get("dateLabel") or news.get("date") or ""

    story.append(Paragraph("LIFE OS&#160;&#160;·&#160;&#160;DAILY NEWS", styles["kicker"]))
    story.append(Paragraph("Tages\u00fcberblick", styles["title"]))
    if label:
        story.append(Paragraph(esc(label), styles["subtitle"]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceBefore=2, spaceAfter=15))

    changes = [c for c in (news.get("changes_since_yesterday") or []) if str(c).strip()]
    if changes:
        inner = [Paragraph("WAS IST NEU SEIT GESTERN", styles["box_title"])]
        for c in changes:
            inner.append(Paragraph("•&#160;&#160;" + esc(c), styles["box_item"]))
        box = Table([[inner]], colWidths=["100%"])
        box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), CARD),
            ("LINEBEFORE", (0, 0), (0, -1), 2.2, ACCENT),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 12),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(box)
        story.append(Spacer(1, 20))

    sections = news.get("sections") or []
    for i, sec in enumerate(sections):
        block = [
            Paragraph(esc(sec.get("title", "")).upper(), styles["sec_kicker"]),
            Paragraph(esc(sec.get("body", "")).replace("\n", "<br/>"), styles["body"]),
        ]
        ch = sec.get("change")
        if ch and str(ch).strip():
            block.append(Paragraph("&#187;&#160;seit gestern:&#160;" + esc(ch), styles["change"]))
        story.append(KeepTogether(block))
        if i < len(sections) - 1:
            story.append(Spacer(1, 10))
            story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceBefore=0, spaceAfter=14))
    return story


def main():
    if not os.path.exists(NEWS_JSON):
        print("FEHLER: %s nicht gefunden." % NEWS_JSON)
        sys.exit(1)
    with open(NEWS_JSON, encoding="utf-8") as f:
        news = json.load(f)

    gen = news.get("generated") or news.get("date") or ""
    gen_label = ("Erstellt %s · automatische Recherche · Life OS" % gen).strip()

    doc = BaseDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm,
        topMargin=1.9 * cm, bottomMargin=1.9 * cm,
        title="Life OS — Daily News", author="Life OS News-Routine",
    )
    doc._gen_label = gen_label
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="news", frames=[frame], onPage=_decorate)])
    doc.build(build(news))
    print("OK: %s erstellt (%d Sektionen)." % (OUT_PDF, len(news.get("sections") or [])))


if __name__ == "__main__":
    main()
