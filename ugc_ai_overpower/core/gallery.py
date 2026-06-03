"""UGC Gallery with SEO pages — auto-generates landing pages for every video.

Every video produced by the system gets:
  - A dedicated SEO landing page with og:meta + JSON-LD
  - Gallery listing with hover-to-play preview
  - Auto-sitemap generation for search engines
  - RSS feed for content discovery
  - View/like/share tracking

Inspired by OpenShorts (2.2k stars) public gallery feature.
"""

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List

log = logging.getLogger(__name__)

_GALLERY_DB_PATH = Path(__file__).parents[1] / "data" / "gallery.db"

_GALLERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS gallery_videos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    slug          TEXT NOT NULL UNIQUE,
    description   TEXT,
    video_path    TEXT NOT NULL,
    thumbnail_path TEXT,
    duration_sec  INTEGER DEFAULT 0,
    platform      TEXT DEFAULT 'tiktok',
    niche         TEXT DEFAULT 'general',
    product       TEXT,
    tags          TEXT DEFAULT '',
    og_image      TEXT,
    views         INTEGER DEFAULT 0,
    likes         INTEGER DEFAULT 0,
    shares        INTEGER DEFAULT 0,
    seo_published INTEGER DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_gallery_slug ON gallery_videos(slug);
CREATE INDEX IF NOT EXISTS idx_gallery_created ON gallery_videos(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_gallery_niche ON gallery_videos(niche);
CREATE INDEX IF NOT EXISTS idx_gallery_product ON gallery_videos(product);
"""


class Gallery:
    """SEO-optimized UGC video gallery with auto-landing-page generation."""

    def __init__(self, db_path: Optional[str] = None, output_dir: Optional[str] = None):
        self._db_path = db_path or str(_GALLERY_DB_PATH)
        self._lock = threading.Lock()
        self._init_db()
        base = Path(output_dir) if output_dir else Path(__file__).parents[1] / "web" / "gallery"
        self.output_dir = base
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._site_url = "https://ugc-empire.ai"

    def _init_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_GALLERY_SCHEMA)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def add_video(self, title: str, video_path: str, thumbnail_path: str = "",
                  duration_sec: int = 0, platform: str = "tiktok",
                  niche: str = "general", product: str = "",
                  tags: str = "", description: str = "") -> int:
        slug = self._make_slug(title)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO gallery_videos
                       (title, slug, description, video_path, thumbnail_path,
                        duration_sec, platform, niche, product, tags, og_image,
                        created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (title, slug, description or title, video_path, thumbnail_path,
                     duration_sec, platform, niche, product, tags,
                     thumbnail_path or "", now, now),
                )
                conn.commit()
                video_id = cur.lastrowid or self._get_id_by_slug(slug)
                self._generate_landing_page(video_id)
                self._regenerate_sitemap()
                return video_id
            finally:
                conn.close()

    def _get_id_by_slug(self, slug: str) -> int:
        conn = self._connect()
        try:
            row = conn.execute("SELECT id FROM gallery_videos WHERE slug=?", (slug,)).fetchone()
            return row["id"] if row else 0
        finally:
            conn.close()

    def _make_slug(self, title: str) -> str:
        import re
        slug = title.lower().strip()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[-\s]+', '-', slug)
        slug = slug[:80] or "video"
        ts = datetime.now().strftime("%s")[-4:]
        return f"{slug}-{ts}"

    def get_video(self, video_id: int) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM gallery_videos WHERE id=?", (video_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_video_by_slug(self, slug: str) -> Optional[dict]:
        conn = self._connect()
        try:
            row = conn.execute("SELECT * FROM gallery_videos WHERE slug=?", (slug,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def list_videos(self, niche: str = "", product: str = "",
                    limit: int = 50, offset: int = 0) -> List[dict]:
        conn = self._connect()
        try:
            conditions = []
            params = []
            if niche:
                conditions.append("niche = ?")
                params.append(niche)
            if product:
                conditions.append("product = ?")
                params.append(product)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            rows = conn.execute(
                f"""SELECT id, title, slug, description, thumbnail_path,
                           duration_sec, platform, niche, product, tags,
                           views, likes, shares, created_at
                    FROM gallery_videos {where}
                    ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                params + [limit, offset],
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def record_view(self, video_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("UPDATE gallery_videos SET views = views + 1 WHERE id=?", (video_id,))
            conn.commit()
        finally:
            conn.close()

    def record_like(self, video_id: int) -> None:
        conn = self._connect()
        try:
            conn.execute("UPDATE gallery_videos SET likes = likes + 1 WHERE id=?", (video_id,))
            conn.commit()
        finally:
            conn.close()

    def get_total_count(self, niche: str = "", product: str = "") -> int:
        conn = self._connect()
        try:
            conditions = []
            params = []
            if niche:
                conditions.append("niche = ?")
                params.append(niche)
            if product:
                conditions.append("product = ?")
                params.append(product)
            where = "WHERE " + " AND ".join(conditions) if conditions else ""
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM gallery_videos {where}", params).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def _generate_landing_page(self, video_id: int) -> None:
        video = self.get_video(video_id)
        if not video:
            return

        slug = video["slug"]
        page_dir = self.output_dir / slug
        page_dir.mkdir(parents=True, exist_ok=True)

        title = video["title"]
        desc = video.get("description") or title
        abs_video_path = Path(video["video_path"]).resolve()
        video_url = f"/output/{abs_video_path.name}" if abs_video_path.exists() else ""
        thumb_url = video.get("thumbnail_path") or ""
        tags_list = [t.strip() for t in video.get("tags", "").split(",") if t.strip()]
        keywords = ", ".join(tags_list) if tags_list else title

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} | UGC Gallery</title>
<meta name="description" content="{desc[:160]}">
<meta name="keywords" content="{keywords}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc[:200]}">
<meta property="og:type" content="video.other">
<meta property="og:url" content="{self._site_url}/gallery/{slug}">
<meta property="og:image" content="{thumb_url or self._site_url + '/og-default.jpg'}">
<meta name="twitter:card" content="player">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{desc[:200]}">
<script type="application/ld+json">{json.dumps({
    "@context": "https://schema.org",
    "@type": "VideoObject",
    "name": title,
    "description": desc[:200],
    "thumbnailUrl": thumb_url or "",
    "contentUrl": video_url or "",
    "duration": f"PT{video['duration_sec']}S",
    "datePublished": video["created_at"][:10],
}, indent=2)}</script>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0}}
.container{{max-width:900px;margin:0 auto;padding:2rem}}
.video-wrapper{{position:relative;width:100%;max-width:400px;margin:2rem auto;border-radius:12px;overflow:hidden;background:#12121a;border:1px solid #1e1e2e}}
video{{width:100%;display:block;border-radius:12px}}
.stats{{display:flex;gap:2rem;margin:1.5rem 0;padding:1rem;background:#12121a;border-radius:12px;border:1px solid #1e1e2e;justify-content:center}}
.stat{{text-align:center}}
.stat-value{{font-size:1.5rem;font-weight:700;color:#fff}}
.stat-label{{font-size:.75rem;color:#888;text-transform:uppercase;margin-top:.25rem}}
.meta{{margin:1rem 0;padding:1rem;background:#12121a;border-radius:12px;border:1px solid #1e1e2e}}
.meta-row{{display:flex;justify-content:space-between;padding:.5rem 0;border-bottom:1px solid #1e1e2e;font-size:.875rem}}
.meta-row:last-child{{border-bottom:none}}
.meta-label{{color:#888}}
.meta-value{{color:#fff}}
.back{{display:inline-block;margin-bottom:1rem;color:#7b2ff7;text-decoration:none;font-size:.875rem}}
.back:hover{{text-decoration:underline}}
h1{{font-size:1.25rem;margin-bottom:.5rem;color:#fff}}
.tags{{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}}
.tag{{background:#1e1e2e;padding:.25rem .75rem;border-radius:999px;font-size:.75rem;color:#888}}
</style>
</head>
<body>
<div class="container">
<a href="/gallery" class="back">&larr; Gallery</a>
<h1>{title}</h1>
<p style="color:#888;font-size:.875rem;margin-bottom:.5rem">{video.get('product','') or video.get('niche','')}</p>
<div class="video-wrapper">
<video src="{video_url}" controls poster="{thumb_url}" preload="metadata"></video>
</div>
<div class="stats">
<div class="stat"><div class="stat-value" id="views">{video['views']}</div><div class="stat-label">Views</div></div>
<div class="stat"><div class="stat-value" id="likes">{video['likes']}</div><div class="stat-label">Likes</div></div>
<div class="stat"><div class="stat-value">{video.get('duration_sec',0)}s</div><div class="stat-label">Duration</div></div>
</div>
<div class="meta">
<div class="meta-row"><span class="meta-label">Platform</span><span class="meta-value">{video['platform'].title()}</span></div>
<div class="meta-row"><span class="meta-label">Niche</span><span class="meta-value">{video['niche'].title()}</span></div>
<div class="meta-row"><span class="meta-label">Created</span><span class="meta-value">{video['created_at'][:10]}</span></div>
</div>
<div class="tags">{''.join(f'<span class="tag">{t}</span>' for t in tags_list)}</div>
<p style="color:#666;font-size:.875rem;line-height:1.6">{desc}</p>
</div>
<script>
fetch('/api/v1/gallery/view/{video_id}',{{method:'POST'}});
document.querySelector('video')?.addEventListener('click',function(){{this.paused?this.play():this.pause()}});
</script>
</body>
</html>"""
        (page_dir / "index.html").write_text(html)

        Path(self.output_dir / "index.html").write_text(self._generate_gallery_page())

    def _generate_gallery_page(self) -> str:
        videos = self.list_videos(limit=50)
        cards = ""
        for v in videos:
            thumb = v.get("thumbnail_path") or ""
            cards += f"""<a href="/gallery/{v['slug']}" class="card">
<div class="thumb">{f'<img src="{thumb}" loading="lazy">' if thumb else '<div class="no-thumb">UGC</div>'}</div>
<div class="card-body">
    <div class="card-title">{v['title'][:60]}</div>
    <div class="card-meta">{v['niche']} &middot; {v['platform']} &middot; {v.get('duration_sec',0)}s</div>
    <div class="card-stats">{v['views']} views &middot; {v['likes']} likes</div>
</div>
</a>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>UGC Gallery — AI-Powered UGC Videos</title>
<meta name="description" content="Browse our gallery of AI-generated UGC videos for TikTok, Instagram, and YouTube. Fresh content daily.">
<meta property="og:title" content="UGC Gallery — AI-Powered UGC Videos">
<meta property="og:description" content="Browse AI-generated UGC videos for social media.">
<meta property="og:type" content="website">
<meta name="google-site-verification" content="">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0}}
.header{{background:#12121a;border-bottom:1px solid #1e1e2e;padding:2rem;text-align:center}}
.header h1{{font-size:1.5rem;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
.header p{{color:#888;font-size:.875rem;margin-top:.5rem}}
.stats-bar{{display:flex;justify-content:center;gap:2rem;padding:1rem;background:#12121a;border-bottom:1px solid #1e1e2e}}
.stats-bar span{{color:#888;font-size:.875rem}}
.stats-bar strong{{color:#fff}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;padding:2rem;max-width:1200px;margin:0 auto}}
.card{{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;overflow:hidden;text-decoration:none;color:inherit;transition:transform .2s,border-color .2s}}
.card:hover{{transform:translateY(-2px);border-color:#7b2ff7}}
.thumb{{aspect-ratio:9/16;overflow:hidden;background:#1a1a2e;display:flex;align-items:center;justify-content:center}}
.thumb img{{width:100%;height:100%;object-fit:cover}}
.no-thumb{{color:#444;font-size:2rem;font-weight:800}}
.card-body{{padding:1rem}}
.card-title{{font-weight:600;font-size:.875rem;color:#fff;margin-bottom:.25rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-meta{{color:#666;font-size:.75rem;margin-bottom:.25rem}}
.card-stats{{color:#444;font-size:.688rem}}
.footer{{text-align:center;padding:2rem;color:#444;font-size:.75rem}}
.footer a{{color:#7b2ff7;text-decoration:none}}
</style>
</head>
<body>
<div class="header"><h1>UGC Gallery</h1><p>AI-generated UGC content for TikTok, Instagram & YouTube</p></div>
<div class="stats-bar"><span>Total: <strong>{self.get_total_count()}</strong> videos</span></div>
<div class="grid">{cards or '<p style="grid-column:1/-1;text-align:center;color:#666;padding:3rem">No videos yet. Generate your first UGC video!</p>'}</div>
<div class="footer"><a href="/gallery/sitemap.xml">Sitemap</a> &middot; <a href="/gallery/feed.xml">RSS Feed</a> &middot; Powered by UGC Empire v2.0</div>
</body>
</html>"""

    def _regenerate_sitemap(self) -> None:
        videos = self.list_videos(limit=500)
        urls = []
        for v in videos:
            urls.append(f"""  <url>
    <loc>{self._site_url}/gallery/{v['slug']}</loc>
    <lastmod>{v['created_at'][:10]}</lastmod>
    <priority>0.8</priority>
  </url>""")

        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{self._site_url}/gallery</loc>
    <priority>1.0</priority>
  </url>
{chr(10).join(urls)}
</urlset>"""
        (self.output_dir / "sitemap.xml").write_text(sitemap)

        rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
<title>UGC Gallery</title>
<link>{self._site_url}/gallery</link>
<description>AI-generated UGC content feed</description>
{''.join(f'''<item>
<title>{v['title']}</title>
<link>{self._site_url}/gallery/{v['slug']}</link>
<description>{v.get('description','')[:200]}</description>
<media:content url="{v.get('thumbnail_path','')}" medium="image"/>
<pubDate>{v['created_at']}</pubDate>
</item>''' for v in videos[:20])}
</channel>
</rss>"""
        (self.output_dir / "feed.xml").write_text(rss)

    def get_stats(self) -> dict:
        conn = self._connect()
        try:
            row = conn.execute("SELECT COUNT(*) as total, SUM(views) as total_views, SUM(likes) as total_likes FROM gallery_videos").fetchone()
            niches = conn.execute("SELECT niche, COUNT(*) as cnt FROM gallery_videos GROUP BY niche ORDER BY cnt DESC").fetchall()
            return {
                "total": row["total"] if row else 0,
                "total_views": row["total_views"] or 0 if row else 0,
                "total_likes": row["total_likes"] or 0 if row else 0,
                "niches": [dict(n) for n in niches],
            }
        finally:
            conn.close()
