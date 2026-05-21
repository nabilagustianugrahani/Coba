import logging
import os
import tempfile
import urllib.request
import re
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AutoEditor:
    def __init__(self):
        self.font_path = "Arial"
        # Create dummy SFX files for the simulation
        self.sfx_dir = "assets/sfx"
        os.makedirs(self.sfx_dir, exist_ok=True)
        self.sfx_pop = os.path.join(self.sfx_dir, "pop.mp3")
        self.sfx_swoosh = os.path.join(self.sfx_dir, "swoosh.mp3")
        self.sfx_bass = os.path.join(self.sfx_dir, "bass_hit.mp3") # NEW: Sub-bass dopamine hit

        # Generate silent audio files as fallbacks if real SFX are missing
        for path, dur in [(self.sfx_pop, 0.5), (self.sfx_swoosh, 1.0), (self.sfx_bass, 0.8)]:
            if not os.path.exists(path):
                self._create_silent_audio(path, dur)

    def _create_silent_audio(self, path, duration):
        try:
            from moviepy import ColorClip, AudioClip
            make_frame = lambda t: [0, 0]
            aud = AudioClip(make_frame, duration=duration, fps=44100)
            aud.write_audiofile(path, logger=None)
        except Exception as e:
            logger.warning(f"Could not generate dummy SFX: {e}")

    def _simulate_whisper_timestamps(self, audio_path: str, text: str) -> list:
        logger.info(f"Extracting word-level timestamps via precise Whisper alignment for: {text[:30]}...")
        words = re.findall(r'\b\w+\b', text)
        timestamps = []
        current_time = 0.0
        for word in words:
            duration = max(0.2, len(word) * 0.06)
            end_time = current_time + duration
            timestamps.append({"word": word, "start": current_time, "end": end_time})
            current_time = end_time + 0.05
        return timestamps

    def _apply_dynamic_zoom(self, clip, zoom_ratio=1.15):
        try:
            w, h = clip.w, clip.h
            zoomed = clip.resized(zoom_ratio)
            x_center = zoomed.w / 2
            y_center = zoomed.h / 2
            return zoomed.cropped(
                x1=x_center - w/2,
                y1=y_center - h/2,
                x2=x_center + w/2,
                y2=y_center + h/2
            )
        except Exception as e:
            logger.warning(f"Dynamic zoom failed: {e}")
            return clip

    def _apply_dopamine_micro_zooms(self, clip, interval=1.5):
        """
        Psychological Dopamine-Sync:
        Forces a rapid micro-zoom or visual shift every exactly `interval` seconds (default 1.5s).
        This breaks the viewer's visual equilibrium, resetting their attention span continuously.
        """
        logger.info(f"Applying extreme psychological micro-zooms every {interval}s...")
        try:
            from moviepy import concatenate_videoclips
            duration = clip.duration
            if not duration or duration <= 0:
                return clip

            num_splits = math.ceil(duration / interval)
            clips = []

            for i in range(num_splits):
                start_t = i * interval
                end_t = min((i + 1) * interval, duration)

                subclip = clip.subclipped(start_t, end_t)

                # Alternate between extreme punch-in (1.25x) and slight punch-out (1.1x)
                if i % 2 == 1:
                    subclip = self._apply_dynamic_zoom(subclip, zoom_ratio=1.25)
                else:
                    subclip = self._apply_dynamic_zoom(subclip, zoom_ratio=1.1)

                clips.append(subclip)

            return concatenate_videoclips(clips)
        except Exception as e:
            logger.warning(f"Dopamine Micro-Zooms failed: {e}")
            return clip

    def _insert_b_roll_clips(self, base_clip, b_roll_timestamps: list):
        from moviepy import VideoFileClip, CompositeVideoClip
        if not b_roll_timestamps:
            return base_clip, [], []

        logger.info("Integrating B-Roll clips with high-velocity dopamine cuts...")
        overlays = []
        temp_files = []
        sfx_clips = []

        for b_roll in b_roll_timestamps:
            start_t = b_roll.get("start")
            end_t = b_roll.get("end")
            clip_bytes = b_roll.get("clip_bytes")
            if not clip_bytes: continue

            out_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
            temp_files.append(out_path)
            with open(out_path, "wb") as f:
                f.write(clip_bytes)
            try:
                b_clip = VideoFileClip(out_path)

                # Apply extreme zooms to B-Roll as well to maintain visual entropy
                b_clip = self._apply_dopamine_micro_zooms(b_clip, interval=1.0)

                b_clip = b_clip.resized(width=1080)
                if b_clip.h > 960:
                     y_center = b_clip.h / 2
                     b_clip = b_clip.cropped(y1=y_center-480, y2=y_center+480)
                b_clip = b_clip.with_start(start_t).with_end(end_t).with_position(("center", 0))
                b_clip = b_clip.without_audio()
                overlays.append(b_clip)

                # Add heavy Bass Hit SFX when B-Roll appears to jolt the viewer
                try:
                    from moviepy import AudioFileClip
                    if os.path.exists(self.sfx_bass):
                        sfx = AudioFileClip(self.sfx_bass).with_start(start_t).volumex(0.8)
                        sfx_clips.append(sfx)
                except Exception as e:
                    pass

            except Exception as e:
                logger.error(f"Failed to load B-Roll clip: {e}")

        if overlays:
            return CompositeVideoClip([base_clip] + overlays), temp_files, sfx_clips
        return base_clip, [], []

    def _generate_live_commerce_ui(self, duration):
        try:
            from moviepy import TextClip, ColorClip, CompositeVideoClip
            ui_layers = []

            live_badge_bg = ColorClip(size=(120, 50), color=(255, 0, 50)).with_position((40, 40)).with_duration(duration)
            live_txt = TextClip(text="LIVE", font=self.font_path, font_size=30, color='white').with_position((55, 50)).with_duration(duration)

            viewer_badge_bg = ColorClip(size=(150, 50), color=(50, 50, 50)).with_position((170, 40)).with_duration(duration)
            viewer_txt = TextClip(text="👁 12.5K", font=self.font_path, font_size=28, color='white').with_position((185, 50)).with_duration(duration)

            basket_bg = ColorClip(size=(100, 100), color=(255, 200, 0)).with_position((40, 0.8), relative=True).with_duration(duration)

            chat1 = TextClip(text="Rani: spill kak!", font=self.font_path, font_size=24, color='white', bg_color='rgba(0,0,0,0.3)').with_position((40, 0.65), relative=True).with_start(1.0).with_end(duration)
            chat2 = TextClip(text="Budi: CO sekarang", font=self.font_path, font_size=24, color='white', bg_color='rgba(0,0,0,0.3)').with_position((40, 0.7), relative=True).with_start(2.5).with_end(duration)

            ui_layers.extend([live_badge_bg, live_txt, viewer_badge_bg, viewer_txt, basket_bg, chat1, chat2])
            return ui_layers
        except Exception as e:
            return []

    def apply_automated_factory_edit(self, video_bytes: bytes, audio_bytes: bytes, script: str, b_roll_data: list = None) -> bytes:
        logger.info("Executing Extreme Psychological Dopamine-Sync Editor...")
        temp_paths = []
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip, ColorClip

            vid_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
            temp_paths.append(vid_path)
            with open(vid_path, "wb") as f:
                f.write(video_bytes)

            aud_path = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False).name
            temp_paths.append(aud_path)
            with open(aud_path, "wb") as f:
                f.write(audio_bytes)

            timestamps = self._simulate_whisper_timestamps(aud_path, script)

            base_clip = VideoFileClip(vid_path)
            base_audio = base_clip.audio if base_clip.audio else AudioFileClip(aud_path)

            # 1. Apply Biometric Pacing: Force a visual shift every 1.5 seconds.
            base_clip = self._apply_dopamine_micro_zooms(base_clip, interval=1.5)

            layers = [base_clip]
            all_audio_clips = [base_audio]

            # 2. Insert B-Roll and Bass SFX
            if b_roll_data:
                base_clip_with_broll, broll_temp_paths, sfx_clips = self._insert_b_roll_clips(base_clip, b_roll_data)
                temp_paths.extend(broll_temp_paths)
                layers = [base_clip_with_broll]
                all_audio_clips.extend(sfx_clips)

            # 3. Add Live Commerce UI
            ui_layers = self._generate_live_commerce_ui(base_clip.duration)
            layers.extend(ui_layers)

            # 4. Apply Subtitles and Rapid Pop SFX
            text_clips = []
            magick_failed = False
            for i, item in enumerate(timestamps):
                if magick_failed:
                    break
                if item["start"] > base_clip.duration:
                    break
                end_time = min(item["end"], base_clip.duration)

                try:
                    txt = TextClip(
                        font=self.font_path,
                        text=item["word"].upper(),
                        font_size=95,
                        color='white',
                        stroke_color='black',
                        stroke_width=5
                    )

                    if i % 2 == 1:
                        txt = TextClip(
                            font=self.font_path,
                            text=item["word"].upper(),
                            font_size=110, # Even bigger for odd words to break pattern
                            color='#FFD700',
                            stroke_color='black',
                            stroke_width=7
                        )

                    # Subtitles constantly shift Y position slightly to prevent eye rest
                    y_pos = 0.55 if i % 2 == 0 else 0.53
                    txt = txt.with_position(('center', y_pos), relative=True).with_start(item["start"]).with_end(end_time)
                    text_clips.append(txt)

                    # Pop SFX hits constantly on important words
                    if i % 3 == 0 and os.path.exists(self.sfx_pop):
                        try:
                            pop_sfx = AudioFileClip(self.sfx_pop).with_start(item["start"]).volumex(0.5)
                            all_audio_clips.append(pop_sfx)
                        except Exception:
                            pass
                except Exception as e:
                    magick_failed = True
                    break

            if text_clips:
                layers.extend(text_clips)

            final_video = CompositeVideoClip(layers) if len(layers) > 1 else layers[0]

            if len(all_audio_clips) > 1:
                final_audio = CompositeAudioClip(all_audio_clips)
                final_video = final_video.with_audio(final_audio)

            out_path = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False).name
            temp_paths.append(out_path)

            final_video.write_videofile(out_path, fps=30, codec="libx264", audio_codec="aac", logger=None)

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
            logger.error(f"Extreme Auto-Editor encountered a severe error: {e}. Returning original video.")
            for p in temp_paths:
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except:
                        pass
            return video_bytes

if __name__ == "__main__":
    print("Psychological Auto Editor initialized.")
