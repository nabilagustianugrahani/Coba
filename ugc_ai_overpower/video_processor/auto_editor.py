import logging
import os
import tempfile
import urllib.request

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

    def _apply_dynamic_zoom(self, clip, zoom_ratio=1.15):
        try:
            w, h = clip.w, clip.h
            zoomed = clip.resized(zoom_ratio)
            x_center = zoomed.w / 2
            y_center = zoomed.h / 2
            cropped = zoomed.cropped(
                x1=x_center - w/2,
                y1=y_center - h/2,
                x2=x_center + w/2,
                y2=y_center + h/2
            )
            return cropped
        except Exception as e:
            logger.warning(f"Dynamic zoom failed: {e}. Returning original clip.")
            return clip

    def _fetch_satisfying_gameplay(self, duration) -> bytes:
        from moviepy import ColorClip, TextClip, CompositeVideoClip
        try:
            base = ColorClip(size=(1080, 960), color=(100, 200, 100), duration=duration)
            try:
                txt = TextClip(text="SATISFYING MINECRAFT/GTA GAMEPLAY", font=self.font_path, font_size=50, color='white')
                txt = txt.with_position('center').with_duration(duration)
                base = CompositeVideoClip([base, txt])
            except Exception:
                pass

            out_path = tempfile.mktemp(suffix=".mp4")
            base.write_videofile(out_path, fps=24, codec="libx264", logger=None)
            with open(out_path, "rb") as f:
                b = f.read()
            os.remove(out_path)
            return b
        except Exception as e:
            logger.error(f"Failed to generate satisfying gameplay: {e}")
            return None

    def _apply_split_screen(self, base_clip):
        logger.info("Applying Brainrot/Dopamine Split-Screen Layout...")
        try:
            from moviepy import VideoFileClip, clips_array
            duration = base_clip.duration
            top_half = base_clip.resized(width=1080)
            if top_half.h > 960:
                y_center = top_half.h / 2
                top_half = top_half.cropped(y1=y_center-480, y2=y_center+480)
            elif top_half.h < 960:
                top_half = top_half.resized((1080, 960))

            gameplay_bytes = self._fetch_satisfying_gameplay(duration)
            if gameplay_bytes:
                bot_path = tempfile.mktemp(suffix=".mp4")
                with open(bot_path, "wb") as f:
                    f.write(gameplay_bytes)
                bottom_half = VideoFileClip(bot_path).without_audio()
            else:
                from moviepy import ColorClip
                bottom_half = ColorClip(size=(1080, 960), color=(50,50,50), duration=duration)

            final_split = clips_array([[top_half], [bottom_half]])
            return final_split
        except Exception as e:
            logger.error(f"Split-screen processing failed: {e}. Falling back to normal video.")
            return base_clip

    def _insert_b_roll_clips(self, base_clip, b_roll_timestamps: list):
        from moviepy import VideoFileClip, CompositeVideoClip
        if not b_roll_timestamps:
            return base_clip, []

        logger.info("Integrating B-Roll clips into main timeline...")
        overlays = []
        temp_files = []
        for b_roll in b_roll_timestamps:
            start_t = b_roll.get("start")
            end_t = b_roll.get("end")
            clip_bytes = b_roll.get("clip_bytes")
            if not clip_bytes: continue

            out_path = tempfile.mktemp(suffix=".mp4")
            temp_files.append(out_path)
            with open(out_path, "wb") as f:
                f.write(clip_bytes)
            try:
                b_clip = VideoFileClip(out_path)
                b_clip = self._apply_dynamic_zoom(b_clip)
                b_clip = b_clip.resized(width=1080)
                if b_clip.h > 960:
                     y_center = b_clip.h / 2
                     b_clip = b_clip.cropped(y1=y_center-480, y2=y_center+480)
                b_clip = b_clip.with_start(start_t).with_end(end_t).with_position(("center", 0))
                b_clip = b_clip.without_audio()
                overlays.append(b_clip)
            except Exception as e:
                logger.error(f"Failed to load B-Roll clip: {e}")

        if overlays:
            return CompositeVideoClip([base_clip] + overlays), temp_files
        return base_clip, []

    def _apply_live_commerce_overlays(self, live_chat_schedule: list):
        """
        Creates visual UI overlays resembling TikTok/Shopee Live comments.
        """
        from moviepy import TextClip, ColorClip, CompositeVideoClip
        overlays = []

        logger.info(f"Generating {len(live_chat_schedule)} Live Commerce Chat Overlays...")

        for chat in live_chat_schedule:
            try:
                username = chat.get("username", "user")
                comment = chat.get("comment", "")
                start_t = chat.get("start", 0)
                end_t = chat.get("end", 5)

                # Create a semi-transparent background bubble for the chat
                # In moviepy v2, ColorClip doesn't easily support rounded corners or pure RGBA alpha compositing
                # natively without complex masking, so we use a dark semi-transparent rectangle.

                # Text for Username
                user_txt = TextClip(text=f"@{username}", font=self.font_path, font_size=35, color="orange")
                # Text for Comment
                comm_txt = TextClip(text=comment, font=self.font_path, font_size=40, color="white")

                # Approximate width and height
                w = max(user_txt.w, comm_txt.w) + 40
                h = user_txt.h + comm_txt.h + 30

                bg = ColorClip(size=(w, h), color=(30, 30, 30), duration=(end_t - start_t))
                # Add opacity using with_opacity (v2 syntax) or similar
                # Just keeping it opaque dark grey for fail-safe rendering if alpha fails

                user_txt = user_txt.with_position((20, 10))
                comm_txt = comm_txt.with_position((20, user_txt.h + 15))

                bubble = CompositeVideoClip([bg, user_txt, comm_txt])
                # Position it on the left side, slightly above the middle (simulating a live chat feed)
                bubble = bubble.with_start(start_t).with_end(end_t).with_position((50, 600))

                overlays.append(bubble)
            except Exception as e:
                logger.warning(f"Failed to create live chat overlay: {e}")

        return overlays

    def apply_automated_factory_edit(self, video_bytes: bytes, audio_bytes: bytes, script: str, b_roll_data: list = None, live_chat_data: list = None) -> bytes:
        logger.info("Executing SOTA Brainrot/Dopamine Factory Edit with Multi-Persona & Live Overlays...")
        temp_paths = []
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip

            vid_path = tempfile.mktemp(suffix=".mp4")
            temp_paths.append(vid_path)
            with open(vid_path, "wb") as f:
                f.write(video_bytes)

            aud_path = tempfile.mktemp(suffix=".mp3")
            temp_paths.append(aud_path)
            with open(aud_path, "wb") as f:
                f.write(audio_bytes)

            timestamps = self._simulate_whisper_timestamps(aud_path, script)

            base_clip = VideoFileClip(vid_path)

            # Base Zoom
            base_clip = self._apply_dynamic_zoom(base_clip, 1.1)

            # Apply Split-Screen FIRST
            base_clip = self._apply_split_screen(base_clip)

            layers = [base_clip]

            # Insert B-Roll
            if b_roll_data:
                base_clip_with_broll, broll_temp_paths = self._insert_b_roll_clips(base_clip, b_roll_data)
                temp_paths.extend(broll_temp_paths)
                layers = [base_clip_with_broll] # Update the base layer

            # Insert Live Commerce Overlays
            if live_chat_data:
                chat_overlays = self._apply_live_commerce_overlays(live_chat_data)
                layers.extend(chat_overlays)

            # Apply Hormozi Captions
            magick_failed = False
            for item in timestamps:
                if magick_failed:
                    break
                try:
                    txt = TextClip(
                        font=self.font_path,
                        text=item["word"].upper(),
                        font_size=80,
                        color='yellow',
                        stroke_color='black',
                        stroke_width=4
                    )
                    txt = txt.with_position(('center', 0.5), relative=True).with_start(item["start"]).with_end(item["end"])
                    layers.append(txt)
                except Exception as e:
                    logger.warning(f"TextClip failed (likely ImageMagick issue): {e}. Falling back to clean video.")
                    magick_failed = True
                    break

            if len(layers) > 1:
                final_video = CompositeVideoClip(layers)
            else:
                logger.info("Skipping overlays to ensure flawless output.")
                final_video = layers[0]

            out_path = tempfile.mktemp(suffix=".mp4")
            temp_paths.append(out_path)

            final_video.write_videofile(out_path, fps=24, codec="libx264", logger=None)

            with open(out_path, "rb") as f:
                final_video_bytes = f.read()

            for p in temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass

            return final_video_bytes

        except Exception as e:
            logger.error(f"Auto-Editor encountered a severe error: {e}. Returning original video.")
            for p in temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass
            return video_bytes

if __name__ == "__main__":
    print("Auto Editor initialized.")
