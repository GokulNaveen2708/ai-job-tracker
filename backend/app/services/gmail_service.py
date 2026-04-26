"""
Gmail service — fetches job-related emails using the Gmail API.

Uses the History API for incremental syncs (after the first full sync)
to minimize API calls and only process new messages.
"""

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from app.config import settings
import base64
import re
import logging

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Keywords used to filter job-related emails on the first (full) sync
JOB_KEYWORDS = [
    "application", "applied", "interview", "offer", "assessment",
    "online assessment", "rejection", "position", "role", "hiring",
    "recruiter", "recruiting", "talent", "opportunity", "candidat",
    "greenhouse", "lever", "workday", "taleo", "icims", "ashby",
]

# Senders that are almost never job-related (skip to save Claude tokens)
SKIP_SENDERS = [
    "noreply@linkedin.com",
    "jobs-noreply@linkedin.com",
    "notifications@linkedin.com",
]


def build_gmail_service(access_token: str, refresh_token: str):
    """
    Build an authenticated Gmail API service client.
    Automatically refreshes the token if expired.
    Returns (service, credentials).
    """
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("gmail", "v1", credentials=creds), creds


def build_job_query(after_date: str | None = None) -> str:
    """
    Build a Gmail search query that finds job-related emails.
    Used only on the first sync (no lastHistoryId yet).
    after_date format: YYYY/MM/DD
    """
    keyword_query = " OR ".join(f'"{kw}"' for kw in JOB_KEYWORDS[:8])
    query = f"({keyword_query})"
    if after_date:
        query += f" after:{after_date}"
    return query


def get_email_body(payload: dict) -> str:
    """Recursively extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
            # Strip HTML tags for a clean text body
            return re.sub(r"<[^>]+>", " ", html)

    for part in payload.get("parts", []):
        result = get_email_body(part)
        if result:
            return result
    return ""


def _is_job_related(subject: str, sender: str, snippet: str) -> bool:
    """
    Quick keyword check to filter messages from the History API
    before sending to Claude (saves API tokens).
    """
    # Skip known non-job senders
    sender_email = sender.lower()
    for skip in SKIP_SENDERS:
        if skip in sender_email:
            return False

    # Check if any job keyword appears in subject or snippet
    text = f"{subject} {snippet}".lower()
    return any(kw in text for kw in JOB_KEYWORDS)


def _extract_email_data(service, msg_id: str) -> dict:
    """Fetch full message details and extract structured data."""
    msg = service.users().messages().get(
        userId="me",
        id=msg_id,
        format="full"
    ).execute()

    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    return {
        "messageId": msg["id"],
        "threadId": msg["threadId"],
        "subject": headers.get("subject", "(no subject)"),
        "sender": headers.get("from", ""),
        "snippet": msg.get("snippet", ""),
        "body": get_email_body(msg["payload"]),
        "date": headers.get("date", ""),
    }


async def fetch_initial_emails(
    access_token: str, refresh_token: str, max_emails: int = 50
) -> tuple:
    """
    First-time sync: use keyword query to fetch job-related emails.
    Capped at max_emails to prevent timeouts on large inboxes.
    Returns (emails_list, updated_credentials, current_history_id).
    """
    service, creds = build_gmail_service(access_token, refresh_token)

    # Get current historyId from profile for future incremental syncs
    profile = service.users().getProfile(userId="me").execute()
    current_history_id = profile.get("historyId")
    logger.info(f"Gmail profile fetched. historyId={current_history_id}")

    query = build_job_query()
    logger.info(f"Initial sync query: {query}")
    emails = []
    page_token = None

    while len(emails) < max_emails:
        kwargs = {"userId": "me", "q": query, "maxResults": min(50, max_emails - len(emails))}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        messages = result.get("messages", [])
        logger.info(f"Gmail returned {len(messages)} message refs (total so far: {len(emails)})")

        for msg_ref in messages:
            if len(emails) >= max_emails:
                break
            try:
                email_data = _extract_email_data(service, msg_ref["id"])
                emails.append(email_data)
            except Exception as e:
                logger.warning(f"Failed to fetch message {msg_ref['id']}: {e}")
                continue

        page_token = result.get("nextPageToken")
        if not page_token or len(emails) >= max_emails:
            break

    logger.info(f"Initial sync: fetched {len(emails)} emails (cap={max_emails})")
    return emails, creds, current_history_id


async def fetch_incremental_emails(
    access_token: str,
    refresh_token: str,
    last_history_id: str
) -> tuple:
    """
    Incremental sync: use Gmail History API to fetch only new messages
    since the last sync. Much more efficient than re-querying everything.

    Returns (emails_list, updated_credentials, new_history_id).
    """
    service, creds = build_gmail_service(access_token, refresh_token)

    # Get current historyId
    profile = service.users().getProfile(userId="me").execute()
    current_history_id = profile.get("historyId")

    # If historyId hasn't changed, no new emails
    if current_history_id == last_history_id:
        return [], creds, current_history_id

    emails = []
    page_token = None
    seen_msg_ids = set()

    try:
        while True:
            kwargs = {
                "userId": "me",
                "startHistoryId": last_history_id,
                "historyTypes": ["messageAdded"],
            }
            if page_token:
                kwargs["pageToken"] = page_token

            result = service.users().history().list(**kwargs).execute()
            history_records = result.get("history", [])

            for record in history_records:
                for msg_added in record.get("messagesAdded", []):
                    msg_id = msg_added["message"]["id"]
                    if msg_id in seen_msg_ids:
                        continue
                    seen_msg_ids.add(msg_id)

                    try:
                        email_data = _extract_email_data(service, msg_id)

                        # Only process job-related emails
                        if _is_job_related(
                            email_data["subject"],
                            email_data["sender"],
                            email_data["snippet"]
                        ):
                            emails.append(email_data)
                    except Exception as e:
                        logger.warning(f"Failed to fetch message {msg_id}: {e}")
                        continue

            page_token = result.get("nextPageToken")
            if not page_token:
                break

    except Exception as e:
        # If historyId is invalid (too old), fall back to initial sync
        if "404" in str(e) or "historyId" in str(e).lower():
            logger.warning(f"History ID expired, falling back to query-based fetch: {e}")
            return await fetch_initial_emails(access_token, refresh_token)
        raise

    logger.info(f"Incremental sync: found {len(emails)} new job-related emails")
    return emails, creds, current_history_id
