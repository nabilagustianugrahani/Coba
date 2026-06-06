"""Integrations package — adapters for social media + e-commerce.

Architecture:

  VPS side (lightweight, this package is imported there):
    - base.py: PlatformAdapter abstract class + dataclasses
    - registry.py: auto-discovery (@register_adapter)
    - dispatcher.py: routes heavy work to codespace
    - runner.py: code that runs in codespace
    - session_manager.py: credential/session storage
    - character_agent.py: niche-based persona system
    - modal_dispatch.py: Modal.com GPU dispatcher (cheap, custom)
    - fal_dispatch.py: fal.ai GPU dispatcher (premium, 985+ pre-deployed)
    - ai_dispatch.py: unified AI dispatcher, picks zerocost-first
    - relationship_graph.py: creator/content/affiliate knowledge graph
    - umami_dispatch.py: web analytics for UGC post tracking

  Core (in core/, used by both VPS and codespace):
    - social_scheduler.py: postiz-inspired post scheduling
    - trend_detector.py: OpenFuego-style trend detection

  Modal.com (serverless GPU, deployed via modal deploy):
    - modal_apps/text_to_image.py: FLUX.2-klein + FLUX.1.1 Pro Ultra
    - modal_apps/text_to_video.py: Wan 2.1 + HunyuanVideo
    - modal_apps/voice_synth.py: CosyVoice 2.0

  16+ social platforms via TikHub unified API.
  4 e-commerce platforms: Shopee, TikTok Shop, Lazada, Tokopedia.
  8 niche presets for character personas (beauty/tech/fashion/etc).
  Trend detection per niche (beauty/tech/fashion/food).
  Knowledge graph for creator→content→campaign→affiliate relationships.

Heavy work NEVER runs on VPS. Modal apps run serverless on pay-per-second GPU.
"""
from __future__ import annotations

from ugc_ai_overpower.integrations.ai_dispatch import (
    COST_TIERS,
    DispatchDecision,
    DispatchRequest,
    FAL_ONLY_MODELS,
    MODAL_TO_FAL_BRIDGE,
    UnifiedAIDispatcher,
)
from ugc_ai_overpower.integrations.base import (
    AccountInfo,
    AffiliateLink,
    EngagementMetrics,
    PlatformAdapter,
    PlatformCategory,
    PostResult,
    Region,
)
from ugc_ai_overpower.integrations.character_agent import (
    Character,
    CharacterAgent,
    CharacterStore,
    ContentLanguage,
    ContentTone,
    NicheAdaptation,
    NICHE_PRESETS,
    PERSONA_TEMPLATES,
    PersonaIdentity,
    PersonalityTraits,
)
from ugc_ai_overpower.integrations.dispatcher import (
    DEFAULT_CODESPACE,
    DEFAULT_TIMEOUT,
    DispatchError,
    dispatch_account,
    dispatch_affiliate_link,
    dispatch_engagement,
    dispatch_post,
)
from ugc_ai_overpower.integrations.ecom_dispatch import (
    AffiliateCache,
    EcomConfig,
    EcomDispatch,
)
from ugc_ai_overpower.integrations.fal_dispatch import (
    FAL_MODELS,
    FalBudgetExceeded,
    FalDispatcher,
    FalResult,
)
from ugc_ai_overpower.integrations.modal_dispatch import (
    MODELS,
    ModalBudgetExceeded,
    ModalDispatch,
    VOICE_PRESETS,
)
from ugc_ai_overpower.integrations.registry import (
    get_adapter,
    get_registry_stats,
    list_platforms,
    register_adapter,
)
from ugc_ai_overpower.integrations.relationship_graph import (
    Edge,
    EdgeType,
    Node,
    NodeType,
    RelationshipGraph,
)
from ugc_ai_overpower.integrations.session_manager import (
    Session,
    SessionBackend,
    SessionManager,
    SessionStatus,
    SessionStore,
)
from ugc_ai_overpower.integrations.social_dispatch import (
    PLATFORMS_INSTAGRAPI,
    PLATFORMS_NATIVE,
    PLATFORMS_TIKHUB,
    SocialDispatch,
    TikHubConfig,
    detect_platform,
)
from ugc_ai_overpower.integrations.umami_dispatch import (
    TrackingEvent,
    UmamiDispatcher,
)

__all__ = [
    "AccountInfo",
    "AffiliateCache",
    "AffiliateLink",
    "Character",
    "CharacterAgent",
    "CharacterStore",
    "ContentLanguage",
    "ContentTone",
    "COST_TIERS",
    "DEFAULT_CODESPACE",
    "DEFAULT_TIMEOUT",
    "DispatchDecision",
    "DispatchError",
    "DispatchRequest",
    "EcomConfig",
    "EcomDispatch",
    "Edge",
    "EdgeType",
    "EngagementMetrics",
    "FAL_MODELS",
    "FAL_ONLY_MODELS",
    "FalBudgetExceeded",
    "FalDispatcher",
    "FalResult",
    "MODAL_TO_FAL_BRIDGE",
    "MODELS",
    "ModalBudgetExceeded",
    "ModalDispatch",
    "NICHE_PRESETS",
    "Node",
    "NodeType",
    "PERSONA_TEMPLATES",
    "PLATFORMS_INSTAGRAPI",
    "PLATFORMS_NATIVE",
    "PLATFORMS_TIKHUB",
    "PersonaIdentity",
    "NicheAdaptation",
    "PersonalityTraits",
    "PlatformAdapter",
    "PlatformCategory",
    "PostResult",
    "Region",
    "RelationshipGraph",
    "Session",
    "SessionBackend",
    "SessionManager",
    "SessionStatus",
    "SessionStore",
    "SocialDispatch",
    "TikHubConfig",
    "TrackingEvent",
    "UmamiDispatcher",
    "UnifiedAIDispatcher",
    "VOICE_PRESETS",
    "detect_platform",
    "dispatch_account",
    "dispatch_affiliate_link",
    "dispatch_engagement",
    "dispatch_post",
    "get_adapter",
    "get_registry_stats",
    "list_platforms",
    "register_adapter",
]

__version__ = "1.2.0"
