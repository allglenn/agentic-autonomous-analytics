from typing import List
from config.guardrails import guardrails


def list_dimensions() -> List[str]:
    """Return the list of available dimensions (PII fields excluded)."""
    return guardrails.allowed_dimensions
