import os, random, requests, asyncio, datetime, logging
from moviepy.editor import *
from moviepy.video.fx.all import fadein, fadeout
import edge_tts

log = logging.getLogger(__name__)

# Color themes for brand consistency
THEMES = {
    "default":  {"bg": (30, 30, 40), "text": "white", "stroke": "black", "accent": "#7b2ff7"},
    "dark":     {"bg": (10, 10, 15), "text": "#e0e0e0", "stroke": "black", "accent": "#00d4ff"},
    "warm":     {"bg": (40, 25, 20), "text": "#fff5e6", "stroke": "#3a1a0a", "accent": "#ff6b35"},
    "fresh":    {"bg": (20, 35, 25), "text": "#e6ffe6", "stroke": "#0a3a1a", "accent": "#4ade80"},
    "luxury":   {"bg": (25, 20, 30), "text": "#f0e6ff", "stroke": "#1a0a2e", "accent": "#a855f7"},
    "bright":   {"bg": (50, 50, 60), "text": "white", "stroke": "#1a1a2e", "accent": "#facc15"},
}

# Background stock queries per niche
BG_QUERIES = {
    "lifestyle":   ["lifestyle", "daily routine", "morning routine", "coffee", "work from home"],
    "skincare":    ["skincare", "beauty", "face", "glowing skin", "spa"],
    "fashion":     ["fashion", "outfit", "style", "shopping", "wardrobe"],
    "food":        ["food", "cooking", "kitchen", "delicious", "restaurant"],
    "tech":        ["technology", "office", "digital", "laptop", "workspace"],
    "fitness":     ["fitness", "workout", "gym", "running", "yoga"],
    "muslim":      ["ramadan", "prayer", "mosque", "hijab fashion", "modest fashion"],
}

# Voice options per gender/niche
VOICES = {
    "male":   ["id-ID-ArdiNeural", "id-ID-DimasNeural"],
    "female": ["id-ID-GadisNeural", "id-ID-AyuNeural"],
}

TEMPLATE_INTROS = [
    "Hai semuanya! Kembali lagi sama gue!",
    "Halo guys! Gue mau share sesuatu nih!",
    "Welcome back! Kali ini gue bakal bahas...",
    "Eh guys, lo pada tau gak sih...",
]

TEMPLATE_OUTROS = [
    "Gitu aja! Jangan lupa like dan subscribe!",
    "Semoga bermanfaat! Share ke temen lo ya!",
    "Makasih udah nonton! Sampai jumpa!",
    "Komen di bawah ya! Gue bales satu-satu!",
]


class VideoComposer:
    def __init__(self, output_dir="output/videos", default_theme="default", watermark_text=""):
        self.output_dir = output_dir
        self.default_theme = THEMES.get(default_theme, THEMES["default"])
        self.watermark_text = watermark_text
        os.makedirs(output_dir, exist_ok=True)
        self._cache_dir = os.path.join(output_dir, ".cache")
        os.makedirs(self._cache_dir, exist_ok=True)

    def set_theme(self, theme_name: str):
        if theme_name in THEMES:
            self.default_theme = THEMES[theme_name]

    def set_watermark(self, text: str):
        self.watermark_text = text

    def _download_stock_video(self, queries: list, duration=10):
        """Download free stock video from Pexels as background."""
        query = random.choice(queries)
        safe_name = query.replace(" ", "_").lower()
        cached = os.path.join(self._cache_dir, f"{safe_name}.mp4")
        if os.path.exists(cached):
            return cached

        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                params={"query": query, "per_page": 5, "orientation": "portrait"},
                headers={"Authorization": os.getenv("PEXELS_API_KEY", "")},
                timeout=10,
            )
            videos = resp.json().get("videos", [])
            if videos:
                chosen = random.choice(videos)
                files = chosen.get("video_files", [])
                best = max(files, key=lambda f: f.get("width", 0) or 0)
                r = requests.get(best["link"], timeout=30)
                with open(cached, "wb") as f:
                    f.write(r.content)
                return cached
        except Exception as e:
            log.warning("Stock download failed: %s", e)
        return None

    async def _generate_voiceover(self, text, output_path, voice="id-ID-ArdiNeural"):
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)
        return output_path

    def _split_into_segments(self, text, max_chars=120):
        import re
        sentences = re.split(r'(?<=[.!?])\s+', text)
        segments = []
        current = ""
        for s in sentences:
            if len(current) + len(s) <= max_chars:
                current += " " + s if current else s
            else:
                if current:
                    segments.append(current)
                current = s
        if current:
            segments.append(current)
        return segments if segments else [text]

    def _time_per_segment(self, total_duration, num_segments):
        if num_segments == 0:
            return []
        each = total_duration / num_segments
        return [(i * each, (i + 1) * each) for i in range(num_segments)]

    def create_ugc_video(
        self,
        script,
        influencer,
        product_image=None,
        niche="lifestyle",
        gender="male",
        add_intro=False,
        add_outro=False,
        theme_override=None,
    ) -> str:
        theme = THEMES.get(theme_override, self.default_theme) if theme_override else self.default_theme
        voice = random.choice(VOICES.get(gender, VOICES["male"]))
        bg_queries = BG_QUERIES.get(niche, BG_QUERIES["lifestyle"])

        # Voiceover
        voiceover_path = os.path.join(self.output_dir, f"vo_{influencer}_{random.randint(1000,9999)}.mp3")
        asyncio.run(self._generate_voiceover(script, voiceover_path, voice))
        audio_clip = AudioFileClip(voiceover_path)
        audio_duration = audio_clip.duration

        # Build final script with intro/outro
        full_text = script
        if add_intro:
            full_text = random.choice(TEMPLATE_INTROS) + " " + full_text
        if add_outro:
            full_text = full_text + " " + random.choice(TEMPLATE_OUTROS)

        # Background
        background = self._download_stock_video(bg_queries, int(audio_duration))
        if background:
            bg_clip = VideoFileClip(background).loop(duration=audio_duration)
            bg_clip = bg_clip.resize((720, 1280))
            if bg_clip.duration > audio_duration:
                bg_clip = bg_clip.subclip(0, audio_duration)
        else:
            bg_clip = ColorClip(size=(720, 1280), color=theme["bg"], duration=audio_duration)

        bg_clip = bg_clip.set_audio(audio_clip)
        bg_clip = fadein(bg_clip, 0.3).fx(fadeout, 0.5)

        overlay_clips = [bg_clip]
        segments = self._split_into_segments(full_text)
        times = self._time_per_segment(audio_duration, len(segments))

        y_pos = 550
        for i, seg in enumerate(segments):
            start_t, end_t = times[i] if i < len(times) else (0, audio_duration)
            txt = TextClip(
                seg, fontsize=42, color=theme["text"],
                stroke_color=theme["stroke"], stroke_width=2,
                method="caption", size=(660, None), align="center"
            ).set_position(("center", y_pos)).set_duration(end_t - start_t).set_start(start_t)
            overlay_clips.append(txt)

        # Product image overlay
        if product_image and os.path.exists(product_image):
            img = (ImageClip(product_image)
                   .resize(height=140)
                   .set_position(("center", 50))
                   .set_duration(audio_duration))
            overlay_clips.append(img)

        # Watermark
        if self.watermark_text:
            wm = (TextClip(self.watermark_text, fontsize=18, color="white", stroke_color="black", stroke_width=1)
                  .set_position(("right", "bottom"))
                  .set_duration(audio_duration)
                  .set_opacity(0.6))
            overlay_clips.append(wm)

        final = CompositeVideoClip(overlay_clips, size=(720, 1280))
        final = final.subclip(0, min(final.duration, 75))

        output = os.path.join(
            self.output_dir,
            f"ugc_{influencer}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{random.randint(100,999)}.mp4"
        )
        final.write_videofile(
            output, codec="libx264", audio_codec="aac",
            fps=20, threads=2, preset="ultrafast",
            logger=None
        )
        final.close()
        audio_clip.close()
        try:
            os.remove(voiceover_path)
        except OSError:
            pass
        return output

    def create_batch_videos(self, scripts: list, product_image: str = "", niche: str = "lifestyle",
                            max_workers: int = 4) -> list:
        """Generate videos for multiple scripts using ThreadPool."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        results = []
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {}
            for i, item in enumerate(scripts):
                fut = pool.submit(
                    self.create_ugc_video,
                    script=item.get("script", ""),
                    influencer=item.get("influencer", "creator"),
                    product_image=product_image,
                    niche=niche,
                    gender=item.get("gender", "male"),
                    add_intro=item.get("add_intro", True),
                    add_outro=item.get("add_outro", True),
                    theme_override=item.get("theme"),
                )
                fut_map[fut] = i
            for fut in as_completed(fut_map):
                idx = fut_map[fut]
                try:
                    path = fut.result()
                    results.append({"index": idx, "path": path})
                except Exception as e:
                    log.warning("Video %d failed: %s", idx, e)
        results.sort(key=lambda r: r["index"])
        return results
