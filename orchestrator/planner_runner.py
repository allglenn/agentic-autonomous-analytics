import logging
import time
import uuid
from google.adk.runners import Runner
from google.genai.types import Content, Part
from agents.planner import planner_agent
from models.plan import AnalysisPlan
from config.session import session_service

_runner = Runner(
    agent=planner_agent,
    app_name="planner",
    session_service=session_service,
)
logger = logging.getLogger(__name__)


async def run_planner(question: str) -> AnalysisPlan:
    """Run only the planner agent and return the structured AnalysisPlan."""
    started = time.monotonic()
    planner_run_id = str(uuid.uuid4())[:8]
    logger.info(
        "[planner:%s] start question_len=%d",
        planner_run_id,
        len(question or ""),
    )
    session = await session_service.create_session(
        app_name="planner",
        user_id="user",
        session_id=str(uuid.uuid4()),
    )
    logger.info("[planner:%s] session_created sid=%s", planner_run_id, session.id)
    message = Content(role="user", parts=[Part(text=question)])
    event_count = 0
    async for _ in _runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=message,
    ):
        event_count += 1
    logger.info("[planner:%s] run_done events=%d", planner_run_id, event_count)

    # ADK writes output_schema result to session.state[output_key]
    session = await session_service.get_session(
        app_name="planner",
        user_id="user",
        session_id=session.id,
    )
    plan_dict = session.state.get("analysis_plan")
    if plan_dict is None:
        logger.error("[planner:%s] missing_analysis_plan", planner_run_id)
        raise ValueError("Planner produced no output.")
    plan = AnalysisPlan.model_validate(plan_dict)
    logger.info(
        "[planner:%s] success intent=%s elapsed=%.2fs",
        planner_run_id,
        plan.intent,
        time.monotonic() - started,
    )
    return plan
