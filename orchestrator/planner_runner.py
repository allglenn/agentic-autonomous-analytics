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


async def run_planner(question: str) -> AnalysisPlan:
    """Run only the planner agent and return the structured AnalysisPlan."""
    session = await session_service.create_session(
        app_name="planner",
        user_id="user",
        session_id=str(uuid.uuid4()),
    )
    message = Content(role="user", parts=[Part(text=question)])
    async for _ in _runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=message,
    ):
        pass

    # ADK writes output_schema result to session.state[output_key]
    session = await session_service.get_session(
        app_name="planner",
        user_id="user",
        session_id=session.id,
    )
    plan_dict = session.state.get("analysis_plan")
    if plan_dict is None:
        raise ValueError("Planner produced no output.")
    return AnalysisPlan.model_validate(plan_dict)
