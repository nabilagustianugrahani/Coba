"""DAG Pipeline Engine — parallel reasoner architecture.

Inspired by reels-af (18 parallel reasoners) and claude-auto-tok (6-agent DAG).

Architecture:
                    ┌── Researcher ──┐
                    ├── Trend Miner ─┤
  Product ──→ Hunter ├── Competitor ─┤──→ Critic ──→ Narrators ──→ Judge ──→ Output
                    ├── Psychology ─┤          (parallel x3)
                    ├── Affiliate ──┤
                    └── Visual ─────┘

Each node runs in its own thread. The DAG resolves dependencies automatically.
"""

import json
import logging
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ugc_ai_overpower.core.notion_sync import NotionDashboard
from ugc_ai_overpower.core.content_bank_v2 import ContentBankV2

log = logging.getLogger(__name__)


class NodeStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class PipelineNode:
    name: str
    fn: Callable
    deps: List[str] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    priority: int = 0

    @property
    def duration(self) -> float:
        if self.started_at and self.finished_at:
            return round(self.finished_at - self.started_at, 6)
        return 0.0


class DAGPipeline:
    """Directed Acyclic Graph pipeline with parallel execution."""

    def __init__(self, name: str = "pipeline", max_workers: int = 6, ai_router=None):
        self.name = name
        self.max_workers = max_workers
        self.ai = ai_router
        self._nodes: Dict[str, PipelineNode] = {}
        self._lock = threading.Lock()
        self._context: Dict[str, Any] = {}
        self._run_id = str(uuid.uuid4())[:8]

    def add_node(self, name: str, fn: Callable, deps: List[str] = None,
                 priority: int = 0) -> "DAGPipeline":
        self._nodes[name] = PipelineNode(
            name=name, fn=fn, deps=deps or [], priority=priority,
        )
        return self

    def resolve_deps(self, node_name: str) -> bool:
        """Check if all dependencies of a node are completed."""
        node = self._nodes.get(node_name)
        if not node:
            return False
        for dep in node.deps:
            dep_node = self._nodes.get(dep)
            if not dep_node or dep_node.status != NodeStatus.COMPLETED:
                return False
        return True

    def get_ready_nodes(self) -> List[str]:
        ready = []
        for name, node in self._nodes.items():
            if node.status == NodeStatus.PENDING and self.resolve_deps(name):
                ready.append(name)
        ready.sort(key=lambda n: self._nodes[n].priority, reverse=True)
        return ready

    def run(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        self._context = context or {}
        self._context["pipeline_run_id"] = self._run_id
        if self.ai:
            self._context["ai"] = self.ai.chat_structured(
                f"Pipeline '{self.name}' auxiliary inference for downstream nodes."
            )
        total_start = time.time()
        log.info("[DAG] Pipeline '%s' started (workers=%d, nodes=%d)",
                 self.name, self.max_workers, len(self._nodes))

        completed = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}

            while len(futures) > 0 or completed + failed < len(self._nodes):
                ready = self.get_ready_nodes()
                for name in ready:
                    node = self._nodes[name]
                    node.status = NodeStatus.RUNNING
                    node.started_at = time.time()
                    future = executor.submit(self._run_node, name)
                    futures[future] = name

                done_futures = []
                for future in as_completed(futures):
                    name = futures[future]
                    try:
                        result = future.result()
                        if result is not None:
                            self._context[name] = result
                        self._nodes[name].status = NodeStatus.COMPLETED
                        completed += 1
                    except Exception as e:
                        self._nodes[name].status = NodeStatus.FAILED
                        self._nodes[name].error = str(e)
                        failed += 1
                        log.error("[DAG] Node '%s' failed: %s", name, e)
                    finally:
                        self._nodes[name].finished_at = time.time()
                    done_futures.append(future)

                for f in done_futures:
                    del futures[f]

                if len(self.get_ready_nodes()) == 0 and len(futures) == 0:
                    break
                time.sleep(0.05)

        total_time = time.time() - total_start
        log.info("[DAG] Pipeline done: %d completed, %d failed in %.2fs",
                 completed, failed, total_time)

        return {
            "run_id": self._run_id,
            "name": self.name,
            "status": "completed" if failed == 0 else "completed_with_errors",
            "completed": completed,
            "failed": failed,
            "total": len(self._nodes),
            "duration_seconds": round(total_time, 2),
            "results": {n: self._context.get(n) for n in self._nodes
                       if self._nodes[n].status == NodeStatus.COMPLETED},
            "context": self._context,
        }

    def _run_node(self, name: str) -> Any:
        node = self._nodes[name]
        log.info("[DAG]   Running '%s' (deps=%s)", name, node.deps)
        try:
            result = node.fn(self._context)
            log.info("[DAG]   '%s' done", name)
            return result
        except Exception as e:
            log.error("[DAG]   '%s' error: %s", name, e)
            raise


class PipelineEngine:
    """High-level engine: products → content generation → Notion sync."""

    def __init__(self, ai_router=None):
        self.ai = ai_router
        self.factory = UGCPipelineFactory(ai_router=ai_router)

    def run_full_pipeline(self) -> dict:
        notion = NotionDashboard()
        bank = ContentBankV2()

        products = bank.get_all_products(limit=100)
        if not products:
            log.warning("No products found in content bank")
            return {"status": "skipped", "reason": "no_products", "products_processed": 0}

        results = []
        for product in products:
            product_name = product.get("name", "unknown")
            log.info("Processing product: %s", product_name)

            scripts_result = self._generate_scripts(product_name)
            sync_result = notion.sync_orchestrator_result(scripts_result, product_name)

            results.append({
                "product": product_name,
                "scripts_generated": len(scripts_result.get("scripts", [])),
                "notion_synced": sync_result.get("synced", False),
            })

        return {
            "status": "completed",
            "products_processed": len(results),
            "details": results,
        }

    def _generate_scripts(self, product_name: str) -> dict:
        if self.ai:
            try:
                prompt = (
                    f"Generate 2-3 UGC video scripts for product '{product_name}'. "
                    f"For each, provide a hook, full script, caption, hashtags, and CTA. "
                    f"Return JSON: {{\"all_scripts\":[{{\"hook\":\"...\",\"script\":\"...\","
                    f"\"caption\":\"...\",\"hashtags\":[...],\"cta\":\"...\"}}]}}"
                )
                response = self.ai.chat_structured(prompt)
                scripts = response.get("all_scripts", [])
                if not scripts:
                    return self._generate_template_scripts(product_name)
                return {
                    "scripts": scripts,
                    "platforms": ["tiktok", "instagram"],
                    "psychology_triggers": "curiosity, social_proof, loss_aversion",
                }
            except Exception as e:
                log.warning("AI router unavailable, generating template scripts: %s", e)
        return self._generate_template_scripts(product_name)

    @staticmethod
    def _generate_template_scripts(product_name: str) -> dict:
        templates = [
            {"hook": f"I tried {product_name} for 30 days... here's what happened",
             "script": f"I used {product_name} every day for a month. The results were shocking.",
             "platform": "tiktok"},
            {"hook": f"Stop buying {product_name} until you watch this",
             "script": f"Before you spend money on {product_name}, watch this. I found something better.",
             "platform": "tiktok"},
            {"hook": f"The {product_name} secret they don't want you to know",
             "script": f"Everyone is buying {product_name}, but nobody is talking about this one thing.",
             "platform": "instagram"},
        ]
        return {
            "scripts": templates,
            "platforms": ["tiktok", "instagram"],
            "psychology_triggers": "curiosity, loss_aversion, social_proof",
        }


class UGCPipelineFactory:
    """Factory that creates pre-configured UGC pipelines."""

    def __init__(self, ai_router=None, predator_agent=None):
        self.ai = ai_router
        self.predator = predator_agent

    def _hunter_researcher(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        niche = ctx.get("niche", "general")
        if self.ai:
            prompt = (
                f"Research product '{product}' (niche: {niche}). "
                f"Return JSON: {{\"target_audience\":\"...\",\"pain_points\":[...],\"benefits\":[...],\"objections\":[...],\"keywords\":[...]}}"
            )
            return {"research": self.ai.chat_structured(prompt)}
        return {"research": {"target_audience": "general", "pain_points": [], "benefits": [], "objections": [], "keywords": []}}

    def _hunter_trend(self, ctx: dict) -> dict:
        niche = ctx.get("niche", "general")
        if self.predator:
            trends = self.predator.get_trends(niche, limit=5)
            return {"trends": trends}
        return {"trends": [{"hook": "I tried this for 30 days...", "format": "storytime"}]}

    def _hunter_competitor(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        if self.ai:
            prompt = (
                f"Analyze top competitor content for '{product}'. "
                f"What hooks do they use? What angles are missing? "
                f"Return JSON: {{\"competitor_hooks\":[...],\"gaps\":[...],\"winning_formats\":[...]}}"
            )
            return {"competitor": self.ai.chat_structured(prompt)}
        return {"competitor": {"competitor_hooks": [], "gaps": [], "winning_formats": []}}

    def _hunter_psychology(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        frameworks = ctx.get("psychology_frameworks",
                             ["loss_aversion", "social_proof", "curiosity", "scarcity"])
        if self.ai:
            prompt = (
                f"Apply these psychology frameworks to '{product}': {frameworks}. "
                f"For each framework, suggest a hook and angle. "
                f"Return JSON: {{\"frameworks\":[{{\"name\":\"...\",\"hook\":\"...\",\"angle\":\"...\"}}]}}"
            )
            return {"psychology": self.ai.chat_structured(prompt)}
        return {"psychology": {"frameworks": []}}

    def _hunter_affiliate(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        if self.ai:
            prompt = (
                f"Suggest best affiliate angles and commission hooks for '{product}'. "
                f"Return JSON: {{\"commission_hooks\":[...],\"cta_variants\":[...],\"affiliate_networks\":[...]}}"
            )
            return {"affiliate": self.ai.chat_structured(prompt)}
        return {"affiliate": {"commission_hooks": [], "cta_variants": []}}

    def _hunter_visual(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        niche = ctx.get("niche", "general")
        if self.ai:
            prompt = (
                f"Suggest visual style for '{product}' UGC video (niche: {niche}). "
                f"Include: lighting, background, camera angle, editing style, color grade. "
                f"Return JSON: {{\"visual_style\":\"...\",\"b_roll_ideas\":[...],\"thumbnail_style\":\"...\"}}"
            )
            return {"visual": self.ai.chat_structured(prompt)}
        return {"visual": {"visual_style": "bright", "b_roll_ideas": [], "thumbnail_style": "product closeup"}}

    def _critic(self, ctx: dict) -> dict:
        product = ctx.get("product", "unknown")
        hunter_results = {}
        for key in ["research", "trends", "competitor", "psychology", "affiliate", "visual"]:
            if key in ctx:
                hunter_results[key] = ctx[key]
        if self.ai:
            prompt = (
                f"As a UGC content strategist, analyze these research findings for '{product}':\n"
                f"{json.dumps(hunter_results, indent=2)}\n\n"
                f"Decide: which hooks, angles, and formats should we use? "
                f"Reject weak ideas. Recommend the strongest combination. "
                f"Return JSON: {{\"recommended_hooks\":[...],\"recommended_angles\":[...],"
                f"\"recommended_format\":\"...\",\"rejected_ideas\":[...],\"reasoning\":\"...\"}}"
            )
            return {"critique": self.ai.chat_structured(prompt)}
        return {"critique": {"recommended_hooks": [], "recommended_angles": [], "recommended_format": "storytime", "rejected_ideas": [], "reasoning": ""}}

    def _narrator(self, ctx: dict, variant: int = 0) -> dict:
        product = ctx.get("product", "unknown")
        critique = ctx.get("critique", {})
        hooks = critique.get("recommended_hooks", ["I tried this..."])
        hook = hooks[variant % len(hooks)] if hooks else "I tried this..."
        if self.ai:
            prompt = (
                f"Write a UGC script for '{product}' using this hook: '{hook}'. "
                f"Style: {critique.get('recommended_format', 'storytime')}. "
                f"Length: 30-60 seconds. Include hook, problem, solution, social proof, CTA. "
                f"Return JSON: {{\"hook\":\"...\",\"script\":\"...\",\"caption\":\"...\","
                f"\"hashtags\":[...],\"cta\":\"...\"}}"
            )
            return {"script": self.ai.chat_structured(prompt)}
        return {"script": {"hook": hook, "script": "", "caption": "", "hashtags": [], "cta": ""}}

    def _narrator_a(self, ctx: dict) -> dict:
        return self._narrator(ctx, 0)

    def _narrator_b(self, ctx: dict) -> dict:
        return self._narrator(ctx, 1)

    def _narrator_c(self, ctx: dict) -> dict:
        return self._narrator(ctx, 2)

    def _judge(self, ctx: dict) -> dict:
        scripts = []
        for v in ["narrator_a", "narrator_b", "narrator_c"]:
            if v in ctx and ctx[v]:
                scripts.append({"variant": v, "script": ctx[v]})
        if not scripts:
            return {"winner": None, "winner_variant": None, "winner_script": None, "all_scripts": []}
        if self.ai:
            prompt = (
                f"As a UGC content judge, select the BEST script from these variants:\n"
                f"{json.dumps(scripts, indent=2)}\n\n"
                f"Pick the one most likely to go viral. Explain why. "
                f"Return JSON: {{\"winner\":\"narrator_a\",\"reasoning\":\"...\","
                f"\"suggested_improvements\":[\"...\"]}}"
            )
            verdict = self.ai.chat_structured(prompt)
        else:
            verdict = {"winner": "narrator_a", "reasoning": "first variant", "suggested_improvements": []}

        winner_name = verdict.get("winner", scripts[0]["variant"])
        winner_data = None
        for s in scripts:
            if s["variant"] == winner_name:
                winner_data = s["script"]
                break
        if winner_data is None:
            winner_name = scripts[0]["variant"]
            winner_data = scripts[0]["script"]

        all_script_texts = []
        for s in scripts:
            output = s["script"]
            if isinstance(output, dict):
                all_script_texts.append(output.get("script", ""))
            else:
                all_script_texts.append(output)

        return {
            "verdict": verdict,
            "winner": winner_name,
            "winner_variant": winner_name,
            "winner_script": winner_data,
            "all_scripts": all_script_texts,
        }

    def create_full_pipeline(self, product: str, niche: str = "general") -> DAGPipeline:
        pipeline = DAGPipeline(name=f"ugc-{product[:20]}", max_workers=6, ai_router=self.ai)

        pipeline.add_node("hunter_researcher", self._hunter_researcher, priority=2)
        pipeline.add_node("hunter_trend", self._hunter_trend, priority=2)
        pipeline.add_node("hunter_competitor", self._hunter_competitor, priority=2)
        pipeline.add_node("hunter_psychology", self._hunter_psychology, priority=2)
        pipeline.add_node("hunter_affiliate", self._hunter_affiliate, priority=2)
        pipeline.add_node("hunter_visual", self._hunter_visual, priority=2)

        critic_deps = ["hunter_researcher", "hunter_trend", "hunter_competitor",
                       "hunter_psychology", "hunter_affiliate", "hunter_visual"]
        pipeline.add_node("critic", self._critic, deps=critic_deps, priority=1)

        pipeline.add_node("narrator_a", self._narrator_a, deps=["critic"], priority=0)
        pipeline.add_node("narrator_b", self._narrator_b, deps=["critic"], priority=0)
        pipeline.add_node("narrator_c", self._narrator_c, deps=["critic"], priority=0)

        narrator_deps = ["narrator_a", "narrator_b", "narrator_c"]
        pipeline.add_node("judge", self._judge, deps=narrator_deps, priority=1)

        return pipeline

    def run_campaign(self, product: str, niche: str = "general") -> dict:
        pipeline = self.create_full_pipeline(product, niche)
        result = pipeline.run({"product": product, "niche": niche})
        return result
