import json
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai.types import Content, Part
from agents.planner import planner_agent
from models.plan import AnalysisPlan

_session_service = InMemorySessionService()
_runner = Runner(
    agent=planner_agent,
    app_name="planner",
    session_service=_session_service,
)


async def run_planner(question: str) -> AnalysisPlan:
    """Run only the planner agent and return the structured AnalysisPlan."""
    session = _session_service.create_session(
        app_name="planner",
        user_id="user",
        session_id=question[:40],  # use truncated question as a unique key
    )
    message = Content(role="user", parts=[Part(text=question)])
    events = list(_runner.run(
        user_id="user",
        session_id=session.id,
        new_message=message,
    ))
    raw = next(
        (e.content.parts[0].text for e in reversed(events) if e.content),
        None,
    )
    if raw is None:
        raise ValueError("Planner produced no output.")
    return AnalysisPlan.model_validate(json.loads(raw))
