import sys
import os
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ugc_ai_overpower.core.content_bank import ContentBank


class TestContentBank:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.db = ContentBank(db_path=self.tmp.name)

    def teardown_method(self):
        self.tmp.close()
        os.unlink(self.tmp.name)

    def test_create_campaign(self):
        cid = self.db.create_campaign("Test Campaign")
        assert isinstance(cid, int)

    def test_add_product(self):
        pid = self.db.add_product("Test Product")
        assert isinstance(pid, int)

    def test_add_content(self):
        pid = self.db.add_product("Test Product")
        iid = self.db.add_influencer("Test Inf", "tech", "male", 25, "cool", "friendly", "modern", "backstory")
        cid = self.db.add_content(iid, pid, "tiktok", "hook", "script", ["#test"])
        assert isinstance(cid, int)
