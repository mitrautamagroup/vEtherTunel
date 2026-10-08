# Catatan Proses Antigravity dan Qwen

Dokumen ini mencatat pekerjaan yang dilakukan pada 9 Oktober 2026 untuk menyiapkan vEtherTunel sebagai proyek kerja bersama: Codex berperan sebagai Engineering Manager, sementara Antigravity dan model lokal Qwen menjadi partner pemrograman. Catatan ini membedakan hasil yang sudah diverifikasi dari pekerjaan yang masih tertahan.

## Hasil yang sudah berhasil

### Rancangan vEtherTunel

- Repo dilengkapi konsep awal overlay jaringan Layer 3, arsitektur, prinsip keamanan, dan roadmap prototipe.
- Repo memuat prototipe QUIC localhost untuk enrollment, ACL, pesan teks, serta framing/relay IP userspace dengan validasi alamat. Ini belum implementasi tunnel IP karena tidak ada adapter TUN/NetworkExtension atau routing OS.
- Pada draf awal, WireGuard sempat dicatat sebagai kandidat. Keputusan pemilik proyek pada 9 Oktober 2026 menetapkan protokol aplikasi vEtherTunel di atas QUIC/TLS 1.3 tanpa WireGuard. Prototipe menerapkan enrollment/control stream, envelope v1, ACL peer, pesan teks DATAGRAM, dan validasi/relay IP userspace di localhost.
- Untuk eksperimen di Mac, dokumentasi Apple menyediakan `NEPacketTunnelProvider` untuk interface virtual Layer 3 dan `NEEthernetTunnelProvider` untuk tunnel frame link-layer kustom. Agen perlu dibuat sebagai Network Extension dan entitlement yang sesuai harus tersedia; Mac tidak otomatis memiliki interface bernama vEtherTunel. Lihat tautan resmi di dokumen arsitektur.
- Persyaratan keselamatan Mac ditambahkan: tidak memakai KEXT, tidak mengubah SIP/boot/system volume/startup, tidak memakai default route/DNS pada MVP, tunnel harus opt-in, dan harus ada stop/rollback. Dukungan macOS belum dipastikan sebelum entitlement/distribusi dan uji VM/Mac terpisah tersedia.
- Ditambahkan `AGENTS.md` di root repo sebagai panduan workspace Antigravity: peran partner implementasi, batas macOS, arsitektur tanpa WireGuard, kebijakan bukti/verifikasi, dan aturan menjaga rahasia. Aturan workspace Antigravity mengenali `AGENTS.md` dan `GEMINI.md`.
- Ollama dapat menjalankan Qwen lokal untuk dipilih Twinny sebagai provider model. Ini bukan kanal komunikasi langsung antara Twinny/Antigravity dan chat Codex. Pada pemeriksaan terakhir, selector Twinny masih menampilkan `qwen2.5-coder:3b`, jadi model khusus harus dipilih secara eksplisit sebelum dipakai di Twinny.

### Profil Qwen untuk proyek

- Dibuat [`../Modelfile.qwen-vether`](../Modelfile.qwen-vether) berdasarkan model Ollama `qwen2.5-coder:3b`.
- Model turunan berhasil dibuat dengan nama `qwen2.5-coder-vether` menggunakan:

  ```sh
  ollama create qwen2.5-coder-vether -f Modelfile.qwen-vether
  ```

- Uji prompt ringkas berhasil: Qwen dapat menyebut MVP sebagai overlay Layer 3 dan topologi hub-and-spoke. Jawaban awalnya masih menyebut WireGuard karena mengikuti draf pada saat uji; keputusan baru di bawah menggantikan konteks itu.
- Qwen juga diarahkan untuk memeriksa kode sebelum mengklaim fitur tersedia, menjaga keamanan peer/rute, dan tidak melakukan push paksa.
- Ini **bukan fine-tuning**. Bobot model dasar tidak berubah; konteks proyek ditambahkan melalui system prompt.
- Hasil uji menunjukkan model masih bisa menghasilkan istilah/terjemahan yang kurang tepat. Tinjau kode dan jawabannya sebelum dipakai.

### Akun Antigravity dan Git (riwayat sebelum autentikasi diperbaiki)

- Menu profil Antigravity menampilkan akun `mitrautamagroup (GitHub)`.
- Ini membuktikan akun tersebut masuk ke profil Antigravity, tetapi tidak membuktikan kredensial Git HTTPS memakai akun yang sama.
- Push dari terminal repo yang benar ditolak GitHub dengan pesan bahwa akses ke `mitrautamagroup/vEtherTunel.git` ditolak untuk akun `citramediatech` (HTTP 403).
- Status Antigravity menunjukkan dua commit lokal menunggu push.

## Status GitHub dan implementasi

Pada 9 Oktober 2026, branch `main` berhasil di-push ke `https://github.com/mitrautamagroup/vEtherTunel.git` sebagai akun `mitrautamagroup`; remote `main` terverifikasi di commit `626eebd`. Push dilakukan memakai GitHub CLI credential helper khusus perintah, karena helper Git global masih memakai kredensial lama `citramediatech`.

Perubahan prototipe userspace yang sekarang dikerjakan belum dipush sampai ditinjau dan disimpan dalam commit.

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

- Uji yang dilakukan sebelumnya adalah pembuatan model Ollama dan satu prompt ringkas; belum ada benchmark kualitas atau evaluasi kode.
- Uji manual loopback dengan dua proses node berhasil untuk enrollment QUIC, pengiriman teks, dan satu envelope IPv4 header-only. Detail runtime dan batas uji ada di `docs/prototipe-quic.md`. Belum diuji ping, routing OS, IPv6, NAT, atau koneksi lintas-host.
