"""
Applications router — CRUD operations for job applications.

Includes paginated listing, timeline events, manual override, and delete.
All endpoints require Firebase auth and verify ownership.
"""

from fastapi import APIRouter, Header, HTTPException, Query
from app.models.application import ApplicationUpdate
from app.services.firestore_service import (
    get_applications_for_user,
    get_events_for_application,
    update_application_manual,
    delete_application,
)
import firebase_admin.auth as fb_auth
from typing import Optional

router = APIRouter()


def _verify_token(authorization: str) -> str:
    """Extract and verify Firebase ID token. Returns uid."""
    token = authorization.replace("Bearer ", "")
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


@router.get("/")
async def list_applications(
    authorization: str = Header(...),
    cursor: Optional[str] = Query(None, description="Cursor for pagination (application ID)"),
    limit: int = Query(20, ge=1, le=100, description="Number of results per page"),
):
    """
    Get paginated list of applications for the authenticated user.
    Ordered by last activity date (most recent first).
    """
    uid = _verify_token(authorization)
    result = await get_applications_for_user(uid, cursor=cursor, limit=limit)
    return result


@router.get("/{app_id}/timeline")
async def get_timeline(
    app_id: str,
    authorization: str = Header(...),
):
    """Get all events for a specific application (timeline view)."""
    uid = _verify_token(authorization)
    events = await get_events_for_application(app_id, uid)
    return {"events": events}


@router.patch("/{app_id}")
async def override_application(
    app_id: str,
    body: ApplicationUpdate,
    authorization: str = Header(...),
):
    """
    Manual override — user corrects company, role, or status.
    Sets manualOverride=true so future syncs don't overwrite the change.
    """
    uid = _verify_token(authorization)

    # Only include fields that were explicitly set
    update_data = body.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert enum to string value for Firestore
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    try:
        await update_application_manual(app_id, uid, update_data)
    except ValueError:
        raise HTTPException(status_code=404, detail="Application not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your application")

    return {"success": True, "message": "Application updated successfully"}


@router.delete("/{app_id}")
async def remove_application(
    app_id: str,
    authorization: str = Header(...),
):
    """
    Delete an application and all its associated events.
    This action is irreversible.
    """
    uid = _verify_token(authorization)

    try:
        await delete_application(app_id, uid)
    except ValueError:
        raise HTTPException(status_code=404, detail="Application not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Not your application")

    return {"success": True, "message": "Application deleted successfully"}
