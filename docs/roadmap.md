# Roadmap

Roadmap ini adalah usulan bertahap untuk membawa konsep vEtherTunel ke prototipe. Urutan dan target rilis belum ditetapkan.

## Status implementasi saat ini

- Prototipe Python userspace tersedia untuk QUIC/TLS 1.3 hub localhost, enrollment node, ACL peer, envelope v1, pesan teks, dan jalur relay IP dengan validasi header/alamat.
- CLI hanya mendemonstrasikan teks. Belum ada adapter TUN/NetworkExtension, routing OS, atau uji IP/lintas-host. Ikuti `docs/prototipe-quic.md`.
- Antigravity mendapat panduan proyek di `AGENTS.md`; minta partner meninjau atau melanjutkan satu milestone kecil setiap sesi, lalu laporkan file, bukti, dan keterbatasan.

## 0. Sepakati kebutuhan

- Tentukan perangkat dan sistem operasi yang akan menjadi node. Untuk macOS, validasi entitlement, jalur distribusi, dan prototype `NEPacketTunnelProvider` di VM/Mac uji sebelum menjanjikan dukungan; evaluasi provider Ethernet Layer 2 sebagai tahap terpisah.
- Tinjau batas keselamatan macOS: tanpa KEXT/SIP/boot/startup modifications, tunnel opt-in, tanpa default route/DNS pada MVP, stop/rollback terbukti.
- Pilih skenario utama: akses antarperangkat, antar-LAN, atau keduanya.
- Tentukan kebutuhan Layer 3 dibanding bridging Ethernet Layer 2.
- Tetapkan threat model, siapa yang mengoperasikan hub, dan model enrollment.

## 1. Tunnel dua node

- [x] Kerangka transport userspace QUIC localhost dengan enrollment, framing, ACL, dan demonstrasi pesan teks.
- Rancang spesifikasi protokol aplikasi vEtherTunel: identitas, enrollment, envelope paket, versi, batas ukuran, dan perilaku error.
- Bangun sesi QUIC/TLS 1.3 antara dua agen; jangan memakai WireGuard atau membuat algoritma kriptografi sendiri.
- Hubungkan interface TUN vEtherTunel ke satu interface/segmen vEther lokal dan tetapkan rute overlay sempit.
- Verifikasi ping dan TCP, restart, serta pembersihan konfigurasi.
- Dokumentasikan instalasi, keterbatasan, dan cara memeriksa status.
- Pastikan uji macOS memakai overlay route yang sempit dan prosedur deactivate/rollback yang terdokumentasi.

## 2. Hub dan kontrol akses

- Tambahkan hub hub-and-spoke untuk menghubungkan beberapa node.
- Kelola keanggotaan vEther, peer, dan rute yang diizinkan dengan default-deny.
- Kirim control messages melalui QUIC streams dan paket data melalui QUIC DATAGRAM; dokumentasikan fallback hanya setelah evaluasi.
- Tambahkan status koneksi dan revoke peer.
- Uji benturan subnet, node tidak sah, reconnect, dan gangguan hub.
- Nyatakan bahwa hub dapat membaca paket pada MVP; rancang enkripsi end-to-end sebelum relay yang tidak dipercaya dipakai.

## 3. Pengalaman operasional

- Sediakan konfigurasi yang tervalidasi dan perintah status/diagnostik.
- Pastikan perubahan interface dan rute dapat dipulihkan dengan aman.
- Tambahkan pencatatan metadata minimal dan panduan pemecahan masalah.

## 4. Koneksi langsung dan relay

- Uji koneksi peer-to-peer pada kombinasi NAT/firewall yang beragam.
- Uji relay sebagai fallback bila koneksi langsung gagal; tetapkan apakah relay meneruskan sesi QUIC end-to-end atau mengakhiri transport, lalu dokumentasikan batas kepercayaan dan kebutuhan enkripsi end-to-end.
- Ukur latensi, throughput, pemakaian relay, dan dampak kegagalan.

## 5. Evaluasi fitur lanjutan

- Multi-hub dan failover.
- Gateway ke LAN dengan aturan forwarding eksplisit.
- Bridging Layer 2 antar-vEther hanya bila ada kebutuhan yang tidak dapat dipenuhi routing Layer 3 dan setelah risiko broadcast, loop, isolasi, MTU, serta storm control dinilai.
