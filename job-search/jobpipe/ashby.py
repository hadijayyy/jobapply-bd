"""Auto-apply for Ashby forms (jobs.ashbyhq.com): plan -> fill + submit in headless Chromium -> log.

Same rules as autoapply.py (Greenhouse):
- answers come only from apply_profile.json and data/answers.json via answers.resolve; a required field
  without an answer blocks the job, nothing is guessed
- every value is read back from the page before Submit; a mismatch cancels the submit
- a job is marked applied only when Ashby shows its success message
- CAPTCHA / spam checks are never worked around: the job is reported as blocked

    python3 -m jobpipe.ashby plan <id>
    python3 -m jobpipe.ashby run <id> [--dry-run]
"""
import json
import re
import subprocess
import sys
import urllib.request

from . import answers
from .store import ROOT, Store, export_tracker, today

OUT = ROOT / "out" / "autoapply"
LOG = ROOT / "data" / "apply_log.jsonl"
JS = ROOT / "jobpipe" / "ashby_submit.js"
GQL = ("query ApiJobPosting($organizationHostedJobsPageName: String!, $jobPostingId: String!) { jobPosting("
       "organizationHostedJobsPageName: $organizationHostedJobsPageName, jobPostingId: $jobPostingId) { id title "
       "applicationForm { sections { title fieldEntries { ... on FormFieldEntry { id field isRequired } } } } } }")


def ashby_ref(job):
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/([0-9a-f-]{36})", job["url"])
    return (m[1], m[2]) if m else None


def fetch_form(job):
    org, jid = ashby_ref(job)
    body = {"operationName": "ApiJobPosting", "query": GQL,
            "variables": {"organizationHostedJobsPageName": org, "jobPostingId": jid}}
    req = urllib.request.Request("https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobPosting",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
    d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    if d.get("errors") or not d.get("data", {}).get("jobPosting"):
        raise RuntimeError(f"form Ashby tidak terbaca: {d.get('errors')}")
    entries = [e for s in d["data"]["jobPosting"]["applicationForm"]["sections"] for e in s["fieldEntries"] if e.get("field")]
    return entries, f"https://jobs.ashbyhq.com/{org}/{jid}/application"


def plan(job):
    entries, url = fetch_form(job)
    P = answers.PROFILE
    cv = ROOT / job["cv"] if job.get("cv") else None
    fields, blocked, skipped, prior = [], [], [], {}

    def block(label, path, why, opts=()):
        blocked.append({"label": answers.norm(label)[:300], "field": path, "why": why, "options": list(opts)[:40]})

    for e in entries:
        f, req = e["field"], e["isRequired"]
        path, typ, label = f["path"], f["type"], f.get("title") or ""
        opts = [v["label"] for v in f.get("selectableValues") or []]
        if typ == "Boolean":
            opts = ["Yes", "No"]
        low = label.lower()
        std = None
        if path == "_systemfield_name":
            std = f"{P['first_name']} {P['last_name']}"
        elif path == "_systemfield_email" or typ == "Email":
            std = P["email"]
        elif typ == "Phone":
            std = P.get("phone_full") or ("+62 " + P["phone_national"])
        elif re.search(r"\b(legal )?first name\b", low):
            std = P["first_name"]
        elif re.search(r"\b(legal )?last name\b|surname|family name", low):
            std = P["last_name"]
        if std is not None:
            fields.append({"path": path, "kind": "text", "label": label, "value": std})
            continue
        if typ == "File":
            if path == "_systemfield_resume" or re.search(r"resume|\bcv\b", low):
                if cv and cv.exists():
                    fields.append({"path": path, "kind": "file", "label": label, "value": str(cv)})
                elif req:
                    block(label, path, "CV tailored belum dibuat")
            elif req:
                block(label, path, "file wajib selain CV (mis. cover letter)")
            continue
        if path == "_systemfield_location" or typ == "Location":
            fields.append({"path": path, "kind": "location", "label": label, "value": P.get("location_search", "Jakarta")})
            continue
        kind, val = answers.resolve(label, opts, job, {}, req, prior)
        if kind == "skip" and req:
            kind, val = "unresolved", f"wajib tapi aturan bilang lewati ({val})"
        if kind in ("unresolved", "skip"):
            if req:
                block(label, path, val, opts)
            else:
                skipped.append({"label": answers.norm(label)[:160], "why": val})
            continue
        if opts:
            multi = typ == "MultiValueSelect"
            picked = answers.choose(opts, val if kind == "pick" else ["^" + re.escape(val) + "$"], multi)
            if not picked:
                (block if req else lambda *a: skipped.append({"label": label[:160], "why": "opsi tidak cocok"}))(
                    label, path, f"tidak ada opsi yang cocok dengan jawaban {val}", opts)
                continue
            fields.append({"path": path, "kind": "boolean" if typ == "Boolean" else ("multi" if multi else "select"),
                           "label": label, "value": picked})
        else:
            if kind == "pick":
                val = "Yes" if val == answers.YES else "No" if val == answers.NO else None
                if val is None:
                    (block if req else lambda *a: None)(label, path, "field teks, aturan hanya punya opsi")
                    continue
            fields.append({"path": path, "kind": "textarea" if typ == "LongText" else "text", "label": label, "value": val})
    return {"id": job["id"], "company": job["company"], "title": job["title"], "url": url, "ats": "ashby",
            "fields": fields, "blocked": blocked, "skipped": skipped, "created": today()}


def write_plan(p):
    d = OUT / p["id"]
    d.mkdir(parents=True, exist_ok=True)
    (d / "plan.json").write_text(json.dumps(p, indent=1, ensure_ascii=False))
    return d / "plan.json"


def submit(p, dry_run=False):
    path = write_plan(p)
    cmd = ["node", str(JS), str(path), str(OUT / p["id"])] + (["--dry-run"] if dry_run else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    try:
        res = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        res = {"status": "error", "detail": (r.stderr or r.stdout)[-600:]}
    with open(LOG, "a") as f:
        f.write(json.dumps({"date": today(), "id": p["id"], "company": p["company"], "ats": "ashby", **res}) + "\n")
    return res


def main(argv):
    action, ref = argv[0], argv[1]
    store = Store()
    j = store.find(ref)
    p = plan(j)
    write_plan(p)
    if action == "plan" or p["blocked"]:
        for f in p["fields"]:
            print(f"   {f['label'][:70]:70} -> {str(f['value'])[:70]}")
        for b in p["blocked"]:
            print(f"   BLOCK {b['field']} | {b['label'][:110]} | {b['why']} | {b['options'][:5]}")
        print(("BLOCKED" if p["blocked"] else "READY  "), j["id"], j["company"], "|", j["title"])
        return
    r = submit(p, "--dry-run" in argv)
    print(r["status"].upper(), j["id"], j["company"], "|", j["title"], r.get("detail") or "")
    if r["status"] == "submitted":
        j["applied"], j["apply_via"] = today(), "auto-ashby"
        store.set_status(j, "applied", "auto-submit Ashby: pesan sukses tampil")
    else:
        j["history"].append({"date": today(), "status": j["status"], "note": f"ashby submit: {r['status']} {r.get('detail', '')}"[:300]})
    store.save()
    export_tracker(store)


if __name__ == "__main__":
    main(sys.argv[1:])
