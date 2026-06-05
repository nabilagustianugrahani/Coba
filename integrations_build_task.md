BUILD: Social media + e-commerce integration layer WITH session management for UGC AI Overpower.

## Context

We're building an autonomous UGC affiliate swarm that posts to Indonesian social media and tracks affiliate sales. The VPS is a thin coordinator. ALL heavy work (API calls, scraping, session management, processing) runs in this codespace.

## Architecture (already built on VPS at /workspaces/Coba/ugc_ai_overpower/integrations/):
- `base.py` - PlatformAdapter abstract class with EngagementMetrics, PostResult, AccountInfo, AffiliateLink dataclasses
- `registry.py` - register_adapter decorator, get_adapter(), list_platforms()
- `dispatcher.py` - dispatch_post(), dispatch_engagement(), dispatch_account(), dispatch_affiliate_link()
- `runner.py` - run_task(task, payload) — entry point

The VPS calls these dispatcher functions. The codespace runs `run_task()` and returns JSON.

## Reference repos (research already done)

Best session/cookie management patterns:
1. **steadfast** (github.com/getsteadfast/steadfast) — multi-account browser automation, anti-detect, session persistence, VNC for manual login
2. **social-cookie-jar** (pypi.org/project/social-cookie-jar/) — 9 platforms, paste-and-send pattern, no typing detection
3. **social-auto-upload** (github.com/dreammis/social-auto-upload, 10K stars) — 7 platforms with full session/login/uploading
4. **instagrapi** (instagrapi.com) — Instagram with session persistence (file/Redis/Postgres patterns)

Key patterns to implement:
- **Session blob**: device fingerprint + cookies + headers + user_pk (instagrapi pattern)
- **Cookie-based auth**: no passwords stored, export from real browser
- **Session persistence**: file-based (default), JSON serializable
- **Session expiry tracking**: 30-90 days, auto-mark expired
- **One in-flight request per session**: prevent anti-bot detection
- **Proxy pinning per account**: same IP for same account
- **Storage backends**: file (default), Redis (if available), Postgres (if available)

## Your job

Build THREE new modules in `/workspaces/Coba/ugc_ai_overpower/integrations/`:

### 1. `session_manager.py` — Universal session management

```python
class SessionStore:
    """Pluggable session storage: file (default), Redis, Postgres."""
    def __init__(self, backend: str = "file", path: str = "/tmp/ugc_sessions"):
        ...

    def save(self, platform: str, account_id: str, session: dict) -> None: ...
    def load(self, platform: str, account_id: str) -> Optional[dict]: ...
    def delete(self, platform: str, account_id: str) -> bool: ...
    def list_accounts(self, platform: str) -> list[str]: ...
    def is_expired(self, platform: str, account_id: str, max_age_days: int = 60) -> bool: ...

class Session:
    """Reusable session object with health checks."""
    def __init__(self, platform: str, account_id: str, cookies: dict,
                 headers: dict = None, fingerprint: dict = None,
                 proxy: str = None, metadata: dict = None): ...
    def is_valid(self) -> bool: ...
    def to_dict(self) -> dict: ...
    @classmethod
    def from_dict(cls, data: dict) -> "Session": ...
    def touch(self) -> None: ...  # mark last-used
    def age_days(self) -> float: ...

class SessionManager:
    """High-level session management per platform."""
    def __init__(self, store: Optional[SessionStore] = None): ...
    def get_or_create(self, platform: str, account_id: str,
                      login_fn: Optional[Callable] = None) -> Session: ...
    def refresh_if_needed(self, platform: str, account_id: str,
                          max_age_days: int = 60) -> bool: ...
    def validate(self, platform: str, account_id: str) -> dict: ...
    def list_all(self, platform: Optional[str] = None) -> list[dict]: ...
```

Implementation:
- File backend: `/tmp/ugc_sessions/{platform}/{account_id}.json` with file locking (fcntl)
- Redis backend: keys `ugc:session:{platform}:{account_id}`, TTL 30 days
- Postgres backend: table `ugc_sessions(platform, account_id, data jsonb, updated_at)`
- All backends implement same interface
- Auto-detect backend: env var `UGC_SESSION_BACKEND` (file/redis/postgres)
- If Redis/Postgres unavailable, fallback to file

Session schema:
```json
{
  "platform": "instagram",
  "account_id": "nabilagustianugrahani",
  "cookies": {"sessionid": "...", "csrftoken": "..."},
  "headers": {"User-Agent": "..."},
  "fingerprint": {"device_id": "...", "app_version": "..."},
  "proxy": "http://user:pass@ip:port",
  "metadata": {"created_at": "...", "last_used": "...", "login_method": "cookie_import"},
  "version": 1
}
```

### 2. `social_dispatch.py` — Real social media implementations

Use **TikHub API** (https://tikhub.io) for read-only data fetch, plus **instagrapi** for Instagram posting.

Install: `pip install tikhub aiohttp instagrapi httpx`

Functions:

```python
async def do_post(payload: dict) -> dict:
    """Post content to a social platform.
    payload: {platform, content, media_urls, metadata: {account_id, ...}}
    Returns: {ok, post_id, post_url, status, error}
    """
    platform = payload.get("platform", "")
    account_id = payload.get("metadata", {}).get("account_id", "default")
    content = payload.get("content", "")
    media_urls = payload.get("media_urls", [])
    
    sm = SessionManager()
    session = sm.get_or_create(platform, account_id)
    if session.is_expired():
        return {"ok": False, "error": f"session expired for {platform}/{account_id}"}
    
    if platform == "instagram":
        # Use instagrapi if session has valid cookies
        from instagrapi import Client
        cl = Client()
        cl.load_settings(session.to_dict().get("fingerprint", {}))
        try:
            if media_urls:
                media = cl.photo_download(media_urls[0]) if media_urls[0].endswith(('.jpg', '.png')) else cl.video_download(media_urls[0])
                result = cl.photo_upload(media.path, content)
            else:
                return {"ok": False, "error": "Instagram requires media"}
            return {
                "ok": True, "post_id": str(result.id), "post_url": f"https://instagram.com/p/{result.code}/",
                "status": "published", "platform": platform,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "platform": platform}
    
    # For all other platforms: simulated (no business account)
    return {
        "ok": True, "status": "simulated",
        "post_id": f"{platform}_{hash(content) % 10**8}",
        "post_url": f"https://{platform}.com/simulated/{hash(content) % 10**8}",
        "platform": platform,
        "note": "Real posting requires business account credentials. Use TikHub for data only.",
    }

async def do_engagement(payload: dict) -> dict:
    """Fetch REAL engagement metrics via TikHub.
    payload: {platform, post_url}
    Returns: {views, likes, comments, shares, saves, engagement_score, fetched_at, source}
    """
    platform = payload.get("platform", "")
    post_url = payload.get("post_url", "")
    
    try:
        from tikhub import AsyncTikHub
        import os
        api_key = os.environ.get("TIKHUB_API_KEY", "")
        if api_key:
            async with AsyncTikHub(api_key=api_key) as client:
                result = await _fetch_engagement_via_tikhub(client, platform, post_url)
                if result.get("ok"):
                    return result
    except Exception:
        pass
    
    # Simulated fallback
    import hashlib
    h = int(hashlib.md5(post_url.encode()).hexdigest()[:8], 16)
    return {
        "views": h % 50000, "likes": (h // 100) % 5000,
        "comments": (h // 10000) % 500, "shares": (h // 100000) % 200,
        "saves": (h // 1000000) % 100, "clicks": (h // 10000000) % 50,
        "engagement_score": round(((h % 100) / 100) * 10, 2),
        "fetched_at": __import__("datetime").datetime.utcnow().isoformat(),
        "platform": platform, "source": "simulated",
    }

async def do_account(payload: dict) -> dict:
    """Get account info via TikHub or stored session.
    payload: {platform, username}
    Returns: {username, display_name, followers, ...}
    """
    platform = payload.get("platform", "")
    username = payload.get("username", "")
    # Try TikHub first, fall back to simulated
    ...

async def do_session(payload: dict) -> dict:
    """Manage sessions: save, load, list, validate, delete.
    payload: {action, platform, account_id, session_data?}
    Actions: save | load | list | validate | delete | refresh
    Returns: appropriate dict
    """
    action = payload.get("action", "list")
    sm = SessionManager()
    if action == "save":
        sm.store.save(payload["platform"], payload["account_id"], payload["session_data"])
        return {"ok": True, "action": "save"}
    if action == "load":
        session = sm.store.load(payload["platform"], payload["account_id"])
        return {"ok": True, "session": session.to_dict() if session else None}
    if action == "list":
        accounts = sm.list_all(payload.get("platform"))
        return {"ok": True, "accounts": accounts}
    if action == "validate":
        return sm.validate(payload["platform"], payload["account_id"])
    if action == "delete":
        deleted = sm.store.delete(payload["platform"], payload["account_id"])
        return {"ok": True, "deleted": deleted}
    return {"ok": False, "error": f"unknown action: {action}"}
```

Helper `_fetch_engagement_via_tikhub()`:
```python
async def _fetch_engagement_via_tikhub(client, platform, post_url) -> dict:
    """Call platform-specific TikHub endpoint, return normalized metrics."""
    try:
        if platform == "tiktok":
            data = await client.tiktok_web.fetch_one_video(url=post_url)
            item = data.get("itemInfo", {}).get("itemStruct", {}) or {}
            stats = item.get("stats", {}) or {}
            return {
                "ok": True, "source": "tikhub",
                "views": stats.get("playCount", 0),
                "likes": stats.get("diggCount", 0),
                "comments": stats.get("commentCount", 0),
                "shares": stats.get("shareCount", 0),
                "saves": stats.get("collectCount", 0),
                "engagement_score": _calc_score(stats),
                "fetched_at": __import__("datetime").datetime.utcnow().isoformat(),
                "platform": platform,
            }
        if platform == "instagram":
            data = await client.instagram_v2.fetch_post(url=post_url)
            # extract from response — structure varies by version
            ...
        if platform == "youtube":
            data = await client.youtube_web.fetch_video(url=post_url)
            ...
        if platform == "twitter":
            data = await client.twitter_web.fetch_tweet(url=post_url)
            ...
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": f"unsupported platform: {platform}"}
```

### 3. `ecom_dispatch.py` — Real e-commerce implementations

Same session pattern + e-commerce specific.

```python
async def do_affiliate(payload: dict) -> dict:
    """Generate affiliate tracking link.
    payload: {platform, product_url, sub_ids}
    Returns: {affiliate_url, short_url, commission_rate, product_id, ok, error}
    """
    platform = payload.get("platform", "").lower()
    product_url = payload.get("product_url", "")
    sub_ids = payload.get("sub_ids", [])
    
    # Check cache first
    cache_path = "/tmp/ugc_affiliate_cache.json"
    cache = _load_cache(cache_path)
    cache_key = f"{platform}:{product_url}"
    if cache_key in cache:
        cached = cache[cache_key]
        if (time.time() - cached.get("cached_at", 0)) < 86400 * 7:  # 7 days
            return {**cached, "source": "cache"}
    
    result = None
    if platform == "shopee":
        result = await _shopee_affiliate(product_url, sub_ids)
    elif platform == "tiktok_shop":
        result = await _tiktok_shop_affiliate(product_url, sub_ids)
    elif platform == "lazada":
        result = await _lazada_affiliate(product_url, sub_ids)
    elif platform == "tokopedia":
        result = await _tiktok_shop_affiliate(product_url, sub_ids + ["tokopedia"])
    else:
        return {"ok": False, "error": f"unsupported: {platform}"}
    
    if result and result.get("ok") and result.get("affiliate_url"):
        _save_cache(cache_path, cache_key, result)
    
    return result or {"ok": False, "error": "no result"}
```

Each platform impl:
- Reads creds from env (SHOPEE_PARTNER_ID etc.)
- Implements real signature/HMAC if creds present
- Falls back to simulated if no creds: returns `{ok: True, status: simulated, affiliate_url: product_url + "?ref=simulated"}`

### 4. Tests

Create at /workspaces/Coba/ugc_ai_overpower/tests/:
- `test_session_manager.py` — test all 3 backends, save/load/delete, expiry
- `test_social_dispatch.py` — mock TikHub + instagrapi, test all 4 task types
- `test_ecom_dispatch.py` — test affiliate link for all 4 platforms, cache, fallback
- `test_modal_dispatch.py` — mock modal client, test render/synthesize/clone

### 5. `modal_dispatch.py` — Modal.com serverless GPU integration

Modal.com gives us on-demand GPU compute for image/video/voice generation. Heaviest work goes here.

Install: `pip install modal` (requires Python 3.10+; codespace is on 3.12 — fine)

Reference: https://modal.com/docs and https://github.com/modal-labs/modal-examples

Modal SDK pattern:
```python
import modal
app = modal.App("ugc-render")
image = modal.Image.debian_slim().pip_install("torch", "diffusers")

@app.function(gpu="A10G", image=image, timeout=300)
def render(prompt: str) -> bytes:
    from diffusers import StableDiffusionPipeline
    import torch
    pipe = StableDiffusionPipeline.from_pretrained("...", torch_dtype=torch.float16).to("cuda")
    image = pipe(prompt).images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()
```

Functions to implement in `modal_dispatch.py`:

```python
async def do_modal_render(payload: dict) -> dict:
    """Render image via Modal GPU.
    payload: {action, prompt, model, width, height, seed}
    Returns: {ok, image_bytes_b64, model, duration_ms, cost_usd}
    """
    action = payload.get("action", "image")
    if action == "image":
        return await _modal_text_to_image(payload)
    if action == "video":
        return await _modal_text_to_video(payload)
    if action == "voice":
        return await _modal_synthesize_voice(payload)
    if action == "list":
        return _list_modal_apps()
    if action == "deploy":
        return await _deploy_modal_app(payload)
    return {"ok": False, "error": f"unknown action: {action}"}

async def do_modal_account(payload: dict) -> dict:
    """List Modal accounts / GPU availability / cost.
    payload: {action} — list | balance | gpus
    Returns: {accounts, balance_usd, available_gpus}
    """
    import modal
    # Modal token is in env: MODAL_TOKEN_ID, MODAL_TOKEN_SECRET
    # We can use the `modal` CLI or the SDK to query
    ...

def _list_modal_apps() -> dict:
    """List all deployed Modal apps with their status."""
    # Use modal app list CLI command
    import subprocess
    result = subprocess.run(["modal", "app", "list"], capture_output=True, text=True, timeout=30)
    return {"ok": True, "raw": result.stdout, "apps": _parse_modal_apps(result.stdout)}

async def _modal_text_to_image(payload: dict) -> dict:
    """Generate image via Modal serverless GPU."""
    import modal
    prompt = payload.get("prompt", "")
    model = payload.get("model", "sdxl-turbo")
    width = int(payload.get("width", 1024))
    height = int(payload.get("height", 1024))
    seed = payload.get("seed")
    
    # Use Modal SDK to call deployed function
    # The function "render_image" is defined in modal_apps/text_to_image.py
    # and deployed via `modal deploy`
    try:
        fn = modal.Function.from_name("ugc-render", "render_image")
        image_bytes = await fn.remote.aio(prompt=prompt, model=model, width=width, height=height, seed=seed)
        import base64
        return {
            "ok": True,
            "image_b64": base64.b64encode(image_bytes).decode(),
            "model": model,
            "size": f"{width}x{height}",
            "source": "modal_gpu",
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "fallback": "use local generation"}

async def _modal_text_to_video(payload: dict) -> dict:
    """Generate video via Modal (Mochi or Hunyuan).
    payload: {prompt, model, num_frames, num_inference_steps}
    Returns: {ok, video_b64, model, duration_s, cost_usd}
    """
    # Use Modal's Mochi deployment
    ...

async def _modal_synthesize_voice(payload: dict) -> dict:
    """TTS via Modal (edge-tts or XTTS).
    payload: {text, voice_id, language}
    Returns: {ok, audio_b64, voice_id, duration_s}
    """
    ...
```

Also create `modal_apps/` directory with the actual Modal app definitions:

`/workspaces/Coba/ugc_ai_overpower/integrations/modal_apps/text_to_image.py`:
```python
import modal
app = modal.App("ugc-render")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch==2.1.0", "diffusers==0.25.0", "transformers==4.36.0", "accelerate")
)

@app.function(image=image, gpu="A10G", timeout=300, container_idle_timeout=120)
def render_image(prompt: str, model: str = "sdxl-turbo", width: int = 1024, height: int = 1024, seed: int = None) -> bytes:
    import io
    import torch
    from diffusers import StableDiffusionXLPipeline, AutoPipelineForText2Image
    
    if model == "sdxl-turbo":
        pipe = AutoPipelineForText2Image.from_pretrained("stabilityai/sdxl-turbo", torch_dtype=torch.float16, variant="fp16").to("cuda")
    elif model == "flux-schnell":
        pipe = ...  # flux
    elif model == "sd-3.5":
        pipe = ...  # sd3.5
    
    generator = torch.Generator("cuda").manual_seed(seed) if seed else None
    result = pipe(prompt=prompt, width=width, height=height, num_inference_steps=4 if "turbo" in model else 25, guidance_scale=0.0 if "turbo" in model else 7.5, generator=generator).images[0]
    
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return buf.getvalue()

@app.local_entrypoint()
def main(prompt: str = "A cat playing piano"):
    import time
    t0 = time.time()
    img_bytes = render_image.remote(prompt=prompt)
    print(f"Generated in {time.time()-t0:.1f}s, {len(img_bytes)} bytes")
    with open("/tmp/render_output.png", "wb") as f:
        f.write(img_bytes)
```

`/workspaces/Coba/ugc_ai_overpower/integrations/modal_apps/text_to_video.py` — Mochi
`/workspaces/Coba/ugc_ai_overpower/integrations/modal_apps/voice_synth.py` — edge-tts or XTTS

Update `runner.py` to handle the new task:
```python
if task == "modal_render":
    from ugc_ai_overpower.integrations.modal_dispatch import do_modal_render
    return do_modal_render(payload)
if task == "modal_account":
    from ugc_ai_overpower.integrations.modal_dispatch import do_modal_account
    return do_modal_account(payload)
```

Update `dispatcher.py`:
```python
def dispatch_modal_render(action, **kwargs) -> dict:
    payload = {"action": action, **kwargs}
    return _dispatch_to_codespace("modal_render", payload)
```

For the `modal_apps/` deployment, we don't actually deploy them now (needs `modal setup` with real account), but the code is there ready to deploy. Just verify imports work and tests pass.

Add to `/workspaces/Coba/ugc_ai_overpower/integrations/modal_apps/__init__.py` and create the file.

## Steps

1. `cd /workspaces/Coba`
2. `pip install tikhub aiohttp instagrapi httpx modal --break-system-packages`
3. Read existing files: `ugc_ai_overpower/integrations/{base,registry,dispatcher,runner}.py`
4. Create `ugc_ai_overpower/integrations/session_manager.py`
5. Create `ugc_ai_overpower/integrations/social_dispatch.py` 
6. Create `ugc_ai_overpower/integrations/ecom_dispatch.py`
7. Create tests in `ugc_ai_overpower/tests/`
8. Run: `PYTHONPATH=/workspaces/Coba python3 -m pytest ugc_ai_overpower/tests/test_session_manager.py ugc_ai_overpower/tests/test_social_dispatch.py ugc_ai_overpower/tests/test_ecom_dispatch.py -v`
9. Smoke test: 
```python
import asyncio
from ugc_ai_overpower.integrations.session_manager import SessionManager
sm = SessionManager()
result = sm.store.save("instagram", "test_user", {"cookies": {"sessionid": "test"}})
print(sm.list_all())
```
10. Commit: `cd /workspaces/Coba && git -c commit.gpgsign=false add -A && git -c commit.gpgsign=false commit -m "feat(integrations): social+ecom+session management with TikHub+instagrapi" && git push origin feat/add-sshd --force`

## Important

- All functions MUST be async (run_task expects async)
- Return JSON-serializable dicts only
- No file IO except: /tmp/ugc_sessions/, /tmp/ugc_affiliate_cache.json
- Robust error handling: catch all, return {"ok": False, "error": str(e)}
- Type hints throughout
- File locking for concurrent session access (fcntl)
- Session expiry: 60 days default
- Anti-bot: one in-flight request per session (use asyncio.Lock per session)

Start now.
