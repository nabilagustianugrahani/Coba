import json
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
import sqlite3
from datetime import datetime, timedelta

# Import with proper path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2, SCHEMA_V2


class TestContentBankV2:
    """Test suite for ContentBankV2 class."""
    
    def test_init_creates_tables(self, temp_db_path):
        """Test that initialization creates all required tables."""
        bank = ContentBankV2(db_path=temp_db_path)
        conn = bank._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [r[0] for r in tables]
        
        # Check main tables exist
        assert "products_v2" in table_names
        assert "influencers_v2" in table_names
        assert "content_v2" in table_names
        assert "content_series" in table_names
        assert "tags" in table_names
        assert "ab_tests" in table_names
        
        # Check FTS tables exist
        assert "products_fts" in table_names
        assert "content_fts" in table_names
        
        conn.close()
        
    def test_connect_wal_mode(self, temp_db_path):
        """Test that connection uses WAL mode."""
        bank = ContentBankV2(db_path=temp_db_path)
        conn = bank._connect()
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert journal_mode.upper() == "WAL"
        conn.close()
        
    def test_connect_row_factory(self, temp_db_path):
        """Test that connection uses row factory."""
        bank = ContentBankV2(db_path=temp_db_path)
        conn = bank._connect()
        
        # Insert test data
        conn.execute("INSERT INTO products_v2 (name, platform) VALUES (?, ?)", 
                    ("Test Product", "shopee"))
        conn.commit()
        
        # Test row factory
        row = conn.execute("SELECT * FROM products_v2 WHERE name = ?", 
                          ("Test Product",)).fetchone()
        assert row["name"] == "Test Product"
        assert isinstance(row, sqlite3.Row)
        
        conn.close()
        
    def test_add_product(self, content_bank):
        """Test adding a product."""
        product_id = content_bank.add_product(
            name="Test Product",
            platform="shopee",
            category="skincare",
            subcategory="moisturizer",
            commission=0.1,
            price=25.99,
            affiliate_link="https://example.com/product",
            image_url="https://example.com/image.jpg",
            tags=["skincare", "beauty"],
            metadata={"brand": "TestBrand", "rating": 4.5}
        )
        
        assert product_id is not None
        assert isinstance(product_id, int)
        
        # Verify product was added
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM products_v2 WHERE id = ?", (product_id,)).fetchone()
        assert row["name"] == "Test Product"
        assert row["platform"] == "shopee"
        assert row["category"] == "skincare"
        assert row["subcategory"] == "moisturizer"
        assert row["commission"] == 0.1
        assert row["price"] == 25.99
        assert json.loads(row["tags"]) == ["skincare", "beauty"]
        assert json.loads(row["metadata"]) == {"brand": "TestBrand", "rating": 4.5}
        
        # Check slug generation
        assert row["slug"] == "test-product"
        
        conn.close()
        
    def test_add_product_minimal(self, content_bank):
        """Test adding a product with minimal data."""
        product_id = content_bank.add_product(name="Minimal Product")
        
        assert product_id is not None
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM products_v2 WHERE id = ?", (product_id,)).fetchone()
        assert row["name"] == "Minimal Product"
        assert row["platform"] == "shopee"  # default
        assert row["commission"] == 0  # default
        assert row["price"] == 0  # default
        assert row["tags"] == "[]"  # default
        assert row["metadata"] == "{}"  # default
        conn.close()
        
    def test_get_all_products(self, content_bank):
        """Test retrieving all products."""
        # Add test products
        for i in range(5):
            content_bank.add_product(f"Product {i}", platform="shopee")
            
        products = content_bank.get_all_products(limit=3, offset=1)
        
        assert len(products) == 3
        # Implementation orders by id DESC (newest first)
        assert products[0]["name"] == "Product 3"
        assert products[1]["name"] == "Product 2"
        assert products[2]["name"] == "Product 1"
        
        # Test with different limit
        all_products = content_bank.get_all_products(limit=10)
        assert len(all_products) == 5
        
    def test_get_all_products_empty(self, content_bank):
        """Test retrieving products when none exist."""
        products = content_bank.get_all_products()
        assert len(products) == 0
        
    def test_search_products(self, content_bank):
        """Test product search functionality."""
        # Add test products
        content_bank.add_product("Skincare Moisturizer", category="skincare")
        content_bank.add_product("Makeup Foundation", category="makeup")
        content_bank.add_product("Hair Shampoo", category="haircare")
        content_bank.add_product("Skincare Serum", category="skincare")
        
        # Search by category
        results = content_bank.search_products("skincare", limit=10)
        assert len(results) >= 2  # Should find at least 2 skincare products
        
        # Search by name
        results = content_bank.search_products("foundation", limit=10)
        assert len(results) >= 1
        assert any("Makeup Foundation" in str(r) for r in results)
        
    def test_search_products_empty(self, content_bank):
        """Test product search when no products match."""
        results = content_bank.search_products("nonexistent", limit=10)
        assert len(results) == 0
        
    def test_add_content(self, content_bank):
        """Test adding content."""
        # First add a product
        product_id = content_bank.add_product("Test Product")
        
        content_id = content_bank.add_content(
            hook="I tried this product for 30 days...",
            script="This is my review of the test product.",
            platform="tiktok",
            hashtags=["skincare", "beauty", "review"],
            status="draft",
            tags=["test", "skincare"],
            metadata={"quality_score": 8.5}
        )
        
        assert content_id is not None
        assert isinstance(content_id, int)
        
        # Verify content was added
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        assert row["hook"] == "I tried this product for 30 days..."
        assert row["script"] == "This is my review of the test product."
        assert row["platform"] == "tiktok"
        assert json.loads(row["hashtags"]) == ["skincare", "beauty", "review"]
        assert row["status"] == "draft"
        assert json.loads(row["tags"]) == ["test", "skincare"]
        assert json.loads(row["metadata"]) == {"quality_score": 8.5}
        
        # Check auto-generated fields
        assert row["script_hash"] is not None
        assert "version_group" in row.keys()
        assert row["version"] == 1
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
        
        conn.close()
        
    def test_add_content_with_product(self, content_bank):
        """Test adding content with product association."""
        product_id = content_bank.add_product("Test Product")
        
        content_id = content_bank.add_content(
            hook="Test hook",
            script="Test script",
            product_id=product_id
        )
        
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        assert row["product_id"] == product_id
        conn.close()
        
    def test_create_version(self, content_bank):
        """Test creating a new version of content."""
        # Add original content
        content_id = content_bank.add_content(
            hook="Original hook",
            script="Original script"
        )
        
        # Create new version
        new_version_id = content_bank.create_version(
            content_id,
            "New updated script",
            hook="Updated hook"
        )
        
        assert new_version_id is not None
        assert new_version_id != content_id
        
        # Verify version tree
        versions = content_bank.get_version_tree(content_id)
        assert len(versions) == 2
        
        # Check version numbers
        versions.sort(key=lambda x: x["version"])
        assert versions[0]["version"] == 1
        assert versions[1]["version"] == 2
        assert versions[1]["parent_version_id"] == content_id
        
        # Check version group consistency
        assert versions[0]["version_group"] == versions[1]["version_group"]
        
    def test_create_version_nonexistent(self, content_bank):
        """Test creating version for non-existent content."""
        with pytest.raises(ValueError, match="Content 999 not found"):
            content_bank.create_version(999, "New script")
            
    def test_get_version_tree_empty(self, content_bank):
        """Test getting version tree for non-existent content."""
        versions = content_bank.get_version_tree(999)
        assert versions == []
        
    def test_search_content(self, content_bank):
        """Test content search functionality."""
        # Add test content
        content_bank.add_content(
            hook="Best skincare routine",
            script="My daily skincare routine",
            hashtags=["skincare", "routine"]
        )
        content_bank.add_content(
            hook="Makeup tutorial",
            script="How to apply makeup",
            hashtags=["makeup", "tutorial"]
        )
        content_bank.add_content(
            hook="Hair care tips",
            script="Tips for healthy hair",
            hashtags=["hair", "care"]
        )
        
        # Search by hook
        results = content_bank.search_content("skincare", limit=10)
        assert len(results) >= 1
        assert any("Best skincare routine" in str(r) for r in results)
        
        # Search by script
        results = content_bank.search_content("makeup", limit=10)
        assert len(results) >= 1
        assert any("How to apply makeup" in str(r) for r in results)
        
        # Search by hashtag
        results = content_bank.search_content("hair", limit=10)
        assert len(results) >= 1
        assert any("Hair care tips" in str(r) for r in results)
        
    def test_search_content_empty(self, content_bank):
        """Test content search when no content matches."""
        results = content_bank.search_content("nonexistent", limit=10)
        assert len(results) == 0
        
    def test_add_tag(self, content_bank):
        """Test adding a tag."""
        tag_id = content_bank.add_tag("skincare", "#FF69B4", "category")
        
        assert tag_id is not None
        assert isinstance(tag_id, int)
        
        # Verify tag was added
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM tags WHERE id = ?", (tag_id,)).fetchone()
        assert row["name"] == "skincare"
        assert row["color"] == "#FF69B4"
        assert row["category"] == "category"
        conn.close()
        
    def test_add_tag_duplicate(self, content_bank):
        """Test adding duplicate tag (should not create duplicate)."""
        tag_id1 = content_bank.add_tag("skincare")
        tag_id2 = content_bank.add_tag("skincare")
        
        assert tag_id1 == tag_id2  # Should return same ID
        
        # Verify only one tag exists
        conn = content_bank._connect()
        count = conn.execute("SELECT COUNT(*) FROM tags WHERE name = ?", ("skincare",)).fetchone()[0]
        assert count == 1
        conn.close()
        
    def test_add_tag_case_insensitive(self, content_bank):
        """Test that tags are case insensitive."""
        tag_id1 = content_bank.add_tag("Skincare")
        tag_id2 = content_bank.add_tag("skincare")
        
        assert tag_id1 == tag_id2  # Should be same
        
    def test_get_tags_by_category(self, content_bank):
        """Test getting tags by category."""
        # Add test tags
        content_bank.add_tag("skincare", "#FF69B4", "category")
        content_bank.add_tag("makeup", "#FF1493", "category")
        content_bank.add_tag("haircare", "#32CD32", "category")
        content_bank.add_tag("fitness", "#FF4500", "subcategory")
        
        # Get tags by category
        tags = content_bank.get_tags_by_category("category")
        
        assert len(tags) == 3
        tag_names = [t["name"] for t in tags]
        assert "skincare" in tag_names
        assert "makeup" in tag_names
        assert "haircare" in tag_names
        assert "fitness" not in tag_names
        
        # Test empty category
        tags = content_bank.get_tags_by_category("nonexistent")
        assert len(tags) == 0
        
    def test_create_series(self, content_bank):
        """Test creating a content series."""
        # First add a product
        product_id = content_bank.add_product("Test Product")
        
        series_id = content_bank.create_series(
            name="Test Series",
            description="A test series",
            product_id=product_id,
            platform="tiktok",
            total_episodes=10,
            episode_interval_hours=24,
            tags=["test", "series"],
            template_json={"format": "storytime"},
            schedule_cron="0 9 * * *"
        )
        
        assert series_id is not None
        assert isinstance(series_id, int)
        
        # Verify series was added
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_series WHERE id = ?", (series_id,)).fetchone()
        assert row["name"] == "Test Series"
        assert row["description"] == "A test series"
        assert row["product_id"] == product_id
        assert row["platform"] == "tiktok"
        assert row["total_episodes"] == 10
        assert row["episode_interval_hours"] == 24
        assert json.loads(row["tags"]) == ["test", "series"]
        assert json.loads(row["template_json"]) == {"format": "storytime"}
        assert row["schedule_cron"] == "0 9 * * *"
        conn.close()
        
    def test_create_series_minimal(self, content_bank):
        """Test creating a series with minimal data."""
        series_id = content_bank.create_series("Minimal Series")
        
        assert series_id is not None
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_series WHERE id = ?", (series_id,)).fetchone()
        assert row["name"] == "Minimal Series"
        assert row["platform"] == "tiktok"  # default
        assert row["total_episodes"] == 10  # default
        assert row["episode_interval_hours"] == 24  # default
        conn.close()
        
    def test_get_series(self, content_bank):
        """Test getting a series by ID."""
        # Create a series first
        series_id = content_bank.create_series("Test Series")
        
        # Get the series
        series = content_bank.get_series(series_id)
        
        assert series["id"] == series_id
        assert series["name"] == "Test Series"
        
        # Test non-existent series
        series = content_bank.get_series(999)
        assert series == {}
        
    def test_get_series_episodes(self, content_bank):
        """Test getting episodes for a series."""
        # Create a series
        series_id = content_bank.create_series("Test Series")
        
        # Add episodes
        for i in range(3):
            content_bank.add_content(
                hook=f"Episode {i+1}",
                script=f"Script for episode {i+1}",
                series_id=series_id,
                episode_number=i+1
            )
        
        # Get episodes
        episodes = content_bank.get_series_episodes(series_id)
        
        assert len(episodes) == 3
        assert episodes[0]["episode_number"] == 1
        assert episodes[1]["episode_number"] == 2
        assert episodes[2]["episode_number"] == 3
        
        # Test non-existent series
        episodes = content_bank.get_series_episodes(999)
        assert episodes == []
        
    def test_update_performance(self, content_bank):
        """Test updating content performance metrics."""
        # Add content first
        content_id = content_bank.add_content(
            hook="Test content",
            script="Test script"
        )
        
        # Update performance
        content_bank.update_performance(
            content_id,
            views=1000,
            likes=100,
            comments=20,
            shares=5,
            clicks=50
        )
        
        # Verify update
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        assert row["views"] == 1000
        assert row["likes"] == 100
        assert row["comments"] == 20
        assert row["shares"] == 5
        assert row["clicks"] == 50
        
        # Check engagement score calculation
        total_engagement = 100 + 20 + 5 + 50
        expected_score = round(total_engagement / 1000 * 100, 2)
        assert row["engagement_score"] == expected_score
        
        conn.close()
        
    def test_update_performance_zero_views(self, content_bank):
        """Test updating performance with zero views."""
        content_id = content_bank.add_content("Test", "Script")
        content_bank.update_performance(content_id, views=0, likes=10)
        
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        # Engagement score should be 0 when views is 0
        assert row["engagement_score"] == 0
        conn.close()
        
    def test_get_top_performing(self, content_bank):
        """Test getting top performing content."""
        # Add content with varying performance
        for i in range(5):
            content_id = content_bank.add_content(f"Content {i}", f"Script {i}")
            # Create different engagement scores
            engagement_score = 10 - i  # 10, 9, 8, 7, 6
            content_bank.update_performance(
                content_id,
                views=100,
                likes=engagement_score,
                engagement_score=engagement_score
            )
        
        # Get top performing
        top = content_bank.get_top_performing(limit=3)
        
        assert len(top) == 3
        assert top[0]["engagement_score"] == 10  # Highest first
        assert top[1]["engagement_score"] == 9
        assert top[2]["engagement_score"] == 8
        
        # Test with platform filter
        top_tiktok = content_bank.get_top_performing(platform="tiktok", limit=5)
        assert len(top_tiktok) == 5  # All content should be tiktok
        
        # Test with days filter
        from datetime import datetime, timedelta
        old_date = (datetime.now() - timedelta(days=10)).isoformat()
        _conn = content_bank._connect()
        _conn.execute(
            "UPDATE content_v2 SET posted_at = ? WHERE id = 1",
            (old_date,)
        )
        _conn.commit()
        _conn.close()

        recent_top = content_bank.get_top_performing(days=7, limit=5)
        # Should exclude the content posted 10 days ago
        assert len(recent_top) == 4
        
    def test_get_top_performing_empty(self, content_bank):
        """Test getting top performing when no content has engagement."""
        content_bank.add_content("Test", "Script")
        top = content_bank.get_top_performing()
        assert len(top) == 0
        
    def test_get_underperforming(self, content_bank):
        """Test getting underperforming content."""
        # Add content with low engagement
        for i in range(3):
            content_id = content_bank.add_content(f"Content {i}", f"Script {i}")
            content_bank.update_performance(
                content_id,
                views=1000,  # High views
                likes=5,     # Low engagement
                engagement_score=0.5
            )
        
        # Add high performing content
        high_id = content_bank.add_content("High", "Script")
        content_bank.update_performance(
            high_id,
            views=100,
            likes=20,
            engagement_score=20.0
        )
        
        # Get underperforming
        under = content_bank.get_underperforming(threshold=1.0, limit=5)
        
        assert len(under) == 3  # Only the low-performing content
        for content in under:
            assert content["engagement_score"] < 1.0
            assert content["views"] > 100  # Only content with >100 views
            
    def test_get_underperforming_empty(self, content_bank):
        """Test getting underperforming when no content qualifies."""
        # Add high performing content
        content_id = content_bank.add_content("High", "Script")
        content_bank.update_performance(
            content_id,
            views=100,
            likes=20,
            engagement_score=20.0
        )
        
        under = content_bank.get_underperforming(threshold=1.0)
        assert len(under) == 0
        
    def test_get_stats(self, content_bank):
        """Test getting database statistics."""
        # Add test data
        for i in range(3):
            content_bank.add_product(f"Product {i}")
            content_bank.add_influencer(f"Influencer {i}")
            content_bank.add_content(f"Content {i}", f"Script {i}")
            
        series_id = content_bank.create_series("Test Series")
        content_bank.add_tag("test")
        
        # Add some performance data
        content_id = content_bank.add_content("Perf", "Script")
        content_bank.update_performance(content_id, views=1000, likes=50)
        
        stats = content_bank.get_stats()
        
        assert stats["products"] == 3
        assert stats["influencers"] == 3
        assert stats["content"] == 4  # 3 regular + 1 with performance
        assert stats["series"] == 1
        assert stats["tags"] == 1
        assert stats["avg_engagement"] == 5.0  # 50/1000 * 100 = 5.0%
        assert "versions" in stats
        
    def test_get_stats_empty(self, content_bank):
        """Test getting stats when database is empty."""
        stats = content_bank.get_stats()
        
        assert stats["products"] == 0
        assert stats["influencers"] == 0
        assert stats["content"] == 0
        assert stats["series"] == 0
        assert stats["tags"] == 0
        assert stats["avg_engagement"] == 0
        
    def test_thread_safety(self, content_bank):
        """Test that the bank is thread-safe."""
        import threading
        import time
        
        results = []
        errors = []
        
        def add_product(index):
            try:
                product_id = content_bank.add_product(f"Thread Product {index}")
                results.append(product_id)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=add_product, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 10, f"Expected 10 products, got {len(results)}"
        
        # Verify all products were added
        products = content_bank.get_all_products()
        assert len(products) == 10
        
    def test_database_lock(self, temp_db_path):
        """Test database locking mechanism."""
        bank1 = ContentBankV2(db_path=temp_db_path)
        bank2 = ContentBankV2(db_path=temp_db_path)
        
        # Add product with first bank
        product_id1 = bank1.add_product("Test Product 1")
        assert product_id1 is not None
        
        # Add product with second bank
        product_id2 = bank2.add_product("Test Product 2")
        assert product_id2 is not None
        
        # Verify both products exist
        products = bank1.get_all_products()
        assert len(products) == 2
        
    def test_sql_injection_protection(self, content_bank):
        """Test protection against SQL injection."""
        malicious_name = "'; DROP TABLE products_v2; --"
        
        # This should not drop the table
        product_id = content_bank.add_product(malicious_name)
        assert product_id is not None
        
        # Verify table still exists
        conn = content_bank._connect()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='products_v2'"
        ).fetchone()
        assert tables is not None
        conn.close()
        
    def test_data_integrity(self, content_bank):
        """Test data integrity constraints."""
        # Test adding content with non-existent product ID
        # This should not fail (foreign key constraints are handled by SQLite)
        content_id = content_bank.add_content(
            hook="Test",
            script="Script",
            product_id=999  # Non-existent product
        )
        assert content_id is not None
        
        # Verify content was added but with NULL product_id
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        assert row["product_id"] is None
        conn.close()
        
    def test_large_data_handling(self, content_bank):
        """Test handling of large data."""
        # Add content with large script
        large_script = "A" * 10000  # 10KB script
        content_id = content_bank.add_content(
            hook="Large content",
            script=large_script,
            metadata={"large_field": "B" * 50000}  # 50KB metadata
        )
        
        assert content_id is not None
        
        # Verify large data was stored correctly
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (content_id,)).fetchone()
        assert row["script"] == large_script
        assert len(json.loads(row["metadata"])["large_field"]) == 50000
        conn.close()
        
    def test_unicode_handling(self, content_bank):
        """Test handling of Unicode characters."""
        unicode_content = content_bank.add_content(
            hook="测试内容",  # Chinese
            script="This contains emojis 🎉 and special chars ñ",  # Emoji and Spanish
            hashtags=["测试", "emoji🎉"],  # Mixed Unicode
            tags=["unicode", "测试"]
        )
        
        assert unicode_content is not None
        
        # Verify Unicode was stored correctly
        conn = content_bank._connect()
        row = conn.execute("SELECT * FROM content_v2 WHERE id = ?", (unicode_content,)).fetchone()
        assert row["hook"] == "测试内容"
        assert "🎉" in row["script"]
        assert "ñ" in row["script"]
        assert "测试" in json.loads(row["hashtags"])[0]
        conn.close()