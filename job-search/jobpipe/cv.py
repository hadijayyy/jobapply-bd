"""Stage 3a: ATS-safe CV PDFs tailored per job description.

Rules (do not relax):
- Facts come only from candidate.json. Tailoring = choosing, ordering and wording, never new claims.
- Skills may only use lexicon phrases whose evidence is "yes" (see ats.py).
- The ATS score is measured on the text extracted from the rendered PDF, not on the source strings.
"""
import re
from pathlib import Path

from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from . import ats
from .store import CANDIDATE, ROOT, slug

CV = CANDIDATE["cv"]
OUT = ROOT / "out" / "cv"
VARIANT_FOR = {"enterprise": "Enterprise", "channel": "Channel", "ai": "AI-Sales"}

# Same facts as the master CV, worded so the matching keyword is explicit. Each line names its source bullet.
BULLETS = {
    "deals": "Closed IDR 10B+ in total contract value across eight enterprise deals (avg. IDR 1.25B+ per deal) for "
             "OneSmartServices' smart CCTV and network infrastructure solutions through full-cycle, consultative sales, "
             "averaging 100%+ of annual quota and exceeding 2025 quota by 15%+.",
    "ai": CV["bullets"]["ai"],
    "pipe": CV["bullets"]["pipe"],
    "team": "Led a three-person BD team and signed four new channel partner agreements by running cross-functional Legal, "
            "Finance, and Operations reviews in parallel, cutting average proposal-to-signature time from 60 to 48 days.",
}
SILOAM = {
    "newbiz": "Exceeded both personal and team new-business targets by 20%+. Built and ran an individual outbound "
              "prospecting pipeline in HubSpot targeting HR and procurement (avg. 20 qualified prospects and 10 discovery "
              "meetings per month), contributing to 12 new corporate accounts and IDR 750M in first-year team revenue.",
    "portfolio": CV["siloam"][1],
    "renew": CV["siloam"][2],
}

SALES = ["business development", "B2B sales", "enterprise sales", "full-cycle sales", "new business", "closing",
         "outbound prospecting", "pipeline generation", "pipeline management", "discovery", "consultative selling",
         "negotiation", "multi-stakeholder", "executive engagement", "account management", "cross-sell",
         "renewals / retention", "quota attainment", "proposals / RFP", "business case", "market sizing"]
PARTNER = ["channel partnerships", "partner management", "partner recruitment", "co-selling / joint plans", "QBR"]
DOMAIN = ["software sales", "cloud", "IT infrastructure", "healthcare"]  # "cloud" phrase already says Managed Services
SOFT = [c for c, k, *_ in ats.LEX if k == "soft"]
TOOLS_LINE = "Salesforce & HubSpot CRM, Power BI, Advanced Excel, AI Sales Workflows (ChatGPT, Claude), Prompt Engineering"
DEFAULT_SALES = ["full-cycle sales", "outbound prospecting", "discovery", "consultative selling", "negotiation",
                 "account management", "cross-sell", "renewals / retention"]
DEFAULT_PARTNER = PARTNER
DEFAULT_SOFT = ["cross-functional collaboration", "communication", "relationship building", "leadership"]


def _ok(c):
    return ats.TERM[c][2] == "yes"


def _pick(group, wanted, defaults, cap):
    """JD-matched terms from the group first (in JD weight order), then defaults, deduped, capped."""
    out = [c for c in wanted if c in group and _ok(c)]
    out += [c for c in defaults if c not in out]
    return [ats.TERM[c][3] for c in out[:cap]]


def _market(jd):
    if re.search(r"indonesia|jakarta", jd, re.I):
        return "covering Indonesia and Southeast Asia" if re.search(r"southeast asia|asean|\bsea\b", jd, re.I) else "covering Indonesia"
    if re.search(r"southeast asia|asean|\bsea\b", jd, re.I):
        return "in Southeast Asia"
    return "across APAC"


def spec_for(job):
    """Builds the content of one tailored CV. Returns (spec, change_log)."""
    jd, title = job.get("desc", ""), job["title"]
    want = ats.usable_terms(jd, title)
    core = ats.role_title_core(title)
    partner_role = bool(re.search(r"partner|channel|alliance|distribution", title, re.I))
    log = []

    focus = "Channel & Partner Management | B2B Sales" if partner_role else "Enterprise B2B Sales | Channel Partnerships"
    headline = f"Business Development Manager | {focus}"

    first = (CV["summary"]["years_ch"] if partner_role else CV["summary"]["years"])
    middle = [CV["summary"]["deals"]]
    if partner_role:
        middle.insert(0, CV["summary"]["ch"])
    middle.append("Runs consultative, multi-stakeholder deals end to end, working cross-functionally with Legal, Finance, "
                  "and Operations.")
    if "AI tools" in want or not partner_role:
        middle.append(CV["summary"]["ai"])
    target = f"Targeting {core} roles {_market(jd)}."
    summary = " ".join([first] + middle + [target])
    log.append(f'Summary diakhiri "{target}" agar judul role JD ({core}) terbaca ATS. Ini target, bukan klaim jabatan.')

    def rank(text):
        return -sum(2 if ats.TERM[c][1].search(text) else 0 for c in want)

    order = sorted(BULLETS, key=lambda k: (rank(BULLETS[k]), list(BULLETS).index(k)))
    if partner_role:
        order = ["pipe", "team"] + [k for k in order if k not in ("pipe", "team")]
    sil = sorted(SILOAM, key=lambda k: (rank(SILOAM[k]), list(SILOAM).index(k)))
    log.append("Urutan bullet Sinar Mas: " + ", ".join(order) + " | Siloam: " + ", ".join(sil))

    skills = [
        ("B2B Sales" if not partner_role else "Sales & Account Growth",
         ", ".join(_pick(SALES, want, DEFAULT_SALES, max(9, min(13, sum(c in SALES for c in want)))))),
        ("Channel Partnerships", ", ".join(_pick(PARTNER, want, DEFAULT_PARTNER, 5))),
        ("Tools & Analytics", TOOLS_LINE),
        ("Solutions & Industries", ", ".join(_pick(DOMAIN, want, DOMAIN, 5))),
        ("Core Strengths", ", ".join(_pick(SOFT, want, DEFAULT_SOFT, 7))),
    ]
    if partner_role:
        skills[0], skills[1] = skills[1], skills[0]
    log.append("Skills disusun dari keyword JD yang punya bukti (evidence=yes); Salesforce ditambahkan (dikonfirmasi Ryan 14 Nov 2026).")
    return {"headline": headline, "summary": summary, "bullets": [BULLETS[k] for k in order],
            "siloam": [SILOAM[k] for k in sil], "skills": skills}, log


def render(spec, path):
    c = CANDIDATE["contact"]
    st = lambda n, **k: ParagraphStyle(n, fontName=k.pop("font", "Helvetica"), **k)
    title = st("t", fontSize=19, leading=22, alignment=TA_CENTER, font="Helvetica-Bold")
    sub = st("s", fontSize=10, leading=12, alignment=TA_CENTER, font="Helvetica-Bold")
    con = st("c", fontSize=8.5, leading=11, alignment=TA_CENTER)
    h = st("h", fontSize=10.5, leading=13, font="Helvetica-Bold", spaceBefore=6, spaceAfter=1)
    body = st("b", fontSize=9, leading=11.3)
    bul = st("bl", fontSize=9, leading=11.3, leftIndent=9, bulletIndent=0)
    role = st("r", fontSize=9.5, leading=12, font="Helvetica-Bold")
    desc = st("d", fontSize=9, leading=11.3, font="Helvetica-Oblique")
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=11 * mm,
                            bottomMargin=10 * mm, title="Ryan Hadi CV", author="Ryan Hadi")
    f = [Paragraph(CANDIDATE["name"].upper(), title), Paragraph(spec["headline"], sub),
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
    f.append(Paragraph(spec["summary"], body))
    sec("EXPERIENCE")
    row("Business Development Manager, B2B Partnerships", "Mar 2023 - Present")
    f.append(Paragraph("Sinar Mas Land (OneSmartServices) | Jakarta, Indonesia", body))
    f.append(Paragraph("IT solutions unit of Sinar Mas Land (developer of BSD City), delivering cloud, managed services, and smart city infrastructure to 110+ corporate clients.", desc))
    for b in spec["bullets"]:
        f.append(Paragraph(b, bul, bulletText="•"))
    f.append(Spacer(1, 4))
    row("Business Development Executive", "Apr 2021 - Mar 2023")
    f.append(Paragraph("Siloam Hospitals Group | Jakarta, Indonesia", body))
    f.append(Paragraph("Indonesian private hospital network serving inpatient, outpatient, and corporate healthcare clients.", desc))
    for b in spec["siloam"]:
        f.append(Paragraph(b, bul, bulletText="•"))
    sec("SKILLS")
    for a, b in spec["skills"]:
        f.append(Paragraph(f"<b>{a}</b> | {b}", body))
        f.append(Spacer(1, 2))
    sec("EDUCATION")
    row("Bachelor of Engineering (S.T.), Civil Engineering", "2021")
    f.append(Paragraph("Universitas Pelita Harapan | Tangerang, Indonesia | GPA 3.53/4.00", body))
    sec("LANGUAGES")
    f.append(Paragraph("Indonesian (Native) | English (Professional Working Proficiency)", body))
    doc.build(f)
    return path


def pages(path):
    from pypdf import PdfReader
    return len(PdfReader(str(path)).pages)


def file_for(job):
    co = re.sub(r"-+", "-", slug(job["company"], 24).title())
    return OUT / f"Ryan-Hadi-CV-{co}-{job['id']}.pdf"


def tailor(job, master_text=None):
    """Renders the tailored CV, scores it on its own extracted text. Returns a result dict."""
    spec, log = spec_for(job)
    path = render(spec, file_for(job))
    text = ats.pdf_text(path)
    after, parts, buckets, core = ats.score(text, job.get("desc", ""), job["title"], job.get("years_required"))
    ceiling, *_ = ats.score(text, job.get("desc", ""), job["title"], job.get("years_required"), include_pending=True)
    before = ats.score(master_text, job.get("desc", ""), job["title"], job.get("years_required"))[0] if master_text else None
    return {"path": str(path.relative_to(ROOT)), "pages": pages(path), "before": before, "after": after,
            "if_pending_confirmed": ceiling, "parts": parts, "buckets": buckets, "core": core, "log": log}


def cv_for(job):
    """Back-compat for kit.py: tailored CV path + label."""
    r = tailor(job)
    job["cv"], job["ats"] = r["path"], {k: r[k] for k in ("after", "if_pending_confirmed", "parts")}
    return r["path"], f"tailored, ATS {r['after']}"


# ---- legacy fixed variants (kept for `pipeline.py rebuild-cv`) ----
def build_variant(name):
    v, S = CV["variants"][name], CV["summary"]
    spec = {"headline": CANDIDATE["headline"], "summary": " ".join(S[k] for k in v["summary"]),
            "bullets": [CV["bullets"][k] for k in v["bullets"]], "siloam": CV["siloam"],
            "skills": [tuple(CV["skills"][i]) for i in v["skills"]]}
    return render(spec, OUT / "_variants" / f"Ryan-Hadi-CV-{name}.pdf")


def rebuild_variants():
    return [build_variant(n) for n in CV["variants"]]
