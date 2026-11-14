"""Single source of truth: data/jobs.json. tracker.csv is only a generated view."""
import csv, hashlib, json, re
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "jobs.json"
CONFIG = json.loads((ROOT / "config.json").read_text())
CANDIDATE = json.loads((ROOT / "candidate.json").read_text())

# new -> verified -> kit_draft -> ready -> applied -> interview -> offer
# terminal: rejected (by us), expired, skipped (Ryan), closed (company said no / ghosted / withdrawn)
STATUSES = ["new", "verified", "kit_draft", "ready", "applied", "interview", "offer",
            "rejected", "expired", "skipped", "closed"]
ACTIVE = {"new", "verified", "kit_draft", "ready", "applied", "interview"}


def today():
    return date.today().isoformat()


def norm_url(u):
    return re.sub(r"[?#].*$", "", u or "").rstrip("/").lower()


def job_id(url):
    return hashlib.sha1(norm_url(url).encode()).hexdigest()[:8]


def slug(s, n=40):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:n].strip("-")


def dedupe_key(company, title):
    return slug(company, 30) + "|" + slug(title, 60)


class Store:
    def __init__(self):
        raw = json.loads(DATA.read_text()) if DATA.exists() else {"jobs": {}}
        self.jobs = raw["jobs"]

    def save(self):
        DATA.parent.mkdir(exist_ok=True)
        DATA.write_text(json.dumps({"updated": today(), "jobs": self.jobs}, indent=1, ensure_ascii=False,
                                   sort_keys=True) + "\n")

    def known_keys(self):
        urls = {norm_url(j["url"]) for j in self.jobs.values()}
        pairs = {dedupe_key(j["company"], j["title"]) for j in self.jobs.values()}
        return urls, pairs

    def add(self, **f):
        jid = job_id(f["url"])
        rec = {"id": jid, "status": "new", "tier": None, "score": None, "blockers": [], "flags": [],
               "discovered": today(), "applied": None, "followups_sent": [], "kit": None, "cv": None,
               "notes": "", "history": [{"date": today(), "status": "new", "note": "discovered"}]}
        rec.update(f)
        self.jobs[jid] = rec
        return rec

    def find(self, ref):
        """Match by id prefix or by unique company/title substring."""
        ref = ref.lower()
        hits = [j for j in self.jobs.values() if j["id"].startswith(ref)]
        if not hits:
            hits = [j for j in self.jobs.values() if ref in (j["company"] + " " + j["title"]).lower()]
        if len(hits) != 1:
            raise SystemExit(f"'{ref}' matches {len(hits)} jobs: " + ", ".join(f"{h['id']} {h['company']}" for h in hits[:8]))
        return hits[0]

    def set_status(self, job, status, note=""):
        assert status in STATUSES, f"status must be one of {STATUSES}"
        job["status"] = status
        job["history"].append({"date": today(), "status": status, "note": note})

    def by_status(self, *statuses):
        return [j for j in self.jobs.values() if j["status"] in statuses]


def days_since(iso):
    return (date.today() - date.fromisoformat(iso)).days if iso else None


def next_action(j):
    s = j["status"]
    if s == "new":
        return "Review (buka halaman asli, cek syarat)", today()
    if s == "verified":
        return "Buat kit (CV + cover letter)", today()
    if s == "kit_draft":
        return "Isi hook/gap/ask lalu lint", today()
    if s == "ready":
        return "Submit manual (lihat APPLY-QUEUE)", today()
    if s == "applied":
        for d in CONFIG["followup_days"]:
            if d not in j["followups_sent"]:
                from datetime import timedelta
                return f"Follow-up hari ke-{d}", (date.fromisoformat(j["applied"]) + timedelta(days=d)).isoformat()
        return "Tunggu / tutup bila tidak ada kabar", ""
    if s == "interview":
        return "Siapkan interview (pipeline.py prep)", ""
    return "", ""


COLS = ["ID", "Company", "Role", "Location", "Comp", "Source", "Score", "Tier", "Status", "Date sourced",
        "Date applied", "Last touch", "Next action", "Next action date", "Link", "Notes"]


def export_tracker(store, path=ROOT / "tracker.csv"):
    order = {s: i for i, s in enumerate(["interview", "offer", "applied", "ready", "kit_draft", "verified", "new"])}
    rows = sorted(store.jobs.values(), key=lambda j: (order.get(j["status"], 9), j["tier"] or "Z", -(j["score"] or 0)))
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        for j in rows:
            na, nad = next_action(j)
            w.writerow([j["id"], j["company"], j["title"], j.get("location", ""), j.get("comp", ""), j.get("source", ""),
                        j["score"] if j["score"] is not None else "", j["tier"] or "", j["status"], j["discovered"],
                        j["applied"] or "", j["history"][-1]["date"], na, nad, j["url"], j.get("notes", "")])
