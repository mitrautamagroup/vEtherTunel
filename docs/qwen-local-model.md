# Qwen lokal untuk vEtherTunel

`Modelfile.qwen-vether` membuat varian Ollama bernama `qwen2.5-coder-vether`. Varian ini memakai bobot dasar `qwen2.5-coder:3b` dan menambahkan system prompt berisi konteks vEtherTunel, batas rancangan MVP, serta aturan kerja untuk partner programming. Repo sekarang memiliki prototipe awal hub/peer userspace; model harus menyebutnya sebagai relay pesan teks QUIC localhost, bukan tunnel IP.

Keputusan rancangan saat ini: protokol aplikasi vEtherTunel sendiri di atas QUIC/TLS 1.3, tidak menggunakan WireGuard, dan tidak membuat algoritma kriptografi baru. Bangun ulang model lokal setelah mengubah Modelfile agar instruksi baru diterapkan.

Untuk macOS, Modelfile juga menetapkan batas keselamatan: integrasi interface di masa depan hanya melalui NetworkExtension yang disetujui, jangan mengubah KEXT/SIP/boot/system volume/startup, jangan menginstal launch daemon, jangan memakai default route/DNS pada MVP, dan jangan menjalankan perintah jaringan berprivilege dari installer atau kode startup. Prototipe saat ini tidak mengubah host networking. Uji perubahan jaringan di VM/Mac terpisah dengan jalur rollback.

Instruksi coding partner Antigravity berada di `AGENTS.md`, yang ditemukan sebagai aturan workspace oleh Antigravity. Baca file itu bersama `docs/architecture.md` dan `docs/prototipe-quic.md` sebelum melanjutkan implementasi.

Ini **bukan fine-tuning** dan tidak mengubah bobot model. System prompt membantu Qwen tetap konsisten pada konteks dan instruksi proyek, tetapi jawaban tetap perlu diperiksa dan model dapat keliru.

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
