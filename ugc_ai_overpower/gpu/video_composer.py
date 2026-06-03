import os
import random
import requests
import asyncio
import datetime
from moviepy.editor import *
from moviepy.video.fx.all import fadein, fadeout
import edge_tts

class VideoComposer:
    def __init__(self, output_dir="output/videos"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def _download_stock_video(self, query="lifestyle", duration=10):
        """Download free stock video from Pexels as background."""
        cache_dir = os.path.join(self.output_dir, ".cache")
        os.makedirs(cache_dir, exist_ok=True)
        safe_name = query.replace(" ", "_").lower()
        cached = os.path.join(cache_dir, f"{safe_name}.mp4")
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
                video_url = best["link"]
                r = requests.get(video_url, timeout=30)
                with open(cached, "wb") as f:
                    f.write(r.content)
                return cached
        except Exception:
            pass
        return None

    async def generate_voiceover(self, text, output_filename="voiceover.mp3", voice="id-ID-ArdiNeural"):
        communicate = edge_tts.Communicate(text, voice)
        filepath = os.path.join(self.output_dir, output_filename)
        await communicate.save(filepath)
        return filepath

    def _split_into_segments(self, text, max_chars=120):
        """Split script into overlay segments at sentence boundaries."""
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

    def create_ugc_video(self, script, influencer, product_image=None) -> str:
        voiceover_path = asyncio.run(self.generate_voiceover(
            script, output_filename=f"{influencer}_voiceover.mp3"
        ))
        audio_clip = AudioFileClip(voiceover_path)
        audio_duration = audio_clip.duration

        background = self._download_stock_video("lifestyle", int(audio_duration))
        if background:
            bg_clip = VideoFileClip(background).loop(duration=audio_duration)
            bg_clip = bg_clip.resize((1080, 1920))
            if bg_clip.duration > audio_duration:
                bg_clip = bg_clip.subclip(0, audio_duration)
        else:
            bg_clip = ColorClip(size=(1080, 1920), color=(30, 30, 40), duration=audio_duration)

        bg_clip = bg_clip.set_audio(audio_clip)
        bg_clip = fadein(bg_clip, 0.5).fx(fadeout, 0.5)

        overlay_clips = [bg_clip]
        segments = self._split_into_segments(script)
        times = self._time_per_segment(audio_duration, len(segments))

        y_pos = 800
        for i, seg in enumerate(segments):
            start_t, end_t = times[i] if i < len(times) else (0, audio_duration)
            txt = TextClip(
                seg, fontsize=55, color="white",
                stroke_color="black", stroke_width=3,
                font="sans-serif-bold", method="caption",
                size=(900, None), align="center"
            ).set_position(("center", y_pos)).set_duration(end_t - start_t).set_start(start_t)
            overlay_clips.append(txt)

        if product_image and os.path.exists(product_image):
            img = (ImageClip(product_image)
                   .resize(height=200)
                   .set_position(("center", 100))
                   .set_duration(audio_duration))
            overlay_clips.append(img)

        final = CompositeVideoClip(overlay_clips, size=(1080, 1920))
        final = final.subclip(0, min(final.duration, 60))

        output = os.path.join(
            self.output_dir,
            f"{influencer}_ugc_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.mp4"
        )
        final.write_videofile(output, codec="libx264", audio_codec="aac", fps=24, threads=2)
        final.close()
        return output
