"""
Firestore service — all database CRUD operations.

Uses Firebase Admin SDK (server-side) so all operations bypass client
security rules. This is the single source of truth for data access.
"""

from firebase_admin import firestore
from google.cloud.firestore_v1 import FieldFilter
from datetime import datetime, timezone
from typing import Optional
import uuid


def _db():
    """Get Firestore client (lazy, cached by firebase_admin internally)."""
    return firestore.client()


def _now_iso() -> str:
    """Current UTC time as ISO string."""
    return datetime.now(timezone.utc).isoformat()


# ── Users ──────────────────────────────────────────────────────────────────

async def get_user(uid: str) -> Optional[dict]:
    """Fetch a user document by UID."""
    doc = _db().collection("users").document(uid).get()
    if doc.exists:
        data = doc.to_dict()
        data["uid"] = doc.id
        return data
    return None


async def create_or_update_user(uid: str, data: dict) -> None:
    """Create or update a user document (upsert)."""
    data["updatedAt"] = _now_iso()
    _db().collection("users").document(uid).set(data, merge=True)


async def update_user_sync(uid: str, updated_creds=None,
                           history_id: str = None) -> None:
    """Update sync metadata after a successful sync run."""
    update_data = {
        "lastSyncAt": _now_iso(),
        "updatedAt": _now_iso(),
    }
    if history_id:
        update_data["lastHistoryId"] = history_id
    if updated_creds:
        # If the token was refreshed during the sync, store the new one
        if hasattr(updated_creds, "token"):
            update_data["gmailAccessToken"] = updated_creds.token
        if hasattr(updated_creds, "refresh_token") and updated_creds.refresh_token:
            update_data["gmailRefreshToken"] = updated_creds.refresh_token
    _db().collection("users").document(uid).update(update_data)


async def update_user_sync_count(uid: str, count: int) -> None:
    """Update the rapid sync count for rate limiting."""
    _db().collection("users").document(uid).update({
        "recentSyncCount": count,
        "lastSyncAt": _now_iso(),
    })


async def get_user_sync_meta(uid: str) -> dict:
    """Get sync rate-limit metadata for a user."""
    user = await get_user(uid)
    if not user:
        return {"lastSyncAt": None, "recentSyncCount": 0}
    return {
        "lastSyncAt": user.get("lastSyncAt"),
        "recentSyncCount": user.get("recentSyncCount", 0),
    }


# ── Applications ───────────────────────────────────────────────────────────

async def get_application_by_thread(uid: str, thread_id: str) -> Optional[dict]:
    """
    Find an application that contains the given threadId in its
    gmailThreadIds array. Returns the first match or None.
    """
    query = (
        _db()
        .collection("applications")
        .where(filter=FieldFilter("userId", "==", uid))
        .where(filter=FieldFilter("gmailThreadIds", "array_contains", thread_id))
        .limit(1)
    )
    docs = list(query.stream())
    if docs:
        data = docs[0].to_dict()
        data["id"] = docs[0].id
        return data
    return None


async def get_applications_for_user(
    uid: str,
    cursor: Optional[str] = None,
    limit: int = 20
) -> dict:
    """
    Get paginated applications for a user, ordered by lastActivityAt DESC.

    Returns: { "applications": [...], "nextCursor": "..." | None }
    """
    query = (
        _db()
        .collection("applications")
        .where(filter=FieldFilter("userId", "==", uid))
        .order_by("lastActivityAt", direction=firestore.Query.DESCENDING)
        .limit(limit)
    )

    # If cursor is provided, start after that document
    if cursor:
        cursor_doc = _db().collection("applications").document(cursor).get()
        if cursor_doc.exists:
            query = query.start_after(cursor_doc)

    docs = list(query.stream())
    applications = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        applications.append(data)

    next_cursor = docs[-1].id if len(docs) == limit else None

    return {
        "applications": applications,
        "nextCursor": next_cursor,
    }


async def create_application(
    uid: str,
    company: str,
    role: str,
    status: str,
    confidence: float,
    thread_id: str
) -> str:
    """Create a new application document. Returns the generated doc ID."""
    now = _now_iso()
    doc_ref = _db().collection("applications").document()
    doc_ref.set({
        "userId": uid,
        "company": company,
        "role": role,
        "status": status,
        "confidence": confidence,
        "manualOverride": False,
        "gmailThreadIds": [thread_id],
        "appliedAt": now,
        "lastActivityAt": now,
        "createdAt": now,
        "updatedAt": now,
    })
    return doc_ref.id


async def update_application_status(
    app_id: str,
    status: str,
    confidence: float,
    thread_id: str = None
) -> None:
    """Update an application's status and optionally add a new threadId."""
    now = _now_iso()
    update_data = {
        "status": status,
        "confidence": confidence,
        "lastActivityAt": now,
        "updatedAt": now,
    }
    _db().collection("applications").document(app_id).update(update_data)

    # Add threadId to array if not already present
    if thread_id:
        _db().collection("applications").document(app_id).update({
            "gmailThreadIds": firestore.ArrayUnion([thread_id])
        })


async def update_application_manual(app_id: str, uid: str, data: dict) -> None:
    """
    Manual override — update allowed fields and set manualOverride=true.
    Verifies ownership before updating.
    """
    doc = _db().collection("applications").document(app_id).get()
    if not doc.exists:
        raise ValueError("Application not found")
    if doc.to_dict().get("userId") != uid:
        raise PermissionError("Not your application")

    data["manualOverride"] = True
    data["updatedAt"] = _now_iso()
    _db().collection("applications").document(app_id).update(data)


async def add_thread_to_application(app_id: str, thread_id: str) -> None:
    """Add a Gmail thread ID to an existing application."""
    _db().collection("applications").document(app_id).update({
        "gmailThreadIds": firestore.ArrayUnion([thread_id]),
        "lastActivityAt": _now_iso(),
        "updatedAt": _now_iso(),
    })


async def delete_application(app_id: str, uid: str) -> None:
    """
    Delete an application and all its associated events.
    Verifies ownership before deleting.
    """
    doc_ref = _db().collection("applications").document(app_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise ValueError("Application not found")
    if doc.to_dict().get("userId") != uid:
        raise PermissionError("Not your application")

    # Delete all events for this application
    events = (
        _db()
        .collection("events")
        .where(filter=FieldFilter("applicationId", "==", app_id))
        .stream()
    )
    batch = _db().batch()
    for event_doc in events:
        batch.delete(event_doc.reference)
    batch.commit()

    # Delete the application itself
    doc_ref.delete()


# ── Events ─────────────────────────────────────────────────────────────────

async def create_event(
    application_id: str,
    uid: str,
    email: dict,
    parsed: dict,
    new_status: Optional[str],
    old_status: Optional[str] = None
) -> str:
    """Create an event documenting what happened (email received, status change, etc.)."""
    now = _now_iso()

    # Determine event type
    if old_status and new_status and old_status != new_status:
        event_type = "status_change"
    else:
        event_type = "email_received"

    description = parsed.get("reasoning", "")
    if not description and new_status:
        description = f"Status set to {new_status}"

    doc_ref = _db().collection("events").document()
    doc_ref.set({
        "applicationId": application_id,
        "userId": uid,
        "type": event_type,
        "fromStatus": old_status,
        "toStatus": new_status,
        "description": description,
        "emailSubject": email.get("subject"),
        "emailSnippet": email.get("snippet", "")[:200],
        "gmailThreadId": email.get("threadId"),
        "confidence": parsed.get("confidence", 0.0),
        "timestamp": email.get("date", now),
        "createdAt": now,
    })
    return doc_ref.id


async def get_events_for_application(app_id: str, uid: str) -> list:
    """Get all events for an application, ordered by timestamp ASC."""
    query = (
        _db()
        .collection("events")
        .where(filter=FieldFilter("applicationId", "==", app_id))
        .where(filter=FieldFilter("userId", "==", uid))
        .order_by("timestamp")
    )
    docs = list(query.stream())
    events = []
    for doc in docs:
        data = doc.to_dict()
        data["id"] = doc.id
        events.append(data)
    return events
