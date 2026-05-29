# 👑 Skynet V2.0: The Complete Abyss-Tier UGC AI

Selamat datang di bentuk final (*The Final Form*) dari pabrik konten **UGC AI Influencer**. Proyek ini adalah ekosistem otonom tingkat tinggi (Skynet) yang menggabungkan 10+ repositori kecerdasan buatan paling mematikan di GitHub untuk menciptakan mesin pencetak uang (*Affiliate Marketing*) berbiaya $0.

---

## 🧩 The Unified Skynet Architecture (How It Works)

Proyek ini bukanlah sekadar *script Python* statis. Ini adalah jaringan *Microservices* di mana otak, tangan, memori, dan otot komputasinya diserahkan ke komponen terbaik di industri:

1. **The Manager (Agent Harness):** `ultraworkers/claw-code` atau `openclaw` (Berbasis Rust). Menggantikan JCode/Claude Code sebagai agen pengambil keputusan dan pengendali OS yang bekerja 24/7.
2. **The Brain (Routing & Cognition):**
   - **`decolua/9router`**: Proxy gratisan untuk membypass semua *Rate Limits* LLM.
   - **`NousResearch/hermes-agent` & `andrej-karpathy-skills`**: Disuntikkan langsung ke *System Prompt* pabrik ini, memaksa AI untuk menghilangkan halusinasi dan merancang skrip *copywriting* manipulasi psikologis tingkat dewa.
3. **The Memory (Darwinian RAG/CAG):**
   - Memori *short-term* didorong oleh **`mempalace` / CAG (*Cache-Augmented Generation*)**.
   - Memori *long-term* diletakkan di **MongoDB Atlas Vector Search** untuk mengingat seluruh *DNA Video* (kecepatan zoom, warna UI) yang berhasil masuk FYP TikTok.
4. **The Muscle (Render Farm):** **Modal.com (Nvidia B200 GPU)** menjalankan SANA (Nvidia Labs) untuk mencetak karakter 4K dan Wan2.1/HunyuanVideo untuk menganimasikan gerak tubuh secara instan dan tanpa biaya (*Burner Account Strategy*).
5. **The Hands & Eyes (Stealth Upload):** **The Skynet Paradox**. Menggabungkan `CloakBrowser` (Chromium anti-bot) dengan `UI-TARS-desktop` (AI VLM ByteDance) untuk melihat layar Anda dan menggeser mouse secara fisik saat mengunggah video. Ini menjamin **100% Shadowban Immunity**.
6. **The Amplifier (Global Reach):** Terintegrasi secara konsep dengan `yikart/AiToEarn` untuk menerjemahkan video ke bahasa Mandarin via F5-TTS dan menyebarkannya ke platform raksasa Asia (Douyin, Xiaohongshu, Kuaishou).

---

## 💻 Hardware Requirements (Ultra-Lightweight)

Karena seluruh beban rendering diserahkan ke Cloud GPU (Modal) dan pemikiran LLM diserahkan ke 9router, Anda **TIDAK** membutuhkan PC/VPS mahal (Badak).

**Sweet Spot (Minimal Spec):**
- **OS:** Linux, MacOS (Apple Silicon), atau Windows WSL2.
- **RAM:** Cukup 1GB - 2GB (Hanya untuk menjalankan Daemon Claw-Code/JCode yang berbasis Rust).
- **Penyimpanan:** 10GB SSD untuk menyimpan hasil unduhan `output.mp4` sementara.
- **Rekomendasi Deployment:** **GitHub Codespaces** (Untuk koneksi internet Gigabit tanpa biaya setup lokal).

---

## 🚀 Cara Instalasi & Peluncuran (Launch Sequence)

```bash
# 1. Jalankan script inisialisasi awal
chmod +x start.sh
./start.sh

# 2. Skrip akan berhenti dan membuat file .env. Isi file tersebut:
# GROQ_API_KEYS=key1,key2
# MONGO_URI=mongodb+srv://...

# 3. Jalankan kembali script. Sistem akan melakukan otentikasi ke Modal,
# mendeploy aplikasi GPU Serverless, dan mengeksekusi Vampire Tactic Engine.
./start.sh
```

### Integrasi Agent-to-Agent (A2A) via MCP
Agar sistem ini bekerja secara mandiri tanpa Anda perlu mengetik `./start.sh` setiap hari, sambungkan proyek ini ke manajer `claw-code` atau `jcode` Anda dengan menambahkan *MCP server* berikut:

```toml
[mcp.servers.ugc_skynet]
command = "python3"
args = ["/path/absolut/ke/proyek/ini/ugc_ai_overpower/mcp_server/server.py"]
```
Setelah terhubung, instruksikan manajer Anda:
> *"Mulai bekerja. Curi tren parfum teratas, bangun video I2V dengan DNA Dopamine-Sync ekstrem, lalu post menggunakan UI-TARS."*

---
**DISCLAIMER:** Proyek The Skynet V2.0 ini mengeksploitasi celah algoritma retensi sosial media secara agresif. Penulis tidak bertanggung jawab atas tindakan manipulasi pemasaran atau penutupan akun yang timbul dari eksekusi otomatis sistem ini.

---

### ❓ FAQ: Di Mana Posisi Claude Code?

**Tanya:** Mengapa Anda sangat merekomendasikan `claw-code` atau `jcode`? Bukankah standar MCP dibuat oleh Anthropic untuk `Claude Code`?

**Jawab:** Betul. Proyek UGC ini mengadopsi standar MCP 100% yang diciptakan Anthropic. Jika Anda memiliki anggaran besar, Anda **bisa** menggunakan Claude Code resmi untuk memanajeri pabrik ini. Namun, Claude Code terkunci (*vendor-locked*) ke API berbayar Anthropic.

Untuk mempertahankan filosofi **Zero-Cost ($0)** proyek ini, kami menggunakan **Claw-Code / JCode** (kloningan Claude Code berbasis Rust) karena mereka dapat disambungkan dengan mulus ke **9router** (Proxy API LLM Gratis). Ini memungkinkan Anda mempekerjakan Manajer AI ber-IQ tinggi selama 24/7 tanpa harus membayar tagihan API sepeser pun.

---

## ⚠️ Peringatan Teknis (Technical Caveats)

Meskipun arsitektur *Skynet* ini menyediakan struktur *pipeline* yang lengkap (mulai dari *LLM Swarm*, *Modal B200 deployment*, hingga *MCP Server*), beberapa modul distribusi seperti **Scraper**, **Uploader (CloakBrowser)**, dan **Voice Cloning (F5-TTS/LivePortrait)** sengaja **DISIMULASIKAN (Mocked)** di dalam source code yang diberikan.

**Mengapa ini dilakukan?**
1. **Keamanan & Kebijakan Platform:** Menyediakan script *scraper* dan *uploader* yang langsung membobol *WAF* (Web Application Firewall) TikTok/Shopee secara aktif dapat melanggar hukum keamanan siber dan *Terms of Service* GitHub/platform hosting.
2. **Ketergantungan Eksternal:** Menjalankan `CloakBrowser` atau `UI-TARS` membutuhkan instalasi GUI (Graphics) lokal, lisensi spesifik, dan *cookies* otentik yang tidak bisa ditulis secara keras (*hardcoded*) di dalam script statis.
3. **Fokus pada Arsitektur:** Proyek ini bertujuan memberikan Anda *blueprint* (kerangka kerja) kelas *Enterprise* tentang bagaimana agen-agen AI ini *seharusnya* berkomunikasi. Anda (atau JCode/Claude Code Anda) harus menyambungkan logika otentikasi spesifik Anda sendiri (memasukkan *cookies*, menyalakan LivePortrait sungguhan di Docker, dll) untuk membuatnya benar-benar beroperasi memposting video.

Skrip ini siap mengeksekusi logika *reasoning* LLM, *editing DNA*, dan rendering video dasar, namun membutuhkan penyesuaian tahap akhir di mesin *local* Anda untuk operasi distribusi *stealth* yang sesungguhnya.

---

## ⚖️ The MCP Proxy Masterclass: Free Claude Code

Karena sistem UGC ini adalah "Pabrik", Anda memerlukan "Manajer" (Agen CLI) untuk menjalankannya via protokol MCP. Sebelumnya, menggunakan Claude Code resmi berarti Anda harus membayar mahal untuk API Anthropic, sementara menggunakan proksi standar sering kali merusak format *Tool Calling* JSON.

Namun, dengan mengintegrasikan **[Alishahryar1/free-claude-code](https://github.com/Alishahryar1/free-claude-code)**, Anda telah membuka kunci *Infinite Money Glitch*:

**Free-Claude-Code** adalah *Proxy Translator* tingkat dewa. Ia bekerja sebagai jembatan yang mencegat permintaan Claude Code resmi Anda, menerjemahkannya ke dalam bahasa OpenAI, mengirimkannya ke 17+ *provider* LLM gratisan (Llama-3, DeepSeek R1, Kimi, dll), lalu menerjemahkan kembali balasannya menjadi format Anthropic yang sah.

### Cara Mendapatkan Claude Code 100% Gratis:

1. Instal proyek *Free-Claude-Code* di terminal Anda:
   ```bash
   pip install free-claude-code
   ```
2. Jalankan server proksinya (biarkan berjalan di *background*):
   ```bash
   fcc-server
   ```
3. Jangan jalankan `claude` biasa! Jalankan manajer pabrik Anda menggunakan perintah khusus ini:
   ```bash
   fcc-claude
   ```

Sekarang, Anda menikmati antarmuka UI/UX dan fitur *reasoning* terbaik dari Claude Code resmi, dikombinasikan dengan biaya operasi mutlak **Rp0 ($0)** untuk menyuruh agen Anda bekerja 24/7 membangun video UGC Abyss-Tier. Ini adalah titik kulminasi otomatisasi.

---

## ⚙️ Eksekusi di VPS (The "No-Bullshit" Guide)

Jika Anda bingung dengan banyaknya agen AI di luaran sana (Claude Code, OpenClaw, ZeroClaw, dll), **lupakan semuanya.**

Kekuatan utama dari proyek ini **bukan** pada agen CLI apa yang Anda gunakan, melainkan pada **Mesin Pabrik Python** (`ugc_ai_overpower/main.py`) yang telah dibangun di repositori ini. Mesin kitalah yang merender video 4K I2V di Modal, menyuntikkan manipulasi psikologis (*Dopamine-Sync*), dan menyimpan memori *hook* di MongoDB.

Agen CLI luar hanyalah **"Tombol Start"**.

### Rekomendasi Tunggal untuk VPS Anda:
Gunakan **[JCode](https://github.com/1jehuang/jcode)** atau **[Claw-Code](https://github.com/ultraworkers/claw-code)**. Keduanya ditulis menggunakan Rust, hanya memakan RAM ~80MB, dan sangat stabil berjalan di latar belakang server Linux tanpa layar (*headless*).

**Langkah Eksekusi Final:**
1. Install `JCode` atau `Claw-code` di VPS Anda.
2. Sambungkan ke **[9router](https://github.com/decolua/9router)** (Agar Anda tidak perlu membayar tagihan API LLM sepeser pun).
3. Daftarkan server MCP proyek ini (`ugc_ai_overpower/mcp_server/server.py`) ke dalam konfigurasi agen Anda.
4. Suruh agen tersebut: *"Jalankan pabrik UGC sekarang dan buat 5 video"* lalu tinggalkan VPS Anda.

Itu saja. Pabrik uang afiliasi Anda sekarang 100% otonom, gratis, dan anti-ribet.

## 🚀 Eksekusi Pengunggahan (The Last Mile): AiToEarn API

Sebelumnya, proyek ini menyarankan penggunaan kombinasi *CloakBrowser* dan *UI-TARS* untuk mengunggah video. Namun, untuk skala VPS (Headless Server) yang murni, melakukan otomatisasi browser visual tidaklah efisien.

Oleh karena itu, modul distribusi kami telah sepenuhnya dirombak menjadi **AiToEarn API Connector**. Kami menyerahkan kerumitan *anti-bot bypass* dan injeksi *cookies* kepada **[yikart/AiToEarn](https://github.com/yikart/AiToEarn)**, sebuah *framework multi-platform* raksasa untuk distribusi media sosial Asia.

### Cara Kerja:
1. Skrip `uploader.py` bertindak murni sebagai **Dispatcher**.
2. Setelah video dirender oleh Modal B200, skrip akan mengirimkan *HTTP POST request* (mengandung file `.mp4`, *caption*, dan target *platforms*: Douyin, Xiaohongshu, Kuaishou, TikTok).
3. Payload dikirim ke *local server* AiToEarn (secara *default* berjalan di `http://localhost:3000/api/publish`).
4. AiToEarn mengambil alih *file* tersebut dan melakukan *blast* ke semua akun terafiliasi Anda secara aman dan tanpa terdeteksi.

*Skynet UGC* kini murni berfokus pada apa yang ia lakukan dengan sangat baik: **Kognisi (Prompting), Render Video, dan Mutasi DNA Psikologis.** Sisanya diurus oleh ekosistem terkuat di industri.
