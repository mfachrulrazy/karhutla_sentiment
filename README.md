# Karhutla Sentiment 🌿

Project NLP berbahasa Indonesia untuk pemula yang ingin menganalisis nuansa berita,
transcript YouTube, dan komentar penonton tentang kebakaran hutan dan lahan di Kalimantan.

**Input:** teks yang ditempelkan, URL artikel berita yang didukung, atau URL video YouTube
(untuk transcript atau komentar publik).
**Output:** prediksi sentiment `positive`/`neutral`/`negative`, distribusi sentiment,
keyword yang sering muncul, word cloud, serta file CSV/JSON yang dapat diunduh.

Aplikasi berjalan secara lokal menggunakan Python package open-source yang gratis dan
pretrained model yang dapat diunduh. Tidak diperlukan layanan AI inference berbayar,
database, atau GPU. Koneksi internet diperlukan untuk menginstal package, mengunduh model
sekali, dan mengambil konten dari URL. YouTube dan situs berita merupakan sumber konten
eksternal, bukan layanan open-source. Mode Comments memerlukan YouTube Data API v3 key;
mode teks, berita, dan transcript tidak memerlukannya.

## 1. Instalasi

Gunakan Python **3.11–3.13**. Jalankan dari folder project:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Pada Windows, gunakan `.venv\Scripts\activate` untuk mengaktifkan environment.
Extra `dev` menginstal test runner dan code checker. Gunakan `pip install -e .`
jika hanya ingin menjalankan aplikasi.

## 2. Menjalankan aplikasi

Untuk deployment dari GitHub, ikuti [panduan Streamlit Community Cloud](docs/DEPLOY_STREAMLIT.md).
Dashboard kini menggunakan mode `direct` secara default dan dapat berjalan sendiri:

```sh
streamlit run app.py --server.address 127.0.0.1
```

Untuk menjalankan API dan dashboard sekaligus:

```sh
python run.py
```

Perintah ini menjalankan API dan dashboard sekaligus. Buka <http://127.0.0.1:8501>,
pilih **Text**, klik **Load sample text**, lalu **Analyze sentiment**. Tekan Ctrl+C
untuk menghentikan kedua service. Gunakan perintah manual berikut jika ingin
menjalankan setiap service pada terminal terpisah.

### Menguji komentar YouTube

1. Tambahkan `YOUTUBE_API_KEY=your_actual_key` ke file `.env` yang diabaikan oleh Git.
   Aktifkan YouTube Data API v3 pada Google Cloud project yang terkait dengan key tersebut.
2. Restart aplikasi agar API membaca key.
3. Pilih **YouTube URL → Comments**, mulai dengan **10** komentar terbaru, lalu tempelkan
   URL video publik yang kolom komentarnya aktif.
4. Klik **Analyze sentiment**. Tabel dan persentase akan menampilkan hasil analisis komentar.

Bentuk API request:

```json
{"url":"https://www.youtube.com/watch?v=VIDEO_ID", "youtube_mode":"comments", "max_comments":10}
```

Aplikasi mengambil hingga 100 top-level comments terbaru berdasarkan urutan waktu API;
reply tidak disertakan. Setiap komentar yang dianalisis dihitung satu kali dalam summary.
Untuk komentar dengan beberapa segment, label ditentukan berdasarkan mayoritas label
segment; jika seri, digunakan jumlah score model. Score komentar merupakan rata-rata
score segment yang memiliki label terpilih. Komentar kosong, komentar tanpa kata, dan
komentar yang melebihi batas total karakter atau segment dilewati dengan pemberitahuan.
Komentar dapat memuat bahasa lain; versi ini mengasumsikan bahasa Indonesia dan belum
melakukan language detection. Hasil hanya menggambarkan sample yang berhasil diambil.

API key dikirim melalui header request backend, bukan melalui URL atau response.
Komentar yang dinonaktifkan, key yang belum diisi atau tidak valid, dan quota yang habis
akan menghasilkan pesan error yang menjelaskan masalahnya.

### Menjalankan API saja

Pada environment yang sudah aktif:

```sh
uvicorn karhutla.api:app --host 127.0.0.1 --port 8000
```

- Dokumentasi API: <http://127.0.0.1:8000/docs>
- Pemeriksaan koneksi: <http://127.0.0.1:8000/health>

Model dimuat saat **analisis pertama**, bukan saat startup. Ukuran model weights
sekitar 500 MB; request pertama dapat memerlukan beberapa menit, tergantung koneksi
dan komputer. Request berikutnya menggunakan kembali model yang sudah dimuat.
Inference dengan CPU didukung. Komputer dengan RAM 8 GB dapat digunakan sebagai
acuan awal; tutup aplikasi lain yang menggunakan banyak memory jika diperlukan.

### Menjalankan dashboard saja

Buka terminal kedua pada folder project:

```sh
source .venv/bin/activate
streamlit run app.py --server.address 127.0.0.1
```

Buka <http://127.0.0.1:8501>. Pilih **Text**, klik **Load sample text**, lalu
**Analyze sentiment**. Biarkan kedua terminal tetap berjalan. Tekan Ctrl+C
pada masing-masing terminal untuk menghentikannya.

Pada mode default `direct`, dashboard menjalankan fungsi analisis tanpa FastAPI server.
Atur `ANALYSIS_MODE=api` jika ingin dashboard memanggil FastAPI server.
Hasil disimpan pada dashboard session yang aktif dan tidak disimpan ke database.

## Fitur yang tersedia

| Fitur | Implementasi |
|---|---|
| Sentiment | Satu pretrained model Indonesian RoBERTa dengan tiga label |
| Berita | Extraction artikel Kompas, Antara, dan Detik menggunakan Trafilatura |
| YouTube | Caption bahasa Indonesia yang tersedia atau komentar publik melalui YouTube Data API v3 |
| Teks panjang | Sentence segmentation dan pemisahan berdasarkan token agar teks tidak terpotong tanpa pemberitahuan |
| Keywords | Kata yang sering muncul dan frasa dua kata yang berulang |
| Word cloud | Visualisasi frekuensi dengan stopword list yang dapat diedit |
| Bukti prediksi | Segment sumber, character offset, dan timestamp video jika tersedia |
| Download | CSV prediksi, JSON lengkap, dan PNG word cloud |
| Evaluasi | Template CSV dan script untuk menghasilkan metric serta confusion matrix |

Batas awal adalah 30.000 karakter teks dan 300 model segment per request.
Aplikasi menolak input yang melebihi batas secara eksplisit. Kegagalan extraction
tidak akan dilaporkan sebagai sentiment neutral.

## Contoh API

`POST /analyze` menerima **tepat satu** field: `text` atau `url`:

```sh
curl -X POST http://127.0.0.1:8000/analyze \
  -H 'Content-Type: application/json' \
  -d '{"text":"Terima kasih kepada petugas yang membantu warga."}'
```

Untuk artikel berita atau video, ganti request body dengan
`{"url":"YOUR_ARTICLE_OR_VIDEO_URL"}`. Gunakan `/docs` untuk mencoba request
secara interaktif tanpa menulis kode.

Hasil JSON berisi:

- `source`: jenis konten, URL, dan metadata judul/caption jika tersedia.
- `model`, `model_revision`, `analyzed_at`: informasi model, revisi, dan waktu analisis.
- `summary`: jumlah dan persentase untuk ketiga label; pada mode Comments, setiap komentar dihitung sekali.
- `segments`: teks, sentiment, score model, offset pada teks yang dibersihkan,
  dan timestamp caption jika tersedia.
- `comments`: hasil per komentar pada mode Comments.
- `keywords`, `word_frequencies`: statistik deskriptif frekuensi kata.
- `warnings`: keterbatasan input dan interpretasi hasil.

`GET /health` mengembalikan `status` dan `model_loaded`. Endpoint ini memeriksa
apakah API berjalan; tidak memverifikasi akses sumber, mengunduh, atau menguji model.

Error yang sudah diantisipasi mengembalikan `detail` yang dapat ditindaklanjuti dan
`code` yang dapat diproses program, seperti `unsupported_source`,
`transcript_unavailable`, `input_too_large`, atau `model_unavailable`.
Field request yang tidak valid menghasilkan validation response dari FastAPI.

## Struktur kode

```text
app.py                       Antarmuka Streamlit
run.py                       Menjalankan/menghentikan kedua service lokal sekaligus
karhutla/
  api.py                     Endpoint FastAPI
  schemas.py                 Struktur request dan response
  extraction.py              Pengambilan berita dan caption
  comments.py                Pengambilan komentar publik melalui YouTube Data API
  text.py                    Pembersihan teks, segmentation, dan penghitungan kata
  model.py                   Lazy model loading dan CPU inference
  analysis.py                Penyusunan hasil analisis akhir
  config.py                  Konfigurasi dari environment variable
  errors.py                  Error aplikasi yang dapat dipahami pengguna
data/
  sample.txt                 Teks demo sintetis, bukan ground truth evaluasi
  evaluation_template.csv    Template header untuk anotasi manual
scripts/
  evaluate.py                Evaluasi menggunakan data berlabel
tests/                       Automated test yang berjalan offline
```

Baca `schemas.py`, lalu `analysis.py`, untuk memahami alur utama.
Mulailah dengan teks yang ditempelkan sebelum melakukan debugging URL eksternal.

## Evaluasi model

Model yang digunakan adalah
[`w11wo/indonesian-roberta-base-sentiment-classifier`](https://huggingface.co/w11wo/indonesian-roberta-base-sentiment-classifier).
Model card mencantumkan lisensi MIT dan training menggunakan komentar/review
berbahasa Indonesia dari SmSA. **Performa pada berita dan caption tentang karhutla
belum dibuktikan melalui evaluasi khusus.**

1. Salin `data/evaluation_template.csv` menjadi `data/evaluation.csv`.
2. Kumpulkan sekitar 150–300 kalimat/segment pendek berbahasa Indonesia dari beberapa
   artikel dan video. Simpan referensi sumbernya dalam catatan penelitian.
3. Isi `text`, `label`, `source_group`, `source_type`, dan `split`.
4. Gunakan label `positive`, `neutral`, atau `negative`; source type `news` atau
   `youtube`; serta split `dev` atau `test`. Tempatkan setiap artikel/video dan
   salinan pemberitaannya hanya pada satu split. `source_group` mengidentifikasi
   kelompok tersebut, misalnya `article_01`.
5. Buat pedoman anotasi sebelum labeling. Neutral berarti tidak ada evaluasi
   positive/negative yang dinyatakan dengan jelas. Berita tentang kebakaran tidak
   otomatis menyatakan opini negatif. Jika memungkinkan, minta orang lain melakukan
   review pada sebagian data yang sama.
6. Gunakan `dev` untuk penyesuaian pipeline; pertahankan `test` tanpa perubahan
   hingga evaluasi akhir.

```sh
python scripts/evaluate.py data/evaluation.csv --split test
```

Script menulis `evaluation_results/report.json` berisi macro-F1, precision/recall/F1
per class, confusion matrix, dan hasil terpisah berdasarkan source type.
File `predictions.csv` juga dibuat untuk memeriksa kesalahan. Setiap baris harus
muat dalam satu model segment. Label diberikan secara manual, bukan menggunakan
prediksi model sebagai ground truth.

Project ini tidak menyertakan score evaluasi rekaan atau label evaluasi otomatis.
Sample text hanya digunakan untuk mencoba antarmuka.

## Test dan pemeriksaan kode

```sh
python -m pytest
ruff check .
```

Test default berjalan offline menggunakan fake model yang deterministik.
Test memeriksa kontrak API, aggregation, segmentation, penanganan error, logika
extraction, dan rendering dashboard; test tersebut **tidak** mengukur accuracy
pretrained model. Coba sample melalui API sebenarnya secara terpisah untuk
memverifikasi instalasi model.

## Konfigurasi

Jika diperlukan, salin `.env.example` menjadi `.env`. API dan dashboard membaca file ini.

| Variable | Default | Keterangan |
|---|---|---|
| `SENTIMENT_MODEL` | `w11wo/indonesian-roberta-base-sentiment-classifier` | Model ID atau direktori lokal |
| `SENTIMENT_MODEL_REVISION` | `ac452dcb…` (hash lengkap pada `.env.example`) | Revisi model yang di-pin |
| `MODEL_LOCAL_FILES_ONLY` | `false` | Hanya gunakan file dalam cache setelah model diunduh |
| `MODEL_CACHE_DIR` | `.cache/models` dalam project ini | Cache download model lokal |
| `MAX_TEXT_CHARACTERS` | `30000` | Panjang maksimum teks yang sudah dibersihkan untuk API |
| `MAX_SEGMENTS` | `300` | Jumlah maksimum model segment per request |
| `API_URL` | `http://127.0.0.1:8000` | Alamat API yang digunakan dashboard |
| `ANALYSIS_MODE` | `direct` | Analisis langsung dalam Streamlit; gunakan `api` untuk FastAPI |
| `YOUTUBE_API_KEY` | kosong | Hanya diperlukan untuk mengambil komentar publik YouTube |

Kotak input teks pada dashboard dibatasi hingga 30.000 karakter. API dapat
menggunakan batas berbeda melalui konfigurasi, hingga batas 100.000 karakter
pada request schema. Restart API setelah mengubah konfigurasi.

Model disimpan dalam folder `.cache/models` yang diabaikan oleh Git. Untuk alur
teks yang sepenuhnya offline, lakukan analisis pertama dengan koneksi internet,
lalu atur `MODEL_LOCAL_FILES_ONLY=true` dan restart API.
Extraction dari URL tetap memerlukan koneksi internet.

Jika mengganti model, gunakan model tiga class yang kompatibel dengan config yang
menyediakan label `positive`, `neutral`, dan `negative`. Aplikasi menolak mapping
`LABEL_0` yang ambigu. Kode model yang diunduh tidak dijalankan
(`trust_remote_code=False`), dan model weights dimuat menggunakan safetensors.

## Keterbatasan sumber dan troubleshooting

- **Extraction berita:** gunakan URL artikel langsung. Paywall, pembatasan situs,
  pagination, dan halaman dinamis dapat menghambat extraction lengkap. Periksa preview
  teks hasil extraction. Tempelkan teks jika pengambilan gagal. Untuk mendukung
  penerbit lain, tambahkan domain ke `NEWS_DOMAINS` pada `extraction.py` dan uji dahulu.
  Salah satu artikel yang diverifikasi selama pengembangan adalah
  [laporan ANTARA tentang pemadaman karhutla di Kalimantan Timur](https://www.antaranews.com/berita/5020525/pemerintah-63-kali-padamkan-karhutla-di-kaltim-sejak-awal-2025).
  Ketersediaan artikel dapat berubah.
- **YouTube:** mode Transcript hanya menggunakan caption bahasa Indonesia yang tersedia.
  Versi ini belum menyediakan audio transcription atau translation. Komentar tersedia
  melalui mode terpisah yang memerlukan API key. Library transcript open-source
  menggunakan antarmuka tidak resmi yang dapat berubah atau diblokir, terutama pada
  cloud server. Gunakan transcript yang ditempelkan sebagai fallback; proxy berbayar
  tidak diperlukan. Lihat [dokumentasi library](https://github.com/jdepoix/youtube-transcript-api).
- **Download model:** masalah koneksi pada penggunaan pertama menghasilkan
  `model_unavailable`. Periksa terminal API, koneksi internet, dan ruang disk.
  Aplikasi tidak menghasilkan sentiment rekaan ketika model tidak tersedia.
- **Video panjang:** tempelkan kutipan yang lebih pendek jika transcript melebihi batas.
- **Nuansa berita:** kutipan ucapan, evaluasi campuran, sarkasme, slang, dan laporan
  faktual tentang kejadian berbahaya dapat salah diklasifikasikan. MVP ini belum
  menyediakan speaker attribution atau target attribution.
- **Score:** score model bukan probabilitas kebenaran yang sudah dikalibrasi.
  Persentase distribusi menghitung segment, atau komentar pada mode Comments;
  bukan perkiraan opini publik atau ukuran tingkat keparahan kebakaran.
  Kalimat panjang dapat menghasilkan beberapa segment sehingga memengaruhi
  distribusi pada mode analisis segment.
- **Keywords:** kata yang sering muncul belum tentu penting atau mengandung sentiment.
  Edit `STOPWORDS` pada `text.py` hanya untuk penghitungan kata; pertahankan negasi
  pada input model.
- **Penggunaan lokal:** perintah yang disediakan menggunakan alamat komputer lokal.
  Pengambilan sumber eksternal dibatasi pada domain yang didukung dan tujuan publik.
  Public deployment memerlukan pembatasan resource dan jaringan tambahan;
  hal tersebut berada di luar cakupan MVP ini.

## Roadmap pembelajaran

1. Jalankan sample dan periksa API response.
2. Pelajari dan ubah penghitungan frekuensi kata.
3. Coba beberapa artikel dan video dengan caption; catat kegagalan extraction.
4. Susun dan anotasi CSV evaluasi, lalu periksa kesalahan model.
5. Tambahkan topic tag sederhana berbasis keyword jika diperlukan.
6. Pertimbangkan emotion detection atau fine-tuning setelah project dasar berjalan.

Pipeline tidak memiliki topic classifier yang di-hardcode. Untuk mengganti topik,
perbarui contoh dan teks antarmuka, lalu evaluasi model pada domain baru.

## Kredit open-source

Kode aplikasi menggunakan lisensi MIT; lihat `LICENSE`.
Dependency dan model tetap menggunakan lisensinya masing-masing:

| Project | Lisensi |
|---|---|
| Python | PSF |
| FastAPI / Uvicorn | MIT / BSD-3-Clause |
| Streamlit | Apache-2.0 |
| Transformers / PyTorch | Apache-2.0 / BSD-3-Clause |
| Sentiment model yang digunakan | MIT (sesuai model card) |
| Trafilatura 2.x | Apache-2.0 |
| youtube-transcript-api | MIT |
| httpx / requests / python-dotenv | BSD-3-Clause / Apache-2.0 / BSD-3-Clause |
| pandas / scikit-learn | BSD-3-Clause |
| wordcloud | MIT |
| Pydantic / pytest / Ruff | MIT |

Project ini tidak mengubah lisensi konten penerbit atau caption YouTube.
Konten yang disertakan hanya sample sintetis dan template anotasi kosong.
