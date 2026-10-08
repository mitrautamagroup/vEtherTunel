# Arsitektur Konseptual vEtherTunel

Dokumen ini merekam rancangan awal vEther: beberapa jaringan/perangkat virtual saling berkomunikasi sebagai satu overlay melalui tunnel. Ini adalah bahan diskusi untuk prototipe; detail di bawah belum menandakan fitur sudah diimplementasikan.

## Istilah

- **Node**: perangkat yang menjalankan agen vEtherTunel.
- **vEther**: jaringan overlay yang mengelompokkan node dengan kebijakan dan ruang alamat tertentu.
- **Hub**: node/gateway yang meneruskan paket antarnode dan membantu distribusi konfigurasi.
- **Tunnel**: kanal terenkripsi antar dua endpoint.
- **Control plane**: mekanisme autentikasi, pendaftaran peer, distribusi kunci publik, alamat, dan rute.
- **Data plane**: jalur paket IP pengguna di dalam tunnel.
- **Relay**: perantara paket saat dua peer tidak dapat membangun koneksi langsung.

## Sasaran MVP

MVP menghubungkan dua atau lebih node dalam satu vEther dan menguji komunikasi IP unicast melalui tunnel. Gunakan overlay Layer 3 terlebih dahulu: paket IP dirutekan berdasarkan alamat overlay, tanpa menjembatani broadcast Ethernet. Bridging Layer 2, discovery broadcast, dan transparansi terhadap protokol non-IP berada di luar MVP sampai kebutuhan dan risikonya jelas.

### Komponen

1. **Agen node** membuat/mengelola interface tunnel, menerapkan alamat overlay dan rute, serta melaporkan status.
2. **Hub** memvalidasi peer, mengirim konfigurasi peer yang diizinkan, dan meneruskan trafik pada topologi awal.
3. **Control plane** menyimpan identitas node, keanggotaan vEther, alamat, endpoint, dan kebijakan akses. Control plane tidak perlu berada pada jalur trafik setelah konfigurasi diterbitkan.
4. **Relay (opsional tahap berikutnya)** menjadi fallback saat NAT/firewall mencegah koneksi langsung atau hub yang dapat dicapai.

Implementasi dapat menggunakan WireGuard sebagai dasar tunnel karena menyediakan enkripsi dan autentikasi peer berbasis kunci. Ini masih pilihan rancangan, bukan keputusan yang mengunci protokol atau pustaka.

## Alur paket

```text
aplikasi pada Node A
  -> rute ke alamat overlay Node B
  -> interface vEther / tunnel terenkripsi
  -> Hub (MVP hub-and-spoke)
  -> tunnel ke Node B
  -> interface vEther Node B
  -> aplikasi tujuan
```

1. Admin membuat vEther dan menetapkan rentang alamat overlay yang tidak bertabrakan dengan LAN yang perlu dijangkau.
2. Node mendaftar dengan identitas dan kunci publik; kredensial pendaftaran memiliki masa berlaku dan cakupan terbatas.
3. Control plane memverifikasi node, lalu menerbitkan konfigurasi minimum: alamat, endpoint hub, peer yang diizinkan, serta rute.
4. Agen membangun tunnel terenkripsi ke hub dan memasang hanya rute overlay yang diperlukan.
5. Paket menuju alamat overlay peer dikirim melalui tunnel. Hub meneruskan paket ke peer yang berhak menerimanya.
6. Agen memantau handshake/keepalive dan mencoba membangun ulang tunnel saat koneksi pulih.

## Topologi dan evolusi

### Tahap 1: hub-and-spoke

Semua node membuat tunnel keluar ke hub. Model ini mudah untuk menguji provisioning, alamat, ACL, dan alur paket; cocok ketika node berada di balik NAT. Kekurangannya adalah hub menjadi jalur data dan potensi bottleneck/single point of failure.

### Tahap 2: direct peer-to-peer dengan relay fallback

Control plane membantu peer menemukan endpoint dan bertukar konfigurasi yang terautentikasi. Node mencoba tunnel langsung; bila gagal, trafik memakai relay. Perlu pengujian NAT yang ketat. Relay harus meneruskan hanya trafik peer yang sudah diotorisasi dan tidak memerlukan akses ke isi paket.

### Tahap 3: multi-hub / redundansi

Tambahkan lebih dari satu hub, pemilihan jalur, dan pemulihan ketika hub gagal. Tahap ini memerlukan definisi konsistensi konfigurasi dan kebijakan failover.

## Alamat dan rute

- Pilih subnet overlay privat yang dapat dikonfigurasi dan validasi benturan dengan rute lokal.
- Beri satu alamat unik per node dalam satu vEther.
- Terapkan rute spesifik overlay; jangan mengiklankan default route kecuali pengguna secara eksplisit mengaktifkan gateway penuh.
- Tolak konfigurasi dengan alamat/rute duplikat atau cakupan yang bertentangan.
- Untuk mengakses LAN di belakang node, tambahkan fitur gateway terpisah dengan persetujuan admin dan aturan forwarding eksplisit.

## Identitas, akses, dan keamanan

- Autentikasi setiap node; jangan menganggap alamat IP sebagai identitas.
- Batasi keanggotaan berdasarkan vEther dan ACL peer-to-peer, default-deny.
- Lindungi kunci privat pada perangkat; repositori hanya boleh berisi contoh konfigurasi tanpa rahasia.
- Rotasi/revoke kunci dan token pendaftaran harus mungkin tanpa menerbitkan ulang rahasia lain.
- Control plane harus memvalidasi input, mencegah pendaftaran ulang identitas, dan mencatat perubahan kebijakan.
- Batasi laju handshake dan permintaan pendaftaran; pertimbangkan perlindungan replay untuk pesan kontrol.
- Hindari logging payload aplikasi. Log metadata secukupnya untuk pemecahan masalah dan tetapkan retensi.
- Jangan membuka port publik atau mengaktifkan IP forwarding secara luas sebagai efek samping instalasi.

## Kegagalan dan observabilitas

Status per peer sebaiknya menampilkan identitas singkat, alamat overlay, endpoint aktif, waktu handshake terakhir, byte masuk/keluar, jalur (langsung/hub/relay), dan alasan kegagalan yang aman untuk ditampilkan. Reconnect harus memakai backoff agar outage tidak menghasilkan loop koneksi agresif. Perubahan rute harus dapat dipulihkan ketika agen dihentikan.

## Keputusan yang masih terbuka

- Platform awal: Linux saja atau Linux/macOS/Windows.
- Apakah hub mengakhiri tunnel per node atau bertindak sebagai control plane saja.
- Format dan transport API control plane.
- Distribusi kunci: provisioning manual untuk prototipe atau layanan enrollment.
- Apakah ada kebutuhan nyata untuk bridging Layer 2, multicast, atau discovery broadcast.
- Model operasi hub publik, self-hosted, atau keduanya.
- Target kapasitas, latensi, dan perilaku saat control plane tidak tersedia.

## Uji penerimaan prototipe

- Dua node pada jaringan berbeda dapat saling ping dan membuka koneksi TCP melalui alamat overlay.
- Peer yang tidak terdaftar tidak dapat membangun tunnel atau mengakses vEther.
- Revoke peer memutus aksesnya tanpa memengaruhi peer lain.
- Rute lokal yang bentrok dideteksi dan dilaporkan sebelum perubahan diterapkan.
- Tunnel pulih setelah koneksi jaringan terputus lalu tersedia kembali.
- Trafik tetap terenkripsi saat melintasi jaringan perantara; uji ini tidak mengasumsikan control plane menyembunyikan metadata koneksi.
- Penghentian agen menghapus atau mengembalikan interface/rute yang dipasang oleh agen.
