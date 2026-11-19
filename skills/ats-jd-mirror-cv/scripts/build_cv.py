#!/usr/bin/env python3
"""Build a one-page, single-column, ATS-safe CV PDF from a JSON spec.

Usage: python3 build_cv.py cv.json [output.pdf]

Auto-fits to one page by shrinking the font from 10pt down to 9.0pt. If it still
overflows, it drops sections listed in spec["drop_if_overflow"] in order, then
exits with code 1 if the CV is still longer than one page.
"""
import copy
import json
import os
import sys

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

FONT_DIRS = ["/usr/share/fonts/truetype/liberation/", "/usr/share/fonts/liberation/"]


def register_fonts():
    for d in FONT_DIRS:
        if os.path.exists(d + "LiberationSerif-Regular.ttf"):
            for n, f in [("Serif", "Regular"), ("Serif-B", "Bold"), ("Serif-I", "Italic"), ("Serif-BI", "BoldItalic")]:
                pdfmetrics.registerFont(TTFont(n, d + f"LiberationSerif-{f}.ttf"))
            addMapping("Serif", 0, 0, "Serif"); addMapping("Serif", 1, 0, "Serif-B")
            addMapping("Serif", 0, 1, "Serif-I"); addMapping("Serif", 1, 1, "Serif-BI")
            return "Serif"
    return "Times-Roman"  # fallback: built-in font


def build(spec, out, fs):
    font = register_fonts()
    bold = "Serif-B" if font == "Serif" else "Times-Bold"
    ld = fs * 1.2
    body = ParagraphStyle("b", fontName=font, fontSize=fs, leading=ld, alignment=TA_JUSTIFY)
    left = ParagraphStyle("l", parent=body, alignment=0)
    right = ParagraphStyle("r", parent=body, alignment=2)
    name = ParagraphStyle("n", fontName=bold, fontSize=22, leading=25, alignment=TA_CENTER)
    head = ParagraphStyle("h", parent=body, alignment=TA_CENTER, fontName=bold, fontSize=fs + 0.5)
    center = ParagraphStyle("c", parent=body, alignment=TA_CENTER, fontSize=fs - 1, leading=ld - 1)
    sect = ParagraphStyle("s", fontName=bold, fontSize=fs + 3, leading=fs + 5, spaceBefore=6)
    W = A4[0] - 30 * mm - 12

    def section(t):
        return [Paragraph(t.upper(), sect),
                HRFlowable(width="100%", thickness=0.8, color="black", spaceBefore=1, spaceAfter=3)]

    def row(l, r):
        t = Table([[Paragraph(l, left), Paragraph(r, right)]], colWidths=[W * 0.65, W * 0.35])
        t.setStyle(TableStyle([(p, (0, 0), (-1, -1), 0) for p in
                               ("LEFTPADDING", "RIGHTPADDING", "TOPPADDING", "BOTTOMPADDING")]))
        return t

    def bullets(items):
        return ListFlowable([ListItem(Paragraph(i, body), leftIndent=12, value="•") for i in items],
                            bulletType="bullet", bulletFontName=font, bulletFontSize=fs, leftIndent=12)

    s = [Paragraph(spec["name"], name)]
    if spec.get("headline"):
        s.append(Paragraph(spec["headline"], head))
    s.append(Paragraph(spec["contact"], center))
    s += section("Summary") + [Paragraph(spec["summary"], body)]
    s += section("Experience")
    for i, e in enumerate(spec["experience"]):
        if i:
            s.append(Spacer(1, 4))
        s += [row(f"<b>{e['company']}</b>", f"<b>{e['location']}</b>"),
              row(f"<i>{e['title']}</i>", f"<i>{e['dates']}</i>")]
        if e.get("about"):
            s.append(Paragraph(e["about"], left))
        s.append(bullets(e["bullets"]))
    if spec.get("projects"):
        s += section(spec.get("projects_title", "Projects")) + [bullets(spec["projects"])]
    if spec.get("leadership"):
        s += section("Leadership")
        for l in spec["leadership"]:
            s.append(row(f"<b>{l['org']}</b> | <i>{l['role']}</i>", f"<i>{l['dates']}</i>"))
            if l.get("text"):
                s.append(Paragraph(l["text"], left))
    for line in spec.get("extra_lines", []):
        s += [Spacer(1, 2), Paragraph(line, left)]
    s += section("Education")
    for ed in spec["education"]:
        s += [row(f"<b>{ed['school']}</b>", f"<b>{ed['location']}</b>"),
              row(f"<i>{ed['degree']}</i>", f"<i>{ed['year']}</i>")]
        if ed.get("note"):
            s.append(Paragraph(ed["note"], left))
    s += section("Skills & Languages")
    s += [Paragraph(f"<b>{k}:</b> {t}", left) for k, t in spec["skills"]]
    if spec.get("languages"):
        s.append(Paragraph(f"<b>Languages:</b> {spec['languages']}", left))

    pages = []
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=11 * mm,
                            bottomMargin=10 * mm, title=f"{spec['name']} CV", author=spec["name"])
    doc.build(s, onLaterPages=lambda c, d: pages.append(1))
    return 1 + len(pages)


def main():
    spec = json.load(open(sys.argv[1]))
    out = sys.argv[2] if len(sys.argv) > 2 else spec.get("output", "cv.pdf")
    sizes = [10, 9.8, 9.6, 9.5, 9.4, 9.3, 9.2, 9.1, 9.0]
    drops = list(spec.get("drop_if_overflow", []))
    while True:
        for fs in sizes:
            n = build(spec, out, fs)
            if n == 1:
                print(f"OK {out} 1 page at {fs}pt")
                return 0
        if not drops:
            print(f"OVERFLOW {out}: {n} pages at 9.0pt. Cut content.")
            return 1
        key = drops.pop(0)
        if key.startswith("skills:"):
            label = key.split(":", 1)[1]
            spec["skills"] = [x for x in spec["skills"] if x[0] != label]
        else:
            spec = copy.deepcopy(spec)
            spec.pop(key, None)
        print(f"dropped {key} to fit one page")


if __name__ == "__main__":
    sys.exit(main())
