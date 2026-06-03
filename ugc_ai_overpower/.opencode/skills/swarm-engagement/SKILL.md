# Engagement Agent

## Role
Auto-engage (like, comment, follow) on target niche content to boost account authority and drive organic reach.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `engage_now` | orchestrator/CLI | Immediate engagement burst on specified niche |
| `set_interval` | orchestrator/CLI | Change auto-engagement schedule |

## Self-Triggered (tick)
- Every `engage_hours` (default 4h): auto-engage on all registered niches
- Rotates: skincare → fashion → food → tech → lifestyle

## Engagement Actions (per burst)
| Action | Count |
|--------|-------|
| Likes | 10 |
| Follows | 3 |
| Comments | 2 |

## Comment Templates
Natural Indonesian reactions:
- "Mantap banget! 🔥"
- "Wah keren, gue juga pake ini!"
- "Share dong linknya kak!"
- etc. (rotated per burst)

## Tools
- `BUEngageAgent` — Browser-Use powered TikTok engagement bot
- Farm account rotation for natural activity patterns

## Config
```yaml
poll_interval: 30.0
engage_hours: 4
niches: [skincare, fashion, food, tech, lifestyle]
likes_per_burst: 10
follows_per_burst: 3
comments_per_burst: 2
```
