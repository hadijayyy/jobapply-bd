"""Auto-apply for Greenhouse forms: plan (answers per field) -> fill + submit in headless Chromium -> log.

plan()   reads the real form from the public board API and resolves every field from apply_profile.json
         and data/answers.json. A required field without an answer blocks the job; nothing is guessed.
submit() hands the plan to gh_submit.js (Playwright). A job is marked applied only when Greenhouse shows
         its confirmation page. CAPTCHA challenges are never worked around: the job is reported as blocked.
"""
import json
import re
import subprocess
import urllib.request

from . import answers
from .store import CONFIG, ROOT, today

CFG = CONFIG["autoapply"]
OUT = ROOT / "out" / "autoapply"
LOG = ROOT / "data" / "apply_log.jsonl"
JS = ROOT / "jobpipe" / "gh_submit.js"
STANDARD = {"first_name", "last_name", "preferred_name", "email", "phone"}


def gh_ref(job):
    """(board token, job id) or None when the job is not a Greenhouse posting."""
    if not job["source"].startswith("GH:"):
        return None
    m = re.search(r"gh_jid=(\d+)|/jobs/(\d+)|/detail/(\d+)|/job/(\d+)", job["url"])
    return (job["source"].split(":", 1)[1], next(g for g in m.groups() if g)) if m else None


def fetch_form(job):
    tok, jid = gh_ref(job)
    with urllib.request.urlopen(f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs/{jid}?questions=true", timeout=25) as r:
        return json.load(r), f"https://job-boards.greenhouse.io/embed/job_app?for={tok}&token={jid}"


def plan(job):
    """Returns the plan dict. plan['blocked'] lists required questions that have no answer."""
    form, url = fetch_form(job)
    cv = ROOT / job["cv"] if job.get("cv") else None
    cover = ROOT / "out" / "cover" / f"Ryan-Hadi-Cover-Letter-{re.sub(r'[^a-z0-9]+', '-', job['company'].lower()).strip('-')[:24].title()}-{job['id']}.pdf"
    cover = cover if cover.exists() else None
    fields, blocked, skipped, prior = [], [], [], {}
    P = answers.PROFILE

    def block(label, name, why, options=()):
        blocked.append({"label": answers.norm(label)[:300], "field": name, "why": why, "options": list(options)[:40]})

    for q in form.get("questions", []):
        label, req = q["label"], q["required"]
        names = {f["name"]: f for f in q["fields"]}
        if "resume" in names:
            if cv and cv.exists():
                fields.append({"name": "resume", "kind": "file", "label": "Resume/CV", "value": str(cv)})
            elif req:
                block(label, "resume", "CV tailored belum dibuat (jalankan tailor)")
            continue
        if "cover_letter" in names:
            if cover:
                fields.append({"name": "cover_letter", "kind": "file", "label": "Cover Letter", "value": str(cover)})
            elif req:
                block(label, "cover_letter", "cover letter wajib tapi belum ada (buat kit + lint)")
            continue
        for f in q["fields"]:
            name, typ = f["name"], f["type"]
            opts = [v["label"] for v in f.get("values", [])]
            if typ == "input_hidden":
                continue
            if name in STANDARD:
                val = {"first_name": P["first_name"], "last_name": P["last_name"], "preferred_name": P["first_name"],
                       "email": P["email"], "phone": P["phone_national"]}[name]
                fields.append({"name": name, "kind": "phone" if name == "phone" else "text", "label": label, "value": val})
                continue
            kind, val = answers.resolve(label, opts, job, {}, req, prior)
            if kind == "skip" and req:
                kind, val = "unresolved", f"wajib tapi aturan bilang lewati ({val})"
            if kind == "unresolved":
                (block if req else lambda *a: skipped.append({"label": answers.norm(label)[:160], "why": val}))(label, name, val, opts)
                continue
            if kind == "skip":
                skipped.append({"label": answers.norm(label)[:160], "why": val})
                continue
            if typ in ("multi_value_single_select", "multi_value_multi_select"):
                multi = typ.endswith("multi_select")
                picked = answers.choose(opts, val if kind == "pick" else ["^" + re.escape(val) + "$"], multi)
                if not picked:
                    (block if req else lambda *a: skipped.append({"label": answers.norm(label)[:160], "why": "opsi tidak cocok"}))(
                        label, name, f"tidak ada opsi yang cocok dengan jawaban {val}", opts)
                    continue
                if re.search(r"country", label, re.I) and re.match(r"other", picked[0], re.I):
                    prior["country_other"] = True
                ids = {v["label"]: v["value"] for v in f["values"]}
                fields.append({"name": name, "kind": "multi" if multi else "select", "label": answers.norm(label)[:200],
                               "value": picked, "value_ids": [ids[p] for p in picked]})
            else:
                if kind == "pick":  # free-text field but the rule only knows options
                    text = "Yes" if val == answers.YES else "No" if val == answers.NO else None
                    if text is None:
                        (block if req else lambda *a: None)(label, name, "field teks, aturan hanya punya opsi")
                        continue
                    val = text
                fields.append({"name": name, "kind": "textarea" if typ == "textarea" else "text",
                               "label": answers.norm(label)[:200], "value": val})
    # Education block: Greenhouse renders it only as school/degree comboboxes; fill it only when the job requires it.
    if form.get("education") == "education_required":
        ed = P.get("education") or {}
        if ed.get("school_option") and ed.get("degree_option"):
            fields.append({"name": "school--0", "kind": "select", "label": "School", "value": [ed["school_option"]], "value_ids": []})
            fields.append({"name": "degree--0", "kind": "select", "label": "Degree", "value": [ed["degree_option"]], "value_ids": []})
        else:
            block("Education (school, degree)", "education", "pendidikan wajib, profil belum punya school_option/degree_option")
    # Demographic survey: only answered when the form makes it mandatory, and then always "decline to answer".
    demo = form.get("demographic_questions") or {}
    answered_demo = False
    for q in demo.get("questions", []):
        if not q.get("required"):
            continue
        dec = [o["label"] for o in q.get("answer_options", []) if o.get("decline_to_answer")]
        if not dec:
            block(q["label"], str(q["id"]), "survei demografi wajib tanpa opsi 'tidak menjawab'", [o["label"] for o in q["answer_options"]])
            continue
        fields.append({"name": str(q["id"]), "kind": "select", "label": answers.norm(q["label"]), "value": dec[:1], "value_ids": []})
        answered_demo = True
    for dc in form.get("data_compliance") or []:
        if dc.get("requires_processing_consent") or dc.get("requires_consent"):
            fields.append({"name": "gdpr_processing_consent_given_1", "kind": "check", "label": "Persetujuan pemrosesan data (wajib untuk melamar)", "value": True})
        if answered_demo and dc.get("demographic_data_consent_applies"):
            fields.append({"name": "gdpr_demographic_data_consent_given_1", "kind": "check", "label": "Persetujuan data demografi (jawaban: tidak menjawab)", "value": True})
    out = OUT / job["id"]
    return {"id": job["id"], "company": job["company"], "title": job["title"], "url": url, "out_dir": str(out),
            "location_search": P["location_search"] if form.get("location_questions") else None,
            "phone_country": P["phone_country"], "fields": fields, "blocked": blocked, "skipped": skipped,
            "code_wait_s": CFG.get("code_wait_s", 0)}


def write_plan(p):
    out = OUT / p["id"]
    out.mkdir(parents=True, exist_ok=True)
    path = out / "plan.json"
    path.write_text(json.dumps(p, indent=1, ensure_ascii=False) + "\n")
    return path


def submit(p, dry_run=False):
    """Runs the browser. Returns {"status": submitted|filled|validation|captcha|needs_code|error, ...}."""
    path = write_plan(p)
    cmd = ["node", str(JS), str(path)] + (["--dry-run"] if dry_run else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=CFG.get("timeout_s", 240) + p["code_wait_s"])
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        res = {"status": "error", "detail": f"{type(e).__name__}: {str(e)[:300]}"}
    res.update(id=p["id"], company=p["company"], title=p["title"], date=today(), dry_run=dry_run)
    if not dry_run:
        with LOG.open("a") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
    return res


def eligible(store):
    """Jobs the bot may submit: Greenhouse, tier A/B, not yet applied. Best score first.
    A posting counts as live when the board API still serves its form (checked in plan())."""
    tiers = set(CFG["tiers"])
    jobs = [j for j in store.by_status("new", "verified", "kit_draft", "ready") if j["tier"] in tiers and gh_ref(j)
            and (j["score"] or 0) >= CFG["min_score"]]
    return sorted(jobs, key=lambda j: (j["tier"], -(j["score"] or 0)))


def pending_md(blocked_jobs):
    """out/autoapply/PENDING.md: every question that stopped a submission, for Ryan (profile) or Claude (draft)."""
    L = ["# Auto-apply: pertanyaan yang menahan lamaran", "",
         "Isi `apply_profile.json` untuk yang bertanda profil, atau simpan jawaban dengan", "",
         "    python3 job-search/pipeline.py autoapply answer <id> <field> \"jawaban\" [--all-jobs]", ""]
    for j, p in blocked_jobs:
        L += [f"## {j['company']} | {j['title']} (`{j['id']}`)", ""]
        for b in p["blocked"]:
            opts = f" Opsi: {' / '.join(b['options'][:12])}" if b["options"] else ""
            L.append(f"- `{b['field']}` **{b['label'][:200]}**: {b['why']}.{opts}")
        L.append("")
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "PENDING.md").write_text("\n".join(L) + "\n")
    return OUT / "PENDING.md"
