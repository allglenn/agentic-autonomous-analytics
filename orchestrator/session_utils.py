"""Utilities for extracting data from ADK sessions."""
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def extract_tool_results_from_events(events: List[Any]) -> List[Dict[str, Any]]:
    """
    Extract tool call results from ADK events.

    Args:
        events: List of events from the ADK runner

    Returns:
        List of tool results (query results, comparison results, etc.)
    """
    tool_results = []

    for event in events:
        try:
            # Check if event has content
            if not hasattr(event, 'content') or not event.content:
                continue

            # Look through parts for function responses
            for part in event.content.parts:
                # ADK stores tool results in function_response
                if hasattr(part, 'function_response') and part.function_response:
                    response = part.function_response
                    # The response might have a 'response' field with the actual data
                    if hasattr(response, 'response'):
                        tool_results.append(response.response)
                    else:
                        tool_results.append(response)

                # Also check for executable_code results (if used)
                if hasattr(part, 'executable_code_result'):
                    tool_results.append(part.executable_code_result)

        except Exception as e:
            logger.debug(f"Error extracting from event: {e}")
            continue

    logger.info(f"Extracted {len(tool_results)} tool results from {len(events)} events")
    return tool_results


async def get_session_state_value(session_service, app_name: str, user_id: str,
                                   session_id: str, key: str) -> Any:
    """
    Get a specific value from session state.

    Args:
        session_service: The ADK session service
        app_name: Application name
        user_id: User ID
        session_id: Session ID
        key: State key to retrieve

    Returns:
        The value from session state, or None if not found
    """
    try:
        session = await session_service.get_session(
            app_name=app_name,
            user_id=user_id,
            session_id=session_id,
        )
        return session.state.get(key)
    except Exception as e:
        logger.warning(f"Failed to get session state key '{key}': {e}")
        return None
