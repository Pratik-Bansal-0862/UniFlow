
from uuid import UUID

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from app.services.google_token_store import (
    load_google_token,
    save_google_token,
)

GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.events",
]


def get_google_credentials(
    student_id: UUID,
) -> Credentials | None:
    """Load and refresh a student's stored Google credentials."""
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
            credentials.to_json() and __import__("json").loads(
                credentials.to_json()
            ),
        )

    return credentials
