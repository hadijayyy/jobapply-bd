"""Stage 4: apply queue, follow-ups, daily report, interview prep skeleton."""
from collections import Counter
from datetime import date, timedelta

from .kit import apply_route
from .store import CONFIG, ROOT, STATUSES, days_since, today

OUT = ROOT / "out"


def followups_due(store):
    due = []
    for j in store.by_status("applied", "interview"):
        n = days_since(j["applied"])
        for d in CONFIG["followup_days"]:
            if n is not None and n >= d and d not in j["followups_sent"]:
                due.append((j, d, n))
                break
    return due


def queue_md(store):
    ats = lambda j: (j.get("ats") or {}).get("after") or 0
    ready = sorted(store.by_status("ready"), key=lambda j: (-ats(j), -(j["score"] or 0)))
    L = ["# Apply queue", "", f"Diperbarui {today()}. Urutan submit = urutan tabel (skor ATS tertinggi dulu). Semua form disubmit manual oleh Ryan.", "",
         "Fit = kecocokan lowongan (scoring.py). ATS = skor CV tailored vs JD (ats.py); angka dalam kurung = jika item pending dikonfirmasi.", "",
         "| # | ATS | Fit | Company | Role | Lokasi | Apply link | CV | Kit | Rute | Flag |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, j in enumerate(ready, 1):
        route, note = apply_route(j)
        a = j.get("ats") or {}
        flags = "; ".join(j["blockers"] + j["flags"]) or "-"
        L.append(f"| {i} | {a.get('after', '-')} ({a.get('if_pending_confirmed', '-')}) | {j['score'] if j['score'] is not None else '-'} | "
                 f"{j['company']} | {j['title']} | {j.get('location', '')} | {j['url']} | {j['cv']} | {j['kit']} | {route}: {note} | {flags} |")
    if not ready:
        L.append("| - | - | - | (kosong) | | | | | | | |")
    drafts = store.by_status("kit_draft")
    if drafts:
        L += ["", "## Kit belum selesai (isi placeholder lalu `pipeline.py lint`)", ""]
        L += [f"- {j['company']} | {j['title']} | {j['kit']}" for j in drafts]
    (OUT / "APPLY-QUEUE.md").write_text("\n".join(L) + "\n")


def funnel(store):
    c = Counter(j["status"] for j in store.jobs.values())
    return " | ".join(f"{s}: {c[s]}" for s in STATUSES if c[s])


def report_md(store, new_ids, notes):
    mx = CONFIG["report_max_items"]
    new = sorted((store.jobs[i] for i in new_ids if store.jobs[i]["status"] not in ("rejected", "expired")),
                 key=lambda j: -(j["score"] or 0))
    L = [f"# Laporan {today()}", "", f"Funnel: {funnel(store)}", ""]
    if notes:
        L += ["## Catatan run"] + [f"- {n}" for n in notes] + [""]
    L += [f"## Lowongan baru ({len(new)}, tampil maks {mx})", ""]
    for j in new[:mx]:
        L += [f"### {j['title']} | {j['company']} | Tier {j['tier']} (skor {j['score']})",
              f"- Link: {j['url']}",
              f"- Lokasi: {j.get('location') or 'tidak disebutkan'} | Gaji: {j.get('comp') or 'tidak disebutkan'} | Diposting: {j.get('posted') or 'tidak disebutkan'}",
              f"- Status: {j['status']} | Liveness: {j.get('liveness', '-')} | Syarat tahun: {j.get('years_required') or 'tidak disebutkan'}",
              f"- Flag: {'; '.join(j['flags']) or 'tidak ada'}",
              f"- Skor: {', '.join(f'{k} {v}' for k, v in j['score_parts'].items())}",
              "- Kenapa cocok + gap: (isi Claude setelah buka halaman asli)", ""]
    due = followups_due(store)
    L += [f"## Follow-up jatuh tempo ({len(due)})", ""]
    L += [f"- Hari ke-{d} ({n} hari sejak apply): {j['company']} | {j['title']} | {j['url']}" for j, d, n in due] or ["- tidak ada"]
    L += ["", "## Perlu review manual (status new/verified, tier A/B)", ""]
    todo = [j for j in store.by_status("new", "verified") if j["tier"] in ("A", "B")]
    L += [f"- [{j['status']}] {j['id']} {j['company']} | {j['title']} | tier {j['tier']}" for j in todo] or ["- tidak ada"]
    L += ["", "Prioritas: " + (f"{new[0]['company']} ({new[0]['title']}), skor tertinggi dan paling segar." if new else "tidak ada lowongan baru."), ""]
    path = OUT / "reports" / f"{today()}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(L))
    return path


def prep_md(job):
    path = OUT / "prep" / f"{job['company'].lower().replace(' ', '-')}-{job['id']}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(f"""# Interview prep | {job['company']} | {job['title']}
- Link: {job['url']} | Applied: {job['applied'] or '-'}

## Peta syarat JD ke bukti (isi Claude; bukti hanya dari candidate.json)
| Syarat JD | Bukti Ryan | Gap / cara jawab jujur |
|---|---|---|

## Pertanyaan yang kemungkinan muncul (6-8, dari JD)

## Cerita STAR (maks 3, pakai angka dari candidate.json saja)

## Pertanyaan balik untuk interviewer (4)

## Gaji/notice: lihat Form answers di {job['kit'] or 'kit'}
""")
    return path


def ats_md(job, r):
    """out/ats/<company>-<id>.md: score breakdown + the three keyword buckets + change log."""
    from .store import slug
    from .ats import TERM
    b = r["buckets"]
    phrase = lambda cs: ", ".join(cs) or "-"
    md = f"""# ATS: {job['company']} | {job['title']}
- Link: {job['url']}
- CV: {r['path']} ({r['pages']} halaman)
- **Skor ATS: {r['before']} (CV master) -> {r['after']} (CV tailored)** | jika item pending dikonfirmasi: {r['if_pending_confirmed']}
- Rincian: {', '.join(f'{k} {v}' for k, v in r['parts'].items())}
- Judul role yang dicari ATS: "{r['core']}"

## Keyword audit
- **Matched:** {phrase(b['matched'])}
- **Missing tapi benar (harus 0):** {phrase(b['missing_but_true'])}
- **Pending (Ryan bilang benar, detail belum ada, TIDAK ditulis):** {phrase(b['pending_confirm'])}
- **Missing dan tidak benar (jangan ditulis; bahas di cover letter/interview):** {phrase(b['missing_not_true'])}

## Perubahan dari CV master
{chr(10).join('- ' + x for x in r['log'])}

Metode skor: lihat jobpipe/ats.py (keywords 50, title 15, soft skills 10, experience 10, education 5, format 10).
Skor dihitung dari teks hasil ekstraksi PDF (pdftotext), sama seperti ATS membaca file.
"""
    p = ROOT / "out" / "ats" / f"{slug(job['company'], 24)}-{job['id']}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(md)
    return p
