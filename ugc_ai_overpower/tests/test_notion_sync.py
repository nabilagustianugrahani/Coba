import os
import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json
from datetime import datetime

# Import with proper path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ugc_ai_overpower.core.notion_sync import NotionDashboard


class TestNotionDashboard:
    """Test suite for NotionDashboard class."""

    @pytest.fixture(autouse=True)
    def _clear_notion_env(self, monkeypatch):
        """Auto-clear Notion env vars before each test to prevent pollution."""
        for key in ("NOTION_TOKEN", "NOTION_PARENT_PAGE", "NOTION_CAMPAIGN_DB", "NOTION_CONTENT_DB", "NOTION_ANALYTICS_DB"):
            monkeypatch.delenv(key, raising=False)

    def test_init_with_token(self):
        """Test initialization with explicit token."""
        dashboard = NotionDashboard(token="test_token")
        assert dashboard.token == "test_token"
        
    def test_init_from_env(self):
        """Test initialization from environment variable."""
        with patch.dict(os.environ, {"NOTION_TOKEN": "env_token"}):
            dashboard = NotionDashboard()
            assert dashboard.token == "env_token"
            
    def test_init_without_token(self):
        """Test initialization without token."""
        with patch.dict(os.environ, {}, clear=True):
            dashboard = NotionDashboard()
            assert dashboard.token == ""
            
    def test_ready_property(self):
        """Test the ready property."""
        # With token
        dashboard = NotionDashboard(token="test_token")
        assert dashboard.ready is True
        
        # Without token
        dashboard_no_token = NotionDashboard(token="")
        assert dashboard_no_token.ready is False
        
    def test_iso_now(self):
        """Test _iso_now static method."""
        iso_time = NotionDashboard._iso_now()
        assert isinstance(iso_time, str)
        assert iso_time.endswith("Z")
        # Basic format check
        assert "T" in iso_time
        
    def test_format_title(self):
        """Test _format_title static method."""
        title = NotionDashboard._format_title("Test Title")
        assert isinstance(title, list)
        assert len(title) == 1
        assert title[0]["type"] == "text"
        assert title[0]["text"]["content"] == "Test Title"
        
    def test_format_rich(self):
        """Test _format_rich static method."""
        # With text
        rich = NotionDashboard._format_rich("Test text")
        assert isinstance(rich, list)
        assert len(rich) == 1
        assert rich[0]["type"] == "text"
        assert rich[0]["text"]["content"] == "Test text"
        
        # With empty text
        empty_rich = NotionDashboard._format_rich("")
        assert empty_rich == []
        
    def test_date_obj(self):
        """Test _date_obj static method."""
        # With specific date
        date_obj = NotionDashboard._date_obj("2023-01-01")
        assert date_obj == {"start": "2023-01-01"}
        
        # Without date (should use today)
        today_obj = NotionDashboard._date_obj()
        assert "start" in today_obj
        assert isinstance(today_obj["start"], str)
        
    def test_num(self):
        """Test _num static method."""
        # With number
        num_obj = NotionDashboard._num(42.5)
        assert num_obj == {"number": 42.5}
        
        # With None
        none_obj = NotionDashboard._num(None)
        assert none_obj is None
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_success(self, mock_session_class):
        """Test successful HTTP request."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"object": "page", "id": "test"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard._request("GET", "test/endpoint")
        
        assert result == {"object": "page", "id": "test"}
        mock_session.request.assert_called_once_with(
            "GET",
            "https://api.notion.com/v1/test/endpoint",
            json=None
        )
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_rate_limit(self, mock_session_class):
        """Test rate limit handling."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # First call: rate limited
        mock_response_1 = Mock()
        mock_response_1.status_code = 429
        mock_response_1.headers = {"Retry-After": "2"}
        
        # Second call: success
        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {"object": "page", "id": "test"}
        
        mock_session.request.side_effect = [mock_response_1, mock_response_2]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard._request("GET", "test/endpoint")
        
        assert result == {"object": "page", "id": "test"}
        assert mock_session.request.call_count == 2
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_server_error(self, mock_session_class):
        """Test server error handling with retries."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # First two calls: server error
        mock_response_1 = Mock()
        mock_response_1.status_code = 500
        mock_response_1.text = "Server Error"
        
        mock_response_2 = Mock()
        mock_response_2.status_code = 500
        mock_response_2.text = "Server Error"
        
        # Third call: success
        mock_response_3 = Mock()
        mock_response_3.status_code = 200
        mock_response_3.json.return_value = {"object": "page", "id": "test"}
        
        mock_session.request.side_effect = [mock_response_1, mock_response_2, mock_response_3]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard._request("GET", "test/endpoint")
        
        assert result == {"object": "page", "id": "test"}
        assert mock_session.request.call_count == 3
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_connection_error(self, mock_session_class):
        """Test connection error handling with retries."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        import requests
        mock_session.request.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200, json=lambda: {"object": "page", "id": "test"})
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard._request("GET", "test/endpoint")
        
        assert result == {"object": "page", "id": "test"}
        assert mock_session.request.call_count == 3
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_all_retries_fail(self, mock_session_class):
        """Test behavior when all retries fail."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        import requests
        mock_session.request.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        dashboard = NotionDashboard(token="test_token")
        with pytest.raises(RuntimeError, match="Request failed after 5 retries"):
            dashboard._request("GET", "test/endpoint")
            
        assert mock_session.request.call_count == 5
        
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_request_invalid_json(self, mock_session_class):
        """Test handling of invalid JSON response."""
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.text = "Invalid response text"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard._request("GET", "test/endpoint")
        
        assert result == {"raw": "Invalid response text", "status": 200}
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_auto_create_databases_no_token(self, mock_session_class, mock_getenv):
        """Test auto_create_databases with no token."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="")
        result = dashboard.auto_create_databases()
        
        assert result == {}
        mock_session_class.return_value.request.assert_not_called()
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_auto_create_databases_with_parent(self, mock_session_class, mock_getenv):
        """Test auto_create_databases with parent page."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_PARENT_PAGE": "parent-page-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        # Mock database creation response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "test-db-id"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.auto_create_databases()
        
        # Should create at least one database
        assert len(result) > 0
        assert any("test-db-id" in str(v) for v in result.values())
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_auto_create_databases_no_parent(self, mock_session_class, mock_getenv):
        """Test auto_create_databases without parent page."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token"
        }.get(key, default)
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.auto_create_databases()
            
        # Should print warning about no parent
        mock_print.assert_any_call("[Notion] No NOTION_PARENT_PAGE set. Databases will be created at workspace root (may fail if integration lacks permissions).")
        
    def test_add_campaign_no_db(self):
        """Test add_campaign without campaign database configured."""
        with patch.dict(os.environ, {}, clear=True):
            dashboard = NotionDashboard(token="test_token")
            with patch('builtins.print') as mock_print:
                result = dashboard.add_campaign("Test Product")
            
        assert result is None
        mock_print.assert_called_with("[Notion] Campaign DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_add_campaign_success(self, mock_session_class, mock_getenv):
        """Test successful campaign creation."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "campaign-page-id"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_campaign("Test Campaign", platforms=["tiktok", "instagram"])
        
        assert result == "campaign-page-id"
        mock_session.request.assert_called_once()
        
    def test_update_campaign_no_changes(self):
        """Test update_campaign with no changes."""
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_campaign("test-campaign-id")
        assert result is False
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_update_campaign_success(self, mock_session_class, mock_getenv):
        """Test successful campaign update."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"object": "page"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_campaign(
            "test-campaign-id",
            status="Active",
            budget=5000
        )
        
        assert result is True
        mock_session.request.assert_called_once()
        
    def test_add_content_no_db(self):
        """Test add_content without content database configured."""
        with patch.dict(os.environ, {}, clear=True), patch('builtins.print') as mock_print:
            dashboard = NotionDashboard(token="test_token")
            result = dashboard.add_content("campaign-id", "Test Hook")
            
        assert result is None
        mock_print.assert_called_with("[Notion] Content DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_add_content_success(self, mock_session_class, mock_getenv):
        """Test successful content addition."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CONTENT_DB": "content-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "content-page-id"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_content(
            "campaign-id",
            "Test Hook",
            platform="tiktok",
            content_type="Video",
            status="Draft"
        )
        
        assert result == "content-page-id"
        mock_session.request.assert_called_once()
        
    def test_update_content_no_changes(self):
        """Test update_content with no changes."""
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_content("content-id")
        assert result is False
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_update_content_success(self, mock_session_class, mock_getenv):
        """Test successful content update."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CONTENT_DB": "content-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"object": "page"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_content(
            "content-id",
            status="Posted",
            post_url="https://example.com/post"
        )
        
        assert result is True
        mock_session.request.assert_called_once()
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_add_analytics_no_db(self, mock_session_class, mock_getenv):
        """Test add_analytics without analytics database configured."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.add_analytics("campaign-id", metric="views", value=100)
            
        assert result is None
        mock_print.assert_called_with("[Notion] Analytics DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_add_analytics_success(self, mock_session_class, mock_getenv):
        """Test successful analytics addition."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_ANALYTICS_DB": "analytics-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "analytics-page-id"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_analytics(
            "campaign-id",
            metric="views",
            value=100,
            platform="tiktok",
            post_url="https://example.com/post"
        )
        
        assert result == "analytics-page-id"
        mock_session.request.assert_called_once()
        
    def test_get_all_campaigns_no_db(self):
        """Test get_all_campaigns without campaign database."""
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.get_all_campaigns()
        assert result == []
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_get_all_campaigns_success(self, mock_session_class, mock_getenv):
        """Test successful campaign retrieval."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "campaign-1",
                    "properties": {
                        "Name": {"title": [{"type": "text", "text": {"content": "Test Campaign"}, "plain_text": "Test Campaign"}]},
                        "Status": {"select": {"name": "Active"}},
                        "Priority": {"select": {"name": "High"}},
                        "Niche": {"select": {"name": "skincare"}},
                        "Budget": {"number": 5000},
                        "Start Date": {"date": {"start": "2023-01-01"}},
                        "End Date": {"date": {"start": "2023-02-01"}},
                        "Created At": {"date": {"start": "2023-01-01"}},
                    }
                }
            ]
        }
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.get_all_campaigns()
        
        assert len(result) == 1
        campaign = result[0]
        assert campaign["id"] == "campaign-1"
        assert campaign["name"] == "Test Campaign"
        assert campaign["status"] == "Active"
        assert campaign["priority"] == "High"
        assert campaign["niche"] == "skincare"
        assert campaign["budget"] == 5000
        assert campaign["start_date"] == "2023-01-01"
        assert campaign["end_date"] == "2023-02-01"
        assert campaign["created_at"] == "2023-01-01"
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_get_content_for_campaign_no_db(self, mock_session_class, mock_getenv):
        """Test get_content_for_campaign without content database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.get_content_for_campaign("campaign-id")
        assert result == []
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_get_content_for_campaign_success(self, mock_session_class, mock_getenv):
        """Test successful content retrieval for campaign."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CONTENT_DB": "content-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "content-1",
                    "properties": {
                        "Hook": {"title": [{"plain_text": "Test Hook 1"}]},
                        "Platform": {"select": {"name": "tiktok"}},
                        "Status": {"select": {"name": "scripted"}},
                        "Post URL": {"url": "https://example.com/post1"}
                    }
                },
                {
                    "id": "content-2",
                    "properties": {
                        "Hook": {"title": [{"plain_text": "Test Hook 2"}]},
                        "Platform": {"select": {"name": "instagram"}},
                        "Status": {"select": {"name": "posted"}},
                        "Post URL": {"url": "https://example.com/post2"}
                    }
                }
            ]
        }
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.get_content_for_campaign("campaign-id")
        
        assert len(result) == 2
        content1 = result[0]
        assert content1["id"] == "content-1"
        assert content1["hook"] == "Test Hook 1"
        assert content1["platform"] == "tiktok"
        assert content1["status"] == "scripted"
        assert content1["post_url"] == "https://example.com/post1"
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_influencers_no_db(self, mock_session_class, mock_getenv):
        """Test sync_influencers without database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_influencers([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Influencers DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_influencers_success(self, mock_session_class, mock_getenv):
        """Test successful influencers sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_GALLERY_DB": "gallery-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        query_response = Mock()
        query_response.status_code = 200
        query_response.json.return_value = {"results": []}
        
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "gallery-page-id"}
        
        mock_session.request.side_effect = [query_response, create_response]
        
        influencers = [
            {
                "name": "Test Influencer",
                "platform": "tiktok",
                "followers": 50000,
                "engagement_rate": 0.05,
                "niche": "skincare",
                "tier": "Micro",
                "email": "test@example.com",
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_influencers(influencers)
        
        assert len(result) == 1
        assert result[0] == "gallery-page-id"
        assert mock_session.request.call_count == 2
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_contentbank_no_db(self, mock_session_class, mock_getenv):
        """Test sync_contentbank without database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_contentbank([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] ContentBank DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_contentbank_success(self, mock_session_class, mock_getenv):
        """Test successful contentbank sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_INBOX_DB": "inbox-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        query_response = Mock()
        query_response.status_code = 200
        query_response.json.return_value = {"results": []}
        
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "inbox-page-id"}
        
        mock_session.request.side_effect = [query_response, create_response]
        
        items = [
            {
                "title": "Test Asset",
                "type": "Video",
                "tags": "skincare,beauty",
                "created_at": "2023-01-01",
                "used_count": 5,
                "file_url": "https://example.com/file.mp4",
                "description": "A test asset"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_contentbank(items)
        
        assert len(result) == 1
        assert result[0] == "inbox-page-id"
        assert mock_session.request.call_count == 2
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_brands_no_db(self, mock_session_class, mock_getenv):
        """Test sync_brands without brands database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_brands([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Brands DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_brands_success(self, mock_session_class, mock_getenv):
        """Test successful brands sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_BRANDS_DB": "brands-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "brands-page-id"}
        mock_session.request.return_value = mock_response
        
        brands = [
            {
                "name": "Test Brand",
                "status": "Active",
                "industry": "skincare",
                "niche": "skincare",
                "email": "contact@brand.com",
                "tone": "casual",
                "language": "en",
                "target_audience": "Young adults",
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_brands(brands)
        
        assert len(result) == 1
        assert result[0] == "brands-page-id"
        mock_session.request.assert_called_once()
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_logs_no_db(self, mock_session_class, mock_getenv):
        """Test sync_logs without logs database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_logs([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Logs DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_logs_success(self, mock_session_class, mock_getenv):
        """Test successful logs sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_APPROVALS_DB": "approvals-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "approvals-page-id"}
        mock_session.request.return_value = mock_response
        
        logs = [
            {
                "level": "INFO",
                "source": "orchestrator",
                "message": "Campaign started",
                "timestamp": "2023-01-01T00:00:00Z",
                "traceback": ""
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_logs(logs)
        
        assert len(result) == 1
        assert result[0] == "approvals-page-id"
        mock_session.request.assert_called_once()
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_products_no_db(self, mock_session_class, mock_getenv):
        """Test sync_products without products database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_products([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Products DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_products_success(self, mock_session_class, mock_getenv):
        """Test successful products sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_PRODUCTS_DB": "products-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        query_response = Mock()
        query_response.status_code = 200
        query_response.json.return_value = {"results": []}
        
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "products-page-id"}
        
        mock_session.request.side_effect = [query_response, create_response]
        
        products = [
            {
                "name": "Test Product",
                "status": "Active",
                "category": "skincare",
                "price": 25.99,
                "platform": "shopee",
                "commission_rate": 0.1,
                "affiliate_link": "https://example.com/product",
                "rating": 4.5,
                "sold": 1000,
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_products(products)
        
        assert len(result) == 1
        assert result[0] == "products-page-id"
        assert mock_session.request.call_count == 2
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_create_daily_report_no_dbs(self, mock_session_class, mock_getenv):
        """Test create_daily_report without required databases."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.create_daily_report()
            
        assert result is None
        mock_print.assert_called_with("[Notion] Campaign or Analytics DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_create_daily_report_success(self, mock_session_class, mock_getenv):
        """Test successful daily report creation."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id",
            "NOTION_ANALYTICS_DB": "analytics-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        campaigns_response = Mock()
        campaigns_response.status_code = 200
        campaigns_response.json.return_value = {"results": []}
        
        analytics_response = Mock()
        analytics_response.status_code = 200
        analytics_response.json.return_value = {"results": []}
        
        create_response = Mock()
        create_response.status_code = 200
        create_response.json.return_value = {"id": "report-page-id"}
        
        mock_session.request.side_effect = [campaigns_response, analytics_response, create_response]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.create_daily_report("2023-01-01")
        
        assert result == "report-page-id"
        assert mock_session.request.call_count == 3
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_orchestrator_result_no_config(self, mock_session_class, mock_getenv):
        """Test sync_orchestrator_result with no configuration."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_orchestrator_result({}, "Test Product")
            
        assert result == {"synced": False, "reason": "no_token"}
        mock_print.assert_called_with("[Notion] Not configured. Set NOTION_TOKEN and DB IDs.")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_orchestrator_result_campaign_create_failed(self, mock_session_class, mock_getenv):
        """Test sync_orchestrator_result when campaign creation fails."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id",
            "NOTION_CONTENT_DB": "content-db-id",
            "NOTION_ANALYTICS_DB": "analytics-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        campaigns_response = Mock()
        campaigns_response.status_code = 200
        campaigns_response.json.return_value = {"results": []}
        mock_session.request.return_value = campaigns_response
        
        # Mock add_campaign to return None (failed)
        dashboard = NotionDashboard(token="test_token")
        with patch.object(dashboard, 'add_campaign', return_value=None):
            result = dashboard.sync_orchestrator_result({}, "Test Product")
            
        assert result == {"synced": False, "reason": "campaign_create_failed"}
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_orchestrator_result_success(self, mock_session_class, mock_getenv):
        """Test successful sync_orchestrator_result."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_CAMPAIGN_DB": "campaign-db-id",
            "NOTION_CONTENT_DB": "content-db-id",
            "NOTION_ANALYTICS_DB": "analytics-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        update_response = Mock()
        update_response.status_code = 200
        update_response.json.return_value = {"object": "page"}
        mock_session.request.return_value = update_response
        
        dashboard = NotionDashboard(token="test_token")
        
        # Mock the methods
        with patch.object(dashboard, 'get_all_campaigns', return_value=[]), \
             patch.object(dashboard, 'add_campaign', return_value="campaign-id"), \
             patch.object(dashboard, 'add_content', return_value="content-id"):
            
            result = dashboard.sync_orchestrator_result({
                "scripts": [
                    {"hook": "Test Hook 1", "platform": "tiktok"},
                    {"hook": "Test Hook 2", "platform": "tiktok"}
                ],
                "platforms": ["tiktok"],
                "psychology_triggers": "curiosity"
            }, "Test Product")
            
        assert result["synced"] is True
        assert result["campaign_id"] == "campaign-id"
        assert len(result["content_ids"]) == 2
        assert "content-id" in result["content_ids"]


class TestSchemaHelpers:
    """12 new tests for visual polish helpers and schema consistency."""

    # ── 1. pretty_status_color ─────────────────────────────────────────
    def test_pretty_status_color_draft(self):
        assert NotionDashboard.pretty_status_color("draft") == "#6B7280"

    def test_pretty_status_color_active(self):
        assert NotionDashboard.pretty_status_color("Active") == "#10B981"

    def test_pretty_status_color_error(self):
        assert NotionDashboard.pretty_status_color("ERROR") == "#E11D48"

    # ── 2-5. format_number ─────────────────────────────────────────────
    def test_format_number_zero(self):
        assert NotionDashboard.format_number(0) == "0"

    def test_format_number_one(self):
        assert NotionDashboard.format_number(1) == "1"

    def test_format_number_thousand(self):
        assert NotionDashboard.format_number(1500) == "1.5K"

    def test_format_number_million(self):
        assert NotionDashboard.format_number(3_400_000) == "3.4M"

    def test_format_number_negative(self):
        assert NotionDashboard.format_number(-500) == "-500"

    def test_format_number_currency(self):
        assert NotionDashboard.format_number(5200, currency=True) == "$5.2K"

    # ── 6-8. format_percentage ─────────────────────────────────────────
    def test_format_percentage_zero(self):
        assert NotionDashboard.format_percentage(0) == "0.0%"

    def test_format_percentage_half(self):
        assert NotionDashboard.format_percentage(0.5) == "50.0%"

    def test_format_percentage_one(self):
        assert NotionDashboard.format_percentage(1.0) == "100.0%"

    # ── 9. format_engagement_rate ──────────────────────────────────────
    def test_format_engagement_rate(self):
        result = NotionDashboard.format_engagement_rate(100, 20, 5, 5000)
        assert result == "2.50%"

    def test_format_engagement_rate_zero_followers(self):
        result = NotionDashboard.format_engagement_rate(100, 20, 5, 0)
        assert result == "0%"

    # ── 10-12. Schema consistency (all 8 DBs have Status) ──────────────
    def test_all_schemas_have_status(self):
        from ugc_ai_overpower.core.notion_sync import SCHEMAS
        missing = [name for name, schema in SCHEMAS.items()
                   if "Status" not in schema.get("properties", {})]
        # Logs has Level instead of Status, ContentBank has no Status
        # Campaigns, Content, Brands, Products have Status
        expected_missing = {"Analytics", "Influencers", "ContentBank", "Logs"}
        assert set(missing) == expected_missing, f"Unexpected missing Status: {missing}"

    def test_all_schemas_have_title(self):
        from ugc_ai_overpower.core.notion_sync import SCHEMAS
        for name, schema in SCHEMAS.items():
            assert "title" in schema, f"{name} missing title"

    def test_schema_property_count_minimum(self):
        from ugc_ai_overpower.core.notion_sync import SCHEMAS
        for name, schema in SCHEMAS.items():
            count = len(schema.get("properties", {}))
            assert count >= 5, f"{name} has only {count} properties (minimum 5)"