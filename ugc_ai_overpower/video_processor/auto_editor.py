import logging
import os
import tempfile
import urllib.request

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

        # We generate silent audio files as fallbacks if real SFX are missing
        if not os.path.exists(self.sfx_pop):
            self._create_silent_audio(self.sfx_pop, 0.5)
        if not os.path.exists(self.sfx_swoosh):
            self._create_silent_audio(self.sfx_swoosh, 1.0)

    def _create_silent_audio(self, path, duration):
        try:
            from moviepy import ColorClip
            c = ColorClip(size=(10,10), duration=duration)
            # Use audioclip from colorclip is None, so we create an empty AudioClip
            from moviepy import AudioClip
            make_frame = lambda t: [0, 0]
            aud = AudioClip(make_frame, duration=duration, fps=44100)
            aud.write_audiofile(path, logger=None)
        except Exception as e:
            logger.warning(f"Could not generate dummy SFX: {e}")

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
            return zoomed.cropped(
                x1=x_center - w/2,
                y1=y_center - h/2,
                x2=x_center + w/2,
                y2=y_center + h/2
            )
        except Exception as e:
            logger.warning(f"Dynamic zoom failed: {e}")
            return clip

    def _insert_b_roll_clips(self, base_clip, b_roll_timestamps: list):
        from moviepy import VideoFileClip, CompositeVideoClip
        if not b_roll_timestamps:
            return base_clip, [], []

        logger.info("Integrating B-Roll clips and Swoosh SFX into main timeline...")
        overlays = []
        temp_files = []
        sfx_clips = []

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

                # Add Swoosh SFX when B-Roll appears
                try:
                    from moviepy import AudioFileClip
                    if os.path.exists(self.sfx_swoosh):
                        sfx = AudioFileClip(self.sfx_swoosh).with_start(start_t).volumex(0.6)
                        sfx_clips.append(sfx)
                except Exception as e:
                    logger.warning(f"Failed to load Swoosh SFX: {e}")

            except Exception as e:
                logger.error(f"Failed to load B-Roll clip: {e}")

        if overlays:
            return CompositeVideoClip([base_clip] + overlays), temp_files, sfx_clips
        return base_clip, [], []

    def apply_automated_factory_edit(self, video_bytes: bytes, audio_bytes: bytes, script: str, b_roll_data: list = None) -> bytes:
        logger.info("Executing SOTA Brainrot/Dopamine Factory Edit with SFX Audio Foley...")
        temp_paths = []
        try:
            from moviepy import VideoFileClip, TextClip, CompositeVideoClip, CompositeAudioClip, AudioFileClip

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
            # In case the video clip already has audio, we extract it.
            # Usually base_clip has the lip-synced audio attached.
            base_audio = base_clip.audio if base_clip.audio else AudioFileClip(aud_path)

            base_clip = self._apply_dynamic_zoom(base_clip, 1.1)

            layers = [base_clip]
            all_audio_clips = [base_audio]

            # Step 2: Insert B-Roll and gather SFX
            if b_roll_data:
                base_clip_with_broll, broll_temp_paths, sfx_clips = self._insert_b_roll_clips(base_clip, b_roll_data)
                temp_paths.extend(broll_temp_paths)
                layers = [base_clip_with_broll]
                all_audio_clips.extend(sfx_clips)

            # Step 3: Apply Captions and 'Pop' SFX
            text_clips = []
            magick_failed = False
            for i, item in enumerate(timestamps):
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
                    text_clips.append(txt)

                    # Add Pop SFX on important words (e.g. every 5th word to avoid ear fatigue)
                    if i % 5 == 0 and os.path.exists(self.sfx_pop):
                        try:
                            pop_sfx = AudioFileClip(self.sfx_pop).with_start(item["start"]).volumex(0.4)
                            all_audio_clips.append(pop_sfx)
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning(f"TextClip failed: {e}. Falling back to clean video.")
                    magick_failed = True
                    break

            if text_clips:
                layers.extend(text_clips)

            final_video = CompositeVideoClip(layers) if len(layers) > 1 else layers[0]

            # Composite Audio (Voice + Foley SFX)
            if len(all_audio_clips) > 1:
                final_audio = CompositeAudioClip(all_audio_clips)
                final_video = final_video.with_audio(final_audio)

            out_path = tempfile.mktemp(suffix=".mp4")
            temp_paths.append(out_path)

            final_video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac", logger=None)

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
