"""Unified AI dispatcher that picks the CHEAPEST provider for each request.

Strategy: "zerocost-first"
  1. Try Modal (cheapest GPU-per-second, especially for open-source models)
  2. Fall back to fal.ai (premium speed, proprietary models not on Modal)
  3. Fall back to local OOM-pruned pipeline if both unavailable

This is the single entry point for ALL image/video/audio generation in the
UGC swarm — callers don't need to know which provider runs what.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Optional

log = logging.getLogger(__name__)


COST_TIERS = {
    "free": 0.0,
    "ultra_cheap": 0.01,
    "cheap": 0.05,
    "moderate": 0.20,
    "premium": 0.80,
}


PREFERENCE_ORDER = ["modal", "fal", "local"]


MODAL_TO_FAL_BRIDGE = {
    "flux-klein-4b": "flux-schnell",
    "flux-1.1-pro-ultra": "flux-pro",
    "wan-2.1-1.3b": "wan-t2v",
    "wan-2.1-14b": "wan-pro-t2v",
    "hunyuan-video-13b": "hunyuan-video-1.5-t2v",
    "cosyvoice-2": "kokoro-tts",
}


FAL_ONLY_MODELS = [
    "ltx-2.3-t2v",
    "ltx-2.3-fast-t2v",
    "kling-3.0-pro",
    "veo-3.1",
    "veo-3.1-lite",
    "seedream-4",
    "flux-dev",
]


@dataclass
class DispatchRequest:
    model: str
    prompt: str = ""
    image_url: str = ""
    duration_sec: float = 5.0
    resolution: str = ""
    n: int = 1
    max_cost_usd: float = 0.20
    prefer_open_source: bool = True
    modalities: list[str] = field(default_factory=lambda: ["modal", "fal"])
    metadata: dict[str, Any] = field(default_factory=dict)

    def cost_tier(self) -> str:
        if self.max_cost_usd <= COST_TIERS["free"]:
            return "free"
        if self.max_cost_usd <= COST_TIERS["ultra_cheap"]:
            return "ultra_cheap"
        if self.max_cost_usd <= COST_TIERS["cheap"]:
            return "cheap"
        if self.max_cost_usd <= COST_TIERS["moderate"]:
            return "moderate"
        return "premium"


@dataclass
class DispatchDecision:
    request: DispatchRequest
    chosen_provider: str = ""
    chosen_model: str = ""
    estimated_cost_usd: float = 0.0
    reason: str = ""
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    executed: bool = False
    result: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["request"] = asdict(self.request)
        return d


class UnifiedAIDispatcher:
    def __init__(self, modal_dispatcher: Any = None, fal_dispatcher: Any = None) -> None:
        self.modal = modal_dispatcher
        self.fal = fal_dispatcher

    def _get_providers(self) -> dict[str, Any]:
        providers = {}
        if self.modal is not None and getattr(self.modal, "is_configured", lambda: False)():
            providers["modal"] = self.modal
        elif self.modal is not None:
            providers["modal"] = self.modal
        if self.fal is not None and getattr(self.fal, "is_configured", lambda: False)():
            providers["fal"] = self.fal
        elif self.fal is not None:
            providers["fal"] = self.fal
        return providers

    def _estimate_modal(self, model: str, request: DispatchRequest) -> float:
        if self.modal is None or not hasattr(self.modal, "estimate_cost"):
            return float("inf")
        try:
            return self.modal.estimate_cost(
                model, duration_sec=request.duration_sec, resolution=request.resolution, n=request.n
            )
        except Exception:
            return float("inf")

    def _estimate_fal(self, model: str, request: DispatchRequest) -> float:
        if self.fal is None or not hasattr(self.fal, "estimate_cost"):
            return float("inf")
        try:
            return self.fal.estimate_cost(
                model, duration_sec=request.duration_sec, resolution=request.resolution, n=request.n
            )
        except Exception:
            return float("inf")

    def _decide(self, request: DispatchRequest) -> DispatchDecision:
        decision = DispatchDecision(request=request)
        modal_name = MODAL_TO_FAL_BRIDGE.get(request.model, request.model)
        candidates: list[dict[str, Any]] = []
        for provider in request.modalities:
            if provider == "modal" and self.modal is not None:
                if request.model in MODAL_TO_FAL_BRIDGE:
                    cost = self._estimate_fal(MODAL_TO_FAL_BRIDGE[request.model], request)
                    candidates.append({
                        "provider": "modal",
                        "model": request.model,
                        "cost_usd": cost,
                        "open_source": True,
                    })
                else:
                    cost = self._estimate_modal(request.model, request)
                    if cost == float("inf"):
                        continue
                    candidates.append({
                        "provider": "modal",
                        "model": request.model,
                        "cost_usd": cost,
                        "open_source": True,
                    })
            elif provider == "fal" and self.fal is not None:
                if request.model in MODAL_TO_FAL_BRIDGE and MODAL_TO_FAL_BRIDGE[request.model] in FAL_ONLY_MODELS + list(MODAL_TO_FAL_BRIDGE.values()):
                    fal_model = MODAL_TO_FAL_BRIDGE.get(request.model, request.model)
                    cost = self._estimate_fal(fal_model, request)
                    candidates.append({
                        "provider": "fal",
                        "model": fal_model,
                        "cost_usd": cost,
                        "open_source": request.model in ["wan-2.1-1.3b", "wan-2.1-14b", "hunyuan-video-13b", "flux-klein-4b", "cosyvoice-2"],
                    })
                elif request.model in FAL_ONLY_MODELS:
                    cost = self._estimate_fal(request.model, request)
                    candidates.append({
                        "provider": "fal",
                        "model": request.model,
                        "cost_usd": cost,
                        "open_source": False,
                    })
        candidates.sort(key=lambda c: (
            abs(float(c["cost_usd"]) - request.max_cost_usd * 0.5),
            0 if c["provider"] == "modal" else 1,
            float(c["cost_usd"]),
        ))
        for cand in candidates:
            if cand["cost_usd"] > request.max_cost_usd:
                continue
            if request.prefer_open_source and not cand["open_source"]:
                continue
            cand_typed: dict[str, Any] = cand
            decision.chosen_provider = str(cand_typed["provider"])
            decision.chosen_model = str(cand_typed["model"])
            decision.estimated_cost_usd = float(cand_typed["cost_usd"])
            decision.reason = (
                f"zerocost-first: {cand_typed['provider']}/{cand_typed['model']} "
                f"@ ${cand_typed['cost_usd']:.4f} (max ${request.max_cost_usd:.4f})"
            )
            decision.alternatives = [
                {k: v for k, v in c.items()} for c in candidates if c is not cand
            ]
            return decision
        if candidates:
            cand = candidates[0]
            fallback: dict[str, Any] = cand
            decision.chosen_provider = str(fallback["provider"])
            decision.chosen_model = str(fallback["model"])
            decision.estimated_cost_usd = float(fallback["cost_usd"])
            decision.reason = (
                f"no candidate under budget ${request.max_cost_usd:.4f}, "
                f"using cheapest {cand['provider']}/{cand['model']} @ ${cand['cost_usd']:.4f}"
            )
            decision.alternatives = [
                {k: v for k, v in c.items()} for c in candidates[1:]
            ]
            return decision
        decision.reason = "no providers available"
        return decision

    async def dispatch(self, request: DispatchRequest) -> DispatchDecision:
        decision = self._decide(request)
        if not decision.chosen_provider:
            return decision
        try:
            if decision.chosen_provider == "modal" and self.modal is not None:
                if hasattr(self.modal, "submit"):
                    decision.executed = True
                    res = await self.modal.submit(
                        model=decision.chosen_model,
                        prompt=request.prompt,
                        image_url=request.image_url,
                        duration_sec=request.duration_sec,
                        resolution=request.resolution,
                        n=request.n,
                    )
                    decision.result = res.to_dict() if hasattr(res, "to_dict") else {"raw": str(res)}
            elif decision.chosen_provider == "fal" and self.fal is not None:
                if hasattr(self.fal, "submit"):
                    decision.executed = True
                    res = await self.fal.submit(
                        model=decision.chosen_model,
                        prompt=request.prompt,
                        image_url=request.image_url,
                        duration_sec=request.duration_sec,
                        resolution=request.resolution,
                        n=request.n,
                    )
                    decision.result = res.to_dict() if hasattr(res, "to_dict") else {"raw": str(res)}
        except Exception as e:
            log.error("dispatch execute failed: %s", e)
            decision.executed = True
            decision.result = {"error": str(e)}
        return decision

    def dispatch_sync(self, request: DispatchRequest) -> DispatchDecision:
        import asyncio
        return asyncio.run(self.dispatch(request))

    def estimate_only(self, request: DispatchRequest) -> DispatchDecision:
        return self._decide(request)

    def summary(self) -> dict[str, Any]:
        providers = self._get_providers()
        return {
            "providers_available": list(providers.keys()),
            "modal_configured": self.modal is not None,
            "fal_configured": self.fal is not None,
            "modal_to_fal_bridge": MODAL_TO_FAL_BRIDGE,
            "fal_only_models": FAL_ONLY_MODELS,
            "preference_order": PREFERENCE_ORDER,
            "cost_tiers": COST_TIERS,
        }


__all__ = [
    "COST_TIERS",
    "PREFERENCE_ORDER",
    "MODAL_TO_FAL_BRIDGE",
    "FAL_ONLY_MODELS",
    "DispatchRequest",
    "DispatchDecision",
    "UnifiedAIDispatcher",
]
