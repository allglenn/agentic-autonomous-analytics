import asyncio
import logging
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.adk.runners import Runner
from google.adk.events import Event, EventActions
from google.genai.types import Content, Part
from orchestrator.pipeline import analysis_loop
from orchestrator.planner_runner import run_planner
from models.plan import IntentType
from config.session import session_service
from config.settings import settings
from db.conversations import (
    create_conversation, get_conversations,
    update_title, delete_conversation as db_delete_conversation,
    add_message, get_messages,
)

router = APIRouter()
logger = logging.getLogger(__name__)

runner = Runner(agent=analysis_loop, app_name="data_analyst", session_service=session_service)


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
    req_id = str(uuid.uuid4())[:8]
    ask_started = time.monotonic()
    logger.info(
        "[ask:%s] start session_id=%s question_len=%d",
        req_id,
        request.session_id,
        len(request.question or ""),
    )
    try:
        async with asyncio.timeout(settings.ask_timeout_seconds):
            # Step 1: run planner once to classify intent and build the plan.
            planner_started = time.monotonic()
            plan = await run_planner(request.question)
            logger.info(
                "[ask:%s] planner_done intent=%s elapsed=%.2fs",
                req_id,
                plan.intent,
                time.monotonic() - planner_started,
            )

            if plan.intent == IntentType.CLARIFICATION_NEEDED:
                logger.info("[ask:%s] clarification_returned", req_id)
                return ClarificationResponse(
                    needs_clarification=True,
                    clarification_question=plan.clarification_question,
                )

            # Step 2: intent is clear — run execution loop with injected analysis_plan.
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
                    state={"analysis_plan": plan.model_dump(), "critic_notes": ""},
                )
                logger.info("[ask:%s] session_created sid=%s", req_id, sid)
            else:
                await session_service.append_event(
                    session=session,
                    event=Event(
                        author="system",
                        actions=EventActions(
                            stateDelta={
                                "analysis_plan": plan.model_dump(),
                                "critic_notes": "",
                            }
                        ),
                    ),
                )
                logger.info("[ask:%s] session_reused sid=%s state_updated", req_id, sid)

            # Register conversation and save user message
            try:
                existing = await get_conversations()
                if not any(c.id == sid for c in existing):
                    await create_conversation(sid, request.question[:60])
                await add_message(sid, "user", request.question)
            except Exception:
                pass

            message = Content(role="user", parts=[Part(text=request.question)])
            events = []
            event_count = 0
            loop_started = time.monotonic()
            logger.info("[ask:%s] analysis_loop_start sid=%s", req_id, session.id)
            async for event in runner.run_async(
                user_id="user",
                session_id=session.id,
                new_message=message,
            ):
                events.append(event)
                event_count += 1
                if event_count <= 5 or event_count % 10 == 0:
                    logger.info(
                        "[ask:%s] analysis_event #%d author=%s has_content=%s",
                        req_id,
                        event_count,
                        getattr(event, "author", "unknown"),
                        bool(getattr(event, "content", None)),
                    )
            logger.info(
                "[ask:%s] analysis_loop_done events=%d elapsed=%.2fs",
                req_id,
                event_count,
                time.monotonic() - loop_started,
            )

            final = next(
                (e.content for e in reversed(events) if e.content),
                None,
            )
            if final is None:
                raise HTTPException(status_code=500, detail="No answer produced.")

            # Save the final assistant answer to our messages table
            try:
                answer_text = " ".join(
                    p.text for p in final.parts if getattr(p, "text", None)
                ).strip()
                if answer_text:
                    await add_message(sid, "assistant", answer_text)
            except Exception:
                pass

            logger.info(
                "[ask:%s] success total_elapsed=%.2fs",
                req_id,
                time.monotonic() - ask_started,
            )
            return final
    except TimeoutError:
        logger.warning(
            "[ask:%s] timeout total_elapsed=%.2fs limit=%ss",
            req_id,
            time.monotonic() - ask_started,
            settings.ask_timeout_seconds,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                f"Request timed out after {settings.ask_timeout_seconds}s. "
                "Try a narrower question or retry."
            ),
        )
    except Exception as e:
        logger.exception(
            "[ask:%s] failed total_elapsed=%.2fs error=%s",
            req_id,
            time.monotonic() - ask_started,
            e,
        )
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
        convs = await get_conversations()
        return {"sessions": [{"session_id": c.id, "title": c.title} for c in convs]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    try:
        # Delete from our conversations table
        await db_delete_conversation(session_id)
        # Also delete the ADK session (best effort)
        try:
            await session_service.delete_session(
                app_name="data_analyst", user_id="user", session_id=session_id
            )
        except Exception:
            pass
        return {"deleted": session_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/sessions/{session_id}/title")
async def update_session_title(session_id: str, body: TitleUpdate):
    try:
        await update_title(session_id, body.title)
        return {"session_id": session_id, "title": body.title}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    try:
        msgs = await get_messages(session_id)
        return {
            "session_id": session_id,
            "messages": [{"role": m.role, "content": m.content} for m in msgs],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
