# Deployment dari GitHub ke Streamlit Community Cloud

Project sudah mendukung `ANALYSIS_MODE=direct`: dashboard memanggil fungsi analisis
secara langsung tanpa FastAPI server terpisah. Endpoint FastAPI tetap dapat digunakan
secara lokal atau melalui deployment terpisah. Deployment Streamlit ini menyediakan
dashboard, bukan public FastAPI endpoint.

## 1. Buat repository GitHub

Masuk ke <https://github.com/new>, lalu buat repository bernama `karhutla-sentiment`.
Untuk alur berikut, jangan tambahkan README, LICENSE, atau `.gitignore` dari GitHub
karena file tersebut sudah tersedia dalam project.

Dari terminal pada folder project, jalankan:

```sh
git init -b main
git add .
git diff --cached --stat
```

Periksa daftar file sebelum commit. `.env`, `.venv/`, `.cache/`, `*.egg-info/`, dan
`.streamlit/secrets.toml` tidak boleh ikut di-upload. `.gitignore` sudah mengabaikannya.
File `.env.example` dan `.streamlit/secrets.toml.example` berisi placeholder dan boleh
disertakan. Jangan menempelkan API key pada file contoh.

```sh
git commit -m "Prepare sentiment app for Streamlit deployment"
git remote add origin https://github.com/YOUR_USERNAME/karhutla-sentiment.git
git push -u origin main
```

Ganti `YOUR_USERNAME` dengan username GitHub. Selesaikan proses autentikasi GitHub
yang diminta terminal atau gunakan GitHub Desktop untuk melakukan push.
Jika repository lokal sudah ada, gunakan repository tersebut tanpa mengulang `git init`.

## 2. Buat aplikasi Streamlit

1. Buka <https://share.streamlit.io/> dan masuk menggunakan akun yang dapat mengakses repository.
2. Klik **Create app**, lalu pilih deployment dari repository GitHub yang sudah ada.
3. Pilih repository `YOUR_USERNAME/karhutla-sentiment`.
4. Pilih branch `main` dan main file path `app.py`.
5. Buka **Advanced settings** dan pilih Python **3.13**, sesuai environment lokal yang diuji.

`requirements.txt` memasang project dari `pyproject.toml` dan menggunakan PyTorch
CPU wheel pada Linux. Jangan memilih `run.py` sebagai main file: Community Cloud
menjalankan Streamlit secara langsung.

## 3. Isi Secrets

Pada **Advanced settings → Secrets**, masukkan:

```toml
ANALYSIS_MODE = "direct"
MODEL_LOCAL_FILES_ONLY = "false"
YOUTUBE_API_KEY = "your_actual_youtube_api_key"
```

Gunakan API key milik Anda pada kolom Secrets, bukan pada repository GitHub.
Contoh konfigurasi tersedia pada `.streamlit/secrets.toml.example`.
`API_URL` tidak diperlukan dalam mode direct. Jangan gunakan path model dari komputer lokal.

Jika key Google dibatasi menggunakan IP komputer lokal atau HTTP referrer,
sesuaikan pembatasannya agar request backend cloud diizinkan. Tetap batasi API key
ke YouTube Data API v3. Seluruh pengunjung menggunakan quota key yang sama.

## 4. Deploy dan uji

1. Simpan pengaturan, lalu klik **Deploy**.
2. Tunggu proses instalasi dependency. Periksa build log jika terjadi kegagalan.
3. Setelah dashboard terbuka, pilih **Text → Load sample text → Analyze sentiment**.
4. Analisis pertama mengunduh model sekitar 500 MB dan memuatnya ke memory server.
5. Setelah sample berhasil, coba **YouTube URL → Comments** dengan 10 komentar.
6. Bagikan URL aplikasi dengan domain `streamlit.app` yang diberikan Streamlit.

Deployment cloud belum dapat diverifikasi sampai proses build dan analisis pertama
dijalankan pada akun Streamlit Anda. Model inference menggunakan resource cloud;
memory yang tidak mencukupi dapat menyebabkan restart atau error resource.
Transcript YouTube dapat diblokir pada cloud server; mode Comments menggunakan API resmi.

## Pembaruan aplikasi

```sh
git add .
git commit -m "Update application"
git push
```

Streamlit membaca perubahan dari branch yang dipilih. Kelola API key melalui
pengaturan Secrets aplikasi; jangan menambahkan `.env` ke GitHub.

## Menjalankan secara lokal

Hanya dashboard, dengan analisis langsung:

```sh
source .venv/bin/activate
streamlit run app.py --server.address 127.0.0.1
```

Untuk dashboard yang memanggil FastAPI, atur `ANALYSIS_MODE=api` dalam `.env`,
lalu jalankan `python run.py`. Nilai default adalah `direct`.

## Dokumentasi resmi

- [Deployment Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [Dependency aplikasi](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
- [Secrets management](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
