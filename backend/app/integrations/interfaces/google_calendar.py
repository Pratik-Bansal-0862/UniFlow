
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


class GoogleCalendarError(Exception):
    """Raised when a Google Calendar operation fails."""


def _calendar_service(credentials):
    return build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def list_events(
    credentials,
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 20,
):
    """List events from the user's primary Google Calendar."""

    if not 1 <= max_results <= 100:
        raise ValueError("max_results must be between 1 and 100.")

    try:
        service = _calendar_service(credentials)

        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=time_min,
                timeMax=time_max,
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = []

        for event in response.get("items", []):
            events.append(
                {
                    "id": event.get("id"),
                    "summary": event.get("summary"),
                    "description": event.get("description"),
                    "location": event.get("location"),
                    "start": event.get("start"),
                    "end": event.get("end"),
                    "status": event.get("status"),
                    "html_link": event.get("htmlLink"),
                }
            )

        return events

    except HttpError as exc:
        raise GoogleCalendarError(
            "Could not retrieve Google Calendar events."
        ) from exc


def create_event(
    credentials,
    summary: str,
    start: datetime,
    end: datetime,
    description: str | None = None,
    location: str | None = None,
    timezone_name: str = "UTC",
):
    """Create an event in the user's primary Google Calendar."""

    if not summary.strip():
        raise ValueError("Event summary cannot be empty.")

    if end <= start:
        raise ValueError("Event end must be after its start.")

    event_body: dict[str, Any] = {
        "summary": summary,
        "start": {
            "dateTime": start.isoformat(),
            "timeZone": timezone_name,
        },
        "end": {
            "dateTime": end.isoformat(),
            "timeZone": timezone_name,
        },
    }

    if description:
        event_body["description"] = description

    if location:
        event_body["location"] = location

    try:
        service = _calendar_service(credentials)

        event = (
            service.events()
            .insert(
                calendarId="primary",
                body=event_body,
            )
            .execute()
        )

        return {
            "id": event.get("id"),
            "summary": event.get("summary"),
            "start": event.get("start"),
            "end": event.get("end"),
            "html_link": event.get("htmlLink"),
            "status": event.get("status"),
        }

    except HttpError as exc:
        raise GoogleCalendarError(
            "Could not create Google Calendar event."
        ) from exc
