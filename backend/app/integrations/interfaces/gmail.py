from email.mime.text import MIMEText
import base64
from html.parser import HTMLParser
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
import socket

_original_getaddrinfo = socket.getaddrinfo


def _gmail_ipv4_getaddrinfo(
    host, port, family=0, type=0, proto=0, flags=0
):
    results = _original_getaddrinfo(
        host, port, family, type, proto, flags
    )

    if isinstance(host, str) and host.lower() == "gmail.googleapis.com":
        ipv4_results = [
            result for result in results
            if result[0] == socket.AF_INET
        ]
        if ipv4_results:
            return ipv4_results

    return results


socket.getaddrinfo = _gmail_ipv4_getaddrinfo


class _HTMLTextExtractor(HTMLParser):
    """Convert HTML email bodies into readable text."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.parts)


def _gmail_service(credentials: Credentials) -> Any:
    return build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )


def _decode_body(data: str) -> str:
    if not data:
        return ""

    padded = data + "=" * (-len(data) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    return decoded.decode("utf-8", errors="replace")


def _extract_body(payload: dict) -> str:
    plain_parts: list[str] = []
    html_parts: list[str] = []

    def visit(part: dict) -> None:
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")

        if body_data and mime_type in ("text/plain", "text/html"):
            decoded = _decode_body(body_data)

            if mime_type == "text/plain":
                plain_parts.append(decoded)
            else:
                html_parts.append(decoded)

        for child in part.get("parts", []):
            visit(child)

    visit(payload)

    if plain_parts:
        return "\n".join(plain_parts)

    if html_parts:
        parser = _HTMLTextExtractor()
        for html in html_parts:
            parser.feed(html)
        return parser.get_text()

    return ""


def _headers(payload: dict) -> dict[str, str]:
    return {
        item["name"].lower(): item["value"]
        for item in payload.get("headers", [])
        if "name" in item and "value" in item
    }


def list_messages(
    credentials: Credentials,
    query: str | None = None,
    max_results: int = 20,
) -> list[dict]:
    """Fetch recent Gmail messages, optionally filtered by Gmail search syntax."""
    service = _gmail_service(credentials)

    params: dict[str, Any] = {
        "userId": "me",
        "maxResults": max_results,
    }

    if query:
        params["q"] = query

    result = service.users().messages().list(**params).execute()
    messages = result.get("messages", [])

    output = []

    for message in messages:
        details = (
            service.users()
            .messages()
            .get(
                userId="me",
                id=message["id"],
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            .execute()
        )

        headers = _headers(details.get("payload", {}))

        output.append({
            "id": details["id"],
            "thread_id": details.get("threadId"),
            "snippet": details.get("snippet", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", "(No subject)"),
            "date": headers.get("date", ""),
            "labels": details.get("labelIds", []),
        })

    return output


def get_message(
    credentials: Credentials,
    message_id: str,
) -> dict:
    """Retrieve a complete Gmail message and its readable body."""
    service = _gmail_service(credentials)

    message = (
        service.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="full",
        )
        .execute()
    )

    payload = message.get("payload", {})
    headers = _headers(payload)

    return {
        "id": message["id"],
        "thread_id": message.get("threadId"),
        "snippet": message.get("snippet", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "subject": headers.get("subject", "(No subject)"),
        "date": headers.get("date", ""),
        "body": _extract_body(payload),
        "labels": message.get("labelIds", []),
    }

def create_draft(
    credentials: Credentials,
    to: str,
    subject: str,
    body: str,
) -> dict:
    """Create a Gmail draft without sending it."""

    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to
    message["subject"] = subject

    raw_message = base64.urlsafe_b64encode(
        message.as_bytes()
    ).decode("utf-8")

    service = _gmail_service(credentials)

    draft = (
        service.users()
        .drafts()
        .create(
            userId="me",
            body={
                "message": {
                    "raw": raw_message,
                }
            },
        )
        .execute()
    )

    message_data = draft.get("message", {})

    return {
        "draft_id": draft["id"],
        "message_id": message_data.get("id"),
        "thread_id": message_data.get("threadId"),
    }


def send_draft(
    credentials: Credentials,
    draft_id: str,
) -> dict:
    """Send an existing Gmail draft."""

    if not draft_id:
        raise ValueError("Gmail draft ID is required.")

    service = _gmail_service(credentials)

    sent_message = (
        service.users()
        .drafts()
        .send(
            userId="me",
            body={"id": draft_id},
        )
        .execute()
    )

    return {
        "message_id": sent_message.get("id"),
        "thread_id": sent_message.get("threadId"),
        "label_ids": sent_message.get("labelIds", []),
    }
