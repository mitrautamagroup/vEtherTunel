# Qwen lokal untuk vEtherTunel

`Modelfile.qwen-vether` membuat varian Ollama bernama `qwen2.5-coder-vether`. Varian ini memakai bobot dasar `qwen2.5-coder:3b` dan menambahkan system prompt berisi konteks vEtherTunel, batas rancangan MVP, serta aturan kerja untuk partner programming.

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

