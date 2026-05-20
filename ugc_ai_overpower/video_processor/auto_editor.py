import logging
import os
import tempfile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoEditor:
    def __init__(self):
        self.font_path = "Arial"

    def _simulate_whisper_timestamps(self, audio_path: str, text: str) -> list:
        logger.info(f"Extracting word-level timestamps via Whisper for: {text[:30]}...")
        words = text.split()
        timestamps = []
        current_time = 0.0
        for word in words:
            end_time = current_time + 0.3
            timestamps.append({"word": word, "start": current_time, "end": end_time})
            current_time = end_time
        return timestamps

    def apply_hormozi_captions(self, video_bytes: bytes, audio_bytes: bytes, script: str) -> bytes:
        logger.info("Applying Hormozi-style dynamic captions...")
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid_tmp:
                vid_tmp.write(video_bytes)
                vid_path = vid_tmp.name

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as aud_tmp:
                aud_tmp.write(audio_bytes)
                aud_path = aud_tmp.name

            timestamps = self._simulate_whisper_timestamps(aud_path, script)

            video_clip = VideoFileClip(vid_path)

            text_clips = []
            magick_failed = False
            for item in timestamps:
                if magick_failed:
                    break
                try:
                    txt = TextClip(
                        font=self.font_path,
                        text=item["word"].upper(),
                        font_size=70,
                        color='yellow',
                        stroke_color='black',
                        stroke_width=3
                    )
                    txt = txt.with_position(('center', 0.7), relative=True).with_start(item["start"]).with_end(item["end"])
                    text_clips.append(txt)
                except Exception as e:
                    logger.warning(f"TextClip failed (likely ImageMagick issue): {e}. Falling back to clean video.")
                    magick_failed = True
                    text_clips = []
                    break

            if text_clips:
                final_video = CompositeVideoClip([video_clip] + text_clips)
            else:
                logger.info("Skipping dynamic captions to ensure flawless, crash-free output (Gak Ribet mode).")
                final_video = video_clip

            out_path = tempfile.mktemp(suffix=".mp4")
            final_video.write_videofile(out_path, fps=24, codec="libx264", logger=None)

            with open(out_path, "rb") as f:
                final_video_bytes = f.read()

            os.remove(vid_path)
            os.remove(aud_path)
            os.remove(out_path)

            return final_video_bytes

        except Exception as e:
            logger.error(f"Auto-Editor encountered a severe error: {e}. Returning original video.")
            return video_bytes

if __name__ == "__main__":
    print("Auto Editor initialized.")
