# Roadmap

Roadmap ini adalah usulan bertahap untuk membawa konsep vEtherTunel ke prototipe. Urutan dan target rilis belum ditetapkan.

## 0. Sepakati kebutuhan

- Tentukan perangkat dan sistem operasi yang akan menjadi node.
- Pilih skenario utama: akses antarperangkat, antar-LAN, atau keduanya.
- Tentukan kebutuhan Layer 3 dibanding bridging Ethernet Layer 2.
- Tetapkan threat model, siapa yang mengoperasikan hub, dan model enrollment.

## 1. Tunnel dua node

- Buat tunnel terenkripsi antara dua node dengan provisioning manual.
- Tetapkan alamat overlay dan rute sempit.
- Verifikasi ping dan TCP, restart, serta pembersihan konfigurasi.
- Dokumentasikan instalasi, keterbatasan, dan cara memeriksa status.

## 2. Hub dan kontrol akses

- Tambahkan hub hub-and-spoke untuk menghubungkan beberapa node.
- Kelola peer dan rute yang diizinkan dengan default-deny.
- Tambahkan status koneksi dan revoke peer.
- Uji benturan subnet, node tidak sah, reconnect, dan gangguan hub.

## 3. Pengalaman operasional

- Sediakan konfigurasi yang tervalidasi dan perintah status/diagnostik.
- Pastikan perubahan interface dan rute dapat dipulihkan dengan aman.
- Tambahkan pencatatan metadata minimal dan panduan pemecahan masalah.

## 4. Koneksi langsung dan relay

- Uji koneksi peer-to-peer pada kombinasi NAT/firewall yang beragam.
- Gunakan relay terenkripsi sebagai fallback bila koneksi langsung gagal.
- Ukur latensi, throughput, pemakaian relay, dan dampak kegagalan.

## 5. Evaluasi fitur lanjutan

- Multi-hub dan failover.
- Gateway ke LAN dengan aturan forwarding eksplisit.
- Bridging Layer 2 hanya bila ada kebutuhan yang tidak dapat dipenuhi routing Layer 3 dan setelah risiko broadcast serta isolasi dinilai.
