from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class InvestigationType(str, Enum):
    DNS = "dns"
    WEB = "web"
    SOCIAL = "social"
    IMAGE = "image"

class InvestigationTask(BaseModel):
    id: Optional[str] = None
    target: str
    type: InvestigationType
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = Field(default_factory=lambda: 0.0) # Placeholder
    results: Optional[Dict[str, Any]] = None

class InvestigationCreate(BaseModel):
    target: str
    type: InvestigationType
