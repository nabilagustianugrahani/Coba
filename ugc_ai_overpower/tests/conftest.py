import os
import tempfile
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
from pathlib import Path

# Add the ugc_ai_overpower directory to Python path
ugc_path = Path(__file__).parent.parent
sys.path.insert(0, str(ugc_path))

@pytest.fixture
def mock_notion_token():
    """Mock Notion token for testing."""
    return "mock_notion_token_12345"

@pytest.fixture
def mock_notion_dashboard(mock_notion_token):
    """Create a NotionDashboard instance with mocked token."""
    from ugc_ai_overpower.core.notion_sync import NotionDashboard
    with patch.dict(os.environ, {"NOTION_TOKEN": mock_notion_token}):
        dashboard = NotionDashboard()
        # Mock the session to prevent actual HTTP requests
        dashboard._session = Mock()
        dashboard._request = Mock(return_value={"object": "page", "id": "test-page-id"})
        return dashboard

@pytest.fixture
def mock_ai_router():
    """Create a mock AI router."""
    mock = Mock()
    mock.chat_structured = Mock(return_value={"test": "response"})
    mock.chat = Mock(return_value="test response")
    mock.analyze_product = Mock(return_value={"analysis": "test analysis"})
    return mock

@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)

@pytest.fixture
def content_bank(temp_db_path):
    """Create a ContentBankV2 instance with temporary database."""
    from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2
    return ContentBankV2(db_path=temp_db_path)

@pytest.fixture
def pipeline_engine(mock_ai_router):
    """Create a PipelineEngine instance with mocked AI router."""
    from ugc_ai_overpower.core.pipeline_engine import PipelineEngine
    return PipelineEngine(ai_router=mock_ai_router)

@pytest.fixture
def sample_product_data():
    """Sample product data for testing."""
    return {
        "name": "Test Product",
        "platform": "shopee",
        "category": "skincare",
        "subcategory": "moisturizer",
        "commission": 0.1,
        "price": 25.99,
        "affiliate_link": "https://example.com/product",
        "image_url": "https://example.com/image.jpg",
        "tags": ["skincare", "beauty"],
        "metadata": {"brand": "TestBrand", "rating": 4.5}
    }

@pytest.fixture
def sample_content_data():
    """Sample content data for testing."""
    return {
        "hook": "I tried this product for 30 days...",
        "script": "This is my review of the test product.",
        "platform": "tiktok",
        "hashtags": ["skincare", "beauty", "review"],
        "status": "draft",
        "tags": ["test", "skincare"]
    }

@pytest.fixture
def sample_campaign_data():
    """Sample campaign data for testing."""
    return {
        "product": "Test Product",
        "platforms": ["tiktok", "instagram"],
        "triggers": "curiosity, social_proof",
        "total_content": 10,
        "content_generated": 5,
        "videos_generated": 3,
        "posts_published": 2
    }