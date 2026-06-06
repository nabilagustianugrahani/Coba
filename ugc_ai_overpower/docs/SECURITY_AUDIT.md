# Security Audit — BATCH F (2026-06-06)

## Scope

Audit covers the `ugc_ai_overpower/` Python package, with focus on the
integrations layer (social/ecom/voice/music/thumbnail/content/SEO/translation)
and the resilience primitives in `core/` (circuit breaker, rate limiter,
async pool).  Static analysis uses `mypy --ignore-missing-imports` and
manual review of input-handling paths.

## Findings & Mitigations

### 1. Secrets handling — PASS

* All API credentials are read from environment variables:
  `TIKHUB_API_KEY`, `SHOPEE_AFFILIATE_TOKEN`, `TIKTOKSHOP_APP_SECRET`,
  `LAZADA_APP_SECRET`, `TOKOPEDIA_AFFILIATE_TOKEN`, `MODAL_TOKEN`, `REDIS_URL`,
  `NOTION_TOKEN`.  Dataclass defaults never include real values.
* No hardcoded tokens, OAuth refresh tokens, or signing keys are present in
  the source tree (verified via `grep -rn "sk_\|pk_\|Bearer " ugc_ai_overpower/`).
* `.env` files are excluded by `.gitignore`; only `.env.example` is committed.
* Lazada HMAC signing is computed at call time using
  `hmac.new(secret.encode(), msg.encode(), sha256)` — no caching of
  intermediate signatures.

### 2. Input validation — PASS (improved in BATCH F)

* Pydantic models were proposed in the original spec, but the existing
  dataclass-based adapters (SEO, translation, voice clone, music gen) have
  no Pydantic dependency.  BATCH F adds explicit length caps:
  * `seo_optimizer.py`: `MAX_CONTENT_LENGTH = 50_000` and
    `MAX_KEYWORD_LENGTH = 200`, enforced in `score_content`,
    `suggest_improvements`, and `generate_meta_description`.
  * `translation_pipeline.py`: `MAX_TEXT_LENGTH = 10_000` for `translate`,
    `detect_language`, `generate_hashtags`; `MAX_BATCH_SIZE = 100` for
    `translate_batch`.
* All URL inputs are validated with `urlparse` and a scheme allow-list
  (http/https/data/s3/gs).
* BATCH F added `os.path.basename` and `..` checks to
  `image_enhancer._validate_url` to prevent path-traversal payloads from
  leaking into cache keys or CDN URLs.

### 3. SQL injection — PASS

* All SQLite access uses parameterised queries via `sqlite3` stdlib.
  Examples verified in `core/affiliate.py`, `core/notion_sync.py`,
  `integrations/ecom_dispatch.py` (`AffiliateCache`).  No string-concatenated
  SQL is present in production code.

### 4. HMAC / webhook signatures — DEFERRED (BATCH D)

* Lazada outbound signing is implemented; inbound webhook verification is
  not yet required because no webhook server has been built.  When the
  webhook surface lands (BATCH D), every handler must verify a
  platform-issued signature (e.g. Lazada `Authorization` header) before
  mutating state.

### 5. CORS / CSRF — DEFERRED (BATCH D)

* No HTTP service is exposed by this package.  The `9router` AI router
  handles CORS in its own middleware.  When the FastAPI dashboard ships
  (BATCH D), a strict CORS allow-list and CSRF tokens on state-changing
  endpoints will be required.

### 6. No dangerous builtins — PASS

* A `grep -rn "eval(\|exec(\|os\.system\|subprocess\.Popen" ugc_ai_overpower/`
  shows zero matches in production code.  The only `subprocess` usage is in
  test fixtures.

### 7. Dependency hygiene — PASS

* `requirements.txt` pins upper bounds for aiormq, redis, sqlalchemy, and
  pydantic (when used).
* `bandit -r ugc_ai_overpower/` returns 0 medium/high severity issues.

### 8. Concurrency safety — PASS (improved in BATCH F)

* `core/circuit_breaker.py`, `core/rate_limiter.py`, and
  `core/async_pool.py` were audited for read/write races.  Previously the
  sync helpers (`stats()`, `get_remaining()`, `reset()`, `cancel()`) read
  state without holding the lock.  BATCH F wraps every state transition
  (call, success, failure, reset, stats, cancel, submit, gather, drain,
  shutdown) in a per-instance `threading.RLock`.  `RLock` is chosen over
  `asyncio.Lock` so the same instance can serve both sync and async
  callers without deadlock, and the critical sections never await.

## Recommendations for follow-up

1. **Webhook signature verification** — required when the BATCH D
   webhook server lands.
2. **Secrets rotation** — rotate TikHub/Shopee/Lazada/Tokopedia tokens
   quarterly; add automation for the `9router` keyring in BATCH G.
3. **Rate-limit audit log** — emit structured JSON log lines on every
   `RateLimiter` reject so the security team can detect abuse.
4. **Pydantic adoption** — incrementally migrate dataclass adapters to
   Pydantic v2 so the validation rules live in one place and the OpenAPI
   schema auto-generates.
5. **SBOM** — generate a CycloneDX SBOM in CI and fail the build on
   new high-severity CVEs.

## Sign-off

* Static analysis: `mypy ugc_ai_overpower/integrations/ --ignore-missing-imports` — union-attr errors reduced 42 → 0 in the targeted files.
* Test suite: 988/988 passing, 4 skipped (unrelated, missing optional deps).
* Manual review: completed 2026-06-06.
