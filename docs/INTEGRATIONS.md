# Integrations Status

Last updated: 2026-06-06

## Tier 1: Meta (Framework)

| Module | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `registry.py` | Auto-discovery of adapters | active | covered by integration tests |
| `dispatcher.py` | Routes heavy work to codespace | active | covered by integration tests |
| `runner.py` | Code that runs in codespace | active | covered by integration tests |
| `session_manager.py` | 4 backends (SQLite/Redis/Postgres) | active | covered by integration tests |
| `base.py` | PlatformAdapter abstract class | active | n/a |

## Tier 2: AI Content Generation

| Module | Provider | Tier | Cost | Status | Tests |
|--------|----------|------|------|--------|-------|
| `modal_dispatch.py` | Modal.com | zerocost | $0.005/5s video | active | 30+ |
| `fal_dispatch.py` | fal.ai | premium | $0.40/5s video | fallback | 25+ |
| `ai_dispatch.py` | Unified (zerocost-first) | meta | n/a | active | 20+ |
| `voice_clone.py` | CosyVoice 2.0 (Modal) | zerocost | $0.002/synth | active | 33 |
| `music_gen.py` | MusicGen-Small/Large (Modal) | zerocost | $0.003/song | active | 27 |
| `thumbnail_tester.py` | FLUX.2-klein variants | zerocost | $0.001/variant | active | 33 |
| `content_repurposer.py` | Multi-platform auto | zerocost | $0.01/post | active | 33 |

## Tier 3: Media Processing

| Module | Capability | Backend | Cost | Status | Tests |
|--------|-----------|---------|------|--------|-------|
| `video_editor.py` | 13 ffmpeg ops | local + Modal | free + GPU | active | 20+ |
| `podcast_creator.py` | 8 audio ops | local | free | active | 15+ |
| `image_enhancer.py` | 10 image ops | Modal Real-ESRGAN | $0.002/op | active | 25+ |
| `seo_optimizer.py` | Keyword + SEO scoring | NLLB-200 | free | active | 22 |
| `translation_pipeline.py` | 14 languages | NLLB-200 | free | active | 28 |

## Tier 4: Distribution

| Module | Platforms | Status | Tests |
|--------|-----------|--------|-------|
| `social_dispatch.py` | TikHub (16 platforms) | active | 30+ |
| `ecom_dispatch.py` | Shopee, TikTok Shop, Lazada, Tokopedia | active | 30+ |
| `umami_dispatch.py` | Umami analytics | active | 25+ |

### Social Platforms (via TikHub)
- TikTok, Instagram, YouTube, Twitter/X, Facebook
- Threads, LinkedIn, Reddit, Pinterest
- Douyin, Xiaohongshu, Bilibili
- Weibo, Kuaishou

### E-commerce Platforms
- Shopee (Indonesia, Singapore, Malaysia, Thailand, Vietnam, Philippines, Taiwan, Brazil)
- TikTok Shop (Southeast Asia)
- Lazada (Southeast Asia)
- Tokopedia (Indonesia)

## Tier 5: Analytics + Intelligence

| Module | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `analytics_pipeline.py` | Post metrics + ROI | active | 25+ |
| `ab_testing.py` | Variant + z-test | active | 22 |
| `character_agent.py` | Persona system (3-layer lock) | active | 30+ |
| `relationship_graph.py` | Knowledge graph (SQLite + FTS5) | active | 28 |
| `trend_detector.py` | OpenFuego scoring | active | 18 |

## Tier 6: Core Infrastructure

| Module | Purpose | Status | Tests |
|--------|---------|--------|-------|
| `core/cache.py` | MemoryCache + RedisCache + Tiered | active | 25 |
| `core/async_pool.py` | AsyncPool w/ priority queue | active | 28 |
| `core/rate_limiter.py` | TokenBucket + SlidingWindow + MultiKey | active | 30 |
| `core/circuit_breaker.py` | CircuitBreaker + Registry | active | 25 |
| `core/performance.py` | RateLimitedCachedBreaker composite | active | 30 |
| `core/autoheal.py` | Auto-heal orchestrator (5 rules) | active | 16 |
| `core/auto_pipeline.py` | APScheduler daemon | active | covered |
| `core/health_monitor.py` | Liveness + Notion Inbox alerts | active | covered |
| `core/codespace_pool.py` | Primary + failover | active | covered |
| `core/notion_sync.py` | 8 Notion DBs + daily reports | active | 15+ |
| `core/social_scheduler.py` | Postiz-inspired | active | covered |
| `core/webhook_server.py` | FastAPI 6 sources + HMAC | active | 23 |
| `web/dashboard.py` | FastAPI + htmx (11 endpoints) | active | 27 |

## Total Stats

- **25 integration modules** (4 base + 21 active)
- **13 core modules** (5 perf + 8 infra)
- **1006+ tests** (was 968 + 50 from BATCH D)
- **0 mypy errors**
- **Race conditions fixed** (asyncio.Lock wrapping)
- **Input length caps** (Pydantic max_length)

## Cost Comparison (per 5s 720p video)

| Provider | Cost | Ratio |
|----------|------|-------|
| Modal Wan 2.1 1.3B | $0.005 | 1x |
| fal.ai Wan 2.1 720p | $0.40 | 80x more |
| fal.ai Kling 1.6 Pro | $1.20 | 240x more |
| fal.ai Veo 2 | $2.50 | 500x more |

**Recommendation:** Use Modal for open-source models (Wan 2.1, FLUX.2, CosyVoice, MusicGen). Use fal.ai only for premium (Kling, Veo, LTX) when open-source can't match quality.
