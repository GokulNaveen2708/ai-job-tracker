from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, sync, applications
from app.config import settings
import firebase_admin
from firebase_admin import credentials
import json
import os

# ── Firebase Admin SDK initialization ──────────────────────────────────────
# Initialize once at startup; used by all services for Firestore + auth
if not firebase_admin._apps:
    sa_path = settings.firebase_service_account_json
    if os.path.isfile(sa_path):
        cred = credentials.Certificate(sa_path)
    else:
        # If it's a JSON string (e.g. from env var in Cloud Run), parse it
        cred = credentials.Certificate(json.loads(sa_path))
    firebase_admin.initialize_app(cred, {
        "projectId": settings.firebase_project_id,
    })

# ── FastAPI app ────────────────────────────────────────────────────────────
app = FastAPI(
    title="Job Tracker API",
    description="AI-powered job application tracker using Gmail + Claude",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(sync.router, prefix="/sync", tags=["sync"])
app.include_router(applications.router, prefix="/applications", tags=["applications"])


@app.get("/health")
def health():
    """Health check for Cloud Run / monitoring."""
    return {"status": "ok"}
