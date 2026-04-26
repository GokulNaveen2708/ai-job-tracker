"""
Sync router — orchestrates the email sync pipeline.

1. Verify Firebase auth
2. Check rate limits (max 2 rapid syncs, then 5-min cooldown)
3. Fetch new emails from Gmail (History API for incremental, query for initial)
4. Parse emails with Gemini AI in batches
5. Upsert applications + events in Firestore
"""

from fastapi import APIRouter, Header, HTTPException
from app.services.gmail_service import fetch_initial_emails, fetch_incremental_emails
from app.services.gemini_service import parse_emails_batch, email_type_to_status
from app.services.firestore_service import (
    get_user,
    update_user_sync,
    update_user_sync_count,
    get_user_sync_meta,
    get_application_by_thread,
    create_application,
    update_application_status,
    add_thread_to_application,
    create_event,
)
from app.config import settings
import firebase_admin.auth as fb_auth
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# Status progression order — only allow forward movement
STATUS_PROGRESSION = ["applied", "oa", "interview", "offer", "rejected", "withdrawn"]


def _verify_token(authorization: str) -> str:
    """Extract and verify Firebase ID token. Returns uid."""
    token = authorization.replace("Bearer ", "")
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def _check_rate_limit(sync_meta: dict) -> None:
    """
    Rate limiting: allow 2 rapid syncs, then enforce 5-min cooldown.
    Raises HTTPException if rate limited.
    """
    last_sync = sync_meta.get("lastSyncAt")
    recent_count = sync_meta.get("recentSyncCount", 0)

    if not last_sync:
        return  # First sync ever — allow it

    try:
        last_sync_dt = datetime.fromisoformat(last_sync)
        now = datetime.now(timezone.utc)
        seconds_since = (now - last_sync_dt).total_seconds()

        if seconds_since > settings.sync_cooldown_seconds:
            # Cooldown period has passed, reset counter
            return

        if recent_count >= settings.sync_max_burst:
            remaining = int(settings.sync_cooldown_seconds - seconds_since)
            raise HTTPException(
                status_code=429,
                detail={
                    "message": f"Rate limited. Please wait {remaining} seconds before syncing again.",
                    "retryAfter": remaining,
                }
            )
    except (ValueError, TypeError):
        return  # If timestamp is malformed, allow the sync


def should_update_status(current: str, new: str) -> bool:
    """
    Only advance status forward in the pipeline.
    Offer, rejection, and withdrawn are terminal — don't overwrite them.
    """
    if current in ("offer", "rejected", "withdrawn"):
        return False
    try:
        return STATUS_PROGRESSION.index(new) > STATUS_PROGRESSION.index(current)
    except ValueError:
        return False


@router.post("/run")
async def run_sync(authorization: str = Header(...)):
    """
    Main sync endpoint. Called by frontend after login or on-demand.

    Pipeline:
    1. Verify Firebase ID token
    2. Check rate limits
    3. Fetch new Gmail emails (initial or incremental)
    4. Batch-parse with Gemini
    5. Upsert applications + events in Firestore
    6. Return sync results summary
    """
    uid = _verify_token(authorization)

    # ── Rate limit check ──────────────────────────────────────────────
    sync_meta = await get_user_sync_meta(uid)
    _check_rate_limit(sync_meta)

    # ── Get user data ─────────────────────────────────────────────────
    user = await get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found. Please re-authenticate.")

    access_token = user.get("gmailAccessToken")
    refresh_token = user.get("gmailRefreshToken", "")
    if not access_token:
        raise HTTPException(status_code=400, detail="Gmail tokens missing. Please sign out and sign in again.")

    last_history_id = user.get("lastHistoryId")

    # ── Fetch emails ──────────────────────────────────────────────────
    try:
        if last_history_id:
            emails, updated_creds, new_history_id = await fetch_incremental_emails(
                access_token, refresh_token, last_history_id
            )
        else:
            emails, updated_creds, new_history_id = await fetch_initial_emails(
                access_token, refresh_token
            )
    except Exception as e:
        logger.error(f"Gmail fetch failed for user {uid}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to fetch emails from Gmail: {str(e)[:200]}")

    if not emails:
        # Update sync timestamp even if no emails found
        await update_user_sync(uid, updated_creds, new_history_id)
        # Update rate limit counter
        new_count = sync_meta.get("recentSyncCount", 0) + 1
        await update_user_sync_count(uid, new_count)
        return {
            "processed": 0, "created": 0, "updated": 0, "skipped": 0,
            "message": "No new job-related emails found."
        }

    # ── Parse with Gemini (batched) ───────────────────────────────────
    try:
        parsed_results = await parse_emails_batch(emails, max_concurrent=5)
    except Exception as e:
        logger.error(f"Gemini parsing failed: {e}")
        raise HTTPException(status_code=502, detail=f"AI parsing failed: {str(e)[:200]}")

    # ── Upsert applications + events ──────────────────────────────────
    results = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    for email, parsed in zip(emails, parsed_results):
        try:
            # Log what Gemini classified for debugging
            logger.info(
                f"Parsed: subject='{email.get('subject', '')[:60]}' → "
                f"type={parsed['email_type']}, company={parsed.get('company')}, "
                f"confidence={parsed.get('confidence', 0):.2f}, "
                f"reason={parsed.get('reasoning', '')[:80]}"
            )

            # Skip only truly unknown emails with very low confidence
            if parsed["email_type"] == "unknown" and parsed.get("confidence", 0) < 0.2:
                results["skipped"] += 1
                continue

            new_status = email_type_to_status(parsed["email_type"])
            existing = await get_application_by_thread(uid, email["threadId"])

            if existing:
                old_status = existing.get("status")

                # Skip status updates on manually overridden applications
                if existing.get("manualOverride") and new_status:
                    logger.info(f"Skipping status update for manually overridden app {existing['id']}")
                elif new_status and should_update_status(old_status, new_status):
                    await update_application_status(
                        existing["id"], new_status, parsed["confidence"], email["threadId"]
                    )
                    results["updated"] += 1
                else:
                    # Still add the thread ID even if status didn't change
                    await add_thread_to_application(existing["id"], email["threadId"])

                # Always log the event (even for manual overrides)
                await create_event(
                    application_id=existing["id"],
                    uid=uid,
                    email=email,
                    parsed=parsed,
                    new_status=new_status,
                    old_status=old_status,
                )
            else:
                # Create new application
                app_id = await create_application(
                    uid=uid,
                    company=parsed["company"],
                    role=parsed["role"],
                    status=new_status or "applied",
                    confidence=parsed["confidence"],
                    thread_id=email["threadId"],
                )
                await create_event(
                    application_id=app_id,
                    uid=uid,
                    email=email,
                    parsed=parsed,
                    new_status=new_status or "applied",
                )
                results["created"] += 1

            results["processed"] += 1

        except Exception as e:
            logger.error(f"Failed to process email {email.get('messageId')}: {e}")
            results["skipped"] += 1
            continue

    # ── Update sync metadata ──────────────────────────────────────────
    await update_user_sync(uid, updated_creds, new_history_id)

    # Update rate limit counter
    last_sync = sync_meta.get("lastSyncAt")
    if last_sync:
        try:
            last_sync_dt = datetime.fromisoformat(last_sync)
            seconds_since = (datetime.now(timezone.utc) - last_sync_dt).total_seconds()
            if seconds_since > settings.sync_cooldown_seconds:
                new_count = 1  # Reset counter after cooldown
            else:
                new_count = sync_meta.get("recentSyncCount", 0) + 1
        except (ValueError, TypeError):
            new_count = 1
    else:
        new_count = 1
    await update_user_sync_count(uid, new_count)

    return results
