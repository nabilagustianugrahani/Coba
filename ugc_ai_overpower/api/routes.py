"""
FastAPI routes for the UGC AI Overpower API.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

# Import our modules
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from ugc_ai_overpower.scheduler.cron import ContentScheduler
from ugc_ai_overpower.analytics.engagement import EngagementTracker

app = FastAPI(title="UGC AI Overpower API", version="1.0.0")

# Initialize scheduler and tracker (in a real app, you'd use dependency injection)
scheduler = ContentScheduler(db_path="data/scheduler.db")
tracker = EngagementTracker(db_path="data/engagement.db")

# Pydantic models
class CampaignCreate(BaseModel):
    product: str
    budget: Optional[float] = None
    platforms: Optional[List[str]] = None

class CampaignResponse(BaseModel):
    id: str
    product: str
    created_at: datetime
    status: str

class PostSchedule(BaseModel):
    content_id: int
    platform: str
    scheduled_time: datetime

class PostResponse(BaseModel):
    schedule_id: int
    content_id: int
    platform: str
    scheduled_time: datetime
    status: str

class MetricsUpdate(BaseModel):
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    clicks: int = 0

class ConversionTrack(BaseModel):
    post_id: int
    product_id: str
    revenue: float

class VideoGenerateRequest(BaseModel):
    script: str
    duration: Optional[int] = 30  # seconds
    style: Optional[str] = "professional"

# Routes
@app.post("/api/campaigns/create", response_model=CampaignResponse)
async def create_campaign(campaign: CampaignCreate):
    """Create a new campaign."""
    campaign_id = str(uuid.uuid4())
    return CampaignResponse(
        id=campaign_id,
        product=campaign.product,
        created_at=datetime.utcnow(),
        status="created"
    )

@app.get("/api/campaigns/{id}", response_model=CampaignResponse)
async def get_campaign(id: str):
    """Get campaign details."""
    # In a real app, we'd fetch from a database
    return CampaignResponse(
        id=id,
        product="Sample Product",
        created_at=datetime.utcnow(),
        status="active"
    )

@app.post("/api/posts/schedule", response_model=PostResponse)
async def schedule_post(post: PostSchedule):
    """Schedule a post for publishing."""
    schedule_id = scheduler.schedule_post(
        content_id=post.content_id,
        platform=post.platform,
        scheduled_time=post.scheduled_time
    )
    return PostResponse(
        schedule_id=schedule_id,
        content_id=post.content_id,
        platform=post.platform,
        scheduled_time=post.scheduled_time,
        status="pending"
    )

@app.get("/api/posts/pending", response_model=List[PostResponse])
async def get_pending_posts():
    """Get all pending posts."""
    pending = scheduler.get_pending_posts()
    # Convert to our response model
    return [
        PostResponse(
            schedule_id=p["id"],
            content_id=p["content_id"],
            platform=p["platform"],
            scheduled_time=datetime.fromisoformat(p["scheduled_time"]),
            status=p["status"]
        )
        for p in pending
    ]

@app.post("/api/posts/{id}/metrics")
async def update_post_metrics(id: int, metrics: MetricsUpdate):
    """Update metrics for a post."""
    tracker.track_post_metrics(
        post_id=id,
        views=metrics.views,
        likes=metrics.likes,
        comments=metrics.comments,
        shares=metrics.shares,
        clicks=metrics.clicks
    )
    return {"message": "Metrics updated successfully"}

@app.get("/api/analytics/engagement")
async def get_engagement_stats(platform: Optional[str] = None, limit: int = 10):
    """Get engagement statistics."""
    if platform:
        # For now, we return dummy stats for a platform
        return tracker.get_platform_stats(platform)
    else:
        # Get top performing posts
        top_posts = tracker.get_top_performing_posts(limit=limit)
        return {"top_posts": top_posts}

@app.get("/api/analytics/roi")
async def get_roi_stats(campaign_id: str):
    """Get ROI statistics for a campaign."""
    return tracker.get_roi_stats(campaign_id)

@app.post("/api/generate/video")
async def generate_video(request: VideoGenerateRequest):
    """Generate a video from a script."""
    try:
        from ugc_ai_overpower.gpu.video_composer import VideoComposer
        vc = VideoComposer()
        path = vc.create_ugc_video(request.script, "api_user", None)
        return {"video_id": os.path.basename(path), "path": path, "status": "completed"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

