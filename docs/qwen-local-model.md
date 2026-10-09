# Qwen lokal untuk vEtherTunel

`Modelfile.qwen-vether` membuat varian Ollama bernama `qwen2.5-coder-vether`. Varian ini memakai bobot dasar `qwen2.5-coder:3b` dan menambahkan system prompt berisi konteks vEtherTunel, batas rancangan MVP, serta aturan kerja untuk partner programming. Repo kini punya relay QUIC/TLS userspace dan implementasi awal adapter TUN Linux yang opt-in. Model harus menyebut TUN sebagai implementasi yang belum diverifikasi di Linux lab; jangan mengklaim ping/TCP atau cleanup berhasil.

Keputusan rancangan saat ini: protokol aplikasi vEtherTunel sendiri di atas QUIC/TLS 1.3, tidak menggunakan WireGuard, dan tidak membuat algoritma kriptografi baru. Bangun ulang model lokal setelah mengubah Modelfile agar instruksi baru diterapkan.

Untuk macOS, Modelfile juga menetapkan batas keselamatan: integrasi interface di masa depan hanya melalui NetworkExtension yang disetujui, jangan mengubah KEXT/SIP/boot/system volume/startup, jangan menginstal launch daemon, jangan memakai default route/DNS pada MVP, dan jangan menjalankan perintah jaringan berprivilege dari installer atau kode startup. Prototipe saat ini tidak mengubah host networking. Uji perubahan jaringan di VM/Mac terpisah dengan jalur rollback.

Instruksi coding partner Antigravity berada di `AGENTS.md`, yang ditemukan sebagai aturan workspace oleh Antigravity. Baca file itu bersama `docs/architecture.md`, `docs/prototipe-quic.md`, dan `docs/roadmap.md` sebelum melanjutkan implementasi.

Prompt sesi yang lebih terarah untuk Antigravity + Qwen ada di [`prompt-antigravity-qwen.md`](prompt-antigravity-qwen.md). Instruksi terbaru juga melarang Qwen mengarang pemanggilan alat, mewajibkan bukti nyata untuk klaim baca/edit/jalankan, dan meminta temuan kode yang punya lokasi serta failure path.

Ini **bukan fine-tuning** dan tidak mengubah bobot model. System prompt membantu Qwen tetap konsisten pada konteks proyek, memberi batas keselamatan, dan menuntut bukti; kemampuan coding dasarnya tetap sama dan jawaban tetap perlu ditinjau.

### Alur Twinny yang disarankan

1. Pilih provider **Ollama** dan model `qwen2.5-coder-vether:latest`.
2. Untuk review tanpa akses workspace yang benar, matikan **Agent mode**. Mode Agent di Twinny sebelumnya membuat model ini mengeluarkan teks JSON pseudo-tool-call (`read_file`) alih-alih benar-benar membaca source.
3. Tempelkan diff atau bagian file yang relevan ke chat dan minta review berdasarkan isi tersebut. Jangan minta model menebak isi repo. Tanpa source, Qwen seharusnya meminta source itu.
4. Untuk perubahan file, aktifkan Agent hanya bila Twinny benar-benar menjalankan baca/edit file dan periksa hasil aktual di Git diff. Jangan menerima teks JSON sebagai bukti file telah dibaca/diubah.

Perilaku sudah dicoba dua cara: `ollama run qwen2.5-coder-vether` menjawab bahwa ia tidak punya akses repo dan meminta source; sedangkan Twinny Agent masih menghasilkan pseudo-tool-call. Karena itu chat Twinny dengan source yang ditempel adalah alur andal saat ini. Ini batas integrasi/tool-use, bukan sesuatu yang bisa diperbaiki sepenuhnya hanya dengan prompt.

## Membuat model

Pastikan Ollama aktif dan model dasar sudah tersedia, lalu jalankan dari root repo:

```sh
ollama create qwen2.5-coder-vether -f Modelfile.qwen-vether
```

Uji dari terminal:

```sh
ollama run qwen2.5-coder-vether "Jelaskan batas MVP vEtherTunel dalam tiga poin."
```

Di Twinny, pilih provider Ollama dan ganti nama model menjadi `qwen2.5-coder-vether`. Untuk memakai instruksi ini di sesi baru, restart percakapan setelah memilih model.

## Memperbarui konteks

Perbarui bagian `Project facts` di Modelfile ketika keputusan rancangan berubah. Buat ulang model dengan perintah `ollama create` yang sama. Untuk detail yang sering berubah atau terlalu panjang untuk system prompt, lampirkan dokumen relevan (`README.md`, `docs/architecture.md`, atau `docs/roadmap.md`) sebagai context Twinny.
