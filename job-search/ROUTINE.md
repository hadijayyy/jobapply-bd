# Playbook routine lowongan (Ryan Hadi)

Bahasa ke user: Indonesia santai, singkat. Materi lamaran: Inggris, tanpa tanda pisah em dash, tanpa klise ("passionate", "thrilled", "results-driven").

## Langkah tiap run
1. `git fetch origin ccr-b1068154-6sqdvu && git checkout ccr-b1068154-6sqdvu` lalu baca `job-search/profile.md` dan `job-search/seen.json`. State ada di branch itu; commit dan push update ke branch yang sama.
2. Cari (mode sesuai routine di bawah). Sumber: halaman ATS (jobs.ashbyhq.com, boards.greenhouse.io, jobs.lever.co), web3.career, cryptocurrencyjobs.co, remote3.co, LinkedIn Jobs, JobStreet, Kalibrr, Wellfound, halaman karier perusahaan, dan pencarian web untuk post hiring di X 7 hari terakhir ("we're hiring" partnerships / business development / channel APAC / Indonesia remote).
3. Buang yang url-nya sudah ada di `seen.json` (jobs atau rejected).
4. Verifikasi tiap kandidat dengan membuka halaman aslinya (firecrawl_scrape dengan maxAge 0 untuk halaman Ashby/Greenhouse/Lever yang dirender JS; WebFetch sering tidak cukup). Buang kalau: closed, sudah lebih dari 7 hari dan tidak ada deadline yang belum lewat, tidak menerima kandidat di Indonesia / WIB, hybrid atau onsite di luar Jakarta, atau komisi saja / MLM / deposit.
5. Tandai red flag: minta bayar atau deposit, rekrut cuma lewat DM atau Gmail pribadi, minta connect wallet atau seed phrase, gaji tidak masuk akal, perusahaan tidak bisa diverifikasi.
6. Jangan mengarang gaji, syarat, deadline. Tidak tertulis = "tidak disebutkan".
7. Ambil maksimal 10, urut paling cocok. Format per lowongan: posisi + perusahaan + link asli; lokasi/eligibility; gaji; syarat utama; kenapa cocok + gap; cara melamar + deadline; red flag. Tutup dengan satu kalimat: mana yang dilamar duluan dan kenapa.
8. Kalau tidak ada yang baru dan lolos: JANGAN kirim apa-apa dan jangan kirim notifikasi. Selesai.
9. Kirim hasil lewat PushNotification (ringkas: jumlah dan 1-3 judul teratas) dan tulis daftar lengkap sebagai jawaban akhir sesi. Tambahkan yang terkirim ke `seen.json` (`jobs`), commit, push.

## Auto apply (diizinkan user, level "Sedang")
User memberi izin eksplisit (12 Nov 2026) untuk melamar otomatis. Batasan yang tetap berlaku:
- Kirim hanya kalau SEMUA benar: tidak ada red flag; perusahaan terverifikasi (domain resmi, halaman karier sendiri / ATS resmi); kecocokan sedang ke atas; tidak ada syarat keras yang tidak dimiliki Ryan (contoh: lisensi WPE/WAPERD, bahasa Mandarin wajib, pengalaman crypto wajib, 7+ tahun di industri tertentu, residensi di negara lain); lowongan terbuka untuk kandidat di Indonesia.
- Jalur: email ke alamat rekrutmen yang tercantum publik di halaman lowongan (Gmail send_message). Satu email per lowongan, tanpa mass-mail. Isi: cover letter 150 sampai 250 kata dalam bahasa Inggris dengan 2 bukti kerja berangka dari profile.md saja. Jangan mengarang angka, tanggal, atau klaim. Kalau tool tidak bisa melampirkan CV, buat DRAFT Gmail (bukan kirim) dan laporkan.
- Jalur form (Ashby, Greenhouse, Lever, Workable): tidak ada browser terautentikasi di sesi routine. Jangan coba submit lewat skrip atau bot. Siapkan paket di `job-search/applications/<perusahaan>-<role>.md` (cover letter, jawaban form, CV change log) dan laporkan sebagai "siap dilamar, tinggal submit".
- Dilarang: LinkedIn Easy Apply otomatis, DM, connection request, melamar ke lowongan yang tidak lolos butuh verifikasi, mengirim materi dengan placeholder `[METRIC?]`.
- Catat tiap pengiriman di `seen.json` bagian `applications` (url, tanggal, jalur, status) dan sebutkan di laporan ("Terkirim otomatis" vs "Draft" vs "Siap submit manual").
- Follow-up: jangan kirim follow-up otomatis. Cukup ingatkan user di laporan hari ke-5 dan ke-10.

## Routine 07:00 WIB (utama)
Cari semua role target: Enterprise Sales / AE, BD / Partnerships Manager, Channel / Partner Manager, Head / Senior BD, remote APAC / global yang menerima Indonesia (juga catat Jakarta hybrid sebagai catatan terpisah kalau sangat cocok).

## Routine 18:00 WIB (freelance / sampingan)
Cari hanya kerja sampingan: konsultan BD, fractional BD / partnerships, freelance lead generation / sales (bukan komisi saja), kontrak jangka pendek, serta kontes atau bounty berbayar yang relevan (pisahkan di bagian sendiri). Aturan verifikasi dan red flag sama. Auto apply untuk freelance: hanya siapkan draft Gmail, jangan kirim.
