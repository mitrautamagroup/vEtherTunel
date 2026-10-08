# vEtherTunel

**vEtherTunel** adalah konsep jaringan Ethernet virtual (vEther) yang memungkinkan beberapa perangkat atau jaringan virtual berkomunikasi melalui tunnel terenkripsi di atas internet atau jaringan lain.

Dokumen ini menjadi rancangan awal, bukan klaim bahwa implementasi perangkat lunak sudah tersedia. Fokus MVP adalah konektivitas IP antarnode yang sederhana, aman, dan dapat diuji.

## Tujuan

- Menghubungkan beberapa vEther/node lintas jaringan tanpa perlu berada pada LAN fisik yang sama.
- Memberi tiap node alamat virtual yang stabil dan rute ke peer yang diizinkan.
- Menggunakan tunnel terenkripsi, dengan relay sebagai jalur koneksi ketika koneksi langsung tidak memungkinkan.
- Menyediakan konfigurasi dan status koneksi yang mudah dipahami.

## Rancangan awal

MVP memakai **overlay Layer 3** dengan protokol vEtherTunel sendiri untuk enrollment node, keanggotaan vEther, kebijakan, dan enkapsulasi paket. Agen menghubungkan interface vEther lokal ke overlay dan meneruskan hanya rute yang diizinkan. Protokol transport memakai QUIC dengan keamanan TLS 1.3; vEtherTunel tidak memakai WireGuard dan tidak membuat algoritma kriptografi sendiri. Bridging Ethernet Layer 2 menjadi opsi tahap lanjutan setelah isolasi broadcast dan keamanan diuji.

Topologi awal menggunakan hub-and-spoke melalui satu gateway/tunnel hub. Setelah protokol kontrol dan autentikasi stabil, koneksi peer-to-peer langsung dapat ditambahkan dengan relay sebagai fallback. Rincian alur paket, identitas node, kontrol akses, dan batas MVP ada di [`docs/architecture.md`](docs/architecture.md). Tahapan kerja ada di [`docs/roadmap.md`](docs/roadmap.md).

Catatan proses menyiapkan model Qwen lokal, menghubungkannya ke Twinny/Antigravity, dan status publikasi GitHub ada di [`docs/catatan-proses-antigravity.md`](docs/catatan-proses-antigravity.md).

## Status

- [x] Konsep dan batas rancangan awal didokumentasikan.
- [ ] Prototipe tunnel dua node.
- [ ] Hub yang mengelola peer dan rute.
- [ ] Uji reconnect, isolasi peer, dan skenario NAT.
- [ ] Evaluasi kebutuhan bridging Layer 2.

## Prinsip keamanan

Setiap peer harus terautentikasi dan hanya menerima rute/akses yang diizinkan. Kunci privat tidak boleh disimpan di repositori. Port forwarding atau akses jaringan tidak boleh dibuka lebih luas daripada kebutuhan. Lihat bagian keamanan di dokumen arsitektur sebelum membuat prototipe.

## Kontribusi

Untuk tahap konsep, silakan ajukan kebutuhan platform, skenario penggunaan, dan batasan jaringan melalui issue atau pull request. Perubahan protokol sebaiknya menyertakan threat model dan rencana pengujian.
