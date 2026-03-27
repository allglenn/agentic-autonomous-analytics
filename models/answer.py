from typing import List, Optional
from pydantic import BaseModel, field_validator


class DraftAnswer(BaseModel):
    summary: str
    findings: List[str]
    evidence: List[str]
    confidence: float  # 0.0 - 1.0


class FinalAnswer(BaseModel):
    summary: str
    findings: List[str]
    evidence: List[str]
    confidence: float  # must be 0.0 – 1.0
    validated: bool = True
    critic_notes: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
