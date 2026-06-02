import unittest
import os
import tempfile
from datetime import datetime, timedelta
from ugc_ai_overpower.scheduler.cron import ContentScheduler

class TestContentScheduler(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.scheduler = ContentScheduler(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_schedule_post_returns_int(self):
        """schedule_post should return an integer schedule_id"""
        content_id = 1
        platform = "twitter"
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        schedule_id = self.scheduler.schedule_post(content_id, platform, scheduled_time)
        self.assertIsInstance(schedule_id, int)
        self.assertGreater(schedule_id, 0)

    def test_get_pending_posts_returns_list(self):
        """get_pending_posts should return a list"""
        pending = self.scheduler.get_pending_posts()
        self.assertIsInstance(pending, list)

    def test_mark_as_posted_updates_status(self):
        """mark_as_posted should update the status to 'posted'"""
        content_id = 1
        platform = "twitter"
        scheduled_time = datetime.utcnow() + timedelta(hours=1)
        schedule_id = self.scheduler.schedule_post(content_id, platform, scheduled_time)
        post_url = "http://example.com/post/123"
        self.scheduler.mark_as_posted(schedule_id, post_url)

        # Fetch the updated row
        conn = self.scheduler._get_conn()
        try:
            row = conn.execute(
                "SELECT status, post_url FROM schedules WHERE id = ?", (schedule_id,)
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(row["status"], "posted")
        self.assertEqual(row["post_url"], post_url)

    def test_get_optimal_time_returns_datetime(self):
        """get_optimal_time should return a datetime object"""
        platform = "twitter"
        optimal_time = self.scheduler.get_optimal_time(platform)
        self.assertIsInstance(optimal_time, datetime)

if __name__ == "__main__":
    unittest.main()
