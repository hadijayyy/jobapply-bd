"""Apply sheet: every field of the real Greenhouse form, pre-answered from the profile, plus a cover letter PDF.

Claude cannot press Submit (reCAPTCHA, and Greenhouse's submit API needs the employer's key), so Ryan pastes
these answers and submits. Rules:
- Answers come from candidate.json / profile.md only.
- Anything only Ryan knows is marked RYAN and never guessed.
- Work authorization is answered literally and honestly: Indonesian citizen, needs sponsorship for SG/MY.
"""
import json
import re
import urllib.request

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from .kit import letter_of
from .store import CANDIDATE, ROOT, slug

C = CANDIDATE["contact"]
RYAN = "⚠ RYAN"
CURRENT_CO = "Sinar Mas Land (OneSmartServices)"
CURRENT_TITLE = "Business Development Manager, B2B Partnerships"

# (label regex, answer). First match wins. {country} = the posting's country.
RULES = [
    (r"^first name|preferred first name|name you.d prefer", "Ryan"),
    (r"preferred last name|^last name", "Hadi"),
    (r"legal name", "(kosongkan, sama)"),
    (r"^email", C["email"]),
    (r"^phone", C["phone"]),
    (r"resume|^cv", "{cv}"),
    (r"cover letter", "{cover}"),
    (r"linkedin|personal website or blog", "https://" + C["linkedin"]),
    (r"^website", "(kosongkan)"),
    (r"current company|current or previous employer", CURRENT_CO),
    (r"current or previous job title", CURRENT_TITLE),
    (r"authorized to work in the country you reside", "Yes (warga negara Indonesia, tinggal di Indonesia)"),
    (r"retain your data|consent to okta using your data", RYAN + ": opsional (saran: Yes, supaya dipertimbangkan untuk role lain)"),
    (r"zip|postal", RYAN + ": kode pos rumah kamu"),
    (r"country where you currently reside|country of residence|country/region are you currently based|country.*reside", "Indonesia (kalau tidak ada: Other, lalu ketik Indonesia)"),
    (r"countries you anticipate working", "{country}"),
    (r"cities are you available", "Singapore, Jakarta"),
    (r"languages you speak fluently", "Bahasa Indonesia, English"),
    (r"how did you hear", "Halaman karier perusahaan (Careers page / Direct to Careers)"),
    (r"legally entitled to work in malaysia", "No (belum punya hak kerja di Malaysia, perlu sponsor)"),
    (r"singaporean or a permanent resident", "No"),
    (r"(eligible|authori[sz]ed|legally authori[sz]ed) to work in the (country|location)", "No (perlu sponsor visa untuk {country})"),
    (r"source of your right to work", "I do not currently have an unlimited right to work where this role is listed and will require sponsorship"),
    (r"sponsorship for a visa to remain in your current location", "No (literal: kamu warga Indonesia di Indonesia). Sponsor untuk Singapura sudah disebut di cover letter"),
    (r"sponsor|immigration", "Yes"),
    (r"remote location, do you plan to work remotely", "No, I intend to work from an office location."),
    (r"(previously|ever been|in the past).{0,40}(employed|worked|consulted)|currently an employee or contractor|presently employed by any company within|employee, intern", "No (sesuai CV; cek kalau pernah freelance/kontrak di sini)"),
    (r"employed by .{0,60}in the past", "No (sesuai CV; cek kalau pernah freelance/kontrak di sini)"),
    (r"previous employment type|previous google|if yes|employee.s name|how you know the employee", "(kosongkan kecuali jawaban sebelumnya Yes)"),
    (r"deloitte", "No, I am not a current/an ex-employee of Deloitte (or its Subsidiary companies)"),
    (r"years of (work )?experience .*cybersecurity", RYAN + ": tidak wajib. Jujurnya 0 tahun di software security (smart CCTV = security fisik). Saran: kosongkan"),
    (r"years of selling experience .*saas or security", "0-1 Years (jujur: belum jual SaaS/security software)"),
    (r"family members|personal relationship", RYAN + ": ada kenalan/keluarga di perusahaan ini? (default No)"),
    (r"outside business activit", RYAN + ": ada side business/advisory? (default No)"),
    (r"employment agreements|post-employment restrictions", RYAN + ": cek kontrak Sinar Mas soal non-compete/non-solicit"),
    (r"accessible and inclusive|accommodat", "(kosongkan)"),
    (r"certify that the information", "Yes"),
    (r"privacy|personal data|consent to|acknowledge|retain your data", "Yes / Acknowledge (wajib untuk lanjut)"),
    (r"whatsapp|text/sms", RYAN + ": preferensi (saran: Yes supaya cepat dihubungi)"),
    (r"email me about other job openings", RYAN + ": preferensi (saran: No)"),
    (r"gender", "Prefer not to disclose"),
]


def form(job):
    tok = job["source"].split(":", 1)[1]
    m = re.search(r"gh_jid=(\d+)|/jobs/(\d+)|/detail/(\d+)", job["url"])
    jid = next(g for g in m.groups() if g)
    with urllib.request.urlopen(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{jid}?questions=true", timeout=25) as r:
        d = json.load(r)
    return d, f"https://job-boards.greenhouse.io/{tok}/jobs/{jid}"


def country(job):
    loc = job["location"] + " " + job["title"] + " " + job.get("desc", "")[:3000]
    if re.search(r"kuala lumpur|malaysia", job["location"], re.I):
        return "Malaysia"
    if re.search(r"singapore", loc, re.I):
        return "Singapore"
    return "Indonesia"


def answer(label, job, cv, cover):
    for rx, ans in RULES:
        if re.search(rx, label, re.I):
            return ans.format(cv=cv, cover=cover, country=country(job))
    return RYAN + ": pertanyaan baru, belum ada aturan"


def cover_pdf(job):
    text = letter_of((ROOT / job["kit"]).read_text())
    path = ROOT / "out" / "cover" / f"Ryan-Hadi-Cover-Letter-{slug(job['company'], 24).title()}-{job['id']}.pdf"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = ParagraphStyle("b", fontName="Helvetica", fontSize=10.5, leading=14.5)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=22 * mm,
                            bottomMargin=20 * mm, title="Ryan Hadi Cover Letter", author="Ryan Hadi")
    f = []
    for para in text.split("\n\n"):
        f += [Paragraph(para.replace("\n", "<br/>"), body), Spacer(1, 8)]
    doc.build(f)
    return str(path.relative_to(ROOT))


def build(jobs):
    L = ["# Apply sheet", "",
         "Claude tidak bisa klik Submit (reCAPTCHA). Buka link, upload file, copy jawaban, cek, Submit. "
         "Lalu bilang \"udah apply <nama>\" supaya tracker + follow-up diupdate.", "",
         f"Baris **{RYAN}** = hanya kamu yang tahu, aku tidak menebak. Bagian EEO/demografi: pilih \"decline / prefer not to say\".", ""]
    for i, j in enumerate(jobs, 1):
        d, link = form(j)
        cover = cover_pdf(j)
        a = j.get("ats") or {}
        L += [f"## {i}. {j['company']} | {j['title']}", "",
              f"- **Apply:** {link}",
              f"- **Upload CV:** `{j['cv']}` (ATS {a.get('after', '-')})",
              f"- **Upload cover letter:** `{cover}`",
              f"- Lokasi: {j['location']} | Flag: {'; '.join(j['flags']) or '-'}", "",
              "| Field | Wajib | Jawaban |", "|---|---|---|"]
        for q in d.get("questions", []):
            lab = re.sub(r"\s+", " ", q["label"]).strip()
            ans = answer(lab, j, f"upload {j['cv']}", f"upload {cover}")
            L.append(f"| {lab[:120]} | {'ya' if q['required'] else ''} | {ans} |")
        for k, lbl in (("location_questions", "Lokasi (autocomplete)"), ("compliance", "EEO / compliance"),
                       ("demographic_questions", "Demografi")):
            if d.get(k):
                L.append(f"| {lbl} | | {'Jakarta, Indonesia' if k == 'location_questions' else 'Decline / prefer not to say'} |")
        L.append("")
    p = ROOT / "out" / "APPLY-SHEET.md"
    p.write_text("\n".join(L) + "\n")
    return p
