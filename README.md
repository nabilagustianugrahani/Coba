# UGC AI Overpower

> **Indonesian social media + e-commerce + AI content automation system.**
> Self-hosted orchestrator + 24+ integrations + 1000+ tests, designed to run 100% on free-tier student credits.

[![Tests](https://img.shields.io/badge/tests-1006%20passed-brightgreen)]()
[![Mypy](https://img.shields.io/badge/mypy-0%20errors-blue)]()
[![Python](https://img.shields.io/badge/python-3.12-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Overview

UGC AI Overpower is a fully autonomous content creation + publishing + monetization pipeline
for Indonesian creators. It combines:

- **24+ platform integrations** (TikTok, Instagram, Shopee, Lazada, Tokopedia, TikTok Shop, etc.)
- **AI content generation** via [Modal.com](https://modal.com) (zerocost) with [fal.ai](https://fal.ai) fallback
- **Character persona system** with 8 niche presets and 3-layer identity lock
- **Affiliate marketing** automation across 4 e-commerce platforms
- **Notion dashboard** with 8 databases for analytics + reporting
- **Auto-heal** + auto-pipeline + codespace failover for 24/7 operation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        VPS (thin)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ 9router LLM  │  │  Watchdog    │  │  Notion sync │      │
│  │  proxy       │  │  + autoheal  │  │  (8 DBs)     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└────────────────────────┬────────────────────────────────────┘
                         │  HTTP/SSH
        ┌────────────────┼────────────────┐
        ▼                ▼                ▼
   ┌─────────┐     ┌─────────┐     ┌─────────┐
   │ CS #1   │     │ CS #2   │     │ CS #3   │  (GitHub Codespaces)
   │ 2c/8GB  │     │ 4c/16GB │     │ 4c/16GB │
   └────┬────┘     └────┬────┘     └────┬────┘
        │               │               │
        └───────────────┼───────────────┘
                        ▼
              ┌──────────────────┐
              │ Modal.com GPU    │  $5/mo budget
              │ Wan 2.1 / FLUX.2 │
              │ CosyVoice 2.0    │
              └──────────────────┘
                        │
                        ▼
              ┌──────────────────┐
              │ fal.ai GPU       │  fallback only
              │ 14 premium models│
              └──────────────────┘
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/nabilagustianugrahani/ugc.git
cd ugc

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure (copy and edit)
cp .env.example .env
$EDITOR .env

# 4. Run
python main.py serve              # Web dashboard on :8000
python main.py worker             # Webhook consumer
python main.py schedule           # Auto-pipeline scheduler
python main.py notion-init        # Create Notion DBs
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `python main.py serve` | Start FastAPI dashboard on port 8000 |
| `python main.py worker` | Start webhook consumer worker |
| `python main.py webhook-server` | Start webhook receiver on port 8001 |
| `python main.py schedule` | Start scheduler daemon |
| `python main.py health-check` | Run daemon health check |
| `python main.py notion-init` | Create Notion databases |
| `python main.py notion-status` | Check Notion connection |
| `python main.py notion-campaigns` | List campaigns |
| `python main.py notion-daily-report [date]` | Generate daily report |
| `python main.py notion-sync <product>` | Manually sync a campaign |

## Module Map

### Core (24+ modules in `ugc_ai_overpower/integrations/`)

| Module | Purpose | Tier |
|--------|---------|------|
| `modal_dispatch` | Modal.com GPU dispatcher | zerocost |
| `fal_dispatch` | fal.ai GPU dispatcher | premium |
| `ai_dispatch` | Unified AI dispatcher (zerocost-first) | meta |
| `character_agent` | 3-layer-locked persona system | meta |
| `relationship_graph` | Creator→Content→Campaign knowledge graph | meta |
| `social_dispatch` | TikHub (16 platforms) + instagrapi | premium |
| `ecom_dispatch` | Shopee + TikTok Shop + Lazada + Tokopedia | premium |
| `umami_dispatch` | Web analytics tracking | zerocost |
| `video_editor` | 13 ffmpeg operations | zerocost |
| `podcast_creator` | 8 audio operations | zerocost |
| `voice_clone` | CosyVoice 2.0 voice synthesis | zerocost |
| `music_gen` | MusicGen-Small/Large | zerocost |
| `thumbnail_tester` | A/B testing with z-test | zerocost |
| `content_repurposer` | Multi-platform auto-adaptation | zerocost |
| `analytics_pipeline` | Post metrics + ROI dashboard | meta |
| `ab_testing` | Variant comparison with z-test | meta |
| `seo_optimizer` | Keyword + SEO scoring | meta |
| `translation_pipeline` | 14 languages via NLLB-200 | meta |
| `image_enhancer` | 10 image ops (Real-ESRGAN + GFPGAN) | zerocost |
| `session_manager` | 4 backends (SQLite/Redis/Postgres) | meta |
| `registry` | Auto-discovery of adapters | meta |
| `dispatcher` | Routes heavy work to codespace | meta |
| `runner` | Code that runs in codespace | meta |

### Core (5 modules in `ugc_ai_overpower/core/`)

| Module | Purpose | Lines |
|--------|---------|-------|
| `cache` | MemoryCache + RedisCache + TieredCache + decorator | ~250 |
| `async_pool` | AsyncPool with priority queue | ~250 |
| `rate_limiter` | TokenBucket + SlidingWindow + MultiKey | ~280 |
| `circuit_breaker` | CircuitBreaker + Registry | ~220 |
| `performance` | RateLimitedCachedBreaker (composite) | ~250 |
| `webhook_server` | FastAPI receiver (6 sources) | ~410 |
| `autoheal` | Auto-heal orchestrator (5 rules) | ~400 |
| `auto_pipeline` | APScheduler daemon | ~300 |
| `health_monitor` | HealthMonitor + Notion Inbox | ~250 |
| `codespace_pool` | Primary-with-failover | ~200 |
| `notion_sync` | 8 Notion DBs + daily reports | ~600 |
| `trend_detector` | OpenFuego-style scoring | ~340 |
| `social_scheduler` | Postiz-inspired scheduler | ~360 |

## Cost Analysis

| Provider | Use Case | Cost | Budget |
|----------|----------|------|--------|
| Modal.com | Open-source models (Wan 2.1, FLUX.2, CosyVoice) | $0.005/5s video | $5/mo (GSP) |
| fal.ai | Premium models (Kling, Veo, LTX) | $0.40/5s video | Pay-per-use |
| TikHub | 16 social platforms via 1 API | ~$0.0001/req | $10/mo (GSP) |
| Umami | Self-hosted analytics | $0 | Free |
| Notion | Dashboard + DBs | $0 | Free |

**Zerocost-first strategy:** Always try Modal → fall back to fal.ai. Modal is 80x cheaper for open-source models.

## Performance Benchmarks

See [docs/BENCHMARKS.md](docs/BENCHMARKS.md) for full details.

| Module | Throughput |
|--------|-----------|
| MemoryCache | 690K ops/s |
| AsyncPool (4 workers) | 763 ops/s |
| TokenBucketLimiter | 795K ops/s |
| CircuitBreaker (fast-fail) | 141K ops/s |
| RateLimitedCachedBreaker | 308K ops/s |

**Load test** (50 workers × 5s): **11,895 req/s, p99 52.3ms, 0 errors**.

## Security

See [docs/SECURITY_AUDIT.md](docs/SECURITY_AUDIT.md) for full audit.

- Secrets via env vars only (no hardcoded credentials)
- SQL: parameterized queries via sqlite3 stdlib
- No eval/exec/os.system in production code
- Webhook HMAC-SHA256 signature verification
- Input length caps on LLM-passing fields

## Roadmap

- [x] Auto-heal + auto-pipeline
- [x] 24+ integrations
- [x] Character persona system
- [x] Affiliate marketing automation
- [x] Notion dashboard (8 DBs)
- [x] Web dashboard (FastAPI + htmx)
- [x] Webhook server (6 sources)
- [x] Docker + docker-compose + CI
- [x] Performance benchmarks
- [x] E2E pipeline tests
- [ ] Real Modal.com deployment (needs user-provided $5 token)
- [ ] Real fal.ai deployment (needs user-provided FAL_KEY)
- [ ] Mobile-responsive dashboard v2
- [ ] GraphQL API

## Contributing

This is a personal project for `nabilagustianugrahani` GitHub Pro (student).
External contributions are not currently accepted.

## License

MIT
