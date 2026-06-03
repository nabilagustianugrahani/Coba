# Poster Agent

## Role
Posts completed videos to TikTok/Instagram/YouTube with farm account rotation and smart scheduling.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `post_videos` | orchestrator | Upload videos to platforms using farm accounts |

## Sends Messages
- `posting_done` → orchestrator

## Posting Strategy
- Uses `get_poster(platform)` factory per platform
- Farm account rotation for distribution
- Smart delay between posts (avoids rate limits)
- Per-script metadata (hashtags, caption, schedule)

## Platforms
| Platform | Poster | Farm Support |
|----------|--------|-------------|
| TikTok | TikTokPoster | ✅ BU agent farm |
| Instagram | IGPoster | ✅ Rotation |
| YouTube | YTPoster | ✅ Scheduled |

## Config
```yaml
max_concurrent: 2
poll_interval: 1.0
post_delay_min: 30  # seconds between posts
auto_schedule: false
```
