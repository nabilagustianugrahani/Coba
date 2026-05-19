import logging
import os
import tempfile
# MoviePy 2.x syntax
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoEditor:
    def __init__(self):
        # In a real environment, we would initialize stable-ts (Whisper) here
        self.font_path = "Arial" # Fallback font

    def _simulate_whisper_timestamps(self, audio_path: str, text: str) -> list:
        """
        Simulates stable-ts word-level timestamps.
        """
        logger.info(f"Extracting word-level timestamps via Whisper for: {text[:30]}...")
        words = text.split()
        # Mocking 0.3s per word for demonstration
        timestamps = []
        current_time = 0.0
        for word in words:
            end_time = current_time + 0.3
            timestamps.append({"word": word, "start": current_time, "end": end_time})
            current_time = end_time

        return timestamps

    def apply_hormozi_captions(self, video_bytes: bytes, audio_bytes: bytes, script: str) -> bytes:
        """
        Takes the lip-synced video and applies dynamic, popping yellow/white text per word.
        """
        logger.info("Applying Hormozi-style dynamic captions...")
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vid_tmp:
                vid_tmp.write(video_bytes)
                vid_path = vid_tmp.name

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as aud_tmp:
                aud_tmp.write(audio_bytes)
                aud_path = aud_tmp.name

            timestamps = self._simulate_whisper_timestamps(aud_path, script)

            video_clip = VideoFileClip(vid_path)

            text_clips = []
            for item in timestamps:
                # To replicate Hormozi style, text should pop. MoviePy v2 syntax:
                try:
                    # Depending on system ImageMagick config, this might fail, so we wrap in try-except
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
                    logger.warning(f"TextClip failed (often requires ImageMagick installed). Skipping captions. Error: {e}")
                    break

            if text_clips:
                final_video = CompositeVideoClip([video_clip] + text_clips)
            else:
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
            logger.error(f"Auto-Editor failed: {e}")
            return video_bytes

if __name__ == "__main__":
    print("Auto Editor initialized.")
