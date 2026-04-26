"""
Auth router — handles user registration and Gmail token storage.

Supports two flows:
1. Firebase popup flow: Frontend sends idToken + accessToken directly
2. Authorization code flow (future): Frontend sends idToken + code for exchange

The popup flow doesn't give us a refresh token, so the access token
will expire in ~1 hour. The user will need to re-sign-in to sync again.
For persistent access, switch to the authorization code flow later.
"""

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from app.config import settings
from app.services.firestore_service import get_user, create_or_update_user
import firebase_admin.auth as fb_auth
import httpx
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class AuthCallbackRequest(BaseModel):
    """Request body for the OAuth callback."""
    id_token: str
    access_token: Optional[str] = None  # Direct access token from Firebase popup
    code: Optional[str] = None  # Authorization code for server-side exchange


class AuthStatusResponse(BaseModel):
    """Response for auth status check."""
    authenticated: bool
    has_gmail_access: bool
    email: str | None = None


@router.post("/callback")
async def auth_callback(body: AuthCallbackRequest):
    """
    Store Gmail access tokens after Google sign-in.

    Accepts either:
    - access_token: directly from Firebase signInWithPopup (simpler, no refresh token)
    - code: authorization code for server-side exchange (gives refresh token)
    """
    # Step 1: Verify Firebase ID token
    try:
        decoded = fb_auth.verify_id_token(body.id_token)
        uid = decoded["uid"]
        email = decoded.get("email", "")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Firebase token: {str(e)}")

    access_token = None
    refresh_token = None

    # Step 2a: If we got an authorization code, exchange it for tokens
    if body.code and body.code != "":
        try:
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "code": body.code,
                        "client_id": settings.google_client_id,
                        "client_secret": settings.google_client_secret,
                        "redirect_uri": settings.google_redirect_uri,
                        "grant_type": "authorization_code",
                    },
                )

            if token_response.status_code == 200:
                tokens = token_response.json()
                access_token = tokens["access_token"]
                refresh_token = tokens.get("refresh_token")
                logger.info(f"Token exchange successful for {email}")
            else:
                logger.warning(f"Token exchange failed, falling back to direct token: {token_response.text[:200]}")
        except Exception as e:
            logger.warning(f"Token exchange error, falling back to direct token: {e}")

    # Step 2b: If no code or exchange failed, use the direct access token
    if not access_token and body.access_token:
        access_token = body.access_token
        logger.info(f"Using direct access token for {email} (no refresh token)")

    if not access_token:
        raise HTTPException(
            status_code=400,
            detail="No access token available. Please sign in again."
        )

    # Validate that the token actually has the Gmail scope
    try:
        async with httpx.AsyncClient() as client:
            token_info_res = await client.get(f"https://oauth2.googleapis.com/tokeninfo?access_token={access_token}")
            if token_info_res.status_code == 200:
                token_info = token_info_res.json()
                scopes = token_info.get("scope", "")
                if "https://www.googleapis.com/auth/gmail.readonly" not in scopes:
                    raise HTTPException(
                        status_code=403,
                        detail="Gmail permission missing! When signing in, you MUST check the box to allow Job Tracker to read your emails."
                    )
            else:
                logger.warning(f"Failed to validate token info: {token_info_res.text}")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Error checking token scopes: {e}")

    # Preserve existing refresh token if we have one
    if not refresh_token:
        existing_user = await get_user(uid)
        if existing_user and existing_user.get("gmailRefreshToken"):
            refresh_token = existing_user["gmailRefreshToken"]

    # Step 3: Store user data + tokens in Firestore
    now = datetime.now(timezone.utc).isoformat()
    user_data = {
        "uid": uid,
        "email": email,
        "gmailAccessToken": access_token,
        "createdAt": now,
    }
    if refresh_token:
        user_data["gmailRefreshToken"] = refresh_token

    await create_or_update_user(uid, user_data)

    return {
        "success": True,
        "uid": uid,
        "email": email,
        "hasRefreshToken": bool(refresh_token),
        "message": "Gmail access granted successfully",
    }


@router.get("/status")
async def auth_status(authorization: str = Header(None)):
    """
    Check if the current user has valid Gmail tokens stored.
    Used by the frontend to determine if re-authorization is needed.
    """
    if not authorization:
        return AuthStatusResponse(authenticated=False, has_gmail_access=False)

    token = authorization.replace("Bearer ", "")
    try:
        decoded = fb_auth.verify_id_token(token)
        uid = decoded["uid"]
    except Exception:
        return AuthStatusResponse(authenticated=False, has_gmail_access=False)

    user = await get_user(uid)
    if not user:
        return AuthStatusResponse(
            authenticated=True,
            has_gmail_access=False,
            email=decoded.get("email"),
        )

    has_tokens = bool(user.get("gmailAccessToken"))
    return AuthStatusResponse(
        authenticated=True,
        has_gmail_access=has_tokens,
        email=user.get("email"),
    )
