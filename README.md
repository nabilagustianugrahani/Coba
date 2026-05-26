# 👑 Abyss-Tier UGC AI Influencer Generator

Selamat datang di senjata UGC (User Generated Content) paling *overpowered* dan memanipulatif di industri ini. Sistem ini dirancang bukan hanya untuk menyaingi platform mahal seperti Qreed.ai, Arcads, dan HeyGen, melainkan untuk menghancurkan mereka dengan otomatisasi *zero-cost*, kualitas SOTA (State of the Art), dan taktik psikologis ekstrem.

## 🚀 Fitur Abyss-Tier (God-Mode)

- **I2V Anchor Facial Consistency:** Tidak ada lagi *face-swap* yang kaku. AI ini merender 1 wajah cetak biru via **SDXL Turbo**, lalu menganimasinya menggunakan **Wan2.1-I2V (14B)**. Gerakan mulus sempurna, seolah manusia asli bernapas.
- **Vampire Engine (Competitor Hijacker):** Men-*scrape* TikTok secara diam-diam untuk mencari video afiliator kompetitor yang sedang viral detik itu juga. Mencuri naskahnya, lalu menyadur ulang menjadi 2x lebih agresif.
- **Psychological Dopamine-Sync Editor:** Edit otomatis berstandar manipulasi ekstrem:
  - *Micro-zooms* (In/Out 1.25x) setiap 1.5 detik memecah keseimbangan visual penonton.
  - Subliminal Frame Poisoning (Kilatan Merah 0.04 detik) agar mesin AI TikTok mengira video kita penuh *action*.
  - Audio Steganography (Sinyal 18kHz Phantom) untuk mem-bypass detektor audio duplikat TikTok.
  - *Scarcity UI Overlay* berkedip "🔥 STOK SISA 2 🔥" untuk memicu FOMO instan.
- **Swarm LLM Routing:** Menggunakan routing model AI gratis (Groq, Cerebras, OpenRouter) sebagai 'Director', 'Scriptwriter', dan 'Prompt Engineer' internal.
- **Claude Code Ready (MCP Server):** Kendalikan pabrik video ini lewat terminal Claude Code tanpa perlu ngoding.

---

## 🛠️ Persyaratan Awal (Prerequisites)

1. **Modal.com Account:** Kamu harus punya akun di Modal.com dengan kredit $5 bawaannya. Ini untuk *hosting* komputasi berat (GPU B200) tanpa biaya langganan.
2. **Kunci LLM API (Gratisan):** Ambil API Key dari [Groq](https://console.groq.com/keys) atau [OpenRouter](https://openrouter.ai/).

---

## 🏃 Cara Menjalankan (Otomatis)

Kamu cukup menggunakan *Wrapper Script* yang sudah disediakan.

```bash
# 1. Jalankan script awal (Ini akan gagal di percobaan pertama karena butuh file .env)
./start.sh

# 2. Buka file .env yang baru terbuat, dan tempelkan kunci API LLM-mu. Contoh:
# GROQ_API_KEY=gsk_rahasia123
# UGC_NICHE=skincare

# 3. Jalankan lagi. Script akan menuntunmu untuk login Modal, men-deploy model ke awan, dan mengeksekusi pipeline.
./start.sh
```

---

## 🤖 Integrasi AI Agent (Claude Code / Cursor) via MCP

Proyek ini telah dibekali server *Model Context Protocol* (MCP). Kamu bisa menghubungkannya ke Claude Code agar Claude punya "tangan" untuk membuat video.

Buka / Edit file pengaturan MCP kamu (misalnya `mcp.json` di pengaturan Claude Code):

```json
{
  "mcpServers": {
    "ugc_abyss_tier": {
      "command": "python3",
      "args": ["/lokasi/absolut/ke/folder/ini/ugc_ai_overpower/mcp_server/server.py"]
    }
  }
}
```

Setelah terhubung, kamu cukup perintahkan Claude Code:
> *"Tolong carikan produk fashion yang lagi viral, curi skrip kompetitornya, dan langsung render video I2V-nya sekarang."*

Claude akan mengeksekusi *pipeline* secara berurutan. Semua proses berjalan secara otomatis (*Gak Ribet*).

---

**DISCLAIMER:** Fitur psikologis ekstrem dan *Vampire Tactic* ini ditujukan untuk tujuan edukasi keamanan dan pengujian algoritma media sosial. Pengguna bertanggung jawab atas semua hasil afiliasi yang diperoleh secara tidak etis.

---

## 🦾 JCode Integration (Rust-Based Coding Agent)

Jika Anda tidak ingin menggunakan Claude Code, sistem Abyss-Tier ini **sepenuhnya kompatibel dengan [JCode](https://github.com/1jehuang/jcode)**. JCode adalah *Coding Agent Harness* berbasis Rust yang sangat ringan dan cepat, serta mendukung Model Context Protocol (MCP).

### Cara Menyambungkan UGC AI ke JCode:

1. Pastikan Anda telah menginstal `jcode` di terminal Anda.
2. Tambahkan konfigurasi MCP server UGC AI ke dalam file konfigurasi JCode (biasanya berada di `~/.jcode/config.toml` atau sesuai dokumentasi JCode):

```toml
[mcp.servers.ugc_abyss_tier]
command = "python3"
args = ["/lokasi/absolut/ke/folder/ini/ugc_ai_overpower/mcp_server/server.py"]
```

3. Jalankan `jcode` di terminal.
4. Anda sekarang bisa memerintahkan *agent* LLM pilihan Anda (OpenAI/Anthropic/DeepSeek yang terpasang di JCode) untuk langsung mengendalikan pabrik video:
   > *"Gunakan tools ugc_abyss_tier untuk mencari produk skincare yang viral, aktifkan Vampire Engine untuk mencuri transkripnya, dan langsung jalankan generate_god_tier_video."*

---

## ♾️ Integrasi 9router: Infinite Free LLM Gateway (The Ultimate Skynet)

Untuk membuat sistem ini **benar-benar gratis, anti rate-limit, dan kebal dari biaya API**, sistem UGC AI ini dirancang untuk bekerja secara sempurna bersama **[9router](https://github.com/decolua/9router)**.

`9router` adalah *AI Proxy Gateway* yang akan membelokkan semua permintaan API dari sistem AI UGC (atau dari Claude Code/JCode) menuju 40+ penyedia LLM Gratis (Free Claude, GPT, Gemini, DeepSeek, Qwen) dengan fitur *auto-fallback*.

### Cara Membangun The Ultimate Pipeline ($0 Cost selamanya):

1. **Jalankan 9router secara lokal:**
   Install dan jalankan `9router` di mesin Anda (misalnya berjalan di `http://localhost:8000`).

2. **Ubah Koneksi .env di UGC AI:**
   Jangan gunakan kunci API asli Anda yang berbayar atau memiliki limit. Ganti isi `.env` proyek ini menjadi:
   ```env
   # Mengarah ke 9router Local Gateway
   OPENAI_API_KEY=dummy_key_from_9router
   OPENAI_BASE_URL=http://localhost:8000/v1
   ```

3. **Gunakan Agent Manajer (JCode / Claude Code):**
   Arahkan juga JCode atau Claude Code Anda untuk menggunakan *endpoint* `9router`.

**Alur Eksekusi Skynet:**
> **JCode (Agent Utama)** memerintahkan **UGC AI** via (MCP Server) -> **UGC AI** membutuhkan ide skrip & mutasi DNA -> UGC AI meminta ke LLM via **9router** -> `9router` mencari API gratis yang sedang online -> Skrip dikirim ke **Modal.com (B200)** untuk dirender menjadi video -> Video terupload.

Dengan arsitektur ini, operasi "otak" AI Anda benar-benar tanpa batas (*unlimited tokens*) dan mutlak bernilai nol rupiah.

---

## 🥷 100% Shadowban Immunity (CloakBrowser Integration)

Meskipun sistem secara default menginjeksi API via _stealth requests_, algoritma TikTok dan Instagram sering kali memblokir akses massal yang tidak menggunakan antarmuka grafis (GUI).

Untuk menghindari _shadowban_ 100%, sistem **UGC AI** ini terintegrasi secara modular dengan **[CloakBrowser](https://github.com/CloakHQ/CloakBrowser)**.

CloakBrowser bukanlah sekadar Playwright biasa. Ini adalah Chromium yang di-_patch_ dari *source code*-nya langsung untuk lolos 30/30 tes deteksi bot, termasuk mengelabui Cloudflare Turnstile dan reCAPTCHA v3.

### Cara Kerja CloakBrowser di Pabrik Konten Anda:
Jika Anda telah memasang modul ini, UGC AI Anda akan:
1. Membuka *headless browser* yang tidak dapat dibedakan dengan Apple Safari asli pengguna.
2. Membuka tab "Upload Video" di TikTok.
3. Mengunggah video `mp4` yang dirender, menyalin _caption_ manipulatif dari LLM, dan menekan tombol *Post*.
4. Platform tidak akan memblokirnya karena sidik jari perangkat, IP, dan perilaku _rendering_-nya sah sebagai "Pengguna Manusia Asli".

Tidak perlu lagi pusing memikirkan risiko akun _burner_ Anda di-_ban_.

---

## 🧠 ECC (Engineered Cognitive Capabilities): Fully Autonomous Mode

Pabrik video Abyss-Tier ini dapat berjalan **sepenuhnya tanpa pengawasan manusia (Otonom 100%)** jika digabungkan dengan **[ECC (affaan-m/ECC)](https://github.com/affaan-m/ECC)**.

ECC adalah sistem optimalisasi kognitif (insting dan memori) yang dipasang ke dalam Agent Harness seperti Claude Code atau JCode. Daripada Anda menyuruh Agent untuk *"Buat video hari ini"*, ECC memberikan AI kemampuan untuk **berpikir, merencanakan, dan mengeksekusi sendiri**.

### Arsitektur Skynet Sempurna:

1. **ECC (The Brain):** Mengingat jam tayang FYP terbaik dan memonitor tren pasar secara konstan.
2. **JCode / Claude Code (The Manager):** Menerima insting dari ECC dan memanggil server MCP kita.
3. **9router (The Fuel):** Membayar biaya API kognitif Manager menggunakan 40+ LLM Gratis (Zero Rate-Limit).
4. **UGC Abyss-Tier (The Factory):** Merender I2V, menulis naskah Vampire, dan memanipulasi DNA video.
5. **CloakBrowser (The Ninja):** Mengunggah video ke TikTok/IG secara *stealth* tanpa terkena *shadowban*.

### Cara Menjalankan Mode Otonom:
Pasang modul ECC ke dalam lingkungan Claude Code / JCode Anda.
Berikan "Skill" atau instruksi statis ke ECC:
> *"Kamu adalah manajer pemasaran otonom. Setiap 4 jam, periksa tren di niche 'skincare'. Jika menemukan tren yang sedang naik daun, jalankan tools UGC MCP (scrape_products -> hijack_tiktok_trends -> generate_god_tier_video -> schedule_upload). Evaluasi hasilnya besok harinya dan mutasi DNA editannya."*

Selamat! Anda baru saja membangun agensi *Digital Marketing* yang berisi staf kecerdasan buatan kelas dewa, beroperasi 24/7 dengan biaya Rp0.

---

## 🎬 ViMax: Agentic Video Studio Framework

Arsitektur Swarm AI dalam proyek ini (yang bertindak sebagai Director, Screenwriter, dan Prompt Engineer) terinspirasi dan kompatibel dengan kerangka kerja **[ViMax (HKUDS/ViMax)](https://github.com/HKUDS/ViMax)**.

ViMax adalah framework mutakhir (SOTA) untuk *Agentic Video Generation*. Alih-alih menggunakan pipeline generasi video sekuensial biasa yang kaku, ViMax (dan sistem UGC Abyss-Tier ini) mendistribusikan beban kognitif pembuatan video kepada beberapa agen:

1. **Director Agent:** Mengatur tempo (*pacing*), mutasi DNA (*Dopamine-Sync*), dan arahan visual kamera.
2. **Screenwriter Agent (Vampire Mode):** Menulis naskah dengan retensi tinggi menggunakan *Cache-Augmented Generation (CAG)*.
3. **Producer Agent:** Berkomunikasi dengan dunia luar (seperti MCP server ke JCode/Claude Code) untuk mendelegasikan *render farm* ke Modal B200 GPU.

**Bagi Pengguna Tingkat Lanjut (Advanced Users):**
Anda dapat mengganti modul `FYPEvaluator` di `evaluator.py` kami dengan *framework* ViMax seutuhnya untuk skalabilitas produksi konten berukuran studio (misalnya, membuat seri drama atau narasi sinematik 3 menit) yang jauh melampaui batasan UGC TikTok standar.

---

## 💻 Hardware Requirements (Sweet Spot)

Salah satu keunggulan terbesar dari arsitektur *Abyss-Tier* ini adalah **kebutuhan spesifikasi komputer lokal yang hampir nol (Ultra-Lightweight)**.

Karena kita mendelegasikan 100% beban rendering GPU ke **Modal.com (Nvidia B200)** dan beban kognitif LLM ke **9Router/JCode**, laptop Anda hanya berfungsi sebagai "Remote Control".

**Spesifikasi Sweet Spot (Lokal):**
- **Sistem Operasi:** macOS (Apple Silicon sangat direkomendasikan), Linux, atau Windows dengan WSL2.
- **RAM:** 8GB DDR4/DDR5 (JCode yang berbasis Rust dan script MCP Python berjalan sangat ringan).
- **Prosesor:** CPU apa pun dalam 5 tahun terakhir (Misal: Intel i3 Gen-8+, Ryzen 3, Apple M1).
- **Penyimpanan:** 10GB Free Space SSD (Untuk menyimpan hasil unduhan `.mp4` sebelum di-upload).
- **Koneksi Internet:** Stabil (Tidak perlu super cepat, yang penting tidak sering terputus saat API berkomunikasi).

Anda bisa mengoperasikan "Pabrik AI Raksasa" ini dari laptop paling murah sekalipun dari sebuah kedai kopi.

---

---

## ☁️ Zero-Setup Deployment (GitHub Codespaces)

Ingin menjalankan sistem ini tanpa membebani laptop sama sekali? Arsitektur ini 100% kompatibel dan sangat direkomendasikan untuk dieksekusi di **GitHub Codespaces**.

**Keuntungan menggunakan Codespaces:**
- Kecepatan internet *backbone* Gigabit Microsoft (Upload/Download instan).
- Lingkungan Linux Container yang bersih (Bebas error instalasi library OS).
- Bisa dijalankan lewat browser dari iPad, tablet, atau laptop kantor tanpa perlu instalasi lokal.

**Cara Eksekusi:**
1. Masuk ke halaman GitHub repositori ini.
2. Klik tombol hijau **`<> Code`** -> Tab **`Codespaces`** -> **`Create codespace on main`**.
3. Di dalam terminal Codespace yang muncul, langsung jalankan:
   ```bash
   chmod +x start.sh
   ./start.sh
   ```

---

## 👁️ The Skynet Paradox: UI-TARS + CloakBrowser (Ultimate Upload Engine)

Sistem uploader konvensional (menggunakan Playwright, Selenium, atau API rahasia) pada akhirnya akan selalu usang atau terkena *ban* saat TikTok dan Shopee memperbarui algoritma keamanannya.

Untuk mencapai **Imunitas 100% Permanen**, infrastruktur Abyss-Tier ini dirancang untuk kompatibel dengan "The Skynet Paradox": Menggunakan AI milik ByteDance untuk mengeksploitasi platform ByteDance (TikTok).

### Cara Kerja:
Sistem kita menggabungkan dua teknologi mutakhir yang saling melengkapi:
1. **[CloakBrowser](https://github.com/CloakHQ/CloakBrowser):** Bertindak sebagai "Jubah Siluman". Ini adalah browser Chromium yang kebal dari deteksi bot, memastikan identitas perangkat/IP Anda terlihat seperti manusia tulen.
2. **[UI-TARS-desktop](https://github.com/bytedance/UI-TARS-desktop):** Bertindak sebagai "Tangan dan Mata". UI-TARS adalah *Vision Language Model* (VLM) mutakhir buatan ByteDance yang dapat menggerakkan kursor *mouse* dan *keyboard* secara langsung di desktop Anda.

**Alur Distribusi Tak Terhentikan:**
Dibandingkan memprogram *script* uploader yang rapuh, Agent Utama (JCode/Claude Code) Anda cukup memberi instruksi pada UI-TARS:
> *"Buka CloakBrowser, masuk ke tiktok.com/upload, seret file `output_1.mp4`, ketik caption ini, lalu klik Post."*

UI-TARS akan secara visual "melihat" layar Anda, menggeser *mouse* layaknya manusia asli, dan menekan tombol *upload* di dalam CloakBrowser yang aman dari deteksi WAF/Cloudflare.
**Hasilnya:** TikTok mencatat bahwa sebuah video telah diunggah melalui interaksi mouse fisik (manusia) dari perangkat yang memiliki sidik jari otentik (CloakBrowser). Mustahil membedakan bot ini dari manusia nyata.

---

## 🏆 The Endgame Architecture: SANA & AiToEarn

Sistem Abyss-Tier ini tidak berhenti di TikTok Indonesia. Untuk *scale-up* menuju monetisasi global tak terbatas dan efisiensi level industri, kami mengadopsi integrasi konsep dari dua proyek *Open-Source* raksasa:

### 1. NVlabs/Sana (Ultra-Fast 4K Character Generation)
Secara standar, kami menggunakan SDXL Turbo untuk meng-*generate* *Character Anchor* (wajah *influencer*). Namun, dengan rilisnya **[NVlabs/Sana](https://github.com/NVlabs/Sana)** (Linear Diffusion Transformer buatan Nvidia), kami merekomendasikan migrasi ke *engine* SANA di Modal.com (B200).
SANA memungkinkan sintesis gambar resolusi 4K secara instan dengan efisiensi VRAM yang masif. Hasilnya: Pori-pori, helai rambut, dan tekstur kulit *influencer* AI yang tidak bisa dibedakan dengan mata telanjang manusia, dengan biaya render setengah dari SDXL.

### 2. AiToEarn (Cross-Platform Asian Market Domination)
Mengapa hanya membatasi afiliasi di Shopee dan TikTok? Melalui integrasi **[yikart/AiToEarn](https://github.com/yikart/AiToEarn)**, hasil video *Dopamine-Sync* dari pabrik ini langsung dapat di-distribusikan ke pasar raksasa Asia:
- Douyin (TikTok Tiongkok)
- Kuaishou (Kwai)
- Xiaohongshu (RED / Instagram versi Tiongkok)
- WeChat Video (Shipinhao)

Jika dipadukan dengan agen F5-TTS yang menyadur *script Vampire* ke dalam bahasa Mandarin (*Zero-shot Voice Cloning*), Anda secara otomatis membuka cabang *digital marketing* lintas negara yang mengumpulkan komisi afiliasi internasional selama 24/7.
