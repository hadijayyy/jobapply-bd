#!/usr/bin/env python3
"""Generate 3 ATS-safe CV variants for Ryan Hadi from the master CV text.

Only reorders existing bullets and re-orders existing summary sentences.
No new claims, numbers, or titles are introduced. Facts come from profile.md.
Output: job-search/cv/Ryan-Hadi-CV-<variant>.pdf
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER

OUT = Path(__file__).parent / "cv"
OUT.mkdir(exist_ok=True)

NAME = "RYAN HADI"
HEADLINE = "Business Development Manager | B2B Sales | Channel Partnerships"
CONTACT = "Jakarta, Indonesia | +62 821 9997 5090 | ryanhadi.career@gmail.com | linkedin.com/in/ryanhadi"

S = {  # summary sentences, all from the master CV
 "years": "Business Development Manager with 5+ years of full-cycle B2B sales and channel partnerships in enterprise IT and corporate healthcare.",
 "years_ch": "Business Development Manager with 5+ years of channel partnerships and full-cycle B2B sales in enterprise IT and corporate healthcare.",
 "deals": "Closed IDR 10B+ across eight enterprise IT deals, exceeding 2025 quota by 15%+, and delivered 120%+ of new-business target in corporate healthcare.",
 "ai": "Builds AI-powered sales workflows that tripled prospecting capacity and doubled discovery meetings.",
 "ent": "Runs consultative, multi-stakeholder deals end to end and manages a 20-partner channel program.",
 "ch": "Manages a 20-partner channel program and grew partner-sourced pipeline 25% in 12 months.",
 "target": "Targeting B2B partnerships and sales roles in technology and SaaS across APAC.",
}
B = {  # Sinar Mas Land bullets (verbatim from master CV)
 "deals": "Closed IDR 10B+ in total contract value across eight enterprise deals (avg. IDR 1.25B+ per deal) for OneSmartServices’ smart CCTV and network infrastructure solutions, averaging 100%+ of annual quota and exceeding 2025 quota by 15%+.",
 "ai": "Built AI-powered workflows (ChatGPT, Claude) for prospect research, outreach, and proposal drafting, saving 10+ hours per week. Tripled monthly prospect research volume, doubled discovery meetings, and cut proposal turnaround from several days to one.",
 "pipe": "Grew qualified partner-sourced pipeline by 25% (IDR 2B to IDR 2.5B) in 12 months by launching quarterly business reviews and joint sales plans with 20 active channel partners.",
 "team": "Led a three-person BD team and signed four new channel partner agreements by running Legal, Finance, and Operations reviews in parallel, cutting average proposal-to-signature time from 60 to 48 days.",
}
SILOAM = [
 "Exceeded both personal and team new-business targets by 20%+. Built and ran an individual outbound pipeline in HubSpot targeting HR and procurement (avg. 20 qualified prospects and 10 discovery meetings per month), contributing to 12 new corporate accounts and IDR 750M in first-year team revenue.",
 "Co-managed a 20-account corporate portfolio with a senior account manager, growing revenue 15% YoY (IDR 1B to IDR 1.15B) by mapping gaps in employee health coverage and cross-selling inpatient and outpatient services.",
 "Owned the commercial side of medical check-up programs for 1,500 employees across 12 corporate clients, working with Operations on delivery; renewed 10 of 12 eligible contracts (83%) and generated IDR 150M in follow-up service revenue.",
]
SKILLS = [
 ("B2B Sales & Account Growth", "Outbound Prospecting, Discovery, Consultative Selling, Multi-stakeholder Negotiation, Account Management, Cross-Selling, Renewals"),
 ("Channel Partnerships", "Partner Recruitment & Onboarding, Joint Sales Planning, Quarterly Business Reviews, Pipeline Management"),
 ("Sales Automation & Analytics", "AI Workflows (ChatGPT, Claude), Prompt Engineering, Power BI, HubSpot CRM, Advanced Excel"),
 ("Commercial Strategy", "Market Sizing, Feasibility Analysis, Business Case Development, Executive Presentations"),
]
VARIANTS = {
 "Enterprise": dict(summary=["years", "deals", "ai", "ent", "target"], bullets=["deals", "ai", "pipe", "team"], skills=[0, 1, 2, 3]),
 "Channel":    dict(summary=["years_ch", "ch", "deals", "ai", "target"], bullets=["pipe", "team", "deals", "ai"], skills=[1, 0, 2, 3]),
 "AI-Sales":   dict(summary=["years", "ai", "deals", "ent", "target"], bullets=["ai", "deals", "pipe", "team"], skills=[2, 0, 1, 3]),
}


def build(name, v):
    st = lambda n, **k: ParagraphStyle(n, fontName=k.pop("font", "Helvetica"), **k)
    title = st("t", fontSize=19, leading=22, alignment=TA_CENTER, font="Helvetica-Bold")
    sub = st("s", fontSize=10, leading=12, alignment=TA_CENTER, font="Helvetica-Bold")
    con = st("c", fontSize=8.5, leading=11, alignment=TA_CENTER)
    h = st("h", fontSize=10.5, leading=13, font="Helvetica-Bold", spaceBefore=7, spaceAfter=1)
    body = st("b", fontSize=9, leading=11.5)
    bul = st("bl", fontSize=9, leading=11.5, leftIndent=9, bulletIndent=0)
    role = st("r", fontSize=9.5, leading=12, font="Helvetica-Bold")
    org = st("o", fontSize=9, leading=11.5)
    desc = st("d", fontSize=9, leading=11.5, font="Helvetica-Oblique")

    doc = SimpleDocTemplate(str(OUT / f"Ryan-Hadi-CV-{name}.pdf"), pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Ryan Hadi CV", author="Ryan Hadi")
    f = [Paragraph(NAME, title), Paragraph(HEADLINE, sub), Paragraph(CONTACT, con)]

    def sec(t):
        f.append(Paragraph(t, h)); f.append(HRFlowable(width="100%", thickness=0.8, color="black", spaceAfter=3))

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
    f.append(Paragraph("Sinar Mas Land (OneSmartServices) | Jakarta, Indonesia", org))
    f.append(Paragraph("IT solutions unit of Sinar Mas Land (developer of BSD City), delivering cloud, managed services, and smart city infrastructure to 110+ corporate clients.", desc))
    for k in v["bullets"]:
        f.append(Paragraph(B[k], bul, bulletText="•"))
    f.append(Spacer(1, 4))
    row("Business Development Executive", "Apr 2021 - Mar 2023")
    f.append(Paragraph("Siloam Hospitals Group | Jakarta, Indonesia", org))
    f.append(Paragraph("Indonesian private hospital network serving inpatient, outpatient, and corporate healthcare clients.", desc))
    for b in SILOAM:
        f.append(Paragraph(b, bul, bulletText="•"))
    sec("SKILLS")
    for i in v["skills"]:
        a, b = SKILLS[i]
        f.append(Paragraph(f"<b>{a}</b> | {b}", body)); f.append(Spacer(1, 2))
    sec("EDUCATION")
    row("Bachelor of Engineering (S.T.), Civil Engineering", "2021")
    f.append(Paragraph("Universitas Pelita Harapan | Tangerang, Indonesia | GPA 3.53/4.00", org))
    sec("LANGUAGES")
    f.append(Paragraph("Indonesian (Native) | English (Professional Working Proficiency)", body))
    doc.build(f)


if __name__ == "__main__":
    for n, v in VARIANTS.items():
        build(n, v)
        print("built", n)
