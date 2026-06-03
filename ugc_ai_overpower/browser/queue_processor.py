"""Auto-process content queue with platform posters + account farm rotation."""
import logging, time, concurrent.futures
from typing import Optional

log = logging.getLogger(__name__)


class QueueProcessor:
    """Process pending content queue items end-to-end.

    Flow per item:
      1. Dequeue → 2. Load content from BankV2 → 3. Rotate farm account
      → 4. Post via platform poster → 5. Mark done/failed → 6. Record farm result
    """

    def __init__(self, farm=None, bank=None, queue=None):
        from ugc_ai_overpower.browser.farm import AccountFarm
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        from ugc_ai_overpower.browser.content_queue import ContentQueue
        self.farm = farm or AccountFarm()
        self.bank = bank or ContentBankV2()
        self.queue = queue or ContentQueue()

    def process_one(self, platform: Optional[str] = None, headless: bool = True) -> dict:
        """Dequeue and process a single pending item. Returns result dict."""
        item = self.queue.dequeue(platform)
        if not item:
            return {"status": "empty"}

        content = self._load_content(item["content_id"])
        if not content:
            self.queue.mark_failed(item["id"], "content not found in bank")
            return {"status": "error", "error": "content not found", "id": item["id"]}

        poster = self._get_poster(item["platform"])
        if not poster:
            self.queue.mark_failed(item["id"], f"no poster for {item['platform']}")
            return {"status": "error", "error": f"no poster for {item['platform']}", "id": item["id"]}

        profile = None
        try:
            profile = self.farm.rotate(item["platform"])
            if profile:
                poster.set_cookie_profile(profile.name)
                log.info("Using farm account %s/%s", profile.platform, profile.name)

            payload = {
                "script": content.get("script", ""),
                "video_path": content.get("video_path", ""),
                "hashtags": content.get("hashtags", []),
                "hook": content.get("hook", ""),
            }
            result = poster.post(payload)
            if result.get("success"):
                self.queue.mark_done(item["id"], result.get("post_url", ""))
                if profile:
                    self.farm.record_result(item["platform"], profile.name, True)
                return {"status": "done", "id": item["id"], "url": result.get("post_url")}
            else:
                err = result.get("error", "unknown")
                self.queue.mark_failed(item["id"], err)
                if profile:
                    self.farm.record_result(item["platform"], profile.name, False)
                return {"status": "failed", "id": item["id"], "error": err}
        except Exception as e:
            self.queue.mark_failed(item["id"], str(e))
            if profile:
                self.farm.record_result(item["platform"], profile.name, False)
            return {"status": "error", "id": item["id"], "error": str(e)}
        finally:
            poster.cleanup()

    def process_all(self, platform: Optional[str] = None, max_items: int = 0) -> dict:
        """Process ALL pending items sequentially. Returns aggregated stats."""
        stats = {"processed": 0, "success": 0, "failed": 0, "errors": []}
        while True:
            if max_items and stats["processed"] >= max_items:
                break
            result = self.process_one(platform)
            if result["status"] == "empty":
                break
            stats["processed"] += 1
            if result["status"] == "done":
                stats["success"] += 1
            else:
                stats["failed"] += 1
                if result.get("error"):
                    stats["errors"].append({"id": result["id"], "error": result["error"]})
            log.info("[%d/%s] %s", stats["processed"], "∞" if not max_items else max_items, result["status"])
        return stats

    def process_parallel(self, platform: Optional[str] = None, max_workers: int = 3) -> dict:
        """Process pending items in parallel using ThreadPoolExecutor."""
        from ugc_ai_overpower.browser.content_queue import ContentQueue
        q = ContentQueue()
        items = q.list_items(status="pending", platform=platform, limit=50)
        if not items:
            return {"processed": 0, "success": 0, "failed": 0}

        stats = {"processed": 0, "success": 0, "failed": 0, "errors": []}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {}
            for i, item in enumerate(items):
                fut = pool.submit(self._process_item, item)
                fut_map[fut] = item["id"]
            for fut in concurrent.futures.as_completed(fut_map):
                item_id = fut_map[fut]
                try:
                    result = fut.result()
                    stats["processed"] += 1
                    if result["status"] == "done":
                        stats["success"] += 1
                    else:
                        stats["failed"] += 1
                        stats["errors"].append({"id": item_id, "error": result.get("error", "unknown")})
                except Exception as e:
                    stats["processed"] += 1
                    stats["failed"] += 1
                    stats["errors"].append({"id": item_id, "error": str(e)})
        return stats

    def _process_item(self, item: dict) -> dict:
        """Process a single item (for parallel execution)."""
        from ugc_ai_overpower.browser.content_queue import ContentQueue
        from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
        from ugc_ai_overpower.browser.farm import AccountFarm
        from ugc_ai_overpower.browser.posters import get_poster

        content = ContentBankV2().get_content(item.get("content_id", 0))
        if not content:
            ContentQueue().mark_failed(item["id"], "content not found")
            return {"status": "error", "error": "content not found"}

        poster = None
        try:
            poster = get_poster(item["platform"])
            farm = AccountFarm()
            profile = farm.rotate(item["platform"])
            if profile:
                poster.set_cookie_profile(profile.name)

            payload = {
                "script": content.get("script", ""),
                "video_path": content.get("video_path", ""),
                "hashtags": content.get("hashtags", []),
                "hook": content.get("hook", ""),
            }
            result = poster.post(payload)
            if result.get("success"):
                ContentQueue().mark_done(item["id"], result.get("post_url", ""))
                if profile:
                    farm.record_result(item["platform"], profile.name, True)
                return {"status": "done", "url": result.get("post_url")}
            else:
                ContentQueue().mark_failed(item["id"], result.get("error", "unknown"))
                if profile:
                    farm.record_result(item["platform"], profile.name, False)
                return {"status": "failed", "error": result.get("error")}
        except Exception as e:
            ContentQueue().mark_failed(item["id"], str(e))
            return {"status": "error", "error": str(e)}
        finally:
            if poster:
                poster.cleanup()

    def retry_failed(self, platform: Optional[str] = None) -> int:
        """Reset all permanently failed items to pending for retry."""
        from ugc_ai_overpower.browser.content_queue import ContentQueue
        q = ContentQueue()
        return q.retry_failed()

    def _load_content(self, content_id: int) -> Optional[dict]:
        try:
            return self.bank.get_content(content_id)
        except Exception:
            return None

    def _get_poster(self, platform: str):
        try:
            from ugc_ai_overpower.browser.posters import get_poster
            return get_poster(platform)
        except Exception as e:
            log.warning("No poster for %s: %s", platform, e)
            return None
