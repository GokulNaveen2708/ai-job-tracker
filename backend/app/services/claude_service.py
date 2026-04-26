"""
Claude AI email parsing service.

Uses the Anthropic async client for non-blocking calls.
Includes batch processing with a concurrency semaphore to avoid
hitting rate limits while still being fast.
"""

import anthropic
import asyncio
import json
from app.config import settings

# ── Async Anthropic client ─────────────────────────────────────────────────
client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

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
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )
        raw = response.content[0].text.strip()

        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        parsed = json.loads(raw.strip())

        # Validate required fields exist
        required_fields = ["company", "role", "email_type", "confidence", "reasoning"]
        for field in required_fields:
            if field not in parsed:
                parsed[field] = _default_for_field(field, sender)

        return parsed

    except (json.JSONDecodeError, IndexError, KeyError, anthropic.APIError) as e:
        return {
            "company": extract_company_from_sender(sender),
            "role": "Unknown Role",
            "email_type": "unknown",
            "confidence": 0.1,
            "reasoning": f"Claude returned malformed response; used fallback extraction. Error: {str(e)[:100]}",
        }


def _default_for_field(field: str, sender: str):
    """Provide defaults for missing fields in Claude's response."""
    defaults = {
        "company": extract_company_from_sender(sender),
        "role": "Unknown Role",
        "email_type": "unknown",
        "confidence": 0.3,
        "reasoning": "Field was missing from Claude response",
    }
    return defaults.get(field, "")


def extract_company_from_sender(sender: str) -> str:
    """Naive fallback: extract domain from email address."""
    try:
        # Handle "Name <email@domain.com>" format
        if "<" in sender:
            sender = sender.split("<")[1].split(">")[0]
        domain = sender.split("@")[1].split(".")[0]
        return domain.capitalize()
    except (IndexError, AttributeError):
        return "Unknown Company"


# ── Batch Processing ──────────────────────────────────────────────────────

async def parse_emails_batch(
    emails: list[dict],
    max_concurrent: int = 5
) -> list[dict]:
    """
    Parse multiple emails concurrently with a semaphore to respect
    API rate limits. Returns results in the same order as input.
    """
    semaphore = asyncio.Semaphore(max_concurrent)

    async def parse_with_limit(email: dict) -> dict:
        async with semaphore:
            result = await parse_email(
                subject=email["subject"],
                sender=email["sender"],
                body=email["body"],
                snippet=email["snippet"],
            )
            result["_threadId"] = email["threadId"]
            result["_messageId"] = email["messageId"]
            return result

    return await asyncio.gather(*[parse_with_limit(e) for e in emails])


# ── Status Mapping ────────────────────────────────────────────────────────

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
    """Map Claude's email_type classification to an application status."""
    return EMAIL_TYPE_TO_STATUS.get(email_type)
