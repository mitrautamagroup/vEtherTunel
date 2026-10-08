# Prototipe QUIC userspace

Prototipe ini adalah langkah implementasi pertama untuk menguji identitas node, keanggotaan vEther, ACL peer, framing vEtherTunel, dan pengiriman data melalui QUIC. Ini **belum** merupakan tunnel IP: paket IP harus diberikan manual sebagai hex, tidak diambil dari stack OS, dan tidak diserahkan ke interface OS. Prototipe tidak mengubah interface, rute, DNS, firewall, atau pengaturan boot macOS.

## Yang tersedia

- Hub QUIC/TLS 1.3, default bind ke `127.0.0.1:4433`.
- Pendaftaran node melalui QUIC stream dan token enrollment per node.
- vEther ID dan identitas source/destination pada envelope berversi.
- ACL peer default-deny yang dibaca dari konfigurasi hub.
- Pesan teks antar node melalui QUIC DATAGRAM.
- Framing IPv4/IPv6 dengan pemeriksaan versi dan panjang; checksum header IPv4 serta kecocokan alamat sumber/destinasi terhadap node terdaftar juga diverifikasi. Hub dapat merelay envelope IP valid yang dikirim oleh pemanggil protokol.
- Validasi sertifikat TLS pada node; sertifikat CA harus diberikan secara eksplisit.
- Batas datagram prototipe 1100 byte.

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
- Tidak ada adapter TUN/NetworkExtension atau cara mengambil paket dari stack OS. Peer hanya menampilkan metadata paket yang diterima; paket tidak diserahkan ke interface OS.
- Prototipe belum membuktikan konektivitas antarjaringan, NAT traversal, ping, TCP overlay, atau interoperabilitas dengan interface vEther appliance.
- Jangan bind hub ke alamat publik atau meneruskan port router sebagai bagian dari uji awal.
- Token contoh harus diganti; konfigurasi hub berisi bearer token untuk lab dan wajib dijaga lokal.
- Tahap berikutnya: uji dua proses, tambah uji protokol/ACL, konfigurasi enrollment yang lebih baik, lalu implementasikan adapter paket di lingkungan Linux lab. Integrasi macOS menunggu desain NetworkExtension, entitlement, review, dan uji VM/Mac terpisah.
- Demo loopback teks dan satu paket IPv4 header-only sudah berhasil pada 9 Oktober 2026. Ini hanya menguji relay envelope aplikasi; paket tidak diserahkan ke interface OS.

## Hasil uji manual loopback

Lingkungan: Python 3.12.14, `aioquic` 1.3.0, hub di `127.0.0.1:4433`, dua proses node, sertifikat self-signed lab dengan CA diberikan eksplisit. Token dibuat acak dalam `hub.json` lokal yang diabaikan Git.

- Kedua node menyelesaikan enrollment QUIC/TLS dan ALPN `vethertunel/1`.
- Pesan `hello-from-a` dikirim dari node A dan diterima node B.
- Paket IPv4 20 byte dari `198.18.0.1` ke `198.18.0.2` lolos pemeriksaan alamat di hub dan diterima node B.
- Paket dengan checksum header IPv4 salah ditolak oleh encoder node sebelum dikirim.
- Node B hanya mencetak metadata paket. Paket uji memakai protocol number 253; tidak ada ping, socket IP, atau routing OS yang diuji.
- Uji ini tidak mencakup penolakan ACL, paket rusak, IPv6, NAT, jaringan lintas-host, throughput, atau TUN/NetworkExtension.
- Hub, klien, serta proses uji dihentikan setelah selesai. Uji berjalan hanya lewat loopback dan tidak mengubah interface atau rute.

## Demo paket IPv4 manual (opsional)

Dengan konfigurasi contoh, alamat node A adalah `198.18.0.1` dan node B `198.18.0.2`. Setelah kedua node tersambung, pada prompt node A masukkan satu paket IPv4 header-only ke peer B:

```text
ip4 node-b 450000140000000040fdedc5c6120001c6120002
```

Paket 20 byte ini hanya demonstrasi framing dan ACL vEtherTunel. Ia memakai protocol number 253 untuk eksperimen, bukan ICMP; keberhasilannya tidak berarti `ping` atau routing OS berfungsi. Node B hanya menampilkan alamat dan ukuran paket.
