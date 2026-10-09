# Prototipe QUIC userspace

Prototipe ini menguji identitas node, keanggotaan vEther, ACL peer, framing vEtherTunel, dan QUIC DATAGRAM. Mode biasa hanya relay userspace. Ada adapter Linux TUN yang opt-in untuk mengambil paket dari stack IP dan memasukkan paket peer yang lolos validasi; adapter ini belum diverifikasi pada Linux lab. Tanpa `--enable-tun`, program tidak membuat interface atau rute. Di macOS, TUN ditolak dan tidak mengubah interface, rute, DNS, firewall, atau pengaturan boot.

## Yang tersedia

- Hub QUIC/TLS 1.3, default bind ke `127.0.0.1:4433`.
- Pendaftaran node melalui QUIC stream dan token enrollment per node.
- vEther ID dan identitas source/destination pada envelope berversi.
- ACL peer default-deny yang dibaca dari konfigurasi hub.
- Pesan teks antar node melalui QUIC DATAGRAM.
- Framing IPv4/IPv6 dengan pemeriksaan versi dan panjang; checksum header IPv4 serta kecocokan alamat sumber/destinasi terhadap node terdaftar juga diverifikasi. Hub dapat merelay envelope IP valid yang dikirim oleh pemanggil protokol.
- Validasi sertifikat TLS pada node; sertifikat CA harus diberikan secara eksplisit.
- Maksimum envelope datagram 1400 byte; ukuran payload efektif juga bergantung pada panjang ID vEther/node.
- Hub tetap bind ke loopback secara default. Bind ke alamat IPv4 RFC1918 atau IPv6 ULA hanya tersedia dengan flag `--allow-private-network`; alamat wildcard dan publik ditolak.

## Persiapan lokal

Jalankan dari root repo. Perintah ini hanya membuat virtual environment, sertifikat uji lokal, dan socket localhost.

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
cp hub.example.json hub.json
```

Ganti token contoh dalam `hub.json` dengan nilai acak khusus lab. `hub.json` diabaikan Git; jangan commit token. Buat sertifikat self-signed khusus localhost untuk uji lokal:

```sh
mkdir -p certs
openssl req -x509 -newkey rsa:3072 -nodes \
  -keyout certs/hub.key -out certs/hub.crt -days 30 \
  -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
```

Terminal 1, jalankan hub:

```sh
.venv/bin/vethertunel-hub \
  --config hub.json --certificate certs/hub.crt --private-key certs/hub.key
```

Terminal 2, jalankan node A. Token dibaca dari environment atau prompt tersembunyi, bukan dari argumen command line:

```sh
.venv/bin/vethertunel-node \
  --host 127.0.0.1 --server-name localhost --ca-cert certs/hub.crt \
  --vether-id lab --node-id node-a
```

Saat diminta, ketik token node A pada prompt tersembunyi. Terminal 3 jalankan node B dengan token dan identitas node B. Pada prompt node A ketik `node-b halo`; pada node B ketik `node-a hai`. Ketik `/quit` untuk menghentikan node. Hentikan hub dengan Ctrl-C.

## Batas dan tindak lanjut

- CLI menerima pesan teks atau paket IPv4/IPv6 manual dalam bentuk hex; hub memeriksa alamat sumber/destinasi terhadap pendaftaran node dan ACL sebelum merelaynya.
- Tanpa `--enable-tun`, tidak ada cara mengambil paket dari stack OS; peer hanya menampilkan metadata paket yang diterima.
- Adapter TUN Linux telah ditambahkan, tetapi belum dijalankan atau diverifikasi pada Linux lab. Karena itu ping, TCP overlay, cleanup saat proses mati, konektivitas lintas-host, NAT traversal, dan interoperabilitas appliance belum terbukti.
- TUN memerlukan Linux, `/dev/net/tun`, `iproute2`, dan izin `CAP_NET_ADMIN`. Berikan satu atau lebih `--overlay-address IP` dan daftar `--peer-address NODE=IP`. Contoh node A:

  ```sh
  .venv/bin/vethertunel-node \
    --host 192.168.1.10 --server-name 192.168.1.10 --ca-cert certs/hub.crt \
    --vether-id lab --node-id node-a --enable-tun --tun-name vtun0 \
    --overlay-address 10.77.0.1 --peer-address node-b=10.77.0.2
  ```

  Node B perlu menjalankan Linux juga, memakai `--overlay-address 10.77.0.2 --peer-address node-a=10.77.0.1`, serta token yang terdaftar. Hub `hub.json` harus memberi alamat yang sama kepada node masing-masing dan mengizinkan peer secara dua arah.
- Adapter membuat interface non-persisten yang terikat ke file descriptor proses. Saat dihentikan atau proses keluar, penutupan descriptor meminta kernel membuang interface dan rute terkait. Konfigurasi hanya menetapkan alamat host dan rute /32 atau /128 peer. Tidak ada default route, DNS, firewall, atau `net.ipv4.ip_forward` yang diaktifkan. Pastikan tidak ada alamat overlay bentrok dengan jaringan host.
- Kirim ping antar-alamat overlay setelah kedua node terhubung. Untuk TCP, jalankan server/client aplikasi di alamat overlay. Hasil harus dicatat setelah benar-benar diamati pada lab; contoh konfigurasi ini bukan bukti hasil koneksi.
- Jangan bind hub ke alamat publik atau meneruskan port router sebagai bagian dari uji awal.
- Token contoh harus diganti; konfigurasi hub berisi bearer token untuk lab dan wajib dijaga lokal.
- Tahap berikutnya: validasi koneksi QUIC lintas-komputer, lalu uji TUN/ping/TCP dan cleanup di dua host Linux disposable. Integrasi macOS menunggu desain NetworkExtension, entitlement, review, dan uji VM/Mac terpisah.
- Demo loopback teks dan satu paket IPv4 header-only sudah berhasil pada 9 Oktober 2026. Ini hanya menguji relay envelope aplikasi; paket tidak diserahkan ke interface OS.

## Demonstrasi antar-node di LAN privat (opt-in)

Mode ini memungkinkan node software pada komputer berbeda bertukar pesan teks dan envelope IP manual melalui hub QUIC. Ini tetap relay userspace; tidak membuat interface, mengubah rute, atau memasukkan paket ke stack IP OS. **Mode lintas-komputer belum diuji.** Gunakan hanya LAN lab tepercaya dengan alamat RFC1918 IPv4 atau ULA IPv6. Jangan gunakan alamat publik, wildcard bind, port-forward router, atau ubah firewall secara luas.

1. Pada komputer hub, buat sertifikat lab dengan SAN berisi alamat privat hub yang benar-benar digunakan. Contoh berikut memakai placeholder `192.168.1.10`; ganti dengan IP privat hub Anda:

   ```sh
   openssl req -x509 -newkey rsa:3072 -nodes \
     -keyout certs/hub.key -out certs/hub.crt -days 30 \
     -subj "/CN=192.168.1.10" \
     -addext "subjectAltName=IP:192.168.1.10"
   ```

2. Jalankan hub dengan bind privat opt-in. Perintah ini hanya membuka socket QUIC pada satu IP privat; tidak mengubah firewall atau router:

   ```sh
   .venv/bin/vethertunel-hub \
     --config hub.json --certificate certs/hub.crt --private-key certs/hub.key \
     --host 192.168.1.10 --allow-private-network
   ```

3. Salin hanya sertifikat publik `hub.crt` ke komputer node melalui jalur administrasi tepercaya; jangan salin `hub.key` atau `hub.json` (registry tersebut berisi token semua node). Masukkan token node pada prompt tersembunyi. Di tiap node, gunakan alamat dan SAN hub yang sama:

   ```sh
   .venv/bin/vethertunel-node \
     --host 192.168.1.10 --server-name 192.168.1.10 --ca-cert certs/hub.crt \
     --vether-id lab --node-id node-a
   ```

   Gunakan `node-b` serta token node B pada komputer kedua. Jika firewall host memblokir koneksi, batasi izin UDP/4433 ke komputer node lab yang dipercaya; jangan meneruskan port dari internet. Setelah kedua node tersambung, gunakan `<node-id> <pesan>` untuk memeriksa relay teks. Perintah `ip4`/`ip6` tetap hanya mengirim paket contoh manual.

## Hasil uji manual loopback

Lingkungan: Python 3.12.14, `aioquic` 1.3.0, hub di `127.0.0.1:4433`, dua proses node, sertifikat self-signed lab dengan CA diberikan eksplisit. Token dibuat acak dalam `hub.json` lokal yang diabaikan Git.

- Kedua node menyelesaikan enrollment QUIC/TLS dan ALPN `vethertunel/1`.
- Pesan `hello-from-a` dikirim dari node A dan diterima node B.
- Paket IPv4 20 byte dari `198.18.0.1` ke `198.18.0.2` lolos pemeriksaan alamat di hub dan diterima node B.
- Paket dengan checksum header IPv4 salah ditolak oleh encoder node sebelum dikirim.
- Node B hanya mencetak metadata paket. Paket uji memakai protocol number 253; tidak ada ping, socket IP, atau routing OS yang diuji.
- Uji awal ini tidak mencakup penolakan ACL, paket rusak, IPv6, NAT, jaringan lintas-host, throughput, atau TUN/NetworkExtension. Uji IPv6 loopback manual dijalankan kemudian dan dicatat di atas.
- Uji IPv6 manual kemudian berhasil merelay datagram 40 byte dari `fd12:3456:789a::1` (node A) ke `fd12:3456:789a::2` (node B). Node B menampilkan `IP fd12:3456:789a::1 -> fd12:3456:789a::2; 40 bytes from node-a`.
- Hub hanya bind ke `127.0.0.1`; node mencetak metadata paket yang direlay melalui QUIC userspace. Tidak ada paket yang disuntikkan ke interface OS. Hasil ini tidak membuktikan ping, routing OS, TUN/NetworkExtension, NAT traversal, atau konektivitas lintas-host.
- Hub, klien, serta proses uji dihentikan setelah selesai. Uji berjalan hanya lewat loopback dan tidak mengubah interface atau rute.

## Demo paket IP manual (opsional)

Dengan konfigurasi contoh, alamat node A adalah `198.18.0.1` dan `fd12:3456:789a::1`; node B adalah `198.18.0.2` dan `fd12:3456:789a::2`. Setelah kedua node tersambung, pada prompt node A masukkan paket header-only ini ke peer B.

```text
ip4 node-b 450000140000000040fdedc5c6120001c6120002
ip6 node-b 600000000000fd40fd123456789a00000000000000000001fd123456789a00000000000000000002
```

Paket tersebut hanya demonstrasi framing dan ACL vEtherTunel. Keduanya memakai protocol number 253 untuk eksperimen, bukan ICMP; keberhasilannya tidak berarti `ping` atau routing OS berfungsi. Node B hanya menampilkan alamat dan ukuran paket.
