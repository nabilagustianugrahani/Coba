import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ugc_ai_overpower.core.psychology import PsychologyEngine, PSYCHOLOGY_FRAMEWORKS


class TestPsychology:
    def setup_method(self):
        self.engine = PsychologyEngine()

    def test_get_target_group(self):
        group, info = self.engine.get_target_group("skincare")
        assert isinstance(group, str)
        assert isinstance(info, dict)

    def test_get_triggers(self):
        triggers = self.engine.get_triggers_for_product("skincare")
        assert isinstance(triggers, list)

    def test_frameworks_count(self):
        assert len(PSYCHOLOGY_FRAMEWORKS) == 8
