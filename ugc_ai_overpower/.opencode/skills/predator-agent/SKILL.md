# 🦅 Predator Agent — Viral Intelligence

## Role
**The most powerful agent in the swarm.** Scrapes TikTok/IG for trending content, reverse-engineers viral hooks, predicts next trends, and auto-steals competitor strategies. Self-improves via reinforcement learning from posting performance data.

## Handles Messages
| msg_type | Trigger | Action |
|----------|---------|--------|
| `scavenge_trends` | orchestrator/CLI | Scrape trending content from target niches |
| `analyze_viral_dna` | orchestrator/CLI | Deconstruct viral videos → hook patterns, pacing, audio, visual formula |
| `generate_zombie_script` | orchestrator/CLI | Generate high-probability viral script using trend data |
| `report_competitor` | orchestrator/CLI | Full competitive landscape report for a niche |
| `inject_viral_dna` | self | Inject latest viral patterns into script templates |
| `predator_tick` | self (tick) | Scheduled scavenge + analyze + update cycle |

## Sends Messages
- `viral_patterns` → broadcaster to all agents (script_writer, video_producer)
- `competitor_report` → orchestrator
- `zombie_scripts` → orchestrator (for direct campaign injection)

## Viral DNA Analysis Pipeline

### 1. SCAVENGE 🕵️
```
TikTok trending → extract top 50 videos/niche
  ├── Hook text & delivery style
  ├── Audio track (spliced reference)
  ├── Visual pacing (cuts per second)
  ├── Engagement ratio (likes/views, comments/views)
  └── Posting time & account authority
```

### 2. DECONSTRUCT 🔬
```
For each viral video:
  ├── Hook classification (question, stat, shock, curiosity gap)
  ├── Pacing profile (timestamp → event map)
  ├── Audio-style embedding
  ├── Visual composition (text overlay, framing, color grading)
  └── CTA strength scoring
```

### 3. SYNTHESIZE 🧬
```
Cross-reference all videos → generate:
  ├── Winning hook templates for niche
  ├── Optimal pacing curve
  ├── Best-performing audio styles
  ├── Visual formula (text placement, thumbnail style)
  └── Posting time heatmap
```

### 4. INFECT 🧟
```
Inject viral DNA into script_writer templates:
  ├── Update HOOKS with harvested winning hooks
  ├── Update TEMPLATES with proven pacing
  ├── Provide influencer direction (energy level, tone, camera style)
  └── Pass audio references to video_producer
```

## Reinforcement Learning Loop
```
Post performance (likes, shares, comments, watch time)
  → Compare against viral baseline
  → Score each DNA element (hook type, pacing, audio, CTA)
  → Amplify winning elements, prune losers
  → Next batch performs better
```

## Tools
| Tool | Purpose |
|------|---------|
| `browser-use` (BUAgent) | Scrape TikTok/IG trending pages |
| `9router` AI | Analyze video text, generate patterns |
| `yt-dlp` | Download reference clips for audio analysis |
| `whisper` | Transcribe viral video audio to text |
| `chromadb` | Store viral DNA profiles for similarity search |
| `sqlite` | Track performance feedback per pattern |

## PredatorConfig
```yaml
max_concurrent: 2
poll_interval: 15.0
scavenge_interval_minutes: 60
niches: [skincare, fashion, food, tech, lifestyle, fitness, beauty]
videos_per_niche: 50
min_views_threshold: 100000
min_engagement_rate: 0.05
dna_db_path: data/viral_dna.db
use_claude_analysis: true
auto_infect_agents: true
post_performance_feedback: true
```

## Agent Communication
```
predator → orchestrator: "competitor_report", "zombie_scripts"
predator → script_writer: "viral_patterns" (injects winning hooks/templates)
predator → video_producer: "viral_patterns" (injects pacing/formula)
predator → analytics: "request_performance" (closes RL loop)
```
