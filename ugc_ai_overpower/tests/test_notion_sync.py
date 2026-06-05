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
        mock_session_class.assert_not_called()
        
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
        mock_response.get.return_value = "test-db-id"
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
        mock_response.get.return_value = "campaign-page-id"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_campaign("Test Product", platforms=["tiktok", "instagram"])
        
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
        mock_response.get.return_value = {"object": "page"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_campaign(
            "test-campaign-id",
            status="Active",
            total_content=10
        )
        
        assert result is True
        mock_session.request.assert_called_once()
        
    def test_add_content_no_db(self):
        """Test add_content without content database configured."""
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
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
        mock_response.get.return_value = "content-page-id"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_content(
            "campaign-id",
            "Test Hook",
            platform="tiktok",
            script="Test script",
            status="scripted"
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
        mock_response.get.return_value = {"object": "page"}
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.update_content(
            "content-id",
            status="posted",
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
            result = dashboard.add_analytics("content-id", views=100, likes=10)
            
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
        mock_response.get.return_value = "analytics-page-id"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.add_analytics(
            "content-id",
            campaign_id="campaign-id",
            views=100,
            likes=10,
            comments=5,
            shares=2,
            clicks=15,
            platform="tiktok"
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
        mock_response.get.return_value = {
            "results": [
                {
                    "id": "campaign-1",
                    "properties": {
                        "Name": {"title": [{"text": {"content": "Test Campaign"}}]},
                        "Product": {"rich_text": [{"text": {"content": "Test Product"}}]},
                        "Status": {"select": {"name": "Active"}},
                        "Target Platforms": {"multi_select": [{"name": "tiktok"}]},
                        "Psychology Triggers": {"rich_text": [{"text": {"content": "curiosity"}}]},
                        "Total Content": {"number": 10},
                        "Content Generated": {"number": 5},
                        "Videos Generated": {"number": 3},
                        "Posts Published": {"number": 2},
                        "Created At": {"date": {"start": "2023-01-01"}},
                        "Updated At": {"date": {"start": "2023-01-02"}}
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
        assert campaign["product"] == "Test Product"
        assert campaign["status"] == "Active"
        assert campaign["platforms"] == ["tiktok"]
        assert campaign["triggers"] == "curiosity"
        assert campaign["total_content"] == 10
        assert campaign["content_generated"] == 5
        assert campaign["videos_generated"] == 3
        assert campaign["posts_published"] == 2
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
        mock_response.get.return_value = {
            "results": [
                {
                    "id": "content-1",
                    "properties": {
                        "Hook": {"title": [{"text": {"content": "Test Hook 1"}}]},
                        "Platform": {"select": {"name": "tiktok"}},
                        "Status": {"select": {"name": "scripted"}},
                        "Post URL": {"url": "https://example.com/post1"}
                    }
                },
                {
                    "id": "content-2",
                    "properties": {
                        "Hook": {"title": [{"text": {"content": "Test Hook 2"}}]},
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
    def test_sync_gallery_no_db(self, mock_session_class, mock_getenv):
        """Test sync_gallery without gallery database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_gallery([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Gallery DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_gallery_success(self, mock_session_class, mock_getenv):
        """Test successful gallery sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_GALLERY_DB": "gallery-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.get.return_value = "gallery-page-id"
        mock_session.request.return_value = mock_response
        
        videos = [
            {
                "title": "Test Video",
                "slug": "test-video",
                "description": "Test description",
                "niche": "skincare",
                "platform": "tiktok",
                "product": "Test Product",
                "tags": "skincare,beauty",
                "views": 1000,
                "likes": 100,
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_gallery(videos)
        
        assert len(result) == 1
        assert result[0] == "gallery-page-id"
        mock_session.request.assert_called_once()
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_inbox_no_db(self, mock_session_class, mock_getenv):
        """Test sync_inbox without inbox database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_inbox([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Inbox DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_inbox_success(self, mock_session_class, mock_getenv):
        """Test successful inbox sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_INBOX_DB": "inbox-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.get.return_value = "inbox-page-id"
        mock_session.request.return_value = mock_response
        
        messages = [
            {
                "content": "Test message",
                "platform": "tiktok",
                "sender_username": "test_user",
                "account_id": "12345",
                "message_type": "comment",
                "sentiment": "positive",
                "ai_suggested_reply": "Thanks for your comment!",
                "reply_sent": False,
                "is_read": False,
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_inbox(messages)
        
        assert len(result) == 1
        assert result[0] == "inbox-page-id"
        mock_session.request.assert_called_once()
        
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
        mock_response.get.return_value = "brands-page-id"
        mock_session.request.return_value = mock_response
        
        brands = [
            {
                "name": "Test Brand",
                "tone": "casual",
                "voice": "friendly",
                "language": "en",
                "target_audience": "Young adults",
                "emoji_style": "moderate",
                "default_cta": "Shop now",
                "is_active": True,
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
    def test_sync_approvals_no_db(self, mock_session_class, mock_getenv):
        """Test sync_approvals without approvals database."""
        mock_getenv.return_value = ""
        
        dashboard = NotionDashboard(token="test_token")
        with patch('builtins.print') as mock_print:
            result = dashboard.sync_approvals([])
            
        assert result == []
        mock_print.assert_called_with("[Notion] Approvals DB not configured")
        
    @patch('ugc_ai_overpower.core.notion_sync.os.getenv')
    @patch('ugc_ai_overpower.core.notion_sync.requests.Session')
    def test_sync_approvals_success(self, mock_session_class, mock_getenv):
        """Test successful approvals sync."""
        mock_getenv.side_effect = lambda key, default=None: {
            "NOTION_TOKEN": "test_token",
            "NOTION_APPROVALS_DB": "approvals-db-id"
        }.get(key, default)
        
        mock_session = Mock()
        mock_session_class.return_value = mock_session
        
        mock_response = Mock()
        mock_response.get.return_value = "approvals-page-id"
        mock_session.request.return_value = mock_response
        
        approvals = [
            {
                "content_data": "Test content",
                "content_type": "script",
                "platform": "tiktok",
                "product": "Test Product",
                "status": "pending_review",
                "reviewer": "admin",
                "review_note": "Needs improvement",
                "is_urgent": False,
                "created_at": "2023-01-01",
                "reviewed_at": "2023-01-02"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_approvals(approvals)
        
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
        
        mock_response = Mock()
        mock_response.get.return_value = "products-page-id"
        mock_session.request.return_value = mock_response
        
        products = [
            {
                "name": "Test Product",
                "platform": "shopee",
                "price": 25.99,
                "commission_rate": 0.1,
                "affiliate_link": "https://example.com/product",
                "product_url": "https://example.com/product-page",
                "image_url": "https://example.com/image.jpg",
                "rating": 4.5,
                "sold": 1000,
                "category": "skincare",
                "status": "active",
                "notes": "Popular product",
                "created_at": "2023-01-01"
            }
        ]
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.sync_products(products)
        
        assert len(result) == 1
        assert result[0] == "products-page-id"
        mock_session.request.assert_called_once()
        
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
        
        mock_response = Mock()
        mock_response.get.return_value = "report-page-id"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        result = dashboard.create_daily_report("2023-01-01")
        
        assert result == "report-page-id"
        mock_session.request.assert_called_once()
        
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
        
        mock_response = Mock()
        mock_response.get.return_value = "page-id"
        mock_session.request.return_value = mock_response
        
        dashboard = NotionDashboard(token="test_token")
        
        # Mock the methods
        with patch.object(dashboard, 'get_all_campaigns', return_value=[]), \
             patch.object(dashboard, 'add_campaign', return_value="campaign-id"), \
             patch.object(dashboard, 'add_content', return_value="content-id"):
            
            result = dashboard.sync_orchestrator_result({
                "scripts": [
                    {"hook": "Test Hook 1", "script": "Test script 1", "platform": "tiktok"},
                    {"hook": "Test Hook 2", "script": "Test script 2", "platform": "tiktok"}
                ],
                "platforms": ["tiktok"],
                "psychology_triggers": "curiosity"
            }, "Test Product")
            
        assert result["synced"] is True
        assert result["campaign_id"] == "campaign-id"
        assert len(result["content_ids"]) == 2
        assert "content-id" in result["content_ids"]