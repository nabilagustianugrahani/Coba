"""Swarm Launcher — starts all agents in threads.

Usage:
    python -m swarm.main
    python main.py swarm
"""
import logging, sys, os, signal, time, json
from threading import Event

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)16s] %(message)s",
)
log = logging.getLogger("swarm")

_shutdown = Event()


def _signal_handler(sig, frame):
    log.info("Shutting down swarm...")
    _shutdown.set()


def start_swarm(ai_router=None, with_engagement=True, with_analytics=True,
                with_predator=True):
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    from swarm.orchestrator import OrchestratorAgent
    from swarm.agents.script_writer_agent import ScriptWriterAgent
    from swarm.agents.affiliator_agent import AffiliatorAgent
    from swarm.agents.video_producer_agent import VideoProducerAgent
    from swarm.agents.poster_agent import PosterAgent
    from swarm.agents.predator_agent import PredatorAgent

    agents = [
        OrchestratorAgent(ai_router=ai_router),
        ScriptWriterAgent(ai_router=ai_router),
        AffiliatorAgent(),
        VideoProducerAgent(),
        PosterAgent(),
    ]

    if with_engagement:
        from swarm.agents.engagement_agent import EngagementAgent
        agents.append(EngagementAgent())

    if with_analytics:
        from swarm.agents.analytics_agent import AnalyticsAgent
        agents.append(AnalyticsAgent())

    if with_predator:
        agents.append(PredatorAgent(ai_router=ai_router))

    for a in agents:
        a.start()

    log.info("=" * 50)
    log.info("  SWARM LAUNCHED — %d agents", len(agents))
    for a in agents:
        log.info("  • %s", a.name)
    log.info("=" * 50)

    while not _shutdown.is_set():
        try:
            time.sleep(1)
        except KeyboardInterrupt:
            break

    for a in agents:
        a.stop()
    log.info("Swarm stopped.")


def run_campaign(ai_router, product: str, niche: str = "general",
                  count: int = 50, platforms: list = None):
    """Start a campaign via the swarm orchestrator."""
    platforms = platforms or ["tiktok"]
    from swarm.message_bus import MessageBus
    bus = MessageBus()
    msg_id = bus.send("cli", "orchestrator", "campaign", {
        "product": product,
        "niche": niche,
        "count": count,
        "platforms": platforms,
        "generate_video": True,
        "use_affiliate": True,
    })
    log.info("Campaign dispatched (msg_id=%d). Run 'python main.py swarm' to start agents.", msg_id)
    return msg_id


if __name__ == "__main__":
    start_swarm()
