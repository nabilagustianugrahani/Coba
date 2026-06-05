import pytest
from unittest.mock import Mock, patch, MagicMock, call
import json
from datetime import datetime

# Import with proper path
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from ugc_ai_overpower.core.pipeline_engine import (
    DAGPipeline, 
    PipelineNode, 
    NodeStatus,
    PipelineEngine,
    UGCPipelineFactory
)


class TestPipelineNode:
    """Test suite for PipelineNode class."""
    
    def test_node_creation(self):
        """Test basic node creation."""
        def dummy_fn(ctx):
            return "test_result"
            
        node = PipelineNode(name="test_node", fn=dummy_fn)
        
        assert node.name == "test_node"
        assert node.fn == dummy_fn
        assert node.deps == []
        assert node.status == NodeStatus.PENDING
        assert node.result is None
        assert node.error is None
        assert node.started_at is None
        assert node.finished_at is None
        assert node.priority == 0
        assert node.duration == 0.0
        
    def test_node_with_deps(self):
        """Test node with dependencies."""
        def dummy_fn(ctx):
            return "test_result"
            
        node = PipelineNode(
            name="test_node",
            fn=dummy_fn,
            deps=["node1", "node2"],
            priority=5
        )
        
        assert node.deps == ["node1", "node2"]
        assert node.priority == 5
        
    def test_node_duration(self):
        """Test node duration calculation."""
        def dummy_fn(ctx):
            import time
            time.sleep(0.1)
            return "test_result"
            
        node = PipelineNode(name="test_node", fn=dummy_fn)
        node.started_at = 1000.0
        node.finished_at = 1000.2
        node.status = NodeStatus.COMPLETED
        
        assert node.duration == 0.2
        
    def test_node_duration_no_times(self):
        """Test duration when times not set."""
        node = PipelineNode(name="test_node", fn=lambda x: x)
        assert node.duration == 0.0


class TestDAGPipeline:
    """Test suite for DAGPipeline class."""
    
    def test_pipeline_creation(self):
        """Test basic pipeline creation."""
        pipeline = DAGPipeline(name="test_pipeline", max_workers=2)
        
        assert pipeline.name == "test_pipeline"
        assert pipeline.max_workers == 2
        assert pipeline.ai is None
        assert len(pipeline._nodes) == 0
        assert pipeline._context == {}
        
    def test_pipeline_with_ai_router(self):
        """Test pipeline creation with AI router."""
        mock_ai = Mock()
        pipeline = DAGPipeline(name="test_pipeline", max_workers=2, ai_router=mock_ai)
        
        assert pipeline.ai is mock_ai
        
    def test_add_node(self):
        """Test adding nodes to pipeline."""
        pipeline = DAGPipeline(name="test_pipeline")
        
        def dummy_fn(ctx):
            return "result"
            
        pipeline.add_node("node1", dummy_fn)
        pipeline.add_node("node2", dummy_fn, deps=["node1"])
        
        assert len(pipeline._nodes) == 2
        assert "node1" in pipeline._nodes
        assert "node2" in pipeline._nodes
        assert pipeline._nodes["node1"].deps == []
        assert pipeline._nodes["node2"].deps == ["node1"]
        
    def test_add_node_chaining(self):
        """Test node addition via chaining."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")\
            .add_node("node1", dummy_fn)\
            .add_node("node2", dummy_fn, deps=["node1"])
            
        assert len(pipeline._nodes) == 2
        
    def test_resolve_deps_no_deps(self):
        """Test dependency resolution for node with no dependencies."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn)
        
        assert pipeline.resolve_deps("node1") is True
        
    def test_resolve_deps_with_deps_completed(self):
        """Test dependency resolution when dependencies are completed."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn)
        pipeline.add_node("node2", dummy_fn, deps=["node1"])
        
        # Mark node1 as completed
        pipeline._nodes["node1"].status = NodeStatus.COMPLETED
        
        assert pipeline.resolve_deps("node2") is True
        
    def test_resolve_deps_with_deps_pending(self):
        """Test dependency resolution when dependencies are pending."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn)
        pipeline.add_node("node2", dummy_fn, deps=["node1"])
        
        # node1 is still pending
        assert pipeline.resolve_deps("node2") is False
        
    def test_resolve_deps_nonexistent_node(self):
        """Test dependency resolution for non-existent node."""
        pipeline = DAGPipeline(name="test_pipeline")
        assert pipeline.resolve_deps("nonexistent") is False
        
    def test_get_ready_nodes_empty(self):
        """Test getting ready nodes from empty pipeline."""
        pipeline = DAGPipeline(name="test_pipeline")
        ready = pipeline.get_ready_nodes()
        assert ready == []
        
    def test_get_ready_nodes_single(self):
        """Test getting ready nodes with single ready node."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn)
        
        ready = pipeline.get_ready_nodes()
        assert ready == ["node1"]
        
    def test_get_ready_nodes_with_deps(self):
        """Test getting ready nodes with dependencies."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn, priority=2)
        pipeline.add_node("node2", dummy_fn, deps=["node1"], priority=1)
        
        # Initially only node1 is ready
        ready = pipeline.get_ready_nodes()
        assert ready == ["node1"]
        
        # Mark node1 as completed
        pipeline._nodes["node1"].status = NodeStatus.COMPLETED
        
        # Now node2 should be ready
        ready = pipeline.get_ready_nodes()
        assert ready == ["node2"]
        
    def test_get_ready_nodes_priority_sorting(self):
        """Test that ready nodes are sorted by priority."""
        def dummy_fn(ctx):
            return "result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn, priority=1)
        pipeline.add_node("node2", dummy_fn, priority=3)
        pipeline.add_node("node3", dummy_fn, priority=2)
        
        ready = pipeline.get_ready_nodes()
        assert ready == ["node2", "node3", "node1"]  # High to low priority
        
    def test_run_empty_pipeline(self):
        """Test running empty pipeline."""
        pipeline = DAGPipeline(name="test_pipeline")
        result = pipeline.run()
        
        assert result["name"] == "test_pipeline"
        assert result["status"] == "completed"
        assert result["completed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0
        
    def test_run_single_node(self):
        """Test running pipeline with single node."""
        def dummy_fn(ctx):
            return "node1_result"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", dummy_fn)
        
        result = pipeline.run()
        
        assert result["status"] == "completed"
        assert result["completed"] == 1
        assert result["failed"] == 0
        assert result["total"] == 1
        assert "node1" in result["results"]
        assert result["results"]["node1"] == "node1_result"
        
    def test_run_with_deps(self):
        """Test running pipeline with dependencies."""
        results = {}
        
        def node1_fn(ctx):
            results["node1"] = "result1"
            return "result1"
            
        def node2_fn(ctx):
            results["node2"] = f"result2_{ctx.get('node1')}"
            return "result2"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", node1_fn)
        pipeline.add_node("node2", node2_fn, deps=["node1"])
        
        result = pipeline.run()
        
        assert result["status"] == "completed"
        assert result["completed"] == 2
        assert result["failed"] == 0
        assert results["node1"] == "result1"
        assert results["node2"] == "result2_result1"
        
    def test_run_with_failure(self):
        """Test running pipeline with node failure."""
        def success_fn(ctx):
            return "success"
            
        def fail_fn(ctx):
            raise ValueError("Node failed")
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", success_fn)
        pipeline.add_node("node2", fail_fn)
        
        result = pipeline.run()
        
        assert result["status"] == "completed_with_errors"
        assert result["completed"] == 1
        assert result["failed"] == 1
        assert result["total"] == 2
        assert "node1" in result["results"]
        assert "node2" not in result["results"]
        
    def test_run_with_context(self):
        """Test running pipeline with context."""
        def node1_fn(ctx):
            return f"result_{ctx.get('input')}"
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", node1_fn)
        
        context = {"input": "test_value"}
        result = pipeline.run(context)
        
        assert result["context"]["input"] == "test_value"
        assert result["results"]["node1"] == "result_test_value"
        
    def test_run_with_ai_router(self):
        """Test running pipeline with AI router."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={"ai": "result"})
        
        def node1_fn(ctx):
            if ctx.get("ai"):
                return f"ai_result_{ctx['ai']['ai']}"
            return "fallback"
            
        pipeline = DAGPipeline(name="test_pipeline", ai_router=mock_ai)
        pipeline.add_node("node1", node1_fn)
        
        result = pipeline.run()
        
        assert result["results"]["node1"] == "ai_result_result"
        mock_ai.chat_structured.assert_called_once()
        
    def test_node_execution_error_handling(self):
        """Test error handling during node execution."""
        def error_fn(ctx):
            raise RuntimeError("Test error")
            
        pipeline = DAGPipeline(name="test_pipeline")
        pipeline.add_node("node1", error_fn)
        
        result = pipeline.run()
        
        assert result["status"] == "completed_with_errors"
        assert result["failed"] == 1
        assert result["total"] == 1
        assert pipeline._nodes["node1"].status == NodeStatus.FAILED
        assert pipeline._nodes["node1"].error == "Test error"
        
    def test_node_timeout_protection(self):
        """Test protection against infinite loops."""
        import time
        
        def slow_fn(ctx):
            time.sleep(0.1)
            return "slow_result"
            
        pipeline = DAGPipeline(name="test_pipeline", max_workers=1)
        pipeline.add_node("node1", slow_fn)
        
        result = pipeline.run()
        
        assert result["status"] == "completed"
        assert result["completed"] == 1
        
    def test_pipeline_id_generation(self):
        """Test that pipeline run ID is generated."""
        pipeline = DAGPipeline(name="test_pipeline")
        result = pipeline.run()
        
        assert "run_id" in result
        assert len(result["run_id"]) == 8  # First 8 chars of UUID
        assert isinstance(result["run_id"], str)


class TestPipelineEngine:
    """Test suite for PipelineEngine class."""
    
    def test_engine_creation(self):
        """Test engine creation."""
        engine = PipelineEngine()
        
        assert engine.ai is None
        assert engine.factory is not None
        assert isinstance(engine.factory, UGCPipelineFactory)
        assert engine.factory.ai is None
        
    def test_engine_with_ai_router(self):
        """Test engine creation with AI router."""
        mock_ai = Mock()
        engine = PipelineEngine(ai_router=mock_ai)
        
        assert engine.ai is mock_ai
        assert engine.factory.ai is mock_ai
        
    def test_generate_template_scripts(self):
        """Test template script generation."""
        scripts = PipelineEngine._generate_template_scripts("Test Product")
        
        assert isinstance(scripts, dict)
        assert "scripts" in scripts
        assert "platforms" in scripts
        assert "psychology_triggers" in scripts
        
        assert len(scripts["scripts"]) == 3
        assert all("hook" in script and "script" in script and "platform" in script 
                  for script in scripts["scripts"])
        assert "tiktok" in scripts["platforms"]
        assert "instagram" in scripts["platforms"]
        
    @patch('ugc_ai_overpower.core.pipeline_engine.PipelineEngine._generate_template_scripts')
    def test_generate_scripts_no_ai(self, mock_generate_template):
        """Test script generation when AI router is not available."""
        engine = PipelineEngine(ai_router=None)
        result = engine._generate_scripts("Test Product")
        
        mock_generate_template.assert_called_once_with("Test Product")
        assert result == mock_generate_template.return_value
        
    def test_generate_scripts_with_ai_success(self):
        """Test script generation with successful AI response."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "all_scripts": [
                {"script": "AI script 1", "hook": "AI hook 1"},
                {"script": "AI script 2", "hook": "AI hook 2"}
            ]
        })
        
        engine = PipelineEngine(ai_router=mock_ai)
        result = engine._generate_scripts("Test Product")
        
        assert len(result["scripts"]) == 2
        assert result["scripts"][0]["script"] == "AI script 1"
        assert result["scripts"][0]["hook"] == "AI hook 1"
        
    def test_generate_scripts_with_ai_error(self):
        """Test script generation when AI fails."""
        mock_ai = Mock()
        mock_ai.chat_structured.side_effect = Exception("AI error")
        
        engine = PipelineEngine(ai_router=mock_ai)
        result = engine._generate_scripts("Test Product")
        
        # Should fall back to template scripts
        assert len(result["scripts"]) == 3
        
    @patch('ugc_ai_overpower.core.pipeline_engine.NotionDashboard')
    @patch('ugc_ai_overpower.core.pipeline_engine.ContentBankV2')
    def test_run_full_pipeline_no_products(self, mock_bank, mock_notion):
        """Test running full pipeline when no products exist."""
        mock_bank.return_value.get_all_products.return_value = []
        
        engine = PipelineEngine(ai_router=None)
        result = engine.run_full_pipeline()
        
        assert result["status"] == "skipped"
        assert result["reason"] == "no_products"
        assert result["products_processed"] == 0
        
    @patch('ugc_ai_overpower.core.pipeline_engine.NotionDashboard')
    @patch('ugc_ai_overpower.core.pipeline_engine.ContentBankV2')
    def test_run_full_pipeline_with_products(self, mock_bank, mock_notion):
        """Test running full pipeline with products."""
        mock_products = [
            {"name": "Product 1", "id": 1},
            {"name": "Product 2", "id": 2}
        ]
        mock_bank.return_value.get_all_products.return_value = mock_products
        
        mock_notion.return_value.sync_orchestrator_result.return_value = {
            "synced": True,
            "campaign_id": "campaign-1",
            "content_ids": ["content-1"]
        }
        
        engine = PipelineEngine(ai_router=None)
        result = engine.run_full_pipeline()
        
        assert result["status"] == "completed"
        assert result["products_processed"] == 2
        assert len(result["details"]) == 2
        
        # Check that sync was called for each product
        assert mock_notion.return_value.sync_orchestrator_result.call_count == 2
        
    @patch('ugc_ai_overpower.core.pipeline_engine.NotionDashboard')
    @patch('ugc_ai_overpower.core.pipeline_engine.ContentBankV2')
    def test_run_full_pipeline_mixed_results(self, mock_bank, mock_notion):
        """Test running full pipeline with mixed sync results."""
        mock_products = [
            {"name": "Product 1", "id": 1},
            {"name": "Product 2", "id": 2}
        ]
        mock_bank.return_value.get_all_products.return_value = mock_products
        
        mock_notion.return_value.sync_orchestrator_result.side_effect = [
            {"synced": True, "campaign_id": "campaign-1", "content_ids": ["content-1"]},
            {"synced": False, "reason": "error"}
        ]
        
        engine = PipelineEngine(ai_router=None)
        result = engine.run_full_pipeline()
        
        assert result["status"] == "completed"
        assert result["products_processed"] == 2
        assert result["details"][0]["notion_synced"] is True
        assert result["details"][1]["notion_synced"] is False


class TestUGCPipelineFactory:
    """Test suite for UGCPipelineFactory class."""
    
    def test_factory_creation(self):
        """Test factory creation."""
        factory = UGCPipelineFactory()
        
        assert factory.ai is None
        assert factory.predator is None
        
    def test_factory_with_ai_router(self):
        """Test factory creation with AI router."""
        mock_ai = Mock()
        factory = UGCPipelineFactory(ai_router=mock_ai)
        
        assert factory.ai is mock_ai
        
    def test_factory_with_predator(self):
        """Test factory creation with predator agent."""
        mock_predator = Mock()
        factory = UGCPipelineFactory(predator_agent=mock_predator)
        
        assert factory.predator is mock_predator
        
    def test_hunter_researcher_no_ai(self):
        """Test researcher function without AI."""
        factory = UGCPipelineFactory()
        result = factory._hunter_researcher({"product": "Test Product", "niche": "skincare"})
        
        assert result["research"] == {
            "target_audience": "general",
            "pain_points": [],
            "benefits": [],
            "objections": [],
            "keywords": []
        }
        
    def test_hunter_researcher_with_ai(self):
        """Test researcher function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "target_audience": "young adults",
            "pain_points": ["acne", "dryness"],
            "benefits": ["hydration", "glow"],
            "objections": ["price", "effectiveness"],
            "keywords": ["skincare", "moisturizer"]
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        result = factory._hunter_researcher({"product": "Test Product", "niche": "skincare"})
        
        mock_ai.chat_structured.assert_called_once()
        assert result["research"] == mock_ai.chat_structured.return_value
        
    def test_hunter_trend_no_predator(self):
        """Test trend function without predator."""
        factory = UGCPipelineFactory()
        result = factory._hunter_trend({"niche": "skincare"})
        
        assert result["trends"] == [{"hook": "I tried this for 30 days...", "format": "storytime"}]
        
    def test_hunter_trend_with_predator(self):
        """Test trend function with predator."""
        mock_predator = Mock()
        mock_predator.get_trends = Mock(return_value=[
            {"hook": " viral trend", "format": "trending"},
            {"hook": " viral challenge", "format": "challenge"}
        ])
        
        factory = UGCPipelineFactory(predator_agent=mock_predator)
        result = factory._hunter_trend({"niche": "skincare"})
        
        mock_predator.get_trends.assert_called_once_with("skincare", limit=5)
        assert len(result["trends"]) == 2
        
    def test_hunter_competitor_no_ai(self):
        """Test competitor function without AI."""
        factory = UGCPipelineFactory()
        result = factory._hunter_competitor({"product": "Test Product"})
        
        assert result["competitor"] == {
            "competitor_hooks": [],
            "gaps": [],
            "winning_formats": []
        }
        
    def test_hunter_competitor_with_ai(self):
        """Test competitor function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "competitor_hooks": ["review", "tutorial"],
            "gaps": ["comparison", "before_after"],
            "winning_formats": ["storytime", "transformation"]
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        result = factory._hunter_competitor({"product": "Test Product"})
        
        mock_ai.chat_structured.assert_called_once()
        assert result["competitor"] == mock_ai.chat_structured.return_value
        
    def test_hunter_psychology_no_ai(self):
        """Test psychology function without AI."""
        factory = UGCPipelineFactory()
        result = factory._hunter_psychology({"product": "Test Product"})
        
        assert result["psychology"] == {"frameworks": []}
        
    def test_hunter_psychology_with_ai(self):
        """Test psychology function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "frameworks": [
                {"name": "loss_aversion", "hook": "Don't miss out", "angle": "limited time"}
            ]
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        result = factory._hunter_psychology({
            "product": "Test Product",
            "psychology_frameworks": ["loss_aversion", "social_proof"]
        })
        
        mock_ai.chat_structured.assert_called_once()
        assert len(result["psychology"]["frameworks"]) == 1
        
    def test_hunter_affiliate_no_ai(self):
        """Test affiliate function without AI."""
        factory = UGCPipelineFactory()
        result = factory._hunter_affiliate({"product": "Test Product"})
        
        assert result["affiliate"] == {
            "commission_hooks": [],
            "cta_variants": []
        }
        
    def test_hunter_affiliate_with_ai(self):
        """Test affiliate function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "commission_hooks": ["earn money", "save money"],
            "cta_variants": ["buy now", "learn more"],
            "affiliate_networks": ["shopee", "tokopedia"]
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        result = factory._hunter_affiliate({"product": "Test Product"})
        
        mock_ai.chat_structured.assert_called_once()
        assert result["affiliate"] == mock_ai.chat_structured.return_value
        
    def test_hunter_visual_no_ai(self):
        """Test visual function without AI."""
        factory = UGCPipelineFactory()
        result = factory._hunter_visual({"product": "Test Product", "niche": "skincare"})
        
        assert result["visual"] == {
            "visual_style": "bright",
            "b_roll_ideas": [],
            "thumbnail_style": "product closeup"
        }
        
    def test_hunter_visual_with_ai(self):
        """Test visual function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "visual_style": "clean",
            "b_roll_ideas": ["product shots", "routine demo"],
            "thumbnail_style": "minimal"
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        result = factory._hunter_visual({
            "product": "Test Product",
            "niche": "skincare"
        })
        
        mock_ai.chat_structured.assert_called_once()
        assert result["visual"] == mock_ai.chat_structured.return_value
        
    def test_critic_no_ai(self):
        """Test critic function without AI."""
        factory = UGCPipelineFactory()
        ctx = {
            "research": {"target_audience": "young adults"},
            "trends": [{"hook": "trend"}]
        }
        result = factory._critic(ctx)
        
        assert result["critique"] == {
            "recommended_hooks": [],
            "recommended_angles": [],
            "recommended_format": "storytime",
            "rejected_ideas": [],
            "reasoning": ""
        }
        
    def test_critic_with_ai(self):
        """Test critic function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "recommended_hooks": ["best hook"],
            "recommended_angles": ["best angle"],
            "recommended_format": "comparison",
            "rejected_ideas": ["bad idea"],
            "reasoning": "test reasoning"
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        ctx = {
            "research": {"target_audience": "young adults"},
            "trends": [{"hook": "trend"}],
            "competitor": {"hooks": []},
            "psychology": {"frameworks": []},
            "affiliate": {"hooks": []},
            "visual": {"style": "bright"}
        }
        result = factory._critic(ctx)
        
        mock_ai.chat_structured.assert_called_once()
        assert result["critique"] == mock_ai.chat_structured.return_value
        
    def test_narrator_no_ai(self):
        """Test narrator function without AI."""
        factory = UGCPipelineFactory()
        ctx = {
            "product": "Test Product",
            "critique": {
                "recommended_hooks": ["test hook"],
                "recommended_format": "storytime"
            }
        }
        result = factory._narrator(ctx, 0)
        
        assert result["script"] == {
            "hook": "test hook",
            "script": "",
            "caption": "",
            "hashtags": [],
            "cta": ""
        }
        
    def test_narrator_with_ai(self):
        """Test narrator function with AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "hook": "AI hook",
            "script": "AI script",
            "caption": "AI caption",
            "hashtags": ["ai", "test"],
            "cta": "AI CTA"
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        ctx = {
            "product": "Test Product",
            "critique": {
                "recommended_hooks": ["test hook"],
                "recommended_format": "storytime"
            }
        }
        result = factory._narrator(ctx, 0)
        
        mock_ai.chat_structured.assert_called_once()
        assert result["script"] == mock_ai.chat_structured.return_value
        
    def test_narrator_variants(self):
        """Test narrator variant functions."""
        factory = UGCPipelineFactory()
        
        ctx = {
            "product": "Test Product",
            "critique": {
                "recommended_hooks": ["hook1", "hook2", "hook3"],
                "recommended_format": "storytime"
            }
        }
        
        # Test each variant
        result_a = factory._narrator_a(ctx)
        result_b = factory._narrator_b(ctx)
        result_c = factory._narrator_c(ctx)
        
        # Each should use a different hook
        assert result_a["script"]["hook"] == "hook1"
        assert result_b["script"]["hook"] == "hook2"
        assert result_c["script"]["hook"] == "hook3"
        
    def test_narrator_variant_wraparound(self):
        """Test narrator variant wraparound with limited hooks."""
        factory = UGCPipelineFactory()
        
        ctx = {
            "product": "Test Product",
            "critique": {
                "recommended_hooks": ["only_one_hook"],
                "recommended_format": "storytime"
            }
        }
        
        # All variants should use the same hook (only one available)
        result_a = factory._narrator_a(ctx)
        result_b = factory._narrator_b(ctx)
        result_c = factory._narrator_c(ctx)
        
        assert result_a["script"]["hook"] == "only_one_hook"
        assert result_b["script"]["hook"] == "only_one_hook"
        assert result_c["script"]["hook"] == "only_one_hook"
        
    def test_narrator_no_hooks(self):
        """Test narrator with no hooks available."""
        factory = UGCPipelineFactory()
        
        ctx = {
            "product": "Test Product",
            "critique": {
                "recommended_hooks": [],
                "recommended_format": "storytime"
            }
        }
        
        result = factory._narrator(ctx, 0)
        assert result["script"]["hook"] == "I tried this..."
        
    def test_judge_no_scripts(self):
        """Test judge function with no scripts."""
        factory = UGCPipelineFactory()
        result = factory._judge({})
        
        assert result["winner"] is None
        assert result["all_scripts"] == []
        
    def test_judge_with_scripts_no_ai(self):
        """Test judge function with scripts but no AI."""
        factory = UGCPipelineFactory()
        
        ctx = {
            "narrator_a": {"script": "script A"},
            "narrator_b": {"script": "script B"},
            "narrator_c": {"script": "script C"}
        }
        
        result = factory._judge(ctx)
        
        assert result["winner"] is not None
        assert result["winner_variant"] in ["narrator_a", "narrator_b", "narrator_c"]
        assert result["all_scripts"] == ["script A", "script B", "script C"]
        
    def test_judge_with_scripts_and_ai(self):
        """Test judge function with scripts and AI."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "winner": "narrator_b",
            "reasoning": "best script",
            "suggested_improvements": ["improvement 1"]
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        
        ctx = {
            "narrator_a": {"script": "script A"},
            "narrator_b": {"script": "script B"},
            "narrator_c": {"script": "script C"}
        }
        
        result = factory._judge(ctx)
        
        mock_ai.chat_structured.assert_called_once()
        assert result["winner_variant"] == "narrator_b"
        assert result["winner_script"] == {"script": "script B"}
        assert result["all_scripts"] == ["script A", "script B", "script C"]
        
    def test_judge_winner_not_found(self):
        """Test judge function when winner is not found in scripts."""
        mock_ai = Mock()
        mock_ai.chat_structured = Mock(return_value={
            "winner": "narrator_x",  # Non-existent
            "reasoning": "best script"
        })
        
        factory = UGCPipelineFactory(ai_router=mock_ai)
        
        ctx = {
            "narrator_a": {"script": "script A"},
            "narrator_b": {"script": "script B"}
        }
        
        result = factory._judge(ctx)
        
        # Should fall back to first script
        assert result["winner_variant"] == "narrator_a"
        assert result["winner_script"] == {"script": "script A"}
        
    def test_create_full_pipeline(self):
        """Test creating full pipeline."""
        mock_ai = Mock()
        factory = UGCPipelineFactory(ai_router=mock_ai)
        
        pipeline = factory.create_full_pipeline("Test Product", "skincare")
        
        assert isinstance(pipeline, DAGPipeline)
        assert pipeline.name == "ugc-Test Product"
        assert pipeline.ai is mock_ai
        assert len(pipeline._nodes) == 11  # All expected nodes
        
        # Check that all expected nodes exist
        node_names = list(pipeline._nodes.keys())
        expected_nodes = [
            "hunter_researcher", "hunter_trend", "hunter_competitor",
            "hunter_psychology", "hunter_affiliate", "hunter_visual",
            "critic", "narrator_a", "narrator_b", "narrator_c", "judge"
        ]
        
        for node in expected_nodes:
            assert node in node_names
            
        # Check dependencies
        assert pipeline._nodes["critic"].deps == [
            "hunter_researcher", "hunter_trend", "hunter_competitor",
            "hunter_psychology", "hunter_affiliate", "hunter_visual"
        ]
        
        assert pipeline._nodes["narrator_a"].deps == ["critic"]
        assert pipeline._nodes["judge"].deps == ["narrator_a", "narrator_b", "narrator_c"]
        
    def test_run_campaign(self):
        """Test running campaign through factory."""
        mock_ai = Mock()
        factory = UGCPipelineFactory(ai_router=mock_ai)
        
        result = factory.run_campaign("Test Product", "skincare")
        
        assert isinstance(result, dict)
        assert "run_id" in result
        assert "name" in result
        assert "status" in result
        
    def test_run_campaign_no_ai(self):
        """Test running campaign without AI."""
        factory = UGCPipelineFactory()
        
        result = factory.run_campaign("Test Product", "skincare")
        
        assert isinstance(result, dict)
        assert "run_id" in result
        # Should complete successfully even without AI