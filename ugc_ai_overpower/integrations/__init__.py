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

from ugc_ai_overpower.integrations.affiliate import (
    AffiliateLink as AffiliateTrackingLink,
    ClickEvent,
    ConversionEvent,
    AffiliateTracker,
)
from ugc_ai_overpower.integrations.affiliate_analytics import (
    RevenueReport,
    AffiliateAnalytics,
)
from ugc_ai_overpower.integrations.caption_link_injector import (
    CaptionLinkInjector,
)
from ugc_ai_overpower.integrations.ab_test_optimizer import (
    ABTestInput,
    ABTestOptimizer,
    ABTestResult,
)
from ugc_ai_overpower.integrations.ab_testing import (
    ABTest,
    ABTestResult as ABTestingResult,
    ABTesting,
    Variant,
)
from ugc_ai_overpower.integrations.ai_dispatch import (
    COST_TIERS,
    DispatchDecision,
    DispatchRequest,
    FAL_ONLY_MODELS,
    MODAL_TO_FAL_BRIDGE,
    UnifiedAIDispatcher,
)
from ugc_ai_overpower.integrations.analytics_pipeline import (
    AnalyticsPipeline,
    PostMetrics,
    ROIDashboard,
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
from ugc_ai_overpower.integrations.caption_optimizer import (
    CaptionInput,
    CaptionOptimizer,
    CaptionResult,
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
from ugc_ai_overpower.integrations.content_calendar import (
    CalendarEntry,
    CalendarInput,
    CalendarResult,
    ContentCalendar,
)
from ugc_ai_overpower.integrations.cta_generator import (
    CTAInput,
    CTAResult,
    CTAGenerator,
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
from ugc_ai_overpower.integrations.image_enhancer import (
    ALLOWED_FIT_MODES,
    ALLOWED_FORMATS,
    ALLOWED_OPERATIONS,
    ALLOWED_POSITIONS,
    COST_PER_IMAGE_USD,
    EnhanceResult,
    ImageEnhancer,
)
from ugc_ai_overpower.integrations.niche_presets import (
    NichePreset,
    NichePresets,
)
from ugc_ai_overpower.integrations.modal_dispatch import (
    MODELS,
    ModalBudgetExceeded,
    ModalDispatch,
    VOICE_PRESETS,
)
from ugc_ai_overpower.integrations.podcast_creator import (
    AUDIO_EDIT_GPU_PER_SEC,
    AudioResult,
    LOUDNESS_DEFAULT_LUFS,
    LOUDNESS_MAX_LUFS,
    LOUDNESS_MIN_LUFS,
    NEGATIVE_WORDS,
    POSITIVE_WORDS,
    PodcastCreator,
    SHOWNOTES_MAX_WORDS,
    TRANSCRIBE_GPU_PER_SEC,
    TranscriptResult,
    TranscriptSegment,
    ViralMoment,
)
from ugc_ai_overpower.integrations.video_editor import (
    ALLOWED_CAPTION_FONTS,
    ALLOWED_TRANSITIONS,
    ASPECT_SQUARE,
    ASPECT_VERTICAL,
    FFMPEG_GPU_PER_SEC,
    MAX_DURATION_SEC,
    MIN_DURATION_SEC,
    VideoEditResult,
    VideoEditor,
    WATERMARK_POSITIONS,
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
from ugc_ai_overpower.integrations.seo_optimizer import (
    Keyword,
    SEOScore,
    SEOOptimizer,
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
from ugc_ai_overpower.integrations.translation_pipeline import (
    LANG_NAMES,
    SUPPORTED_LANGS,
    TranslationPipeline,
    TranslationResult,
)
from ugc_ai_overpower.integrations.umami_dispatch import (
    TrackingEvent,
    UmamiDispatcher,
)
from ugc_ai_overpower.core.notifications import (
    NotificationEvent,
    NotificationChannel,
    NotificationDispatcher,
    SlackChannel,
    DiscordChannel,
    EmailChannel,
    WebhookChannel,
    ConsoleChannel,
)
from ugc_ai_overpower.core.notification_events import (
    campaign_launched,
    content_viral,
    rate_limit_hit,
    circuit_breaker_open,
    autoheal_restart,
    webhook_received,
    notion_sync_success,
    notion_sync_failed,
    quota_warning,
    quota_exceeded,
    cost_alert,
    deploy_success,
)

__all__ = [
    "ABTest",
    "AffiliateAnalytics",
    "AffiliateTracker",
    "AffiliateTrackingLink",
    "CaptionLinkInjector",
    "ClickEvent",
    "ConversionEvent",
    "RevenueReport",
    "ABTestInput",
    "ABTestOptimizer",
    "ABTestResult",
    "ABTesting",
    "ABTestingResult",
    "ALLOWED_CAPTION_FONTS",
    "ALLOWED_FIT_MODES",
    "ALLOWED_FORMATS",
    "ALLOWED_OPERATIONS",
    "ALLOWED_POSITIONS",
    "ALLOWED_TRANSITIONS",
    "AUDIO_EDIT_GPU_PER_SEC",
    "ASPECT_SQUARE",
    "ASPECT_VERTICAL",
    "AccountInfo",
    "AnalyticsPipeline",
    "AudioResult",
    "AffiliateCache",
    "AffiliateLink",
    "COST_PER_IMAGE_USD",
    "COST_TIERS",
    "CTAInput",
    "CTAResult",
    "CTAGenerator",
    "CalendarEntry",
    "CalendarInput",
    "CalendarResult",
    "CaptionInput",
    "CaptionOptimizer",
    "CaptionResult",
    "Character",
    "CharacterAgent",
    "CharacterStore",
    "ContentCalendar",
    "ContentLanguage",
    "ContentTone",
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
    "EnhanceResult",
    "FAL_MODELS",
    "FAL_ONLY_MODELS",
    "FalBudgetExceeded",
    "FalDispatcher",
    "FalResult",
    "FFMPEG_GPU_PER_SEC",
    "ImageEnhancer",
    "Keyword",
    "LANG_NAMES",
    "LOUDNESS_DEFAULT_LUFS",
    "LOUDNESS_MAX_LUFS",
    "LOUDNESS_MIN_LUFS",
    "MAX_DURATION_SEC",
    "MIN_DURATION_SEC",
    "MODAL_TO_FAL_BRIDGE",
    "MODELS",
    "ModalBudgetExceeded",
    "ModalDispatch",
    "NEGATIVE_WORDS",
    "NICHE_PRESETS",
    "NichePreset",
    "NichePresets",
    "Node",
    "NodeType",
    "PERSONA_TEMPLATES",
    "PLATFORMS_INSTAGRAPI",
    "PLATFORMS_NATIVE",
    "PLATFORMS_TIKHUB",
    "POSITIVE_WORDS",
    "PersonaIdentity",
    "NicheAdaptation",
    "PersonalityTraits",
    "PlatformAdapter",
    "PlatformCategory",
    "PodcastCreator",
    "PostMetrics",
    "PostResult",
    "ROIDashboard",
    "Region",
    "RelationshipGraph",
    "SEOScore",
    "SEOOptimizer",
    "SHOWNOTES_MAX_WORDS",
    "SUPPORTED_LANGS",
    "Session",
    "SessionBackend",
    "SessionManager",
    "SessionStatus",
    "SessionStore",
    "SocialDispatch",
    "TRANSCRIBE_GPU_PER_SEC",
    "TikHubConfig",
    "TrackingEvent",
    "TranscriptResult",
    "TranscriptSegment",
    "TranslationPipeline",
    "TranslationResult",
    "UmamiDispatcher",
    "UnifiedAIDispatcher",
    "VOICE_PRESETS",
    "Variant",
    "VideoEditResult",
    "VideoEditor",
    "ViralMoment",
    "WATERMARK_POSITIONS",
    "detect_platform",
    "dispatch_account",
    "dispatch_affiliate_link",
    "dispatch_engagement",
    "dispatch_post",
    "get_adapter",
    "get_registry_stats",
    "list_platforms",
    "register_adapter",
    "NotificationEvent",
    "NotificationChannel",
    "NotificationDispatcher",
    "SlackChannel",
    "DiscordChannel",
    "EmailChannel",
    "WebhookChannel",
    "ConsoleChannel",
    "campaign_launched",
    "content_viral",
    "rate_limit_hit",
    "circuit_breaker_open",
    "autoheal_restart",
    "webhook_received",
    "notion_sync_success",
    "notion_sync_failed",
    "quota_warning",
    "quota_exceeded",
    "cost_alert",
    "deploy_success",
]

__version__ = "1.4.0"
