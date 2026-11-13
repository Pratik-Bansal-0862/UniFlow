
import base64
import hashlib
import hmac
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID
from app.integrations.interfaces.gmail import send_draft as gmail_send_draft
import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.errors import HttpError
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_current_student, get_db
from app.integrations.interfaces.gmail import (
    create_draft as gmail_create_draft,
    get_message as gmail_get_message,
    list_messages as gmail_list_messages,
)
from app.models.agent_action import AgentAction
from app.models.student import Student
from app.services.action_service import (
    ActionError,
    create_action,
    claim_action_for_execution,
    complete_action,
    fail_action,
)
from app.integrations.interfaces.google_calendar import (
    GoogleCalendarError,
    create_event as calendar_create_event,
    list_events as calendar_list_events,
)

from app.services.approval_service import (
    ApprovalError,
    create_approval,
)
from app.services.google_token_store import (
    GoogleTokenError,
    delete_google_token,
    load_google_token,
    save_google_token,
)

from app.services.google_credentials import (
    GOOGLE_SCOPES,
    get_google_credentials,
)

router = APIRouter()

class GmailDraftRequest(BaseModel):
    to: str = Field(min_length=3, max_length=320)
    subject: str = Field(max_length=998)
    body: str = Field(min_length=1, max_length=100000)
    idempotency_key: str = Field(min_length=1, max_length=128)

class CalendarEventRequest(BaseModel):
    summary: str = Field(min_length=1, max_length=500)
    start: datetime
    end: datetime
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=1000)
    timezone_name: str = Field(default="UTC", min_length=1, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=128)

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
    return get_google_credentials(student_id)

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


# ---------------------------------------------------------------------
# Google OAuth endpoints
# ---------------------------------------------------------------------


@router.get("/connect")
def connect_google(
    current_student: Annotated[Student, Depends(get_current_student)],
):
    """Start Google OAuth for the authenticated UniFlow student."""
    try:
        state = _make_state(current_student.id)

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


# ---------------------------------------------------------------------
# Gmail read and search endpoints
# ---------------------------------------------------------------------


@router.get("/gmail/messages")
def get_gmail_messages(
    current_student: Annotated[Student, Depends(get_current_student)],
    q: str | None = Query(default=None, max_length=500),
    max_results: int = Query(default=20, ge=1, le=50),
):
    """Fetch recent Gmail messages or search using Gmail query syntax."""
    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            raise HTTPException(
                status_code=409,
                detail="Connect your Google account before accessing Gmail.",
            )

        messages = gmail_list_messages(
            credentials=credentials,
            query=q,
            max_results=max_results,
        )

        return {
            "messages": messages,
            "count": len(messages),
        }

    except HTTPException:
        raise

    except HttpError as exc:
        logging.exception("Gmail message listing failed")

        status_code = getattr(
            getattr(exc, "resp", None),
            "status",
            502,
        )
        if status_code not in (403, 404, 429):
            status_code = 502

        raise HTTPException(
            status_code=status_code,
            detail="Could not retrieve Gmail messages.",
        ) from exc

    except Exception as exc:
        logging.exception("Gmail message listing failed")

        raise HTTPException(
            status_code=502,
            detail="Could not retrieve Gmail messages.",
        ) from exc


@router.get("/gmail/messages/{message_id}")
def read_gmail_message(
    message_id: str,
    current_student: Annotated[Student, Depends(get_current_student)],
):
    """Read the full contents of one Gmail message."""
    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            raise HTTPException(
                status_code=409,
                detail="Connect your Google account before accessing Gmail.",
            )

        return gmail_get_message(
            credentials=credentials,
            message_id=message_id,
        )

    except HTTPException:
        raise

    except HttpError as exc:
        logging.exception("Gmail message retrieval failed")

        status_code = getattr(
            getattr(exc, "resp", None),
            "status",
            502,
        )
        if status_code not in (403, 404, 429):
            status_code = 502

        raise HTTPException(
            status_code=status_code,
            detail="Could not retrieve this Gmail message.",
        ) from exc

    except Exception as exc:
        logging.exception("Gmail message retrieval failed")

        raise HTTPException(
            status_code=502,
            detail="Could not retrieve this Gmail message.",
        ) from exc


# ---------------------------------------------------------------------
# Gmail draft and central approval endpoint
# ---------------------------------------------------------------------


@router.post("/gmail/drafts", status_code=201)
def create_gmail_draft_and_request_approval(
    payload: GmailDraftRequest,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a Gmail draft and submit its send action for approval.

    This endpoint does not send the email.
    Sending will happen only through the approved action executor.
    """

    body_hash = hashlib.sha256(
        payload.body.encode("utf-8")
    ).hexdigest()

    action_arguments = {
        "to": payload.to,
        "subject": payload.subject,
        "body_sha256": body_hash,
    }

    # Check idempotency before creating another Gmail draft.
    existing = db.execute(
        select(AgentAction).where(
            AgentAction.student_id == current_student.id,
            AgentAction.idempotency_key == payload.idempotency_key,
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing_arguments = existing.arguments or {}

        if (
            existing.tool_name != "gmail.send"
            or any(
                existing_arguments.get(key) != value
                for key, value in action_arguments.items()
            )
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency key was already used "
                    "for a different action."
                ),
            )

        return {
            "draft_id": existing_arguments.get("draft_id"),
            "action": existing,
        }

    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Connect your Google account before "
                    "creating Gmail drafts."
                ),
            )

        # Create a draft only. This does not send the email.
        draft = gmail_create_draft(
            credentials=credentials,
            to=payload.to,
            subject=payload.subject,
            body=payload.body,
        )

        action = create_action(
            db=db,
            student_id=current_student.id,
            tool_name="gmail.send",
            arguments={
                **action_arguments,
                "draft_id": draft["draft_id"],
            },
            idempotency_key=payload.idempotency_key,
        )

        create_approval(db, action)

        db.commit()
        db.refresh(action)

        return {
            "draft_id": draft["draft_id"],
            "action": action,
        }

    except HTTPException:
        db.rollback()
        raise

    except (ActionError, ApprovalError) as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except GoogleTokenError as exc:
        db.rollback()

        raise HTTPException(
            status_code=502,
            detail="Could not access stored Google credentials.",
        ) from exc

    except HttpError as exc:
        db.rollback()
        logging.exception("Gmail draft creation failed")

        status_code = getattr(
            getattr(exc, "resp", None),
            "status",
            502,
        )
        if status_code not in (403, 404, 429):
            status_code = 502

        raise HTTPException(
            status_code=status_code,
            detail="Could not create Gmail draft.",
        ) from exc

    except Exception as exc:
        db.rollback()
        logging.exception("Gmail draft approval request failed")

        raise HTTPException(
            status_code=502,
            detail="Could not create Gmail draft approval request.",
        ) from exc
@router.post("/gmail/actions/{action_id}/execute")
def execute_gmail_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # Confirm the action belongs to this student.
    candidate = db.execute(
        select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.student_id == current_student.id,
        )
    ).scalar_one_or_none()

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Action not found.",
        )

    if candidate.tool_name != "gmail.send":
        raise HTTPException(
            status_code=400,
            detail="This executor only supports gmail.send actions.",
        )

    # Claim only an approved action. The claim service also verifies
    # the approval, expiry, and payload hashes.
    try:
        action = claim_action_for_execution(
            db=db,
            action_id=action_id,
            student_id=current_student.id,
        )
        db.commit()
    except ActionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # Credentials must be available before attempting to send.
    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            fail_action(
                db,
                action,
                "google_credentials_unavailable",
            )
            db.commit()
            raise HTTPException(
                status_code=409,
                detail="Google account is not connected.",
            )

    except GoogleTokenError as exc:
        fail_action(
            db,
            action,
            "google_credentials_error",
        )
        db.commit()
        raise HTTPException(
            status_code=409,
            detail="Google credentials could not be loaded.",
        ) from exc

    # Send the exact draft recorded in the approved action.
    draft_id = action.arguments.get("draft_id")

    if not draft_id:
        fail_action(db, action, "gmail_draft_id_missing")
        db.commit()
        raise HTTPException(
            status_code=400,
            detail="The approved action has no Gmail draft ID.",
        )

    try:
        result = gmail_send_draft(
            credentials=credentials,
            draft_id=draft_id,
        )

        complete_action(db, action, result)
        db.commit()
        db.refresh(action)

        return {
            "id": str(action.id),
            "tool_name": action.tool_name,
            "status": action.status,
            "result": action.result,
            "error_code": action.error_code,
            "executed_at": action.executed_at,
        }

    except HTTPException:
        raise

    except Exception as exc:
        # A failed request may have reached Gmail even if its response
        # was lost. Do not make this action executable again.
        fail_action(
            db,
            action,
            "gmail_send_outcome_unknown",
        )
        db.commit()

        raise HTTPException(
            status_code=502,
            detail=(
                "Gmail send did not return a confirmed result. "
                "Check the Gmail Sent folder before taking further action."
            ),
        ) from exc

# ---------------------------------------------------------------------
# Google Calendar read and approval endpoints
# ---------------------------------------------------------------------


@router.get("/calendar/events")
def get_calendar_events(
    current_student: Annotated[Student, Depends(get_current_student)],
    time_min: datetime | None = Query(default=None),
    time_max: datetime | None = Query(default=None),
    max_results: int = Query(default=20, ge=1, le=100),
):
    """Fetch events from the student's primary Google Calendar."""

    if time_min and time_min.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail="time_min must include a timezone.",
        )

    if time_max and time_max.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail="time_max must include a timezone.",
        )

    if time_min and time_max and time_max <= time_min:
        raise HTTPException(
            status_code=400,
            detail="time_max must be later than time_min.",
        )

    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            raise HTTPException(
                status_code=409,
                detail="Connect your Google account before accessing Calendar.",
            )

        events = calendar_list_events(
            credentials=credentials,
            time_min=time_min.isoformat() if time_min else None,
            time_max=time_max.isoformat() if time_max else None,
            max_results=max_results,
        )

        return {
            "events": events,
            "count": len(events),
        }

    except HTTPException:
        raise

    except GoogleTokenError as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not access stored Google credentials.",
        ) from exc

    except (GoogleCalendarError, HttpError) as exc:
        logging.exception("Google Calendar event listing failed")
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve Google Calendar events.",
        ) from exc

    except Exception as exc:
        logging.exception("Google Calendar event listing failed")
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve Google Calendar events.",
        ) from exc


@router.post("/calendar/events", status_code=201)
def request_calendar_event_creation(
    payload: CalendarEventRequest,
    current_student: Annotated[Student, Depends(get_current_student)],
    db: Annotated[Session, Depends(get_db)],
):
    """
    Create a pending Calendar action.

    This endpoint does not create the event in Google Calendar.
    The event is created only after approval and execution.
    """

    if payload.start.tzinfo is None or payload.end.tzinfo is None:
        raise HTTPException(
            status_code=400,
            detail="Calendar event start and end must include timezones.",
        )

    if payload.end <= payload.start:
        raise HTTPException(
            status_code=400,
            detail="Event end must be later than event start.",
        )

    action_arguments = {
        "summary": payload.summary,
        "start": payload.start.isoformat(),
        "end": payload.end.isoformat(),
        "description": payload.description,
        "location": payload.location,
        "timezone_name": payload.timezone_name,
    }

    # Check idempotency before creating another action.
    existing = db.execute(
        select(AgentAction).where(
            AgentAction.student_id == current_student.id,
            AgentAction.idempotency_key == payload.idempotency_key,
        )
    ).scalar_one_or_none()

    if existing is not None:
        if (
            existing.tool_name != "calendar.create_event"
            or existing.arguments != action_arguments
        ):
            raise HTTPException(
                status_code=409,
                detail=(
                    "Idempotency key was already used "
                    "for a different action."
                ),
            )

        return {"action": existing}

    try:
        # No Google API call here. This only records the proposed action.
        action = create_action(
            db=db,
            student_id=current_student.id,
            tool_name="calendar.create_event",
            arguments=action_arguments,
            idempotency_key=payload.idempotency_key,
        )

        create_approval(db, action)

        db.commit()
        db.refresh(action)

        return {"action": action}

    except (ActionError, ApprovalError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        db.rollback()
        logging.exception("Calendar event approval request failed")
        raise HTTPException(
            status_code=500,
            detail="Could not create Calendar event approval request.",
        ) from exc

@router.post("/calendar/actions/{action_id}/execute")
def execute_calendar_action(
    action_id: UUID,
    db: Session = Depends(get_db),
    current_student: Student = Depends(get_current_student),
):
    # Confirm the action belongs to this student.
    candidate = db.execute(
        select(AgentAction).where(
            AgentAction.id == action_id,
            AgentAction.student_id == current_student.id,
        )
    ).scalar_one_or_none()

    if candidate is None:
        raise HTTPException(
            status_code=404,
            detail="Action not found.",
        )

    if candidate.tool_name != "calendar.create_event":
        raise HTTPException(
            status_code=400,
            detail="This executor only supports calendar.create_event actions.",
        )

    # Claim only an approved action. This verifies approval, expiry,
    # ownership and payload hashes.
    try:
        action = claim_action_for_execution(
            db=db,
            action_id=action_id,
            student_id=current_student.id,
        )
        db.commit()

    except ActionError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    # Load credentials after claiming the action.
    try:
        credentials = _get_credentials(current_student.id)

        if credentials is None:
            fail_action(
                db,
                action,
                "google_credentials_unavailable",
            )
            db.commit()

            raise HTTPException(
                status_code=409,
                detail="Google account is not connected.",
            )

    except GoogleTokenError as exc:
        fail_action(
            db,
            action,
            "google_credentials_error",
        )
        db.commit()

        raise HTTPException(
            status_code=409,
            detail="Google credentials could not be loaded.",
        ) from exc

    arguments = action.arguments or {}

    try:
        result = calendar_create_event(
            credentials=credentials,
            summary=arguments["summary"],
            start=datetime.fromisoformat(arguments["start"]),
            end=datetime.fromisoformat(arguments["end"]),
            description=arguments.get("description"),
            location=arguments.get("location"),
            timezone_name=arguments.get("timezone_name", "UTC"),
        )

        complete_action(db, action, result)
        db.commit()
        db.refresh(action)

        return {
            "id": str(action.id),
            "tool_name": action.tool_name,
            "status": action.status,
            "result": action.result,
            "error_code": action.error_code,
            "executed_at": action.executed_at,
        }

    except Exception as exc:
        # The request may have reached Google even if its response
        # was lost. Do not permit this action to be executed again.
        db.rollback()

        fail_action(
            db,
            action,
            "calendar_create_outcome_unknown",
        )
        db.commit()

        logging.exception("Google Calendar event creation failed")

        raise HTTPException(
            status_code=502,
            detail=(
                "Calendar event creation did not return a confirmed result. "
                "Check Google Calendar before taking further action."
            ),
        ) from exc
