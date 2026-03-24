from typing import List
from config.guardrails import guardrails


def list_metrics() -> List[str]:
    """Return the list of available business metrics."""
    return guardrails.allowed_metrics
