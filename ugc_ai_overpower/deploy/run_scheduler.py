"""Scheduler daemon entry point."""
import sys, os
# App lives at: .../ugc/ugc_ai_overpower/
# sys.path needs: .../ugc/
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(app_dir))
os.chdir(app_dir)
from scheduler.engine import SkynetScheduler

s = SkynetScheduler()
s.schedule_campaign_daily("Tahu Kriuk", hour=8, minute=0)
s.schedule_campaign_daily("Skincare Routine", hour=12, minute=0)
s.schedule_campaign_daily("Fashion Muslim", hour=18, minute=0)
s.start()
