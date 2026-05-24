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
