from typing import List, Optional
from pydantic import BaseModel


class DraftAnswer(BaseModel):
    summary: str
    findings: List[str]
    evidence: List[str]
    confidence: float  # 0.0 - 1.0


class FinalAnswer(BaseModel):
    summary: str
    findings: List[str]
    evidence: List[str]
    confidence: float
    validated: bool = True
    critic_notes: Optional[str] = None
