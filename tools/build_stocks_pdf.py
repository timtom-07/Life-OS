#!/usr/bin/env python3
"""
build_stocks_pdf.py — rendert data/aktien.json in eine schoene 1-2-Seiten-PDF
(data/stocks-latest.pdf) im Life-OS-Look.

Aufruf (vom Repo-Root oder von ueberall):
    python tools/build_stocks_pdf.py

Single source of truth: aktien.json. Die PDF wird IMMER daraus erzeugt, damit
Webseite und PDF denselben Inhalt zeigen. Sauberer Textfluss -> nichts ueberlappt.
Schriften liegen in tools/fonts/ (mit Standard-Fallback, laeuft also immer).

Abhaengigkeit:  pip install reportlab
"""

import json
import os
import sys

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.colors import HexColor
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
AKTIEN_JSON = os.path.join(DATA, "aktien.json")
OUT_PDF = os.path.join(DATA, "stocks-latest.pdf")

# ---------------------------------------------------------------- Farben
BG     = HexColor("#F4EFE6")
INK    = HexColor("#2A2622")
SOFT   = HexColor("#5A5048")
MUTE   = HexColor("#9A8E80")
ACCENT = HexColor("#9C4221")
LINE   = HexColor("#E2D9CC")
GREEN  = "#2E7D5B"
RED    = "#B23A2E"
SOFTHX = "#5A5048"

# Flag -> (Farbe, Standard-Label)
FLAG_META = {
    "buy":   ("#2E7D5B", "Buy"),
    "watch": ("#2F6FBF", "Watch"),
    "hold":  ("#B7891F", "Hold"),
    "alert": ("#C2410C", "Alert"),
    "sell":  ("#9C2B22", "Sell"),
}
CONTENT_W = 17 * cm  # A4 (21cm) minus 2cm Rand je Seite


# ---------------------------------------------------------------- Schriften
def _reg(name, filename):
    path = os.path.join(FONTS, filename)
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont(name, path)); return name
        except Exception:
            return None
    return None


SERIF_TITLE = _reg("FrauncesBlack", "Fraunces-Black.ttf") or _reg("FrauncesSB", "Fraunces-SemiBold.ttf") or "Times-Bold"
SANS        = _reg("Manrope", "Manrope-Regular.ttf") or "Helvetica"
SANS_SB     = _reg("ManropeSB", "Manrope-SemiBold.ttf") or "Helvetica-Bold"
MONO        = _reg("JBMono", "JetBrainsMono-Regular.ttf") or "Courier"


# ---------------------------------------------------------------- Styles
styles = {
    "kicker":   ParagraphStyle("kicker", fontName=MONO, fontSize=8, textColor=ACCENT, leading=11, spaceAfter=6),
    "title":    ParagraphStyle("title", fontName=SERIF_TITLE, fontSize=30, textColor=INK, leading=34, spaceAfter=3),
    "subtitle": ParagraphStyle("subtitle", fontName=SANS, fontSize=11, textColor=SOFT, leading=15),
    "lead":     ParagraphStyle("lead", fontName=SANS, fontSize=10.5, textColor=INK, leading=15.5),
    "stk_left": ParagraphStyle("stk_left", fontName=SANS_SB, fontSize=12, textColor=INK, leading=15),
    "stk_right": ParagraphStyle("stk_right", fontName=MONO, fontSize=10, textColor=INK, leading=15, alignment=2),
    "stk_note": ParagraphStyle("stk_note", fontName=SANS, fontSize=10, textColor=SOFT, leading=14.5, spaceBefore=3),
}


def esc(s):
    return (str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _decorate(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(BG)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setStrokeColor(LINE); canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 1.5 * cm, w - doc.rightMargin, 1.5 * cm)
    canvas.setFont(MONO, 7); canvas.setFillColor(MUTE)
    canvas.drawString(doc.leftMargin, 1.15 * cm, doc._foot)
    canvas.drawRightString(w - doc.rightMargin, 1.15 * cm, "Seite %d" % doc.page)
    canvas.restoreState()


def _item(it):
    flag = it.get("flag", "watch")
    if flag not in FLAG_META:
        flag = "watch"
    fcolor, flabel_def = FLAG_META[flag]
    flabel = esc(it.get("flagLabel") or flabel_def).upper()

    cp = it.get("changePct")
    change = ""
    if isinstance(cp, (int, float)):
        up = cp >= 0
        arrow = "\u25B2" if up else "\u25BC"
        col = GREEN if up else RED
        sign = "+" if up else "\u2212"
        num = ("%.1f" % abs(cp)).replace(".", ",")
        change = '<font color="%s">%s&#160;%s%s&#160;%%</font>&#160;&#160;&#160;' % (col, arrow, sign, num)

    left = Paragraph(
        '<font name="%s">%s</font>&#160;&#160;<font size="9" color="%s">%s</font>'
        % (MONO, esc(it.get("ticker", "")), SOFTHX, esc(it.get("name", ""))),
        styles["stk_left"],
    )
    right = Paragraph(
        '%s<font name="%s" color="%s">\u25CF %s</font>' % (change, MONO, fcolor, flabel),
        styles["stk_right"],
    )
    row = Table([[left, right]], colWidths=[CONTENT_W * 0.56, CONTENT_W * 0.44])
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    block = [row]
    if it.get("note"):
        block.append(Paragraph(esc(it["note"]), styles["stk_note"]))
    return KeepTogether(block)


def build(data):
    story = []
    label = data.get("dateLabel") or data.get("updated") or ""
    story.append(Paragraph("LIFE OS&#160;&#160;·&#160;&#160;DAILY STOCKS", styles["kicker"]))
    story.append(Paragraph("Markt\u00fcberblick", styles["title"]))
    if label:
        story.append(Paragraph(esc(label), styles["subtitle"]))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.2, color=ACCENT, spaceBefore=2, spaceAfter=15))

    if data.get("summary"):
        story.append(Paragraph(esc(data["summary"]), styles["lead"]))
        story.append(Spacer(1, 16))

    items = data.get("items") or []
    for i, it in enumerate(items):
        story.append(_item(it))
        if i < len(items) - 1:
            story.append(Spacer(1, 9))
            story.append(HRFlowable(width="100%", thickness=0.5, color=LINE, spaceBefore=0, spaceAfter=13))
    return story


def main():
    if not os.path.exists(AKTIEN_JSON):
        print("FEHLER: %s nicht gefunden." % AKTIEN_JSON); sys.exit(1)
    with open(AKTIEN_JSON, encoding="utf-8") as f:
        data = json.load(f)

    gen = data.get("generated") or data.get("updated") or ""
    foot = ("Hypothetische Einschaetzung · keine Anlageberatung · keine Trade-Ausfuehrung · %s" % gen).strip(" ·")

    doc = BaseDocTemplate(
        OUT_PDF, pagesize=A4,
        leftMargin=2.0 * cm, rightMargin=2.0 * cm, topMargin=1.9 * cm, bottomMargin=1.9 * cm,
        title="Life OS — Daily Stocks", author="Life OS Stocks-Routine",
    )
    doc._foot = foot
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="stocks", frames=[frame], onPage=_decorate)])
    doc.build(build(data))
    print("OK: %s erstellt (%d Werte)." % (OUT_PDF, len(data.get("items") or [])))


if __name__ == "__main__":
    main()
