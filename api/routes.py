import uuid
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

# In-memory custom title store (survives hot-reload, resets on container restart)
_session_titles: dict[str, str] = {}


class QuestionRequest(BaseModel):
    question: str
    session_id: str | None = None


class ClarificationResponse(BaseModel):
    needs_clarification: bool
    clarification_question: str


class TitleUpdate(BaseModel):
    title: str


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
        sid = request.session_id or str(uuid.uuid4())
        session = await session_service.get_session(
            app_name="data_analyst",
            user_id="user",
            session_id=sid,
        )
        if session is None:
            session = await session_service.create_session(
                app_name="data_analyst",
                user_id="user",
                session_id=sid,
            )
        if not _session_titles.get(sid):
            _session_titles[sid] = request.question[:60]
        message = Content(role="user", parts=[Part(text=request.question)])
        events = []
        async for event in runner.run_async(
            user_id="user",
            session_id=session.id,
            new_message=message,
        ):
            events.append(event)
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


@router.get("/sessions")
async def list_sessions():
    try:
        resp = await session_service.list_sessions(app_name="data_analyst", user_id="user")
        result = []
        for s in resp.sessions:
            title = _session_titles.get(s.id)
            if not title:
                for ev in s.events:
                    if ev.author == "user" and ev.content and ev.content.parts:
                        text = next((p.text for p in ev.content.parts if getattr(p, "text", None)), None)
                        if text:
                            title = text[:60]
                            break
            result.append({"session_id": s.id, "title": title or "New conversation"})
        result.sort(key=lambda x: x["session_id"], reverse=True)
        return {"sessions": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        await session_service.delete_session(app_name="data_analyst", user_id="user", session_id=session_id)
        _session_titles.pop(session_id, None)
        return {"deleted": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}/title")
async def update_title(session_id: str, body: TitleUpdate):
    _session_titles[session_id] = body.title[:80]
    return {"session_id": session_id, "title": body.title}


@router.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str):
    try:
        session = await session_service.get_session(app_name="data_analyst", user_id="user", session_id=session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        msgs = []
        for ev in session.events:
            if not ev.content or not ev.content.parts:
                continue
            text = " ".join(p.text for p in ev.content.parts if getattr(p, "text", None)).strip()
            if not text:
                continue
            # Skip function call / tool result noise — only keep human-readable text
            if any(hasattr(p, "function_call") and p.function_call for p in ev.content.parts):
                continue
            if any(hasattr(p, "function_response") and p.function_response for p in ev.content.parts):
                continue
            role = "user" if ev.author == "user" else "assistant"
            msgs.append({"role": role, "content": text})
        return {"session_id": session_id, "messages": msgs}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
