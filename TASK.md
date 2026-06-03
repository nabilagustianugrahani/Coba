# Skynet V2 — Autonomous UGC Empire

## Status: Phase 7 ✅ (Video Generation + Auto-Posting)

### Done
- ✅ Video generation with moviepy + edge-tts (720p, 20fps, ultrafast)
- ✅ Stock background footage from Pexels API
- ✅ Text overlay with sentence segmentation
- ✅ Product image overlay support
- ✅ CookieManager (save/load/delete/export profiles)
- ✅ Cookie profiles wired into all posters (TikTok, IG, YouTube)
- ✅ CLI: generate-video, post-video, cookie-save, cookie-list
- ✅ CLI: schedule-campaign, unschedule, list-jobs
- ✅ APScheduler daemon for recurring campaigns
- ✅ FastAPI server with real video generation endpoint
- ✅ 19 passing tests

### Next
1. **Pull on codespace**: `git pull && pip install -r requirements.txt`
2. **Save cookies**: Login to TikTok/IG/YT once, run `cookie-save tiktok myprofile`
3. **Auto-post**: `post-video <path> tiktok`
4. **Drip campaign**: `schedule-campaign "Skincare X" 1440 7` (7 days, daily)

### Commands
```bash
python3 main.py campaign "Product Name"
python3 main.py analyze "Product Name"
python3 main.py search "keyword"
python3 main.py generate-video "Script here" [product_image.jpg]
python3 main.py post-video output.mp4 tiktok
python3 main.py cookie-save tiktok myprofile
python3 main.py schedule-campaign "Product" 1440 7
python3 main.py scheduler
python3 main.py api
```

### Architecture
- VPS: 9router API gateway + Cloudflare tunnel + code development
- Codespace: heavy lifting (video gen, Playwright posting, tests)
- GitHub: source of truth
