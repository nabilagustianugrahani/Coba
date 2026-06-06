# Architecture

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1: CLI (main.py)                                      │
│   - argparse subcommands                                    │
│   - daemon entry points                                     │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2: Orchestration (core/)                             │
│   - autoheal.py: rule-based incident response               │
│   - auto_pipeline.py: APScheduler-driven jobs               │
│   - codespace_pool.py: primary + failover                   │
│   - notion_sync.py: 8 DBs + daily reports                   │
│   - trend_detector.py: OpenFuego scoring                    │
│   - social_scheduler.py: Postiz-inspired                    │
│   - webhook_server.py: 6 sources + HMAC + queue             │
│   - health_monitor.py: liveness + alerts                    │
│   - cache.py / async_pool.py / rate_limiter.py /            │
│     circuit_breaker.py / performance.py: BATCH B perf        │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3: Integrations (integrations/)                       │
│   - ai_dispatch.py: Modal + fal unified (zerocost-first)    │
│   - character_agent.py: persona system                      │
│   - relationship_graph.py: knowledge graph (SQLite + FTS5)  │
│   - social_dispatch.py: 16 platforms via TikHub             │
│   - ecom_dispatch.py: 4 e-commerce platforms                │
│   - umami_dispatch.py: web analytics                        │
│   - video_editor.py / podcast_creator.py: media             │
│   - voice_clone / music_gen / thumbnail_tester /            │
│     content_repurposer: content tools (BATCH C)             │
│   - analytics_pipeline / ab_testing / seo_optimizer /       │
│     translation_pipeline / image_enhancer: analytics        │
│   - session_manager.py: 4 backends                          │
│   - registry.py / dispatcher.py / runner.py: framework      │
└────────────────────────┬────────────────────────────────────┘
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 4: Modal.com Serverless GPU                           │
│   - text_to_image: FLUX.2-klein + FLUX.1.1 Pro Ultra        │
│   - text_to_video: Wan 2.1 + HunyuanVideo                   │
│   - voice_synth: CosyVoice 2.0                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

```
Character (3-layer locked)
    ↓ persona prompt
Modal AI Dispatcher
    ↓ image / video / audio
Image Enhancer / Video Editor / Podcast Creator
    ↓ enhanced media
Social Dispatcher (TikHub)
    ↓ 16 platform URLs
E-commerce Dispatcher (4 platforms)
    ↓ affiliate links
Scheduler (Postiz-style)
    ↓ scheduled slots
Auto-pipeline (APScheduler)
    ↓ execute at time
Notion Sync (8 DBs)
    ↓ analytics write
Umami Analytics
    ↓ track post views
Analytics Pipeline
    ↓ metrics aggregation
ROI Dashboard
    ↓ report
Daily Notion Report
    ↓ alert if ROI drops
Auto-heal Rules
    ↓ incident response
Codespace Failover
```

## Module Dependencies

```
main.py
  └─ integrations/registry.py
      ├─ integrations/character_agent.py
      ├─ integrations/relationship_graph.py
      ├─ integrations/ai_dispatch.py
      │   └─ integrations/modal_dispatch.py
      │   └─ integrations/fal_dispatch.py
      ├─ integrations/social_dispatch.py
      ├─ integrations/ecom_dispatch.py
      ├─ integrations/umami_dispatch.py
      ├─ integrations/video_editor.py
      ├─ integrations/podcast_creator.py
      └─ integrations/session_manager.py
  └─ core/autoheal.py
      └─ core/notion_sync.py
      └─ core/health_monitor.py
  └─ core/auto_pipeline.py
      └─ core/codespace_pool.py
  └─ core/webhook_server.py
      └─ core/notion_sync.py
  └─ core/cache.py / core/async_pool.py / core/rate_limiter.py / core/circuit_breaker.py
```

## Configuration

All configuration via env vars. See [`.env.example`](../.env.example).

| Var | Required | Default | Description |
|-----|----------|---------|-------------|
| `MODAL_TOKEN_ID` | yes (for prod) | — | Modal.com token ID |
| `MODAL_TOKEN_SECRET` | yes (for prod) | — | Modal.com token secret |
| `FAL_KEY` | no | — | fal.ai API key (fallback only) |
| `TIKHUB_API_KEY` | no | — | TikHub API key (16 platforms) |
| `INSTAGRAPI_USERNAME` | no | — | Instagram username |
| `INSTAGRAPI_PASSWORD` | no | — | Instagram password |
| `NOTION_TOKEN` | yes (for prod) | — | Notion integration token |
| `NOTION_PARENT_PAGE` | no | — | Parent page for DBs |
| `UMAMI_BASE_URL` | no | `https://umami.example.com` | Umami URL |
| `UMAMI_WEBSITE_ID` | yes (for analytics) | — | Umami website ID |
| `UMAMI_API_KEY` | no | — | Umami API key |
| `SHOPEE_AFFILIATE_ID` | no | — | Shopee affiliate ID |
| `SHOPEE_AFFILIATE_TOKEN` | no | — | Shopee affiliate token |
| `TIKTOKSHOP_APP_KEY` | no | — | TikTok Shop app key |
| `TIKTOKSHOP_ACCESS_TOKEN` | no | — | TikTok Shop access token |
| `LAZADA_APP_KEY` | no | — | Lazada app key |
| `LAZADA_APP_SECRET` | no | — | Lazada app secret |
| `LAZADA_ACCESS_TOKEN` | no | — | Lazada access token |
| `TOKOPEDIA_AFFILIATE_ID` | no | — | Tokopedia affiliate ID |
| `TOKOPEDIA_AFFILIATE_TOKEN` | no | — | Tokopedia affiliate token |
| `SESSION_BACKEND` | no | `sqlite` | `sqlite` / `redis` / `postgres` |
| `REDIS_URL` | no | — | Redis connection URL |
| `DATABASE_URL` | no | — | Postgres connection URL |
| `LOG_LEVEL` | no | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `ENV` | no | `dev` | `dev` / `staging` / `prod` |
| `MODAL_BUDGET_USD` | no | `5.0` | Modal budget per month |
| `FAL_DAILY_BUDGET_USD` | no | `1.0` | fal.ai daily budget |
| `UGC_CHARACTER_DB` | no | — | Custom path for character DB |
| `UGC_UMAMI_DB` | no | — | Custom path for Umami DB |

## Deployment

### Local

```bash
python main.py serve
```

### Docker

```bash
docker-compose up
```

Services:
- `api` (port 8000) — FastAPI dashboard
- `worker` — Webhook consumer
- `scheduler` — APScheduler daemon
- `redis` (port 6379) — Cache + queue

### CI

GitHub Actions runs on push + PR:
- `ruff check`
- `black --check`
- `isort --check`
- `mypy` (0 errors required)
- `pytest` (1006+ tests)
- `docker build` (sanity)

## Scaling

### Codespace Pool

- **Primary:** codespace-1 (2c/8GB) for content tools
- **Secondary:** codespace-2 (4c/16GB) for performance layer
- **Failover:** `core/codespace_pool.py` detects primary death and switches

### Auto-heal

- **5 rules** in `core/autoheal_rules.json`
- **Triggers:** Notion sync failure > 3x, codespace down > 5min, Modal 5xx > 10/min, disk > 90%, memory > 80%
- **Actions:** Restart service, switch codespace, alert Notion Inbox, log incident

### Auto-pipeline

- **APScheduler** with cron + interval jobs
- **Daily:** Notion sync, analytics rollup, ROI report
- **Hourly:** Trend detection, scheduler flush
- **Every 5min:** Health check, codespace ping
