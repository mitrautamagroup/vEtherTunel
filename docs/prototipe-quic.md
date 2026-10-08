# Prototipe QUIC userspace

Prototipe ini adalah langkah implementasi pertama untuk menguji identitas node, keanggotaan vEther, ACL peer, framing vEtherTunel, dan pengiriman pesan melalui QUIC. Ini **belum** merupakan tunnel IP: belum membuat TUN/NetworkExtension, belum membawa paket IPv4/IPv6, dan tidak mengubah interface, rute, DNS, firewall, atau pengaturan boot macOS.

## Yang tersedia

- Hub QUIC/TLS 1.3, default bind ke `127.0.0.1:4433`.
- Pendaftaran node melalui QUIC stream dan token enrollment per node.
- vEther ID dan identitas source/destination pada envelope berversi.
- ACL peer default-deny yang dibaca dari konfigurasi hub.
- Pesan teks antar node melalui QUIC DATAGRAM.
- Framing IPv4/IPv6 dengan pemeriksaan panjang header, versi, dan kecocokan alamat sumber/destinasi terhadap node yang terdaftar. Hub dapat merelay envelope IP valid yang dikirim oleh pemanggil protokol.
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

- CLI node saat ini hanya mengirim pesan teks; belum ada adapter TUN/NetworkExtension atau cara mengambil paket dari stack OS. Jalur framing/relay IP belum dibuktikan berjalan.
- Prototipe belum membuktikan konektivitas antarjaringan, NAT traversal, ping, TCP overlay, atau interoperabilitas dengan interface vEther appliance.
- Jangan bind hub ke alamat publik atau meneruskan port router sebagai bagian dari uji awal.
- Token contoh harus diganti; konfigurasi hub berisi bearer token untuk lab dan wajib dijaga lokal.
- Tahap berikutnya: uji dua proses, tambah uji protokol/ACL, konfigurasi enrollment yang lebih baik, lalu implementasikan adapter paket di lingkungan Linux lab. Integrasi macOS menunggu desain NetworkExtension, entitlement, review, dan uji VM/Mac terpisah.
- Relay IP userspace belum diuji. Paket yang lolos validasi belum diserahkan ke interface OS.
