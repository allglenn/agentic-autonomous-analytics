from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class IntentType(str, Enum):
    SINGLE_VALUE = "single_value"
    COMPARISON = "comparison"
    INSIGHT = "insight"
    CLARIFICATION_NEEDED = "clarification_needed"


class AnalysisPlan(BaseModel):
    intent: IntentType
    metrics: List[str] = []
    dimensions: List[str] = []
    time_range: str = ""
    comparison_range: Optional[str] = None
    drilldown_path: Optional[List[str]] = None
    success_criteria: str = ""
    # Populated only when intent == CLARIFICATION_NEEDED
    clarification_question: Optional[str] = None
