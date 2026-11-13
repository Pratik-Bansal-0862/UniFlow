import asyncio

import pytest

from app.integrations.providers import google_workspace
from app.schemas.tool import ToolRequest


STUDENT_ID = "11111111-1111-4111-8111-111111111111"


def make_request(tool_name, arguments=None):
    return ToolRequest(
        tool_name=tool_name,
        student_id=STUDENT_ID,
        arguments=arguments or {},
        idempotency_key="provider-test-key",
    )


@pytest.mark.parametrize(
    ("tool_name", "arguments", "mock_name", "expected_data"),
    [
        (
            "gmail.list_messages",
            {"query": "is:unread", "max_results": 10},
            "list_messages",
            {"messages": [{"id": "message-1", "subject": "Test"}]},
        ),
        (
            "gmail.get_message",
            {"message_id": "message-1"},
            "get_message",
            {"message": {"id": "message-1", "body": "Hello"}},
        ),
    ],
)
def test_gmail_read_operations(
    monkeypatch, tool_name, arguments, mock_name, expected_data
):
    credentials = object()
    monkeypatch.setattr(
        google_workspace,
        "get_google_credentials",
        lambda student_id: credentials,
    )

    expected_result = (
        expected_data["messages"]
        if mock_name == "list_messages"
        else expected_data["message"]
    )
    monkeypatch.setattr(
        google_workspace.gmail,
        mock_name,
        lambda *args: expected_result,
    )

    result = asyncio.run(
        google_workspace.GmailToolProvider().execute(
            make_request(tool_name, arguments)
        )
    )

    assert result.status == "succeeded"
    assert result.verified is True
    assert result.data == expected_data


def test_gmail_create_draft(monkeypatch):
    credentials = object()
    expected_draft = {
        "draft_id": "draft-1",
        "message_id": "message-1",
    }

    monkeypatch.setattr(
        google_workspace,
        "get_google_credentials",
        lambda student_id: credentials,
    )
    monkeypatch.setattr(
        google_workspace.gmail,
        "create_draft",
        lambda *args: expected_draft,
    )

    result = asyncio.run(
        google_workspace.GmailToolProvider().execute(
            make_request(
                "gmail.create_draft",
                {
                    "to": "student@example.com",
                    "subject": "Test subject",
                    "body": "Test body",
                },
            )
        )
    )

    assert result.status == "succeeded"
    assert result.data == {"draft": expected_draft}


def test_calendar_list_events(monkeypatch):
    credentials = object()
    expected_events = [
        {"id": "event-1", "summary": "Study session"}
    ]

    monkeypatch.setattr(
        google_workspace,
        "get_google_credentials",
        lambda student_id: credentials,
    )
    monkeypatch.setattr(
        google_workspace.google_calendar,
        "list_events",
        lambda *args: expected_events,
    )

    result = asyncio.run(
        google_workspace.GoogleCalendarToolProvider().execute(
            make_request(
                "calendar.list_events",
                {
                    "time_min": "2026-11-01T00:00:00Z",
                    "time_max": "2026-11-30T23:59:59Z",
                    "max_results": 15,
                },
            )
        )
    )

    assert result.status == "succeeded"
    assert result.verified is True
    assert result.data == {"events": expected_events}


@pytest.mark.parametrize(
    ("provider", "tool_name"),
    [
        (google_workspace.GmailToolProvider(), "gmail.list_messages"),
        (
            google_workspace.GoogleCalendarToolProvider(),
            "calendar.list_events",
        ),
    ],
)
def test_provider_reports_google_not_connected(
    monkeypatch, provider, tool_name
):
    monkeypatch.setattr(
        google_workspace,
        "get_google_credentials",
        lambda student_id: None,
    )

    result = asyncio.run(
        provider.execute(make_request(tool_name))
    )

    assert result.status == "failed"
    assert result.error_code == "google_not_connected"


@pytest.mark.parametrize(
    ("provider", "tool_name", "expected_error"),
    [
        (
            google_workspace.GmailToolProvider(),
            "gmail.send_message",
            "unsupported_gmail_tool",
        ),
        (
            google_workspace.GoogleCalendarToolProvider(),
            "calendar.create_event",
            "approval_required",
        ),
    ],
)
def test_registry_providers_block_unapproved_write_operations(
    provider, tool_name, expected_error
):
    result = asyncio.run(
        provider.execute(make_request(tool_name))
    )

    assert result.status == "failed"
    assert result.error_code == expected_error
