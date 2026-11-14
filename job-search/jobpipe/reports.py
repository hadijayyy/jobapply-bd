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
    ready = sorted(store.by_status("ready"), key=lambda j: (j["tier"] or "Z", -(j["score"] or 0)))
    L = ["# Apply queue", "", f"Diperbarui {today()}. Urutan submit = urutan tabel. Semua form ber-captcha harus disubmit manual.", "",
         "| # | Tier | Skor | Company | Role | Apply link | CV | Kit | Rute |", "|---|---|---|---|---|---|---|---|---|"]
    for i, j in enumerate(ready, 1):
        route, note = apply_route(j)
        L.append(f"| {i} | {j['tier']} | {j['score'] if j['score'] is not None else '-'} | {j['company']} | {j['title']} | "
                 f"{j['url']} | {j['cv']} | {j['kit']} | {route}: {note} |")
    if not ready:
        L.append("| - | - | - | (kosong) | | | | | |")
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
