# Workflow lamaran end-to-end (Greenhouse + Hiring Cafe)

Satu CLI: `python3 job-search/pipeline.py <command>` (jalankan dari root repo). State tunggal: `data/jobs.json`.
`tracker.csv` dan `out/APPLY-QUEUE.md` adalah view yang di-generate ulang, jangan diedit manual.

```
SOURCE ──> FILTER+SCORE ──> VERIFY ──> TAILOR CV (ATS ≥ 90) ──> KIT ──> LINT ──> APPLY (manual) ──> FOLLOW-UP ──> INTERVIEW
greenhouse   scoring.py      liveness   cv.py + ats.py          kit.py   kit.py    Ryan klik Submit   cadence 5/10   prep
hiringcafe   config.json     + baca JD
```

## 1. Source
| Sumber | Cara | Catatan |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io` (API publik resmi), 142 board di `config.json > boards.greenhouse` | Tambah board: probe token dulu, lalu masukkan ke config |
| Hiring Cafe | Paste link lowongan ke `data/hiringcafe_import.txt` (satu per baris) | hiringcafe.com memblokir akses otomatis (Cloudflare, 403). Link yang mengarah ke Greenhouse otomatis ditarik JD-nya lewat API resmi; link lain masuk sebagai "isi manual" |

Sumber lain (Lever, Ashby, Remotive, dll.) masih ada di kode; aktifkan lewat `config.json > sources_enabled`.

## 2. Filter + score (otomatis, deterministik)
- Judul: `title_include` / `title_exclude` (buang SDR/BDR, junior, region non-APAC, bahasa lokal tertentu)
- Lokasi: Indonesia/Jakarta, remote APAC/global, onsite SG/MY. Negara di judul ikut dibaca (Cloudflare menulis "Hybrid" di lokasi)
- Umur posting maks 45 hari; > 30 hari diberi flag ghost-job
- Hard blocker -> tier C: 7+ tahun, Mandarin/Jepang/Korea/Thai/Viet wajib, crypto wajib, SaaS-essential/adtech/iGaming wajib, lisensi, komisi saja, onsite di luar Jakarta/SG/MY
- Onsite SG/MY: lolos, tapi diberi flag "sponsor visa disebut / TIDAK disebut, tanya recruiter"
- Fit score 0-100: title 30, lokasi 25, fresh 15, seniority 15, industri 10, gaji 5. Tier A ≥ 65, B ≥ 45

```
python3 job-search/pipeline.py discover          # tarik + score lowongan baru
python3 job-search/pipeline.py rescore           # setelah edit config.json
python3 job-search/pipeline.py list --status new
```

## 3. Verify (wajib sebelum bikin materi)
- Liveness: endpoint job Greenhouse harus 200
- Baca bagian requirements JD. Syarat tersembunyi yang lolos regex -> `review <id> reject "<alasan>"`
```
python3 job-search/pipeline.py show <id> --desc
python3 job-search/pipeline.py review <id> ok|reject "catatan"
```

## 4. Tailor CV, target ATS ≥ 90
`ats.py` menghitung skor seperti Jobscan pada **teks hasil ekstraksi PDF**:
keywords 50 · judul role 15 · soft skills 10 · pengalaman 10 · pendidikan 5 · format 10.

Setiap keyword di lexicon punya status bukti:
- `yes`: ada di CV / dikonfirmasi Ryan -> boleh ditulis
- `pending`: Ryan bilang benar tapi detail belum ada -> **tidak ditulis**, dihitung terpisah ("jika dikonfirmasi")
- `no`: tidak benar -> tidak pernah ditulis; dibahas jujur di paragraf GAP cover letter

Tailoring = memilih, mengurutkan dan memilih kata dari fakta di `candidate.json`. Tidak ada klaim baru.
```
python3 job-search/pipeline.py tailor            # semua verified/ready
python3 job-search/pipeline.py tailor <id>
```
Output: `out/cv/Ryan-Hadi-CV-<Company>-<id>.pdf` + `out/ats/<company>-<id>.md` (skor before/after + 3 bucket keyword).

Kalau skor < 90 dan bucket "missing tapi benar" kosong, sisa gap-nya adalah item pending atau gap nyata.
Konfirmasi detail pending -> ubah evidence di `ats.py` dari `pending` ke `yes` + tambahkan faktanya ke `candidate.json` -> `tailor` lagi.

## 5. Kit (cover letter + jawaban form)
```
python3 job-search/pipeline.py kit all           # skeleton; isi {{HOOK}} {{GAP}} {{ASK}} dari JD
python3 job-search/pipeline.py lint              # tolak em dash, klise, angka yang tidak ada di candidate.json
```
Lolos lint -> status `ready` -> muncul di `out/APPLY-QUEUE.md` (urut skor ATS).
Draft outreach LinkedIn: `out/OUTREACH.md` (maks 300 karakter, nama kontak belum diverifikasi).

## 6. Apply (human gate)
- Ryan submit sendiri. Claude boleh bantu isi form satu per satu, **berhenti sebelum Submit**
- Tidak ada auto-apply massal, tidak ada pengiriman email/DM tanpa "ya" per item
```
python3 job-search/pipeline.py applied <id> --via form
```

## 7. Follow-up dan interview
```
python3 job-search/pipeline.py followups                  # yang jatuh tempo hari ini (hari ke-5 dan ke-10)
python3 job-search/pipeline.py followups --done <id> 5
python3 job-search/pipeline.py status <id> interview "screening call 20 Nov"
python3 job-search/pipeline.py prep <id>
```
Ghosted: tidak ada balasan setelah hari ke-21 -> `status <id> closed "ghosted"`.

## Rutin harian (opsional)
`python3 job-search/pipeline.py run` = discover + verify + laporan `out/reports/<tanggal>.md`. Bisa dijadwalkan Senin-Jumat 07:07 WIB.
