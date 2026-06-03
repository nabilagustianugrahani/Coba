"""Enterprise-grade browser-use agent wrapper — AI browser automation via 9router LLM."""
import asyncio, logging, time
from typing import Optional, Callable
from dataclasses import dataclass, field

from langchain_openai import ChatOpenAI
from browser_use import Agent, Controller

from ugc_ai_overpower.core.config import skynet_config

log = logging.getLogger(__name__)


@dataclass
class BUResult:
    success: bool
    output: str = ""
    actions_taken: int = 0
    elapsed: float = 0.0
    error: Optional[str] = None


class BUAgent:
    """Base wrapper for browser-use AI agents.

    All browser-use agents extend this. Handles LLM setup,
    browser lifecycle, error recovery, and result parsing.
    """

    def __init__(self, headless: bool = None, model: str = None, max_actions: int = None):
        cfg = skynet_config
        self.headless = headless if headless is not None else cfg.get("browser", "headless", default=True)
        self.model = model or cfg.get("browser_use", "model", default="gemini-2.5-flash")
        self.max_actions = max_actions or cfg.get("browser_use", "max_actions_per_step", default=10)
        self.use_vision = cfg.get("browser_use", "use_vision", default=True)
        self._controller = Controller()

    def _build_llm(self) -> ChatOpenAI:
        """Create LangChain OpenAI client pointed at 9router."""
        cfg = skynet_config
        return ChatOpenAI(
            base_url=cfg.get("router", "base_url") + "/v1",
            api_key=cfg.get("router", "api_key"),
            model=self.model,
            temperature=0.2,
            max_tokens=4096,
        )

    async def run(self, task: str, sensitive: bool = False) -> BUResult:
        """Execute a browser automation task.

        Args:
            task: Natural language instruction for the agent.
            sensitive: If True, task output is not logged.

        Returns:
            BUResult with success status, output text, and metadata.
        """
        start = time.time()
        llm = self._build_llm()

        agent = Agent(
            task=task,
            llm=llm,
            controller=self._controller,
            use_vision=self.use_vision,
            max_actions_per_step=self.max_actions,
        )

        try:
            history = await agent.run(max_steps=50)
            elapsed = round(time.time() - start, 2)

            actions = len(history.action_names()) if history else 0
            output = history.final_result() if history else ""

            log.info("BUAgent done: %d actions in %.1fs | %s",
                     actions, elapsed, task[:80])

            return BUResult(
                success=True,
                output=output or "",
                actions_taken=actions,
                elapsed=elapsed,
            )
        except Exception as e:
            elapsed = round(time.time() - start, 2)
            log.error("BUAgent failed after %.1fs: %s", elapsed, e)
            return BUResult(
                success=False,
                error=str(e),
                elapsed=elapsed,
            )

    def run_sync(self, task: str, **kwargs) -> BUResult:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(task, **kwargs))

    def register_action(self, action: Callable, description: str):
        """Register a custom tool/action for the agent."""
        self._controller.action(description)(action)


class BUFactory:
    """Factory for creating specialized browser-use agents."""

    @staticmethod
    def login_agent(headless: bool = True) -> "BULoginAgent":
        from ugc_ai_overpower.browser.bu_login import BULoginAgent
        return BULoginAgent(headless=headless)

    @staticmethod
    def engage_agent(headless: bool = True) -> "BUEngageAgent":
        from ugc_ai_overpower.browser.bu_engage import BUEngageAgent
        return BUEngageAgent(headless=headless)

    @staticmethod
    def scraper_agent(headless: bool = True) -> "BUScraperAgent":
        from ugc_ai_overpower.browser.bu_scraper import BUScraperAgent
        return BUScraperAgent(headless=headless)

    @staticmethod
    def registrar_agent(headless: bool = True) -> "BUFarmRegistrar":
        from ugc_ai_overpower.browser.farm_registrar import BUFarmRegistrar
        return BUFarmRegistrar(headless=headless)
