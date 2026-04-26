# Job Application Tracker — Full Implementation Spec

> Hand this file to Claude Code at the root of your repo. It contains everything needed to scaffold, build, and deploy the full stack.

---

## Project Overview

A personal job application tracker that reads Gmail, uses Claude AI to parse and classify emails, and displays a live dashboard showing application status per company and role. The user logs in with Google (OAuth 2.0), grants Gmail read access, and the app does the rest.

**Core features:**
- Gmail OAuth login (single flow for auth + email access)
- Claude AI email parsing (company, role, status, confidence score)
- Dashboard: Company → Role → Status pipeline (Applied → OA/Interview → Offer/Rejected)
- Timeline view per application (click to expand)
- Manual override on any parsed field
- Stats panel (response rate, avg time to reply, interview conversion)
- Confidence score shown on each card

---

## Monorepo Structure

```
job-tracker/
├── frontend/                  # React + Tailwind (Firebase Hosting)
│   ├── public/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ApplicationCard.jsx
│   │   │   ├── TimelineDrawer.jsx
│   │   │   ├── StatsPanel.jsx
│   │   │   ├── OverrideModal.jsx
│   │   │   └── LoginPage.jsx
│   │   ├── hooks/
│   │   │   ├── useApplications.js
│   │   │   └── useSync.js
│   │   ├── lib/
│   │   │   ├── firebase.js
│   │   │   └── api.js
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── .env.local
│   ├── package.json
│   └── vite.config.js
│
├── backend/                   # FastAPI (Cloud Run via Docker)
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── sync.py
│   │   │   └── applications.py
│   │   ├── services/
│   │   │   ├── gmail_service.py
│   │   │   ├── claude_service.py
│   │   │   └── firestore_service.py
│   │   ├── models/
│   │   │   ├── application.py
│   │   │   └── event.py
│   │   └── config.py
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env
│
├── firebase.json              # Firebase Hosting + Firestore rules
├── firestore.rules
├── firestore.indexes.json
└── README.md
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| Frontend | React 18 + Vite | Fast dev, small bundle |
| Styling | Tailwind CSS v3 | Utility-first, no overhead |
| Auth | Firebase Auth (Google provider) | Handles Google OAuth, token refresh |
| Frontend DB client | Firebase SDK (Firestore) | Real-time updates, offline support |
| Backend | FastAPI (Python 3.11) | Async-native, great for Gmail + Claude calls |
| Email access | Gmail API (google-api-python-client) | Official, handles pagination |
| AI parsing | Anthropic Claude API (claude-sonnet-4-20250514) | Best email understanding |
| Database | Firebase Firestore | GCP free tier, no server needed |
| Hosting | Firebase Hosting (frontend) + Cloud Run (backend) | GCP free tier |
| Containerisation | Docker (backend only) | Required for Cloud Run |

---

## Environment Variables

### `backend/.env`
```env
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=...
FIREBASE_PROJECT_ID=job-tracker-xxxxx
FIREBASE_SERVICE_ACCOUNT_JSON=/secrets/firebase-sa.json
ALLOWED_ORIGINS=https://your-firebase-app.web.app,http://localhost:5173
```

### `frontend/.env.local`
```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=job-tracker-xxxxx.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=job-tracker-xxxxx
VITE_BACKEND_URL=https://your-cloud-run-url.run.app
```

---

## Firestore Schema

### Collection: `users/{uid}`
```json
{
  "uid": "google-uid-string",
  "email": "user@gmail.com",
  "gmailAccessToken": "ya29...",
  "gmailRefreshToken": "1//...",
  "tokenExpiresAt": "2026-04-25T12:00:00Z",
  "lastSyncAt": "2026-04-25T10:00:00Z",
  "lastHistoryId": "1234567",
  "createdAt": "2026-01-01T00:00:00Z"
}
```

> `lastHistoryId` is the Gmail history ID used for incremental sync — only fetch emails newer than this on subsequent syncs, not the whole inbox every time.

### Collection: `applications/{appId}`
```json
{
  "id": "auto-generated",
  "userId": "google-uid-string",
  "company": "Stripe",
  "role": "Software Engineer, Payments",
  "status": "interview",
  "confidence": 0.94,
  "manualOverride": false,
  "gmailThreadIds": ["18abc123", "18abc456"],
  "appliedAt": "2026-03-10T09:00:00Z",
  "lastActivityAt": "2026-04-01T14:30:00Z",
  "createdAt": "2026-03-10T09:00:00Z",
  "updatedAt": "2026-04-01T14:30:00Z"
}
```

**Status enum values:** `applied` | `oa` | `interview` | `offer` | `rejected` | `withdrawn` | `unknown`

### Collection: `events/{eventId}`
```json
{
  "id": "auto-generated",
  "applicationId": "app-id-string",
  "userId": "google-uid-string",
  "type": "status_change",
  "fromStatus": "applied",
  "toStatus": "interview",
  "description": "Interview invite received from recruiting@stripe.com",
  "emailSubject": "Interview Invitation — Software Engineer at Stripe",
  "emailSnippet": "Hi, we'd love to invite you for a technical interview...",
  "gmailThreadId": "18abc456",
  "confidence": 0.94,
  "timestamp": "2026-04-01T14:30:00Z",
  "createdAt": "2026-04-01T14:30:00Z"
}
```

**Event type enum:** `email_received` | `status_change` | `manual_edit` | `sync_created`

### Firestore Indexes (firestore.indexes.json)
```json
{
  "indexes": [
    {
      "collectionGroup": "applications",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "userId", "order": "ASCENDING" },
        { "fieldPath": "lastActivityAt", "order": "DESCENDING" }
      ]
    },
    {
      "collectionGroup": "events",
      "queryScope": "COLLECTION",
      "fields": [
        { "fieldPath": "applicationId", "order": "ASCENDING" },
        { "fieldPath": "timestamp", "order": "ASCENDING" }
      ]
    }
  ]
}
```

---

## Backend Implementation

### `backend/requirements.txt`
```
fastapi==0.111.0
uvicorn[standard]==0.29.0
anthropic==0.25.0
google-api-python-client==2.127.0
google-auth-oauthlib==1.2.0
google-auth-httplib2==0.2.0
firebase-admin==6.5.0
pydantic==2.7.0
python-dotenv==1.0.1
httpx==0.27.0
```

### `backend/Dockerfile`
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### `backend/app/config.py`
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    google_client_id: str
    google_client_secret: str
    firebase_project_id: str
    firebase_service_account_json: str
    allowed_origins: list[str] = ["http://localhost:5173"]

    class Config:
        env_file = ".env"

settings = Settings()
```

### `backend/app/main.py`
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, sync, applications
from app.config import settings

app = FastAPI(title="Job Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])

@app.get("/health")
def health():
    return {"status": "ok"}
```

### `backend/app/services/claude_service.py`

This is the core AI parsing logic. The prompt is carefully designed to handle all the messy edge cases of job emails.

```python
import anthropic
import json
from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

SYSTEM_PROMPT = """You are an expert at parsing job application emails.
Given an email, extract structured information and return ONLY valid JSON, no explanation.

Rules:
- company: The hiring company name. Not a recruiter/agency unless it is the direct employer.
- role: The specific job title. Use the exact title from the email if present.
- email_type: One of: application_confirm | oa_invite | interview_invite | offer | rejection | follow_up | unknown
- confidence: Float 0.0 to 1.0 representing how certain you are of all fields combined.
- reasoning: One short sentence explaining your classification (used for debugging).

Email types defined:
- application_confirm: An ATS or recruiter confirming they received the application
- oa_invite: An online assessment or coding challenge invitation
- interview_invite: Any interview scheduling (phone screen, technical, onsite, final round)
- offer: A job offer (verbal or written)
- rejection: Any rejection at any stage, however softly worded
- follow_up: A recruiter follow-up, status update, or request for more info
- unknown: Cannot determine with confidence

Return JSON only in this exact shape:
{
  "company": "string",
  "role": "string",
  "email_type": "string",
  "confidence": 0.0,
  "reasoning": "string"
}"""

async def parse_email(subject: str, sender: str, body: str, snippet: str) -> dict:
    """
    Parse a single email and return structured classification.
    Falls back gracefully if Claude returns malformed JSON.
    """
    user_message = f"""Subject: {subject}
From: {sender}
Snippet: {snippet}

Body:
{body[:3000]}"""  # Truncate to avoid token limits on huge emails

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}]
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except (json.JSONDecodeError, IndexError, KeyError):
        return {
            "company": extract_company_from_sender(sender),
            "role": "Unknown Role",
            "email_type": "unknown",
            "confidence": 0.1,
            "reasoning": "Claude returned malformed response; used fallback extraction."
        }

def extract_company_from_sender(sender: str) -> str:
    """Naive fallback: extract domain from email address."""
    try:
        domain = sender.split("@")[1].split(".")[0]
        return domain.capitalize()
    except IndexError:
        return "Unknown Company"

EMAIL_TYPE_TO_STATUS = {
    "application_confirm": "applied",
    "oa_invite": "oa",
    "interview_invite": "interview",
    "offer": "offer",
    "rejection": "rejected",
    "follow_up": None,   # Don't change status on follow-ups
    "unknown": None,
}

def email_type_to_status(email_type: str) -> str | None:
    return EMAIL_TYPE_TO_STATUS.get(email_type)
```

### `backend/app/services/gmail_service.py`
```python
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import base64
import re

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

JOB_KEYWORDS = [
    "application", "applied", "interview", "offer", "assessment",
    "online assessment", "rejection", "position", "role", "hiring",
    "recruiter", "recruiting", "talent", "opportunity", "candidat",
    "greenhouse", "lever", "workday", "taleo", "icims", "ashby"
]

def build_gmail_service(access_token: str, refresh_token: str):
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
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")

    if payload.get("mimeType") == "text/html":
        data = payload.get("body", {}).get("data", "")
        html = base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
        # Strip HTML tags for a clean text body
        return re.sub(r"<[^>]+>", " ", html)

    for part in payload.get("parts", []):
        result = get_email_body(part)
        if result:
            return result
    return ""

async def fetch_new_emails(access_token: str, refresh_token: str, last_sync_date: str | None):
    """
    Fetch job-related emails since last sync.
    Returns list of dicts with subject, sender, body, snippet, threadId.
    """
    service, updated_creds = build_gmail_service(access_token, refresh_token)
    query = build_job_query(after_date=last_sync_date)

    emails = []
    page_token = None

    while True:
        kwargs = {"userId": "me", "q": query, "maxResults": 50}
        if page_token:
            kwargs["pageToken"] = page_token

        result = service.users().messages().list(**kwargs).execute()
        messages = result.get("messages", [])

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me",
                id=msg_ref["id"],
                format="full"
            ).execute()

            headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
            emails.append({
                "messageId": msg["id"],
                "threadId": msg["threadId"],
                "subject": headers.get("subject", "(no subject)"),
                "sender": headers.get("from", ""),
                "snippet": msg.get("snippet", ""),
                "body": get_email_body(msg["payload"]),
                "date": headers.get("date", ""),
            })

        page_token = result.get("nextPageToken")
        if not page_token:
            break

    return emails, updated_creds
```

### `backend/app/routers/sync.py`
```python
from fastapi import APIRouter, Header, HTTPException
from app.services.gmail_service import fetch_new_emails
from app.services.claude_service import parse_email, email_type_to_status
from app.services.firestore_service import (
    get_user, update_user_sync,
    get_application_by_thread, create_application, update_application_status,
    create_event
)
import firebase_admin.auth as fb_auth
from datetime import datetime, timezone

router = APIRouter()

@router.post("/run")
async def run_sync(authorization: str = Header(...)):
    """
    Main sync endpoint. Called by frontend after login or on-demand.
    1. Verify Firebase ID token
    2. Fetch new Gmail emails
    3. Parse each with Claude
    4. Upsert applications + events in Firestore
    """
    token = authorization.replace("Bearer ", "")
    try:
        decoded = fb_auth.verify_id_token(token)
        uid = decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = await get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    last_sync = user.get("lastSyncAt")
    last_sync_date = last_sync[:10].replace("-", "/") if last_sync else None

    emails, updated_creds = await fetch_new_emails(
        user["gmailAccessToken"],
        user["gmailRefreshToken"],
        last_sync_date
    )

    results = {"processed": 0, "created": 0, "updated": 0, "skipped": 0}

    for email in emails:
        parsed = await parse_email(
            subject=email["subject"],
            sender=email["sender"],
            body=email["body"],
            snippet=email["snippet"]
        )

        # Skip unknowns with low confidence
        if parsed["email_type"] == "unknown" and parsed["confidence"] < 0.4:
            results["skipped"] += 1
            continue

        new_status = email_type_to_status(parsed["email_type"])
        existing = await get_application_by_thread(uid, email["threadId"])

        if existing:
            # Update status only if the new status is a progression forward
            if new_status and should_update_status(existing["status"], new_status):
                await update_application_status(existing["id"], new_status, parsed["confidence"])
                results["updated"] += 1
            await create_event(
                application_id=existing["id"],
                uid=uid,
                email=email,
                parsed=parsed,
                new_status=new_status
            )
        else:
            app_id = await create_application(
                uid=uid,
                company=parsed["company"],
                role=parsed["role"],
                status=new_status or "applied",
                confidence=parsed["confidence"],
                thread_id=email["threadId"]
            )
            await create_event(
                application_id=app_id,
                uid=uid,
                email=email,
                parsed=parsed,
                new_status=new_status or "applied"
            )
            results["created"] += 1

        results["processed"] += 1

    await update_user_sync(uid, updated_creds)
    return results

STATUS_PROGRESSION = ["applied", "oa", "interview", "offer", "rejected", "withdrawn"]

def should_update_status(current: str, new: str) -> bool:
    """
    Only advance status forward in the funnel.
    Offer and rejection are always terminal — don't overwrite them.
    """
    if current in ("offer", "rejected", "withdrawn"):
        return False
    try:
        return STATUS_PROGRESSION.index(new) > STATUS_PROGRESSION.index(current)
    except ValueError:
        return False
```

### `backend/app/routers/applications.py`
```python
from fastapi import APIRouter, Header, HTTPException
from app.services.firestore_service import (
    get_applications_for_user, get_events_for_application,
    update_application_manual
)
import firebase_admin.auth as fb_auth

router = APIRouter()

def verify_token(authorization: str) -> str:
    token = authorization.replace("Bearer ", "")
    try:
        decoded = fb_auth.verify_id_token(token)
        return decoded["uid"]
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/")
async def list_applications(authorization: str = Header(...)):
    uid = verify_token(authorization)
    apps = await get_applications_for_user(uid)
    return {"applications": apps}

@router.get("/{app_id}/timeline")
async def get_timeline(app_id: str, authorization: str = Header(...)):
    uid = verify_token(authorization)
    events = await get_events_for_application(app_id, uid)
    return {"events": events}

@router.patch("/{app_id}")
async def override_application(
    app_id: str,
    body: dict,
    authorization: str = Header(...)
):
    """Manual override — user corrects company, role, or status."""
    uid = verify_token(authorization)
    allowed_fields = {"company", "role", "status"}
    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    update_data["manualOverride"] = True
    await update_application_manual(app_id, uid, update_data)
    return {"success": True}
```

---

## Frontend Implementation

### `frontend/src/lib/firebase.js`
```javascript
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { getFirestore } from "firebase/firestore";

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
};

const app = initializeApp(firebaseConfig);
export const auth = getAuth(app);
export const db = getFirestore(app);

export const googleProvider = new GoogleAuthProvider();
// Request Gmail readonly scope alongside login
googleProvider.addScope("https://www.googleapis.com/auth/gmail.readonly");
```

### `frontend/src/lib/api.js`
```javascript
const BASE_URL = import.meta.env.VITE_BACKEND_URL;

async function authFetch(path, options = {}) {
  const { getAuth } = await import("firebase/auth");
  const token = await getAuth().currentUser?.getIdToken();
  return fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
}

export async function runSync() {
  const res = await authFetch("/sync/run", { method: "POST" });
  return res.json();
}

export async function getApplications() {
  const res = await authFetch("/applications/");
  return res.json();
}

export async function getTimeline(appId) {
  const res = await authFetch(`/applications/${appId}/timeline`);
  return res.json();
}

export async function overrideApplication(appId, fields) {
  const res = await authFetch(`/applications/${appId}`, {
    method: "PATCH",
    body: JSON.stringify(fields),
  });
  return res.json();
}
```

### `frontend/src/components/Dashboard.jsx` — Component outline

```jsx
// Dashboard.jsx
// Layout: StatsPanel at top, then a grid of ApplicationCards
// Each card shows: Company, Role, StatusBar, Confidence badge
// Click a card -> opens TimelineDrawer (slide-in from right)
// "Sync" button top-right triggers runSync() with loading state

// Status pipeline order for the progress bar:
const STATUSES = ["applied", "oa", "interview", "offer"];
// "rejected" and "withdrawn" are terminal — shown with a red/gray indicator instead

// Confidence badge colors:
// >= 0.85  -> green
// >= 0.6   -> yellow
// < 0.6    -> red (with "Unverified" label, prompts user to review)

// Cards grouped by company, then show each role as a sub-row
// If multiple roles at same company, stack them under one company header
```

### `frontend/src/components/ApplicationCard.jsx` — Key logic

```jsx
// Props: application object
// Shows:
//   - Company name (large, bold)
//   - Role title (secondary text)
//   - Progress bar: 4 segments (applied/oa/interview/offer)
//     - Fill up to current status
//     - If rejected: show a red "Rejected" pill instead of progress bar
//   - Confidence score: small badge bottom-right
//     - If manualOverride=true: show a pencil icon instead
//   - Click anywhere on card: trigger onSelect(application)
//   - Hover: show "Edit" button that opens OverrideModal

// Progress bar implementation:
// Map status to step index (applied=0, oa=1, interview=2, offer=3)
// Fill steps 0..currentIndex with accent color
// Rejected gets a separate visual treatment (red border, strike styling)
```

### `frontend/src/components/TimelineDrawer.jsx`

```jsx
// Slide-in drawer from right when an application card is clicked
// Fetches events from GET /applications/:id/timeline on open
// Shows a vertical timeline:
//   Each event:
//   - Date + time (relative: "3 days ago")
//   - Icon by event type (email, status change, manual edit)
//   - Email subject (if available)
//   - Short description
//   - Claude's reasoning snippet (collapsible, shown in gray italic)
// Bottom of drawer: "Override" button opens OverrideModal
```

### `frontend/src/components/StatsPanel.jsx`

```jsx
// Computed from applications array passed as prop
// Metrics to show:
//   - Total applications
//   - Response rate (%) = (non-applied statuses / total) * 100
//   - Interview rate (%) = (interview + offer) / total * 100
//   - Offer rate (%) = offer / total * 100
//   - Avg days to first response (mean of appliedAt->firstEventAt delta)
//   - Active applications (not rejected/withdrawn/offer)
// Layout: horizontal pill row on desktop, 2-col grid on mobile
```

### `frontend/src/components/OverrideModal.jsx`

```jsx
// Modal for manual correction
// Fields:
//   - Company (text input, pre-filled)
//   - Role (text input, pre-filled)
//   - Status (dropdown: applied | oa | interview | offer | rejected | withdrawn)
// On save: calls PATCH /applications/:id, sets manualOverride=true
// After save: show a "Manually verified" badge on the card (pencil icon)
// Important: manual overrides are never touched by future syncs
//   (backend checks manualOverride=true and skips status updates)
```

---

## Auth Flow (Step by Step)

```
1. User clicks "Sign in with Google"
2. Firebase signInWithPopup(googleProvider) runs
   - Requests: openid, email, profile, gmail.readonly
3. Firebase returns: idToken (for our backend), credential.accessToken (for Gmail)
4. Frontend sends both tokens to backend POST /auth/register:
   {
     idToken: "...",
     gmailAccessToken: "ya29...",
     gmailRefreshToken: "1//..."
   }
5. Backend verifies idToken with Firebase Admin SDK
6. Backend stores gmailAccessToken + gmailRefreshToken in Firestore users/{uid}
7. Frontend immediately triggers POST /sync/run
8. Backend fetches emails, Claude parses, Firestore updated
9. Frontend subscribes to Firestore collection (onSnapshot) for real-time updates
```

> **Note on refresh tokens:** Google only returns the refresh token on the *first* consent. If the user has logged in before without `prompt: "consent"`, you won't get it. Set `googleProvider.setCustomParameters({ access_type: "offline", prompt: "consent" })` to force it.

---

## Claude Parsing — Prompt Engineering Notes

The prompt in `claude_service.py` is the most critical piece. Key decisions:

**Why truncate body to 3000 chars?**
ATS emails (Greenhouse, Workday) often include 10k+ chars of HTML boilerplate. The relevant signal is always in the first 500 words. Truncating saves tokens and improves accuracy by reducing noise.

**Why not use regex or keyword matching?**
Rejection emails are notoriously euphemistic. "We've decided to move our process forward with other candidates" does not contain the word "reject". Claude handles this perfectly; regex does not.

**Confidence score calibration:**
- `>= 0.85`: Claude is very confident. Display as-is, no warning.
- `0.6 – 0.84`: Reasonable but flag it. Show yellow badge.
- `< 0.6`: Low confidence. Show red badge, prompt user to verify.
- Skip `unknown` type with confidence `< 0.4` entirely (cold recruiter emails, newsletters).

**Deduplication logic:**
Group by `threadId`. Gmail threads all emails in a conversation, so an application_confirm + rejection in the same thread are one application. The `gmailThreadIds` array on the application stores all related thread IDs.

---

## Deployment

### Backend to Cloud Run

```bash
# Build and push Docker image
gcloud builds submit --tag gcr.io/PROJECT_ID/job-tracker-backend ./backend

# Deploy to Cloud Run (free tier: min-instances=0)
gcloud run deploy job-tracker-backend \
  --image gcr.io/PROJECT_ID/job-tracker-backend \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars ANTHROPIC_API_KEY=sk-ant-...,GOOGLE_CLIENT_ID=...
```

### Frontend to Firebase Hosting

```bash
npm run build --prefix frontend
firebase deploy --only hosting
```

### Firestore Rules (`firestore.rules`)

```
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
    match /applications/{appId} {
      allow read, write: if request.auth != null
        && resource.data.userId == request.auth.uid;
    }
    match /events/{eventId} {
      allow read: if request.auth != null
        && resource.data.userId == request.auth.uid;
      allow write: if false; // Backend only via Admin SDK
    }
  }
}
```

---

## GCP Free Tier Limits (for reference)

| Service | Free allowance | Expected usage |
|---|---|---|
| Cloud Run | 2M requests/month, 360k GB-seconds | ~100 requests/month → well within |
| Firestore reads | 50,000/day | ~500/day at active job search pace |
| Firestore writes | 20,000/day | ~50/day during sync |
| Firebase Hosting | 10 GB storage, 360 MB/day transfer | Easily within |
| Claude API | Pay per token | ~500 emails × ~800 tokens = ~400k tokens total |

---

## Known Edge Cases to Handle

| Scenario | Handling |
|---|---|
| Recruiter cold outreach (not your application) | Claude classifies as `unknown`, low confidence → skipped |
| Automated LinkedIn job alerts | Filtered by job query keywords — rarely match |
| Same company, two different roles | Separate applications (different role title in parsed output) |
| Email chain: apply → reject in same thread | Two events on same application; status advances to rejected |
| No refresh token on re-login | Force consent with `prompt: "consent"` in OAuth config |
| Claude rate limit | Wrap in exponential backoff retry (max 3 attempts) |
| Manual override then new email arrives | `manualOverride=true` → backend skips status update, still logs event |
| Company name variations ("Meta" vs "Meta Platforms") | Accept Claude's output; user can override via modal |

---

## Local Development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend
npm install
cp .env.local.example .env.local  # fill in Firebase config
npm run dev
# Set VITE_BACKEND_URL=http://localhost:8000 for local dev
```

---

## What to Build First (Recommended Order)

1. Firebase project setup + Google OAuth working end-to-end
2. Backend `/auth/register` storing tokens in Firestore
3. Gmail fetch returning raw emails (log them, don't parse yet)
4. Claude parsing on a single hardcoded email to validate the prompt
5. Full sync route wiring Gmail → Claude → Firestore
6. Frontend login page + sync trigger
7. Dashboard with application cards (static data first)
8. Status progress bar + confidence badge
9. Timeline drawer
10. Stats panel
11. Manual override modal
12. Docker + Cloud Run deploy
13. Firebase Hosting deploy