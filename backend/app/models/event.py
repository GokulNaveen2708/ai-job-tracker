from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class EventType(str, Enum):
    EMAIL_RECEIVED = "email_received"
    STATUS_CHANGE = "status_change"
    MANUAL_EDIT = "manual_edit"
    SYNC_CREATED = "sync_created"


class EventCreate(BaseModel):
    """Internal model for creating a new event."""
    application_id: str
    user_id: str
    event_type: EventType
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    description: str = ""
    email_subject: Optional[str] = None
    email_snippet: Optional[str] = None
    gmail_thread_id: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class EventResponse(BaseModel):
    """Model returned to the frontend."""
    id: str
    applicationId: str
    userId: str
    type: EventType
    fromStatus: Optional[str] = None
    toStatus: Optional[str] = None
    description: str
    emailSubject: Optional[str] = None
    emailSnippet: Optional[str] = None
    gmailThreadId: Optional[str] = None
    confidence: float
    timestamp: str
    createdAt: str
