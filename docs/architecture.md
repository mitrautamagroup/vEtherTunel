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

1. **Agen node** menghubungkan interface vEther lokal ke overlay, menerapkan alamat/rute yang diizinkan, dan melaporkan status.
2. **Hub** menjalankan control plane vEtherTunel, memvalidasi peer, mengirim konfigurasi peer yang diizinkan, dan meneruskan trafik pada topologi awal.
3. **Control plane** menyimpan identitas node, keanggotaan vEther, alamat, endpoint, dan kebijakan akses. Control plane tidak perlu berada pada jalur trafik setelah konfigurasi diterbitkan.
4. **Relay (opsional tahap berikutnya)** menjadi fallback saat NAT/firewall mencegah koneksi langsung atau hub yang dapat dicapai.

## Protokol vEtherTunel

vEtherTunel memiliki protokol aplikasi sendiri di atas QUIC. Protokol ini mendefinisikan enrollment, identitas node, keanggotaan vEther, kebijakan rute/peer, jenis payload, dan bagaimana gateway mengirim paket ke node tujuan. QUIC menyediakan transport UDP dengan sesi terenkripsi dan terautentikasi menggunakan TLS 1.3; vEtherTunel tidak memakai WireGuard dan tidak merancang cipher, key exchange, atau algoritma kriptografi sendiri. QUIC/TLS dipilih sebagai fondasi transport yang ditinjau dan distandardkan; spesifikasi primer: [RFC 9000](https://www.rfc-editor.org/rfc/rfc9000.html) dan [RFC 9001](https://www.rfc-editor.org/rfc/rfc9001.html).

### Jalur data dan kontrol

- **Control plane** memakai QUIC streams yang andal untuk enrollment, perubahan keanggotaan, pertukaran konfigurasi, keepalive/status, dan pembaruan kebijakan.
- **Data plane MVP** memakai QUIC DATAGRAM (RFC 9221) untuk paket IP overlay agar batas paket dipertahankan dan paket tidak menunggu retransmisi paket lain. Datagram dapat hilang saat jaringan padat atau receiver kewalahan; QUIC memberi congestion control tetapi aplikasi tetap harus menangani kehilangan paket sesuai sifat IP. Validasi ukuran harus mengikuti batas QUIC dan path MTU untuk menghindari fragmentasi.
- Agen membuat interface virtual Layer 3 (TUN atau padanan platform), lalu memasang rute overlay terbatas. Interface vEther yang ada di perangkat, misalnya veth0 pada appliance, bertindak sebagai LAN/segmen lokal di belakang gateway. Gateway merutekan trafik yang diizinkan antara segmen itu dan node vEther remote.
- Envelope data vEtherTunel versi awal membawa `version`, `vEther_id`, `source_node_id`, `destination_node_id`, `payload_type`, dan payload IPv4/IPv6. Batas ukuran, validasi panjang, dan versi harus eksplisit. Header aplikasi tidak membawa key atau cipher buatan sendiri.
- Untuk MVP hub-and-spoke, hub menjadi titik routing tepercaya: paket terlindungi saat melewati jaringan luar, tetapi hub dapat melihat paket setelah terminasi sesi QUIC. Ini harus dinyatakan dalam threat model. Enkripsi end-to-end antarnode dapat menjadi desain tahap lanjut bila dibutuhkan.
- Setiap node memiliki identitas kriptografis yang diverifikasi saat enrollment. Hub menerapkan default-deny, memeriksa keanggotaan dan izin tujuan sebelum meneruskan paket, serta mendukung pencabutan identitas. Sertifikat/kunci privat tidak dikirim lewat chat atau disimpan dalam repo.

vEtherTunel mendefinisikan aturan dan framing protokolnya sendiri, tetapi memakai QUIC/TLS untuk fungsi transport aman. QUIC DATAGRAM merupakan ekstensi standar, bukan fitur otomatis di setiap implementasi; dukungan peer harus dinegosiasikan. Rancangan ini menghindari pembuatan kriptografi baru yang belum ditinjau. Referensi primer untuk datagram: [RFC 9221](https://www.rfc-editor.org/rfc/rfc9221.html).

## Alur paket

```text
aplikasi pada Node A
  -> rute ke alamat overlay Node B
  -> interface TUN vEtherTunel / paket QUIC DATAGRAM
  -> Hub (MVP hub-and-spoke)
  -> sesi QUIC ke Node B
  -> interface vEther Node B
  -> aplikasi tujuan
```

1. Admin membuat vEther dan menetapkan rentang alamat overlay yang tidak bertabrakan dengan LAN yang perlu dijangkau.
2. Node mendaftar dengan identitas dan kunci publik; kredensial pendaftaran memiliki masa berlaku dan cakupan terbatas.
3. Control plane memverifikasi node, lalu menerbitkan konfigurasi minimum: alamat, endpoint hub, peer yang diizinkan, serta rute.
4. Agen membuat sesi QUIC terautentikasi ke hub dan memasang hanya rute overlay yang diperlukan.
5. Paket IP dibungkus sebagai envelope vEtherTunel dan dikirim memakai QUIC DATAGRAM. Hub memvalidasi keanggotaan/ACL, lalu meneruskan paket kepada peer yang diizinkan.
6. Agen memantau status sesi QUIC dan mencoba membangun ulang koneksi dengan backoff saat jaringan pulih.

## Topologi dan evolusi

### Tahap 1: hub-and-spoke

Semua node membuka sesi QUIC keluar ke hub. Model ini mudah untuk menguji enrollment, alamat, ACL, dan alur paket; cocok ketika node berada di balik NAT. Kekurangannya adalah hub menjadi jalur data, titik kepercayaan, dan potensi bottleneck/single point of failure.

### Tahap 2: direct peer-to-peer dengan relay fallback

Control plane membantu peer menemukan endpoint dan bertukar konfigurasi yang terautentikasi. Node mencoba sesi QUIC langsung; bila gagal, trafik memakai relay. Perlu pengujian NAT yang ketat. Relay harus meneruskan hanya trafik peer yang sudah diotorisasi. Jika relay hanya meneruskan sesi QUIC end-to-end, relay tidak mengakhiri sesi. Jika relay menjadi endpoint transport, kerahasiaan dari relay memerlukan desain enkripsi end-to-end antarnode terpisah sebelum fitur itu dirilis.

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
- Untuk macOS, jalur MVP yang tersedia pada dokumentasi Apple adalah app extension NetworkExtension berbasis `NEPacketTunnelProvider`, yang menyediakan virtual interface Layer 3 dan alur paket IP untuk protokol tunnel kustom. Penggunaan provider ini memerlukan entitlement NetworkExtension. Jika kebutuhan kemudian benar-benar mengharuskan frame Ethernet Layer 2, Apple juga mendokumentasikan `NEEthernetTunnelProvider` dan `NEEthernetTunnelNetworkSettings`; kelayakan entitlement, provisioning, dan distribusi harus diuji sebelum menjadikannya target MVP. Referensi: [NEPacketTunnelProvider](https://developer.apple.com/documentation/networkextension/nepackettunnelprovider), [NEEthernetTunnelProvider](https://developer.apple.com/documentation/networkextension/neethernettunnelprovider).
- Mac tidak langsung menyediakan interface produk bernama vEtherTunel; agen vEtherTunel perlu membuat dan mengelola virtual interface melalui NetworkExtension. Untuk uji awal, gunakan mode IP Layer 3.
- Apakah hub merutekan sesi QUIC per node atau control plane hanya membantu pembentukan sesi langsung.
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
