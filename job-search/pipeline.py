#!/usr/bin/env python3
"""Job application pipeline for Ryan Hadi. One CLI, one state file (data/jobs.json).

  discover -> score/tier -> verify -> kit (CV + cover letter) -> lint -> ready -> applied -> follow-up -> interview

Daily:    python3 job-search/pipeline.py run
Judgment steps (Claude does these, see WORKFLOW.md): review, fill kit placeholders, Gmail drafts.
`autoapply run` fills and submits Greenhouse applications (Ryan chose auto-submit, 16 Nov 2026). When Greenhouse asks
for its human-verification code it stops and waits for Ryan. It never sends email.
"""
import argparse, sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent))

from jobpipe import cv, kit, liveness, reports, scoring, sources  # noqa: E402
from jobpipe.store import CONFIG, ROOT, STATUSES, Store, dedupe_key, export_tracker, norm_url, today  # noqa: E402


def say(*a):
    print(*a, file=sys.stderr)


# ---------- stage 1+2: discover, score ----------
def discover(store, days):
    urls, pairs = store.known_keys()
    cands, seen_now = [], set()
    for j in sources.fetch_all():
        if not scoring.passes_prefilter(j, days):
            continue
        u, p = norm_url(j["url"]), dedupe_key(j["company"], j["title"])
        if u in urls or p in pairs or u in seen_now or p in seen_now:
            continue
        seen_now |= {u, p}
        cands.append(j)
    sources.enrich(cands)
    new_ids = []
    for j in cands:
        red = scoring.evaluate(j)
        fields = {k: j[k] for k in ("source", "title", "company", "location", "url", "posted", "comp", "desc", "workplace",
                                    "score", "score_parts", "years_required", "tier", "blockers", "flags", "red_flags")}
        rec = store.add(**fields)
        if red:
            store.set_status(rec, "rejected", "red flag: " + "; ".join(j["red_flags"]))
        elif j["tier"] == "C":
            why = "; ".join(j["blockers"]) or f"skor {j['score']} di bawah ambang"
            store.set_status(rec, "rejected", "tier C: " + why)
        new_ids.append(rec["id"])
    return new_ids


# ---------- stage 3: verify ----------
def verify(store, new_ids, notes):
    """Liveness for new A/B jobs and for everything waiting in the pipeline. ATS-sourced + active = auto verified."""
    targets = [store.jobs[i] for i in new_ids if store.jobs[i]["status"] == "new"]
    targets += store.by_status("verified", "kit_draft", "ready")
    verdict = liveness.check_many([j["url"] for j in targets])
    dropped = 0
    for j in targets:
        v = verdict.get(j["url"], "uncertain")
        j["liveness"] = v
        if v == "expired":
            store.set_status(j, "expired", "liveness check")
            dropped += 1
        elif j["status"] == "new" and v == "active" and j["source"].startswith(sources.ATS_SOURCES) and j.get("desc"):
            store.set_status(j, "verified", "auto: ATS API aktif + JD terbaca")
    if dropped:
        notes.append(f"{dropped} lowongan ditandai expired oleh liveness check")


# ---------- commands ----------
def cmd_run(a):
    store, notes = Store(), []
    new_ids = discover(store, a.days or CONFIG["freshness_days"])
    verify(store, new_ids, notes)
    live = [i for i in new_ids if store.jobs[i]["status"] in ("new", "verified")]
    path = reports.report_md(store, live, notes)
    reports.queue_md(store)
    export_tracker(store)
    store.save()
    due = reports.followups_due(store)
    ab = sorted((store.jobs[i] for i in live), key=lambda j: -(j["score"] or 0))
    say(f"funnel: {reports.funnel(store)}")
    say(f"laporan: {path.relative_to(ROOT)}")
    if not ab and not due:
        print("NOTHING_NEW")  # routine: send no notification
        return
    top = "; ".join(f"{j['company']} - {j['title']} (tier {j['tier']}, skor {j['score']})" for j in ab[:3])
    print(f"NEW={len(ab)} FOLLOWUPS={len(due)} TOP: {top or '-'}")


def cmd_discover(a):
    store = Store()
    ids = discover(store, a.days or CONFIG["freshness_days"])
    store.save()
    for i in ids:
        j = store.jobs[i]
        print(f"{j['id']} [{j['status']:8}] tier {j['tier']} skor {j['score']:>3} {j['company']} | {j['title']}")


def cmd_rescore(a):
    """Re-runs scoring.evaluate on stored jobs that the pipeline itself graded (new / rejected-by-score).
    Use after editing config.json rules. Never touches jobs Ryan or Claude already reviewed."""
    store, n = Store(), 0
    for j in store.jobs.values():
        auto_rej = j["status"] == "rejected" and j["history"][-1]["note"].startswith(("tier C", "red flag"))
        if j["status"] != "new" and not auto_rej:
            continue
        red = scoring.evaluate(j)
        if not scoring.passes_prefilter(j, 10 ** 6):
            if j["status"] != "rejected":
                store.set_status(j, "rejected", "tier C: judul/lokasi tidak lolos filter config")
            n += 1
            continue
        if red:
            store.set_status(j, "rejected", "red flag: " + "; ".join(j["red_flags"]))
        elif j["tier"] == "C":
            if j["status"] != "rejected":
                store.set_status(j, "rejected", "tier C: " + ("; ".join(j["blockers"]) or f"skor {j['score']}"))
        elif j["status"] == "rejected":
            store.set_status(j, "new", "rescore: lolos aturan baru")
        n += 1
    store.save(); export_tracker(store)
    print(f"rescored {n}")


def cmd_list(a):
    store = Store()
    for j in sorted(store.jobs.values(), key=lambda j: (j["tier"] or "Z", -(j["score"] or 0))):
        if (not a.status or j["status"] in a.status) and (not a.tier or j["tier"] == a.tier):
            print(f"{j['id']} [{j['status']:9}] {j['tier'] or '-'} {str(j['score'] or '-'):>3} {j['company']} | {j['title']}")


def cmd_show(a):
    store = Store()
    j = store.find(a.ref)
    for k in ("id", "status", "tier", "score", "score_parts", "blockers", "flags", "red_flags", "location", "comp", "posted",
              "years_required", "liveness", "url", "kit", "cv", "applied", "followups_sent", "notes"):
        print(f"{k}: {j.get(k)}")
    print("history:", *[f"  {h['date']} {h['status']} {h['note']}" for h in j["history"]], sep="\n")
    if a.desc:
        print("\n" + (j.get("desc") or "(kosong)"))


def cmd_review(a):
    """Claude opened the real page. ok -> verified. reject -> rejected with reason."""
    store = Store()
    j = store.find(a.ref)
    if a.verdict == "ok":
        store.set_status(j, "verified", a.note or "review manual: halaman asli dibuka")
    else:
        store.set_status(j, "rejected", a.note or "review manual")
    store.save(); export_tracker(store)
    print(j["id"], j["status"])


def cmd_kit(a):
    store = Store()
    jobs = store.by_status("verified") if a.ref == "all" else [store.find(a.ref)]
    jobs = [j for j in jobs if j["tier"] in ("A", "B") or a.force]
    for j in jobs:
        if j["status"] not in ("verified", "kit_draft") and not a.force:
            print(f"skip {j['company']}: status {j['status']}, harus verified dulu"); continue
        k, c = kit.build(j)
        store.set_status(j, "kit_draft", "kit dibuat")
        print(f"{j['company']}: {k} + {c}")
    store.save(); export_tracker(store)


MASTER_CV = ROOT / "master" / "Ryan-Hadi-CV-master.pdf"


def cmd_tailor(a):
    """Tailored CV per JD + ATS report (before = master CV, after = tailored PDF text)."""
    from jobpipe import ats
    store = Store()
    master = ats.pdf_text(MASTER_CV) if MASTER_CV.exists() else None
    jobs = store.by_status("verified", "kit_draft", "ready") if a.ref == "all" else [store.find(a.ref)]
    rows = []
    for j in jobs:
        r = cv.tailor(j, master)
        j["cv"], j["ats"] = r["path"], {k: r[k] for k in ("before", "after", "if_pending_confirmed", "parts")}
        reports.ats_md(j, r)
        rows.append((r["after"], j, r))
    for sc, j, r in sorted(rows, key=lambda x: -x[0]):
        flag = "OK " if sc >= a.target else "LOW"
        print(f"{flag} {j['id']} ATS {r['before']} -> {sc} (jika pending dikonfirmasi: {r['if_pending_confirmed']}) "
              f"{r['pages']} hlm | {j['company']} | {j['title']}")
    store.save(); export_tracker(store)


def cmd_applysheet(a):
    """out/APPLY-SHEET.md: real Greenhouse form fields per ready job, pre-answered, + cover letter PDFs."""
    from jobpipe import applysheet
    store = Store()
    ats_of = lambda j: (j.get("ats") or {}).get("after") or 0
    jobs = sorted(store.by_status("ready"), key=lambda j: -ats_of(j))
    print(applysheet.build(jobs).relative_to(ROOT))


def cmd_autoapply(a):
    """plan: show answers per job. run: tailor CV, fill and SUBMIT. answer: store an answer for a blocked question."""
    import time
    from jobpipe import answers, autoapply
    store = Store()
    cfg = CONFIG["autoapply"]
    if a.action == "code":  # Ryan read the 8-character code from his own inbox; hand it to the waiting browser
        j = store.find(a.ref)
        d = autoapply.OUT / j["id"]
        if not (d / "NEED_CODE").exists():
            raise SystemExit(f"tidak ada browser yang sedang menunggu kode untuk {j['company']} (jalankan `autoapply run {j['id']} --wait-code 600`)")
        (d / "code.txt").write_text(a.field.strip())
        print("kode diteruskan ke form; lihat hasil proses run")
        return
    if a.action == "answer":
        j = store.find(a.ref)
        p = autoapply.plan(j)
        b = next((b for b in p["blocked"] if b["field"] == a.field), None)
        if not b:
            raise SystemExit(f"field {a.field} tidak sedang menahan {j['company']}; lihat `autoapply plan {j['id']}`")
        if b["options"] and a.value not in b["options"]:
            raise SystemExit("jawaban harus salah satu opsi: " + " / ".join(b["options"]))
        answers.save_answer(b["label"], a.value, None if a.all_jobs else j, a.source)
        print(f"disimpan: {b['label'][:80]} -> {a.value[:80]}")
        return
    jobs = [store.find(a.ref)] if a.ref else autoapply.eligible(store)
    master = None
    blocked, results, per_co, sent = [], [], {}, 0
    for j in jobs:
        if j["status"] == "applied" or not autoapply.gh_ref(j):
            continue
        if a.action == "run" and not a.dry_run and (sent >= (a.limit or cfg["max_per_run"]) or per_co.get(j["company"], 0) >= cfg["max_per_company"]):
            continue
        if not j.get("cv") or not (ROOT / j["cv"]).exists():
            from jobpipe import ats
            master = master or (ats.pdf_text(MASTER_CV) if MASTER_CV.exists() else None)
            r = cv.tailor(j, master)
            j["cv"], j["ats"] = r["path"], {k: r[k] for k in ("before", "after", "if_pending_confirmed", "parts")}
            reports.ats_md(j, r)
        try:
            p = autoapply.plan(j)
        except Exception as e:  # noqa: BLE001  posting pulled, API error
            print(f"SKIP    {j['id']} {j['company']} | form tidak terbaca: {e}"); continue
        p["code_wait_s"] = a.wait_code or cfg.get("code_wait_s", 0)
        autoapply.write_plan(p)
        if j["status"] == "new":
            store.set_status(j, "verified", "auto: form Greenhouse masih aktif")
        if p["blocked"]:
            blocked.append((j, p))
            j["apply_blocked"] = [b["label"][:120] for b in p["blocked"]]
            print(f"BLOCKED {j['id']} {j['company']} | {j['title']} ({len(p['blocked'])} pertanyaan wajib tanpa jawaban)")
            continue
        j.pop("apply_blocked", None)
        if a.action == "plan":
            print(f"READY   {j['id']} {j['company']} | {j['title']} ({len(p['fields'])} field)")
            if a.ref:
                for f in p["fields"]:
                    print(f"   {f['label'][:70]:70} -> {str(f['value'])[:70]}")
            continue
        if sent and not a.dry_run:
            time.sleep(cfg["pause_s"])
        r = autoapply.submit(p, a.dry_run)
        results.append(r)
        print(f"{r['status'].upper():9} {j['id']} {j['company']} | {j['title']} {r.get('detail') or ''} {r.get('errors') or ''}")
        if r["status"] == "submitted":
            sent += 1; per_co[j["company"]] = per_co.get(j["company"], 0) + 1
            j["applied"], j["apply_via"] = today(), "auto"
            store.set_status(j, "applied", "auto-submit: halaman konfirmasi Greenhouse tampil")
        elif not a.dry_run:
            j["history"].append({"date": today(), "status": j["status"], "note": f"auto-submit gagal: {r['status']} {r.get('detail') or r.get('errors') or ''}"[:300]})
            if r["status"] in ("captcha", "needs_code"):
                print("STOP: Greenhouse meminta verifikasi manusia (kode ke email Ryan / CAPTCHA). Tidak diakali; sisa antrean ditunda.\n"
                      f"      Lanjutkan dengan: autoapply run {j['id']} --wait-code 600, lalu autoapply code {j['id']} <KODE>"); break
        store.save()
    path = autoapply.pending_md(blocked)
    reports.queue_md(store); export_tracker(store); store.save()
    print(f"\nterkirim {sent} | ditahan {len(blocked)} (lihat {path.relative_to(ROOT)}) | gagal {sum(1 for r in results if r['status'] not in ('submitted', 'filled'))}")


def cmd_lint(a):
    store = Store()
    jobs = store.by_status("kit_draft") if a.ref == "all" else [store.find(a.ref)]
    bad = 0
    for j in jobs:
        probs = kit.lint(j)
        if probs:
            bad += 1
            print(f"FAIL {j['company']} ({j['id']}):", *probs, sep="\n  - ")
        else:
            store.set_status(j, "ready", "lint lolos")
            print(f"OK   {j['company']} -> ready")
    reports.queue_md(store); export_tracker(store); store.save()
    sys.exit(1 if bad else 0)


def cmd_applied(a):
    store = Store()
    j = store.find(a.ref)
    if j["status"] not in ("ready", "kit_draft", "verified") and not a.force:
        raise SystemExit(f"status {j['status']}: hanya kit ready yang boleh ditandai applied (--force untuk paksa)")
    j["applied"] = a.date or today()
    j["apply_via"] = a.via
    store.set_status(j, "applied", f"via {a.via}")
    reports.queue_md(store); export_tracker(store); store.save()
    print(f"{j['company']} applied {j['applied']}; follow-up hari ke-{CONFIG['followup_days']}")


def cmd_status(a):
    store = Store()
    j = store.find(a.ref)
    store.set_status(j, a.status, a.note)
    if a.note:
        j["notes"] = (j["notes"] + " | " if j["notes"] else "") + a.note
    reports.queue_md(store); export_tracker(store); store.save()
    print(j["id"], j["status"])


def cmd_followups(a):
    store = Store()
    if a.done:
        j = store.find(a.done[0]); d = int(a.done[1])
        j["followups_sent"].append(d); j["history"].append({"date": today(), "status": j["status"], "note": f"follow-up hari ke-{d} dikirim"})
        store.save(); export_tracker(store); print("dicatat"); return
    due = reports.followups_due(store)
    for j, d, n in due:
        print(f"hari ke-{d} ({n} hari): {j['id']} {j['company']} | {j['title']} | {j['url']}")
    if not due:
        print("tidak ada")


def cmd_prep(a):
    store = Store()
    print(reports.prep_md(store.find(a.ref)).relative_to(ROOT))


def cmd_export(a):
    store = Store()
    reports.queue_md(store); export_tracker(store)
    print(reports.funnel(store))


def cmd_rebuild_cv(a):
    for p in cv.rebuild_variants():
        print(p.relative_to(ROOT))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("run", help="discover + score + verify + report (routine harian)"); p.add_argument("--days", type=int); p.set_defaults(f=cmd_run)
    p = sp.add_parser("discover"); p.add_argument("--days", type=int); p.set_defaults(f=cmd_discover)
    p = sp.add_parser("rescore", help="nilai ulang setelah config.json diubah"); p.set_defaults(f=cmd_rescore)
    p = sp.add_parser("list"); p.add_argument("--status", nargs="*"); p.add_argument("--tier"); p.set_defaults(f=cmd_list)
    p = sp.add_parser("show"); p.add_argument("ref"); p.add_argument("--desc", action="store_true"); p.set_defaults(f=cmd_show)
    p = sp.add_parser("review", help="setelah halaman asli dibuka"); p.add_argument("ref"); p.add_argument("verdict", choices=["ok", "reject"]); p.add_argument("note", nargs="?", default=""); p.set_defaults(f=cmd_review)
    p = sp.add_parser("kit", help="buat CV + kit (ref atau 'all')"); p.add_argument("ref"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_kit)
    p = sp.add_parser("tailor", help="CV per JD + skor ATS (ref atau 'all')"); p.add_argument("ref", nargs="?", default="all"); p.add_argument("--target", type=int, default=90); p.set_defaults(f=cmd_tailor)
    p = sp.add_parser("applysheet", help="jawaban form Greenhouse + cover letter PDF untuk semua job ready"); p.set_defaults(f=cmd_applysheet)
    p = sp.add_parser("autoapply", help="plan | run (SUBMIT) | answer")
    p.add_argument("action", choices=["plan", "run", "answer", "code"]); p.add_argument("ref", nargs="?"); p.add_argument("field", nargs="?"); p.add_argument("value", nargs="?")
    p.add_argument("--dry-run", action="store_true", help="isi form + screenshot, tidak submit"); p.add_argument("--limit", type=int); p.add_argument("--wait-code", type=int, default=0, help="detik menunggu kode verifikasi email dari Ryan")
    p.add_argument("--all-jobs", action="store_true", help="answer: pakai jawaban ini untuk semua form berlabel sama"); p.add_argument("--source", default="ai")
    p.set_defaults(f=cmd_autoapply)
    p = sp.add_parser("lint", help="cek kit; lolos -> ready"); p.add_argument("ref", nargs="?", default="all"); p.set_defaults(f=cmd_lint)
    p = sp.add_parser("applied", help="catat sudah disubmit"); p.add_argument("ref"); p.add_argument("--via", default="form", choices=["form", "email", "referral"]); p.add_argument("--date"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_applied)
    p = sp.add_parser("status"); p.add_argument("ref"); p.add_argument("status", choices=STATUSES); p.add_argument("note", nargs="?", default=""); p.set_defaults(f=cmd_status)
    p = sp.add_parser("followups"); p.add_argument("--done", nargs=2, metavar=("REF", "DAY")); p.set_defaults(f=cmd_followups)
    p = sp.add_parser("prep", help="skeleton persiapan interview"); p.add_argument("ref"); p.set_defaults(f=cmd_prep)
    p = sp.add_parser("export", help="tulis ulang tracker.csv + APPLY-QUEUE.md"); p.set_defaults(f=cmd_export)
    p = sp.add_parser("rebuild-cv"); p.set_defaults(f=cmd_rebuild_cv)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
