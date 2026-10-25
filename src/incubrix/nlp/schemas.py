from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class OccurrenceChoice(BaseModel):
    occurrence_id: str
    index: int
    label: str
    source_range: List[float] = Field(description="[start_time, end_time]")
    context: Optional[str] = None

class ClarificationPayload(BaseModel):
    clarification_id: str
    intent_type: str
    prompt: str
    options: List[OccurrenceChoice]
    pending_operation: Dict[str, Any]

class InstructionResult(BaseModel):
    status: str  # APPLIED, NEEDS_CLARIFICATION, REJECTED
    message: str
    operation_id: Optional[str] = None
    operation_type: Optional[str] = None
    clarification: Optional[ClarificationPayload] = None
    error_code: Optional[str] = None
    timeline: Optional[Dict[str, Any]] = None
    timeline_hash: Optional[str] = None
