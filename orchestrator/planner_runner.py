import json
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
    events = []
    async for event in _runner.run_async(
        user_id="user",
        session_id=session.id,
        new_message=message,
    ):
        events.append(event)

    raw = next(
        (e.content.parts[0].text for e in reversed(events) if e.content),
        None,
    )
    if raw is None:
        raise ValueError("Planner produced no output.")
    return AnalysisPlan.model_validate(json.loads(raw))
