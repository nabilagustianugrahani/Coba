import unittest
import os
import tempfile
from datetime import datetime
from ugc_ai_overpower.analytics.engagement import EngagementTracker

class TestEngagementTracker(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.tracker = EngagementTracker(db_path=self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_track_metrics_no_error(self):
        """track_post_metrics should not raise an exception"""
        self.tracker.track_post_metrics(post_id=1, views=100, likes=10, comments=5, shares=2, clicks=3)
        # If no exception, test passes.

    def test_calculate_engagement_rate_returns_float(self):
        self.tracker.track_post_metrics(post_id=2, views=200, likes=20, comments=10, shares=5, clicks=0)
        rate = self.tracker.calculate_engagement_rate(post_id=2)
        self.assertIsInstance(rate, float)

    def test_get_top_posts_returns_list(self):
        # Insert multiple rows
        for i in range(3):
            self.tracker.track_post_metrics(post_id=i, views=100*i+100, likes=10*i, comments=5*i, shares=2*i, clicks=1*i)
        top = self.tracker.get_top_performing_posts(limit=2)
        self.assertIsInstance(top, list)
        self.assertLessEqual(len(top), 2)

    def test_track_conversion_returns_int(self):
        conv_id = self.tracker.track_conversion(post_id=1, product_id="prod-123", revenue=99.99)
        self.assertIsInstance(conv_id, int)

if __name__ == "__main__":
    unittest.main()
