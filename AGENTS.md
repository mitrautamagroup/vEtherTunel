# Panduan engineering vEtherTunel

Antigravity dan coding agent lain bekerja sebagai partner implementasi untuk proyek ini. Ikuti batas dan urutan kerja berikut pada setiap perubahan.

## Peran dan alur kerja

- Baca `README.md`, `docs/architecture.md`, dan `docs/roadmap.md` sebelum mengubah desain atau protokol.
- Kerjakan potongan kecil yang dapat ditinjau. Jelaskan file yang diubah, keputusan, batas fitur, dan risiko sebelum meminta review.
- Perbarui dokumentasi dan status roadmap ketika implementasi berubah. Jangan menyebut fitur selesai sebelum kode serta bukti verifikasinya tersedia.
- Jangan menimpa perubahan lokal atau melakukan push/merge eksternal tanpa instruksi eksplisit pengguna.
- Jangan memasukkan kredensial, token, private key, sertifikat produksi, atau data jaringan privat ke repo, log, maupun chat.
- Jangan menjalankan test suite atau membuat tes baru kecuali pengguna memintanya secara eksplisit. Jika kode belum diuji, nyatakan batas itu.

## Batas arsitektur

- Protokol aplikasi milik proyek adalah vEtherTunel; transport aman memakai QUIC/TLS 1.3 dan tidak menggunakan WireGuard.
- Jangan membuat algoritma kriptografi, key exchange, atau cipher sendiri.
- Mulai dari Layer 3 dan hub-and-spoke. Layer 2, broadcast, discovery, direct peer, dan relay fallback bukan bagian implementasi awal.
- Prototipe userspace yang tidak memasang interface atau rute harus disebut prototipe transport, bukan tunnel IP yang sudah berfungsi.
- Terapkan default-deny untuk identitas/peer dan validasi setiap panjang, versi, tipe payload, membership, serta tujuan.

## Keselamatan macOS

- Jangan membuat atau memasang KEXT, mengubah SIP, boot arguments, volume sistem, launch daemon, firewall, DNS, atau konfigurasi jaringan host.
- Jangan menjalankan `sudo`, `route`, atau `ifconfig` untuk mengubah jaringan.
- MVP awal tidak mengelola TUN, NetworkExtension, rute, atau interface. Semua aktivitas jaringan harus opt-in dan terbatas pada socket userspace.
- Integrasi NetworkExtension hanya boleh menjadi tahap terpisah dengan persetujuan pengguna dan uji pada VM/Mac uji; tunnel selalu mati secara default, rute overlay sempit, tersedia stop/rollback.

## Verifikasi dan komunikasi

- Jangan mengklaim tes, interoperabilitas, keamanan, atau keberhasilan koneksi yang belum benar-benar dijalankan dan diamati.
- Tampilkan perintah verifikasi yang aman dan hasilnya. Hindari tes yang mengubah rute, membuka port publik, atau mengubah konfigurasi host tanpa persetujuan pengguna.
- Jika agent Antigravity tidak memiliki kuota atau tidak dapat menyelesaikan langkah, laporkan keterbatasan itu. Jangan menganggap model lokal sudah berkomunikasi langsung dengan Codex.
