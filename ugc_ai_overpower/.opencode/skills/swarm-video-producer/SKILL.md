# Video Producer Agent

## Role
Renders UGC videos from scripts. Uses AI avatar (NAVA/HappyHorse) for face+TTS compositing, with overlay effects and product shots.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `render_videos` | orchestrator | Render N videos in parallel via Modal GPU |

## Sends Messages
- `videos_ready` → orchestrator

## Rendering Pipeline
1. **Primary**: `UGCVideoEditor` — full compositing (avatar + TTS + product + captions)
2. **Fallback**: `VideoComposer` — lightweight text-overlay video
3. **Avatar Engine**: NAVA/HappyHorse-1.0 audio-driven avatar via Modal
4. **TTS**: Edge-TTS / Kokoro-FastAPI for Indonesian voiceovers
5. **Thumbnail**: `ThumbnailGenerator` — auto-generates clickable thumbnails

## Quality Settings
- Resolution: 1080×1920 (TikTok vertical)
- FPS: 30
- Duration: 30–60s
- Codec: H.264

## Config
```yaml
max_concurrent: 1
poll_interval: 1.0
output_dir: output/videos
default_theme: default
worker_threads: 4
use_editor: true
```
