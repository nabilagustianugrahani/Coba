"""Scheduler daemon entry point — UGC mass production."""
import sys, os
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(app_dir))
os.chdir(app_dir)
from scheduler.engine import SkynetScheduler

s = SkynetScheduler()

s.schedule_mass_production_daily(
    "Tahu Kriuk", niche="food", count=50, hour=8, minute=0,
    platforms=["tiktok", "instagram"], generate_video=True,
)
s.schedule_mass_production_daily(
    "Skincare Routine", niche="skincare", count=50, hour=12, minute=0,
    platforms=["tiktok", "instagram"], generate_video=True, theme="fresh",
)
s.schedule_mass_production_daily(
    "Fashion Muslim", niche="fashion", count=50, hour=18, minute=0,
    platforms=["tiktok", "instagram", "youtube"], generate_video=True, theme="luxury",
)

s.start()
