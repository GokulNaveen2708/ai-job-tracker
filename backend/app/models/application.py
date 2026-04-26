from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


class ApplicationStatus(str, Enum):
    APPLIED = "applied"
    OA = "oa"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"
    UNKNOWN = "unknown"


class ApplicationCreate(BaseModel):
    """Internal model for creating a new application."""
    user_id: str
    company: str
    role: str
    status: ApplicationStatus = ApplicationStatus.APPLIED
    confidence: float = Field(ge=0.0, le=1.0)
    gmail_thread_ids: List[str] = []


class ApplicationResponse(BaseModel):
    """Model returned to the frontend."""
    id: str
    userId: str
    company: str
    role: str
    status: ApplicationStatus
    confidence: float
    manualOverride: bool = False
    gmailThreadIds: List[str] = []
    appliedAt: Optional[str] = None
    lastActivityAt: Optional[str] = None
    createdAt: str
    updatedAt: str


class ApplicationUpdate(BaseModel):
    """Model for manual override PATCH request."""
    company: Optional[str] = None
    role: Optional[str] = None
    status: Optional[ApplicationStatus] = None


class PaginatedApplicationsResponse(BaseModel):
    """Paginated list of applications."""
    applications: List[ApplicationResponse]
    nextCursor: Optional[str] = None
    total: Optional[int] = None
