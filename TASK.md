# SKYNET V2.0 — Enterprise Roadmap

## Phase 1: Auth & Dashboard (hari ini)
1. **JWT Login** — login page di dashboard, token di localStorage, middleware verify
2. **Env system** — `.env` file, `load_dotenv()`, gak ada hardcoded keys
3. **User management** — register/login/logout, 2 admin users hardcoded (admin:admin123, owner:skynet2024)
4. **Dashboard pages** — login page, dashboard utama (charts), campaign list, content list
5. **Structured logging** — JSON logs ke file, rotation

## Phase 2: Content Automation (besok)
1. **Playwright stealth** — auto-post ke TikTok/IG/YT
2. **Content queue** — SQLite-based antrian posting + retry
3. **TTS + video** — edge-tts buat voiceover + moviepy buat compose video pendek

## Phase 3: GPU Pipeline (3 hari)
1. **Modal.com** — Wan2.1 video gen + FishSpeech TTS
2. **Job queue** — Redis bull atau SQLite-based antrian GPU job
3. **Auto fallback** — CPU mode kalo GPU quota habis

## Phase 4: Monitoring (4 hari)
1. **Campaign analytics** — engagement tracker, conversion estimator
2. **Dashboard charts** — campaign performance over time
3. **Telegram/Discord alerts** — notifikasi campaign complete/failed

## Phase 5: DevOps (5 hari)
1. **GitHub Actions** — CI/CD auto deploy ke codespace
2. **Automated tests** — pytest untuk core logic
3. **Docker optimization** — multi-stage build, smaller image

---

## Cara Kerja
1. Baca semua file existing di ~/ugc/ugc_ai_overpower/
2. Kerjakan Phase 1 dulu sampai selesai
3. Report progress ke /tmp/skynet_progress.txt setiap selesai 1 subtask
4. Jangan ubah structure folder existing, tambahin aja
