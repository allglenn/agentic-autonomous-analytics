import asyncio
import json
import logging
import time
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.adk.runners import Runner
from google.genai.types import Content, Part
from orchestrator.pipeline import analysis_loop
from orchestrator.planner_runner import run_planner
from orchestrator.chart_runner import generate_chart
from orchestrator.session_utils import extract_tool_results_from_events
from models.plan import AnalysisPlan, IntentType
from models.answer import FinalAnswer
from tools.run_query import run_query
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


async def _fast_single_value(plan: AnalysisPlan) -> tuple[dict, list]:
    """
    Fast path for single_value intents: call run_query directly, skip the
    Executor+Critic loop entirely. Saves 3-4 LLM round-trips.

    Returns (answer_dict_without_chart, query_results) so the caller can
    parallelise chart generation with DB persistence.
    """
    result = await run_query(
        metric=plan.metrics[0],
        dimensions=plan.dimensions,
        time_range=plan.time_range,
    )
    rows = result.get("rows", [])
    metric = plan.metrics[0]
    time_range = plan.time_range.replace("_", " ")

    if not rows:
        summary = f"No data found for {metric} over {time_range}."
        findings = [summary]
    elif not plan.dimensions:
        # Single aggregated number
        value = rows[0].get(metric)
        if isinstance(value, float) and value < 1:
            formatted = f"{value:.1%}"
        elif isinstance(value, float):
            formatted = f"{value:,.2f}"
        else:
            formatted = f"{value:,}" if value is not None else "N/A"
        summary = f"{metric.replace('_', ' ').title()} for {time_range}: {formatted}."
        findings = [summary]
    else:
        # Grouped result — summarise top rows
        dim = plan.dimensions[0]
        top = rows[:5]
        findings = [
            f"{r.get(dim, '?')}: {r.get(metric)}"
            for r in top
        ]
        summary = f"{metric.replace('_', ' ').title()} by {dim} for {time_range} ({len(rows)} segments)."

    answer = FinalAnswer(
        summary=summary,
        findings=findings,
        evidence=[f"Source: {metric} / {plan.time_range}"],
        confidence=0.95,
        validated=True,
    )
    return answer.model_dump(), [result]


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
            sid = request.session_id or str(uuid.uuid4())

            # Fetch prior turns BEFORE saving current message (used for planner context)
            try:
                prior_messages = await get_messages(sid)
            except Exception:
                prior_messages = []

            # Step 1: run planner with conversation context so follow-ups resolve correctly.
            planner_started = time.monotonic()
            plan = await run_planner(request.question, history=prior_messages[-6:])
            logger.info(
                "[ask:%s] planner_done intent=%s elapsed=%.2fs",
                req_id,
                plan.intent,
                time.monotonic() - planner_started,
            )

            if plan.intent == IntentType.CLARIFICATION_NEEDED:
                logger.info("[ask:%s] clarification_returned", req_id)
                # Save clarification exchange so next turn has context
                try:
                    existing = await get_conversations()
                    if not any(c.id == sid for c in existing):
                        await create_conversation(sid, request.question[:60])
                    await add_message(sid, "user", request.question)
                    await add_message(sid, "assistant", plan.clarification_question)
                except Exception:
                    pass
                return ClarificationResponse(
                    needs_clarification=True,
                    clarification_question=plan.clarification_question,
                )

            # Step 2a: fast path for simple single-value lookups — skip the full
            # Executor+Critic loop and answer directly from run_query.
            if plan.intent == IntentType.SINGLE_VALUE and len(plan.metrics) == 1:
                fast_started = time.monotonic()
                answer_dict, query_results = await _fast_single_value(plan)
                logger.info(
                    "[ask:%s] fast_path_done elapsed=%.2fs",
                    req_id,
                    time.monotonic() - fast_started,
                )

                # Chart generation and conversation/user-message DB setup are
                # independent — run them in parallel.
                async def _fast_db_setup():
                    try:
                        existing = await get_conversations()
                        if not any(c.id == sid for c in existing):
                            await create_conversation(sid, request.question[:60])
                        await add_message(sid, "user", request.question)
                    except Exception:
                        pass

                chart_config, _ = await asyncio.gather(
                    generate_chart(
                        user_question=request.question,
                        final_answer=answer_dict,
                        analysis_plan=plan.model_dump(),
                        query_results=query_results,
                    ),
                    _fast_db_setup(),
                )
                answer_dict["chart"] = chart_config

                try:
                    await add_message(sid, "assistant", json.dumps(answer_dict))
                except Exception:
                    pass

                logger.info(
                    "[ask:%s] success total_elapsed=%.2fs",
                    req_id,
                    time.monotonic() - ask_started,
                )
                return {"answer": answer_dict}

            # Step 2b: comparison/insight intents — run the full Executor+Critic loop.
            # Create a fresh ADK session per request so old tool results never bleed
            # into the new execution context.
            adk_sid = str(uuid.uuid4())
            session = await session_service.create_session(
                app_name="data_analyst",
                user_id="user",
                session_id=adk_sid,
                state={"analysis_plan": plan.model_dump(), "critic_notes": ""},
            )
            logger.info("[ask:%s] adk_session_created sid=%s", req_id, adk_sid)

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

            # Extract tool results from events for chart generation
            tool_results = extract_tool_results_from_events(events)

            # Extract text from final event
            raw_text = " ".join(
                p.text for p in final.parts if getattr(p, "text", None)
            ).strip()

            # Try to parse as FinalAnswer for structured response
            try:
                fa = FinalAnswer.model_validate_json(raw_text)
                answer_dict = fa.model_dump()

                # Generate chart for the final answer
                chart_config = None
                try:
                    chart_config = await generate_chart(
                        user_question=request.question,
                        final_answer=answer_dict,
                        analysis_plan=plan.model_dump(),
                        query_results=tool_results,
                    )
                    if chart_config:
                        logger.info("[ask:%s] chart_generated", req_id)
                except Exception as e:
                    logger.warning(f"[ask:%s] chart_generation_failed: {e}", req_id)

                # Add chart to answer dict dynamically
                # (chart not in Pydantic model to avoid Dict[str, Any] API error)
                answer_dict["chart"] = chart_config

                # Save full JSON so history can render the structured card
                try:
                    await add_message(sid, "assistant", json.dumps(answer_dict))
                except Exception:
                    pass
                logger.info(
                    "[ask:%s] success total_elapsed=%.2fs",
                    req_id,
                    time.monotonic() - ask_started,
                )
                return {"answer": answer_dict}
            except Exception:
                pass  # Not a FinalAnswer — return raw text

            try:
                if raw_text:
                    await add_message(sid, "assistant", raw_text)
            except Exception:
                pass

            logger.info(
                "[ask:%s] success total_elapsed=%.2fs",
                req_id,
                time.monotonic() - ask_started,
            )
            return {"answer": raw_text}
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
