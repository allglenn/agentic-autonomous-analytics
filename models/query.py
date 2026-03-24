from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class QueryRequest(BaseModel):
    metric: str
    dimensions: List[str]
    time_range: str
    filters: Optional[Dict[str, Any]] = None


class QueryResult(BaseModel):
    metric: str
    dimensions: List[str]
    time_range: str
    rows: List[Dict[str, Any]]
    row_count: int
