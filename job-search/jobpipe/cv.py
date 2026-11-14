"""Stage 3a: ATS-safe CV PDFs. Only reorders existing sentences from candidate.json, never adds claims."""
import shutil
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .store import CANDIDATE, ROOT, slug

CV = CANDIDATE["cv"]
OUT = ROOT / "out" / "cv"
VARIANT_FOR = {"enterprise": "Enterprise", "channel": "Channel", "ai": "AI-Sales"}


def build_variant(name):
    v, c, S, B = CV["variants"][name], CANDIDATE["contact"], CV["summary"], CV["bullets"]
    st = lambda n, **k: ParagraphStyle(n, fontName=k.pop("font", "Helvetica"), **k)
    title = st("t", fontSize=19, leading=22, alignment=TA_CENTER, font="Helvetica-Bold")
    sub = st("s", fontSize=10, leading=12, alignment=TA_CENTER, font="Helvetica-Bold")
    con = st("c", fontSize=8.5, leading=11, alignment=TA_CENTER)
    h = st("h", fontSize=10.5, leading=13, font="Helvetica-Bold", spaceBefore=7, spaceAfter=1)
    body = st("b", fontSize=9, leading=11.5)
    bul = st("bl", fontSize=9, leading=11.5, leftIndent=9, bulletIndent=0)
    role = st("r", fontSize=9.5, leading=12, font="Helvetica-Bold")
    desc = st("d", fontSize=9, leading=11.5, font="Helvetica-Oblique")
    path = OUT / "_variants" / f"Ryan-Hadi-CV-{name}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm,
                            bottomMargin=12 * mm, title="Ryan Hadi CV", author="Ryan Hadi")
    f = [Paragraph(CANDIDATE["name"].upper(), title), Paragraph(CANDIDATE["headline"], sub),
         Paragraph(f"{c['city']} | {c['phone']} | {c['email']} | {c['linkedin']}", con)]

    def sec(t):
        f.append(Paragraph(t, h))
        f.append(HRFlowable(width="100%", thickness=0.8, color="black", spaceAfter=3))

    def row(left, right):
        t = Table([[Paragraph(left, role), Paragraph(right, st("rr", fontSize=9.5, leading=12, font="Helvetica-Bold", alignment=2))]],
                  colWidths=[None, 40 * mm])
        t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                               ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        f.append(t)

    sec("SUMMARY")
    f.append(Paragraph(" ".join(S[k] for k in v["summary"]), body))
    sec("EXPERIENCE")
    row("Business Development Manager, B2B Partnerships", "Mar 2023 - Present")
    f.append(Paragraph("Sinar Mas Land (OneSmartServices) | Jakarta, Indonesia", body))
    f.append(Paragraph("IT solutions unit of Sinar Mas Land (developer of BSD City), delivering cloud, managed services, and smart city infrastructure to 110+ corporate clients.", desc))
    for k in v["bullets"]:
        f.append(Paragraph(B[k], bul, bulletText="•"))
    f.append(Spacer(1, 4))
    row("Business Development Executive", "Apr 2021 - Mar 2023")
    f.append(Paragraph("Siloam Hospitals Group | Jakarta, Indonesia", body))
    f.append(Paragraph("Indonesian private hospital network serving inpatient, outpatient, and corporate healthcare clients.", desc))
    for b in CV["siloam"]:
        f.append(Paragraph(b, bul, bulletText="•"))
    sec("SKILLS")
    for i in v["skills"]:
        a, b = CV["skills"][i]
        f.append(Paragraph(f"<b>{a}</b> | {b}", body))
        f.append(Spacer(1, 2))
    sec("EDUCATION")
    row("Bachelor of Engineering (S.T.), Civil Engineering", "2021")
    f.append(Paragraph("Universitas Pelita Harapan | Tangerang, Indonesia | GPA 3.53/4.00", body))
    sec("LANGUAGES")
    f.append(Paragraph("Indonesian (Native) | English (Professional Working Proficiency)", body))
    doc.build(f)
    return path


def cv_for(job):
    """Builds the variant if missing and copies it to a per-company file name. Returns repo-relative path."""
    from .scoring import family
    name = VARIANT_FOR[family(job)]
    src = OUT / "_variants" / f"Ryan-Hadi-CV-{name}.pdf"
    if not src.exists():
        build_variant(name)
    dst = OUT / f"Ryan-Hadi-CV-{slug(job['company'], 30).title().replace('--', '-')}.pdf"
    shutil.copy(src, dst)
    return str(dst.relative_to(ROOT)), name


def rebuild_variants():
    return [build_variant(n) for n in CV["variants"]]
