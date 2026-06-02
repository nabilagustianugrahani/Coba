import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ugc_ai_overpower.auth import verify_user, create_token, verify_token


class TestAuth:
    def test_verify_user_valid(self):
        result = verify_user("admin", "admin123")
        assert isinstance(result, dict)

    def test_verify_user_invalid(self):
        result = verify_user("admin", "wrong")
        assert result is None

    def test_create_token(self):
        token = create_token("admin", "admin")
        assert isinstance(token, str)

    def test_verify_token_valid(self):
        token = create_token("admin", "admin")
        payload = verify_token(token)
        assert isinstance(payload, dict)
        assert "sub" in payload

    def test_verify_token_invalid(self):
        result = verify_token("invalid")
        assert result is None
