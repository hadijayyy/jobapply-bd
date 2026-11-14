#!/usr/bin/env python3
"""One-time import of the pre-rebuild state (tracker.csv, seen.json, APPLY-QUEUE.md) into data/jobs.json."""
import csv, json, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.dont_write_bytecode = True
from jobpipe.store import Store, norm_url, job_id
from jobpipe import kit

old = ROOT / "archive/2026-11-12"
store = Store()
# kit + cv paths from the old queue table, keyed by normalized apply link
paths = {}
for line in (old / "APPLY-QUEUE.md").read_text().splitlines():
    c = [x.strip() for x in line.strip("|").split("|")]
    if len(c) >= 7 and c[0].isdigit():
        paths[norm_url(c[4])] = (c[6].replace("applications/", "out/kits/"), c[5].replace("cv/by-company/", "out/cv/"))
n = 0
for r in csv.DictReader((ROOT / "tracker.csv").open()):
    if "Link" not in r:
        break
    url = r["Link"]
    if job_id(url) in store.jobs:
        continue
    kit_p, cv_p = paths.get(norm_url(url), (None, None))
    has_kit = kit_p and (ROOT / kit_p).exists()
    status = "skipped" if r["Status"] == "Skipped" else ("kit_draft" if has_kit else "verified")
    j = store.add(url=url, company=r["Company"], title=r["Role"], location=r["Location / Remote"], comp=r["Comp"],
                  source=r["Source"], posted=None, desc="", tier=r["Tier"] or None, notes=r["Notes"],
                  flags=["legacy: skor tidak dihitung, tier dari penilaian manual 12 Nov"],
                  kit=kit_p if has_kit else None, cv=cv_p if has_kit else None)
    j["discovered"] = r["Date sourced"] or j["discovered"]
    store.set_status(j, status, "import dari tracker lama")
    n += 1
seen = json.loads((old / "seen.json").read_text())
for s in seen.get("jobs", []):
    if job_id(s["url"]) not in store.jobs:
        j = store.add(url=s["url"], company=s["company"], title=s["title"], location="", source="legacy seen.json", posted=None, desc="")
        store.set_status(j, "skipped", "legacy: pernah dilaporkan, tidak ada aksi tercatat"); n += 1
for s in seen.get("rejected", []):
    if job_id(s["url"]) not in store.jobs:
        j = store.add(url=s["url"], company="(unknown)", title="(legacy rejected)", location="", source="legacy seen.json", posted=None, desc="")
        store.set_status(j, "rejected", s["reason"]); n += 1
# legacy kits: lint decides whether they are really ready
for j in store.by_status("kit_draft"):
    if not kit.lint(j):
        store.set_status(j, "ready", "kit lama lolos lint baru")
store.save()
print("imported", n, {s: len(store.by_status(s)) for s in ("ready", "kit_draft", "verified", "skipped", "rejected")})
