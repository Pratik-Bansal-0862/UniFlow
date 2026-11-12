
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.services.google_token_store import (
    GoogleTokenError,
    delete_google_token,
    load_google_token,
    save_google_token,
)

router = APIRouter()

GOOGLE_SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


def _validate_google_config() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured on the backend.",
        )


def _code_verifier_for_state(state: str) -> str:
    """
    Generate a deterministic PKCE verifier from the signed OAuth state.

    This allows the connect and callback requests to independently
    reconstruct the same verifier without storing it in a session.
    """
    secret = settings.jwt_secret_key.encode("utf-8")

    digest = hmac.new(
        secret,
        state.encode("utf-8"),
        hashlib.sha256,
    ).digest()

    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _new_flow(state: str | None = None) -> Flow:
    _validate_google_config()

    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }

    flow_options = {}

    if state:
        flow_options["code_verifier"] = _code_verifier_for_state(state)
        flow_options["autogenerate_code_verifier"] = False

    flow = Flow.from_client_config(
        client_config,
        scopes=GOOGLE_SCOPES,
        state=state,
        **flow_options,
    )

    flow.redirect_uri = settings.google_redirect_uri
    return flow


def _make_state(student_id: UUID) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(student_id),
        "purpose": "google_oauth",
        "iat": now,
        "exp": now + timedelta(minutes=10),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def _student_from_state(state: str, db: Session) -> Student:
    try:
        payload = jwt.decode(
            state,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        if payload.get("purpose") != "google_oauth":
            raise ValueError("Invalid OAuth state purpose.")

        student_id = UUID(payload["sub"])

    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired Google OAuth state.",
        ) from None

    student = db.scalar(
        select(Student).where(
            Student.id == student_id,
            Student.is_active.is_(True),
        )
    )

    if student is None:
        raise HTTPException(
            status_code=400,
            detail="The associated UniFlow account was not found.",
        )

    return student


def credentials_to_dict(credentials: Credentials) -> dict:
    return json.loads(credentials.to_json())


def _get_credentials(student_id: UUID) -> Credentials | None:
    token_data = load_google_token(student_id)

    if token_data is None:
        return None

    credentials = Credentials.from_authorized_user_info(
        token_data,
        GOOGLE_SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(GoogleRequest())

        save_google_token(
            student_id,
            credentials_to_dict(credentials),
        )

    return credentials


@router.get("/connect")
def connect_google(
    current_student: Annotated[Student, Depends(get_current_student)],
):
    """Start Google OAuth for the authenticated UniFlow student."""
    try:
        state = _make_state(current_student.id)

        # Use the same deterministic PKCE verifier in the callback.
        flow = _new_flow(state=state)

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )

        return {
            "authorization_url": authorization_url,
            "message": "Open authorization_url to connect Google.",
        }

    except HTTPException:
        raise

    except Exception as exc:
        logging.exception("Could not start Google authorization")

        raise HTTPException(
            status_code=500,
            detail="Could not start Google authorization.",
        ) from exc


@router.get("/callback")
def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Handle Google's redirect. OAuth state identifies the student."""
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Google authorization was not completed: {error}",
        )

    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Google did not return the required authorization data.",
        )

    student = _student_from_state(state, db)

    try:
        # Reconstruct the exact PKCE verifier used during /connect.
        flow = _new_flow(state=state)

        flow.fetch_token(code=code)

        credentials = flow.credentials

        if not credentials.refresh_token:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google did not return a refresh token. "
                    "Disconnect UniFlow in your Google account permissions "
                    "and try connecting again."
                ),
            )

        save_google_token(
            student.id,
            credentials_to_dict(credentials),
        )

        return {
            "connected": True,
            "provider": "google",
            "student_email": student.email,
            "message": "Google account connected successfully.",
        }

    except HTTPException:
        raise

    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception:
        logging.exception("Google OAuth callback failed")

        raise HTTPException(
            status_code=400,
            detail=(
                "Google authorization failed. "
                "Check backend logs for details."
            ),
        ) from None


@router.get("/status")
def google_status(
    current_student: Annotated[Student, Depends(get_current_student)],
):
    """Check whether the current student has connected Google."""
    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            return {
                "connected": False,
                "provider": "google",
            }

        return {
            "connected": True,
            "provider": "google",
            "scopes": credentials.scopes or [],
            "has_refresh_token": bool(credentials.refresh_token),
        }

    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    except Exception:
        logging.exception("Google connection status check failed")

        raise HTTPException(
            status_code=500,
            detail="Could not check Google connection.",
        ) from None


@router.delete("/disconnect")
def disconnect_google(
    current_student: Annotated[Student, Depends(get_current_student)],
):
    """Remove the current student's locally stored Google credentials."""
    try:
        deleted = delete_google_token(current_student.id)

        return {
            "disconnected": True,
            "removed_local_credentials": deleted,
        }

    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc
