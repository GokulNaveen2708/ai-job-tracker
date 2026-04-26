# Job Tracker — AI-Powered Application Dashboard

A full-stack job application tracker that reads your Gmail, uses Claude AI to parse and classify emails, and displays a live dashboard showing application status per company and role.

## Architecture

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│   React + Vite   │────▶│  FastAPI Backend  │────▶│  Firestore   │
│  Firebase Hosting│     │   Cloud Run       │     │  (Database)  │
└──────────────────┘     └────────┬──────────┘     └──────────────┘
                                  │
                         ┌────────┴────────┐
                         │                 │
                    ┌────▼────┐      ┌─────▼─────┐
                    │ Gmail   │      │ Claude AI │
                    │  API    │      │ (Parsing) │
                    └─────────┘      └───────────┘
```

## Features

- **Gmail OAuth Login** — single flow for auth + email access
- **Claude AI Parsing** — extracts company, role, status, confidence score
- **Dashboard** — Company → Role → Status pipeline (Applied → OA → Interview → Offer)
- **Timeline View** — click any card to see full email history
- **Manual Override** — correct any parsed field; future syncs respect your edits
- **Stats Panel** — response rate, interview rate, offer rate, avg time to reply
- **Rate-Limited Sync** — 2 rapid syncs then 5-min cooldown
- **Delete Applications** — remove duplicates or incorrect entries

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.11+
- Firebase project with Firestore + Auth enabled
- Google Cloud project with Gmail API + OAuth consent screen
- Anthropic API key

### Backend

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your keys
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local  # fill in Firebase config
npm run dev
# Set VITE_BACKEND_URL=http://localhost:8000
```

## Deployment

### Backend → Cloud Run

```bash
gcloud builds submit --tag gcr.io/PROJECT_ID/job-tracker-backend ./backend
gcloud run deploy job-tracker-backend \
  --image gcr.io/PROJECT_ID/job-tracker-backend \
  --platform managed --region us-central1 \
  --allow-unauthenticated --min-instances 0 --max-instances 2
```

### Frontend → Firebase Hosting

```bash
npm run build --prefix frontend
firebase deploy --only hosting
```

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite |
| Styling | Vanilla CSS |
| Auth | Firebase Auth (Google) |
| Backend | FastAPI (Python 3.11) |
| Email | Gmail API (History API) |
| AI | Claude claude-sonnet-4-20250514 |
| Database | Firestore |
| Hosting | Firebase Hosting + Cloud Run |
