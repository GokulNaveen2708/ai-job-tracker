"""
Gemini AI email parsing service.

Drop-in replacement for claude_service.py using Google's Gemini API.
Same interface (parse_email, parse_emails_batch, email_type_to_status)
so the sync router doesn't need to know which AI is being used.
"""

import google.generativeai as genai
import asyncio
import json
import logging
from app.config import settings

logger = logging.getLogger(__name__)

# ── Configure Gemini ───────────────────────────────────────────────────
genai.configure(api_key=settings.gemini_api_key)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    generation_config={
        "temperature": 0.2,
        "max_output_tokens": 400,
        "response_mime_type": "application/json",
    },
)

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
    Falls back gracefully if Gemini returns malformed JSON.
    """
    user_message = f"""Subject: {subject}
From: {sender}
Snippet: {snippet}

Body:
{body[:3000]}"""

    try:
        # Gemini's SDK is synchronous, so we run it in a thread
        response = await asyncio.to_thread(
            model.generate_content,
            [
                {"role": "user", "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_message}]},
            ],
        )

        raw = response.text.strip()
        logger.debug(f"Gemini raw response: {raw[:300]}")

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

    except (json.JSONDecodeError, IndexError, KeyError, Exception) as e:
        logger.warning(f"Gemini parse error for '{subject[:50]}': {e}")
        return {
            "company": extract_company_from_sender(sender),
            "role": "Unknown Role",
            "email_type": "unknown",
            "confidence": 0.1,
            "reasoning": f"Gemini returned malformed response; used fallback. Error: {str(e)[:100]}",
        }


def _default_for_field(field: str, sender: str):
    """Provide defaults for missing fields in Gemini's response."""
    defaults = {
        "company": extract_company_from_sender(sender),
        "role": "Unknown Role",
        "email_type": "unknown",
        "confidence": 0.3,
        "reasoning": "Field was missing from Gemini response",
    }
    return defaults.get(field, "")


def extract_company_from_sender(sender: str) -> str:
    """Naive fallback: extract domain from email address."""
    try:
        if "<" in sender:
            sender = sender.split("<")[1].split(">")[0]
        domain = sender.split("@")[1].split(".")[0]
        return domain.capitalize()
    except (IndexError, AttributeError):
        return "Unknown Company"


# ── Batch Processing ──────────────────────────────────────────────────

async def parse_emails_batch(
    emails: list[dict],
    max_concurrent: int = 2
) -> list[dict]:
    """
    Parse multiple emails with rate-limit-friendly pacing.
    Sends max_concurrent at a time with delays to stay under
    the Gemini free tier limit (15 RPM).
    """
    results = []

    for i in range(0, len(emails), max_concurrent):
        batch = emails[i:i + max_concurrent]
        logger.info(f"Parsing batch {i // max_concurrent + 1} ({len(batch)} emails)")

        tasks = []
        for email in batch:
            tasks.append(parse_email(
                subject=email["subject"],
                sender=email["sender"],
                body=email["body"],
                snippet=email["snippet"],
            ))

        batch_results = await asyncio.gather(*tasks)

        for email, result in zip(batch, batch_results):
            result["_threadId"] = email["threadId"]
            result["_messageId"] = email["messageId"]
            results.append(result)

        # Wait between batches to respect rate limits (15 RPM)
        # 10 second delay for a batch of 2 = 12 requests per minute (very safe)
        if i + max_concurrent < len(emails):
            await asyncio.sleep(10)

    return results


# ── Status Mapping ────────────────────────────────────────────────────

EMAIL_TYPE_TO_STATUS = {
    "application_confirm": "applied",
    "oa_invite": "oa",
    "interview_invite": "interview",
    "offer": "offer",
    "rejection": "rejected",
    "follow_up": "applied",  # follow-ups still indicate an active application
    "unknown": None,
}


def email_type_to_status(email_type: str) -> str | None:
    """Map email_type classification to an application status."""
    return EMAIL_TYPE_TO_STATUS.get(email_type)
