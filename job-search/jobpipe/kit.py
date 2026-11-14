"""Stage 3b: application kit = cover letter + form answers + Gmail draft block. Includes the lint gate.

The script writes the skeleton and picks the proof points. The role-specific sentences (HOOK, GAP, ASK)
need to be read from the job description, so they are left as {{...}} for Claude to fill. lint() refuses
a kit until they are filled and every number in the letter traces back to candidate.json.
"""
import re

from .cv import cv_for
from .scoring import family
from .store import CANDIDATE, CONFIG, ROOT, slug

P = CANDIDATE["proofs"]
PROOFS = {"channel": ["partners", "signing"], "enterprise": ["deals", "siloam"], "ai": ["siloam", "ai"]}
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}|\[METRIC\?\]|TODO|XXX", re.I)
ATS_HINTS = [("greenhouse.io", "Greenhouse"), ("ashbyhq.com", "Ashby"), ("lever.co", "Lever"), ("myworkdayjobs", "Workday"),
             ("comeet.com", "Comeet"), ("smartrecruiters.com", "SmartRecruiters"), ("rippling.com", "Rippling"),
             ("teamtailor.com", "Teamtailor"), ("workable.com", "Workable")]
AGGREGATORS = re.compile(r"jobleads|linkedin\.com|indeed|bebee|jobgether|remoterocketship|remotive|himalayas|remoteok|weworkremotely", re.I)


def apply_route(job):
    """(route, note). Forms with captcha are manual. A public recruiting email becomes a Gmail draft."""
    emails = [e for e in re.findall(CONFIG["email_regex"], job.get("desc", ""))
              if not re.search(r"noreply|no-reply|example\.", e, re.I)]
    if emails:
        return "email", f"Email rekrutmen publik di JD: {emails[0]}. Buat draft Gmail, jangan kirim otomatis."
    for key, name in ATS_HINTS:
        if key in job["url"]:
            return "form", f"{name}. Form ber-captcha, submit manual."
    if AGGREGATORS.search(job["url"]):
        return "find_official", "Link agregator. Cari halaman apply resmi perusahaan dulu."
    return "form", "Halaman karier perusahaan. Submit manual."


def skeleton(job):
    fam = family(job)
    p1, p2 = (P[k] for k in PROOFS[fam])
    return "\n".join([
        f"Hello {job['company']} team,", "",
        "{{HOOK}} I am a Business Development Manager in Jakarta with five years of B2B sales and channel "
        "partnerships in enterprise IT and corporate healthcare.", "",
        f"{p1}. {p2}.", "",
        "{{GAP}}", "",
        "{{ASK}} My CV is attached.", "",
        "Best regards,", CANDIDATE["signature"]])


def build(job):
    """Creates CV + kit skeleton. Returns paths. Never overwrites a kit that is already filled."""
    cv_path, variant = cv_for(job)
    kit_path = ROOT / "out" / "kits" / f"{slug(job['company'], 30)}-{job['id']}.md"
    route, note = apply_route(job)
    if kit_path.exists() and not PLACEHOLDER.search(kit_path.read_text()):
        job["cv"], job["kit"] = cv_path, str(kit_path.relative_to(ROOT))
        return job["kit"], cv_path
    desc = (job.get("desc") or "(kosong: buka halaman asli lalu tempel ringkasannya di sini)")[:1800]
    notes = "; ".join(job["blockers"] + job["flags"]) or "tidak ada"
    md = f"""# {job['company']} | {job['title']}
- ID: {job['id']} | Tier: {job['tier']} | Skor: {job['score']} | CV: {cv_path} ({variant})
- Apply: {job['url']}
- Rute: {route}. {note}
- Lokasi: {job.get('location') or 'tidak disebutkan'} | Gaji: {job.get('comp') or 'tidak disebutkan'} | Diposting: {job.get('posted') or 'tidak disebutkan'}
- Catatan/flag: {notes}

## Cover letter
Ganti tiga placeholder di bawah: HOOK (1 kalimat spesifik dari JD), GAP (jujur soal gap, atau hapus paragrafnya), ASK (1 kalimat ajakan). Jangan ubah paragraf bukti.

{skeleton(job)}

## Gmail draft (hanya jika Rute = email)
- To: (alamat dari JD)
- Subject: Application: {job['title']} | Ryan Hadi
- Body: cover letter di atas. Lampirkan {cv_path}.

## Form answers (dari candidate.json)
{chr(10).join('- ' + a for a in CANDIDATE['form_answers'])}

## Ringkasan JD (referensi, hapus bagian ini kalau perlu)
{desc}
"""
    kit_path.write_text(md)
    job["cv"], job["kit"] = cv_path, str(kit_path.relative_to(ROOT))
    return job["kit"], cv_path


def letter_of(md):
    m = re.search(r"## Cover letter.*?\n(Hello .*?)\n\n## ", md, re.S)
    return m[1] if m else ""


def lint(job):
    """Returns a list of problems. Empty list means the kit may move to 'ready'."""
    if not job.get("kit"):
        return ["belum ada kit"]
    md = (ROOT / job["kit"]).read_text()
    text = letter_of(md)
    if not text:
        return ["cover letter tidak ditemukan"]
    problems = []
    if PLACEHOLDER.search(md):
        problems.append("masih ada placeholder ({{HOOK}}/{{GAP}}/{{ASK}}/TODO/[METRIC?])")
    if re.search(CONFIG["banned_phrases"], text, re.I):
        problems.append("ada em dash atau klise terlarang")
    lo, hi = CONFIG["cover_letter_words"]
    words = len(re.sub(r"\{\{[A-Z_]+\}\}", "", text).split())
    if not lo <= words <= hi:
        problems.append(f"panjang {words} kata, harus {lo}-{hi}")
    allowed = " ".join(P.values()) + " " + CANDIDATE["signature"] + " " + " ".join(CANDIDATE["form_answers"] + CANDIDATE["facts"])
    allowed_nums = set(re.findall(r"\d[\d.,]*[A-Za-z%+]*", allowed)) | {"5"}
    body = text.replace(job["company"], "")  # digits inside a company name are not claims
    for num in set(re.findall(r"\d[\d.,]*[A-Za-z%+]*", body)):
        if num.rstrip(".,") not in {a.rstrip(".,") for a in allowed_nums}:
            problems.append(f"angka '{num}' tidak ada di candidate.json (jangan mengarang)")
    if not (ROOT / job["cv"]).exists():
        problems.append("file CV hilang")
    return problems
