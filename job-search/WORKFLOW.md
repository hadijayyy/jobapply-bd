# Workflow lamaran end-to-end (Greenhouse + Hiring Cafe)

Satu CLI: `python3 job-search/pipeline.py <command>` (jalankan dari root repo). State tunggal: `data/jobs.json`.
`tracker.csv` dan `out/APPLY-QUEUE.md` adalah view yang di-generate ulang, jangan diedit manual.

```
SOURCE ──> FILTER+SCORE ──> VERIFY ──> TAILOR CV (ATS ≥ 90) ──> KIT ──> LINT ──> APPLY (auto)   ──> FOLLOW-UP ──> INTERVIEW
greenhouse   scoring.py      liveness   cv.py + ats.py          kit.py   kit.py    autoapply.py       cadence 5/10   prep
hiringcafe   config.json     + baca JD
```

## 1. Source
| Sumber | Cara | Catatan |
|---|---|---|
| Greenhouse | `boards-api.greenhouse.io` (API publik resmi), 142 board di `config.json > boards.greenhouse` | Tambah board: probe token dulu, lalu masukkan ke config |
| Hiring Cafe | Paste link lowongan ke `data/hiringcafe_import.txt` (satu per baris) | hiringcafe.com memblokir akses otomatis (Cloudflare, 403). Link yang mengarah ke Greenhouse otomatis ditarik JD-nya lewat API resmi; link lain masuk sebagai "isi manual" |

Fokus Greenhouse (Ryan, 21 Nov 2026). Ashby/Lever dimatikan di `config.json > sources_enabled`: form mereka memunculkan reCAPTCHA/hCaptcha saat submit dari server. `jobpipe/ashby.py` tetap ada (isi form + berhenti di CAPTCHA).

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

## 4. Tailor CV, target ATS ≥ 80
`ats.py` menghitung skor seperti Jobscan pada **teks hasil ekstraksi PDF**:
keywords 50 · judul role 15 · soft skills 10 · pengalaman 10 (selalu penuh, syarat tahun di JD tidak mengurangi skor) · pendidikan 5 · format 10.

Setiap keyword di lexicon punya status bukti:
- `yes`: ada di CV / dikonfirmasi Ryan -> boleh ditulis
- `pending`: Ryan bilang benar tapi detail belum ada -> **tidak ditulis**, dihitung terpisah ("jika dikonfirmasi")
- `no`: tidak benar -> tidak pernah ditulis; dibahas jujur di paragraf GAP cover letter

Tailoring = memilih, mengurutkan dan memilih kata dari fakta di `candidate.json`. Tidak ada klaim baru.
```
python3 job-search/pipeline.py tailor            # semua verified/ready
python3 job-search/pipeline.py tailor <id>
```
Output: `out/cv/<Company>-<id>/Ryan Hadi_CV_Business Development.pdf` (nama file yang dilihat recruiter: tanpa tanggal, tanpa nama perusahaan) + `out/ats/<company>-<id>.md` (skor before/after + 3 bucket keyword).

Kalau skor < 90 dan bucket "missing tapi benar" kosong, sisa gap-nya adalah item pending atau gap nyata.
Konfirmasi detail pending -> ubah evidence di `ats.py` dari `pending` ke `yes` + tambahkan faktanya ke `candidate.json` -> `tailor` lagi.

## 5. Kit (cover letter + jawaban form)
```
python3 job-search/pipeline.py kit all           # skeleton; isi {{HOOK}} {{GAP}} {{ASK}} dari JD
python3 job-search/pipeline.py lint              # tolak em dash, klise, angka yang tidak ada di candidate.json
```
Lolos lint -> status `ready` -> muncul di `out/APPLY-QUEUE.md` (urut skor ATS).
Draft outreach LinkedIn: `out/OUTREACH.md` (maks 300 karakter, nama kontak belum diverifikasi).

## 6. Apply (auto-fill + submit, `jobpipe/autoapply.py`)
Ryan memilih auto-submit pada 16 Nov 2026. Target: remote global, APAC, luar APAC bila JD menyebut sponsor visa; level entry + mid.

```
python3 job-search/pipeline.py autoapply plan            # jawaban per form; yang tertahan -> out/autoapply/PENDING.md
python3 job-search/pipeline.py autoapply plan <id>       # lihat setiap field + jawaban satu lowongan
python3 job-search/pipeline.py autoapply run --dry-run   # isi form + screenshot, TIDAK submit
python3 job-search/pipeline.py autoapply run             # submit (maks config.autoapply.max_per_run, 2 per perusahaan)
python3 job-search/pipeline.py autoapply answer <id> <field> "jawaban" [--all-jobs]
```

Aturan:
- Jawaban hanya dari `apply_profile.json` (fakta Ryan) dan `data/answers.json` (jawaban tersimpan / draft AI). Tidak ada tebakan.
  Nilai `null` di profil + pertanyaan wajib = lowongan ditahan, bukan dikirim.
- Hak kerja dijawab apa adanya: WNI, butuh sponsor di luar Indonesia. Demografi/EEO: tidak diisi, atau "tidak menjawab" bila wajib.
- Sebelum submit, setiap nilai dibaca ulang dari halaman; beda dengan plan = batal.
- `applied` hanya dicatat bila halaman konfirmasi Greenhouse tampil. Log: `data/apply_log.jsonl`.
- Persetujuan hukum (mis. arbitration agreement) dan esai tidak pernah diisi otomatis tanpa jawaban tersimpan.

**Verifikasi manusia.** Dari server/cloud, Greenhouse meminta kode 8 karakter yang dikirim ke email Ryan
("Security code for your application to <Company>"). Ryan mengizinkan Claude membaca inbox-nya untuk kode ini (21 Nov 2026).
Claude membaca kode lewat Gmail (pengirim `no-reply@us.greenhouse-mail.io`), memakai email terbaru yang dikirim
setelah form mulai menunggu, lalu meneruskannya ke browser. CAPTCHA tetap tidak diakali.
```
python3 job-search/pipeline.py autoapply run <id> --wait-code 600   # form terisi, browser menunggu (file NEED_CODE muncul)
python3 job-search/pipeline.py autoapply code <id> <KODE>           # kode dari email Greenhouse terbaru untuk perusahaan itu
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
