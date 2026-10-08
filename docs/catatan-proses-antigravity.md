# Catatan Proses Antigravity dan Qwen

Dokumen ini mencatat pekerjaan yang dilakukan pada 9 Oktober 2026 untuk menyiapkan vEtherTunel sebagai proyek kerja bersama: Codex berperan sebagai Engineering Manager, sementara Antigravity dan model lokal Qwen menjadi partner pemrograman. Catatan ini membedakan hasil yang sudah diverifikasi dari pekerjaan yang masih tertahan.

## Hasil yang sudah berhasil

### Rancangan vEtherTunel

- Repo dilengkapi konsep awal overlay jaringan Layer 3, arsitektur, prinsip keamanan, dan roadmap prototipe.
- Dokumen menyatakan dengan jelas bahwa repo saat ini masih berisi rancangan, belum implementasi tunnel.
- WireGuard dicatat sebagai kandidat teknologi, belum menjadi keputusan atau fitur yang sudah dibuat.

### Profil Qwen untuk proyek

- Dibuat [`../Modelfile.qwen-vether`](../Modelfile.qwen-vether) berdasarkan model Ollama `qwen2.5-coder:3b`.
- Model turunan berhasil dibuat dengan nama `qwen2.5-coder-vether` menggunakan:

  ```sh
  ollama create qwen2.5-coder-vether -f Modelfile.qwen-vether
  ```

- Uji prompt ringkas berhasil: Qwen dapat menyebut MVP sebagai overlay Layer 3, topologi hub-and-spoke, dan membedakan kandidat WireGuard dari implementasi yang sudah ada.
- Qwen juga diarahkan untuk memeriksa kode sebelum mengklaim fitur tersedia, menjaga keamanan peer/rute, dan tidak melakukan push paksa.
- Ini **bukan fine-tuning**. Bobot model dasar tidak berubah; konteks proyek ditambahkan melalui system prompt.
- Hasil uji menunjukkan model masih bisa menghasilkan istilah/terjemahan yang kurang tepat. Tinjau kode dan jawabannya sebelum dipakai.

### Akun Antigravity dan Git

- Menu profil Antigravity menampilkan akun `mitrautamagroup (GitHub)`.
- Ini membuktikan akun tersebut masuk ke profil Antigravity, tetapi tidak membuktikan kredensial Git HTTPS memakai akun yang sama.
- Push dari terminal repo yang benar ditolak GitHub dengan pesan bahwa akses ke `mitrautamagroup/vEtherTunel.git` ditolak untuk akun `citramediatech` (HTTP 403).
- Status Antigravity menunjukkan dua commit lokal menunggu push.

## Status yang belum berhasil

Push ke GitHub belum berhasil. Penyebab yang teramati adalah Git memakai kredensial `citramediatech`, walaupun profil Antigravity menunjukkan `mitrautamagroup`. Email akun saja tidak mengganti kredensial yang dipakai Git.

Model `qwen2.5-coder-vether` sudah tersedia di Ollama dan berhasil diuji dari terminal. Namun, selector Twinny yang terlihat pada pemeriksaan masih menunjukkan `qwen2.5-coder:3b`; jangan menganggap Twinny sudah memakai model turunan sampai nama model itu terlihat dipilih di selector dan mendapat respons.

## Langkah pemulihan autentikasi GitHub di macOS

1. Buka aplikasi **Keychain Access**.
2. Cari `github.com` dan periksa entri kredensial Internet Password yang dipakai Git. Pastikan entri yang akan diubah memang milik akun `citramediatech`; jangan hapus entri yang tidak dapat diidentifikasi.
3. Hapus atau perbarui hanya entri kredensial GitHub yang salah.
4. Kembali ke terminal Antigravity pada folder repo vEtherTunel, lalu jalankan:

   ```sh
   git push origin main
   ```

5. Jika Git meminta autentikasi, selesaikan alur login GitHub sebagai akun `mitrautamagroup` yang memiliki akses tulis ke repo.
6. Pastikan hasil push sukses dan indikator repo tidak lagi menunjukkan dua commit di depan `origin/main`.

Jika Git tidak meminta login lagi, hentikan percobaan berulang. Periksa helper kredensial Git yang aktif dan entri GitHub terkait terlebih dahulu. Jangan menaruh token atau kata sandi di chat, file repo, URL remote, atau perintah yang tersimpan di shell history.

## Prosedur penggunaan Qwen di Twinny

1. Pastikan Ollama berjalan dan `qwen2.5-coder-vether` tersedia (`ollama list`).
2. Pada panel Twinny, pilih provider **Ollama** dan pilih/masukkan nama model `qwen2.5-coder-vether`.
3. Mulai percakapan baru agar system prompt proyek diterapkan sejak awal.
4. Berikan pekerjaan dengan konteks repo yang relevan, misalnya `README.md`, `docs/architecture.md`, dan `docs/roadmap.md`.
5. Periksa diff, jalankan pemeriksaan yang sesuai, dan minta model menjelaskan bukti implementasi. Jangan menganggap keluaran model sebagai bukti bahwa kode telah berjalan.

## Batasan verifikasi

- Uji yang dilakukan adalah pembuatan model Ollama dan satu prompt ringkas; belum ada benchmark kualitas atau evaluasi kode.
- Implementasi software vEtherTunel belum dibuat atau diuji pada tahap ini.
- Push belum diverifikasi berhasil; dokumentasi ini dan commit terkait masih lokal sampai kredensial Git benar dan push sukses.
