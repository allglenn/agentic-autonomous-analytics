from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.adk.runners import Runner
from google.genai.types import Content, Part
from orchestrator.pipeline import pipeline
from orchestrator.planner_runner import run_planner
from models.answer import FinalAnswer
from models.plan import IntentType
from config.session import session_service

router = APIRouter()

runner = Runner(agent=pipeline, app_name="data_analyst", session_service=session_service)


class QuestionRequest(BaseModel):
    question: str
    session_id: str = "default"


class ClarificationResponse(BaseModel):
    needs_clarification: bool
    clarification_question: str


@router.post("/ask")
async def ask(request: QuestionRequest):
    """
    Submit a business question to the analysis pipeline.

    Returns either a FinalAnswer or a ClarificationResponse if the
    intent cannot be determined from the question.
    """
    try:
        # Step 1: run the planner only to check intent
        plan = await run_planner(request.question)

        if plan.intent == IntentType.CLARIFICATION_NEEDED:
            return ClarificationResponse(
                needs_clarification=True,
                clarification_question=plan.clarification_question,
            )

        # Step 2: intent is clear — run the full pipeline
        session = await session_service.create_session(
            app_name="data_analyst",
            user_id="user",
            session_id=request.session_id,
        )
        message = Content(role="user", parts=[Part(text=request.question)])
        events = list(runner.run(
            user_id="user",
            session_id=session.id,
            new_message=message,
        ))
        final = next(
            (e.content for e in reversed(events) if e.content),
            None,
        )
        if final is None:
            raise HTTPException(status_code=500, detail="No answer produced.")
        return final
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/metrics")
async def get_metrics():
    """Return available metrics."""
    from tools.list_metrics import list_metrics
    return {"metrics": list_metrics()}


@router.get("/dimensions")
async def get_dimensions():
    """Return available dimensions."""
    from tools.list_dimensions import list_dimensions
    return {"dimensions": list_dimensions()}
