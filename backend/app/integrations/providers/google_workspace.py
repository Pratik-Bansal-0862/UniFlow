
import asyncio
from uuid import UUID

from app.integrations.interfaces import gmail, google_calendar
from app.schemas.tool import ToolRequest, ToolResult
from app.services.google_credentials import get_google_credentials


class GmailToolProvider:
    """Registry provider for safe Gmail read and draft operations."""

    name = "gmail"

    async def health_check(self) -> bool:
        return True

    async def execute(self, request: ToolRequest) -> ToolResult:
        supported_tools = {
            "gmail.list_messages",
            "gmail.get_message",
            "gmail.create_draft",
        }

        if request.tool_name not in supported_tools:
            return ToolResult(
                status="failed",
                error_code="unsupported_gmail_tool",
                message=(
                    "This Gmail tool is not available through the registry. "
                    "Email sending must use the approval-controlled API."
                ),
            )

        try:
            student_id = UUID(request.student_id)

            credentials = await asyncio.to_thread(
                get_google_credentials,
                student_id,
            )

            if credentials is None:
                return ToolResult(
                    status="failed",
                    error_code="google_not_connected",
                    message="Google is not connected for this student.",
                )

            arguments = request.arguments

            if request.tool_name == "gmail.list_messages":
                query = arguments.get("query")
                max_results = int(arguments.get("max_results", 20))

                if not 1 <= max_results <= 100:
                    raise ValueError(
                        "max_results must be between 1 and 100."
                    )

                messages = await asyncio.to_thread(
                    gmail.list_messages,
                    credentials,
                    query,
                    max_results,
                )

                data = {"messages": messages}

            elif request.tool_name == "gmail.get_message":
                message_id = str(
                    arguments.get("message_id", "")
                ).strip()

                if not message_id:
                    raise ValueError("message_id is required.")

                message = await asyncio.to_thread(
                    gmail.get_message,
                    credentials,
                    message_id,
                )

                data = {"message": message}

            else:
                recipient = str(
                    arguments.get("to", "")
                ).strip()
                subject = str(
                    arguments.get("subject", "")
                )
                body = str(
                    arguments.get("body", "")
                )

                if not recipient:
                    raise ValueError("to is required.")

                draft = await asyncio.to_thread(
                    gmail.create_draft,
                    credentials,
                    recipient,
                    subject,
                    body,
                )

                data = {"draft": draft}

            return ToolResult(
                status="succeeded",
                data=data,
                verified=True,
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                error_code="invalid_arguments",
                message=str(exc),
            )

        except Exception:
            return ToolResult(
                status="failed",
                error_code="gmail_operation_failed",
                message="The Gmail operation could not be completed.",
            )


class GoogleCalendarToolProvider:
    """Registry provider for safe Google Calendar read operations."""

    name = "calendar"

    async def health_check(self) -> bool:
        return True

    async def execute(self, request: ToolRequest) -> ToolResult:
        if request.tool_name != "calendar.list_events":
            return ToolResult(
                status="failed",
                error_code="approval_required",
                message=(
                    "Calendar event creation must use the existing "
                    "approval-controlled Calendar API."
                ),
            )

        try:
            student_id = UUID(request.student_id)

            credentials = await asyncio.to_thread(
                get_google_credentials,
                student_id,
            )

            if credentials is None:
                return ToolResult(
                    status="failed",
                    error_code="google_not_connected",
                    message="Google is not connected for this student.",
                )

            arguments = request.arguments
            max_results = int(arguments.get("max_results", 20))

            if not 1 <= max_results <= 100:
                raise ValueError(
                    "max_results must be between 1 and 100."
                )

            events = await asyncio.to_thread(
                google_calendar.list_events,
                credentials,
                arguments.get("time_min"),
                arguments.get("time_max"),
                max_results,
            )

            return ToolResult(
                status="succeeded",
                data={"events": events},
                verified=True,
            )

        except ValueError as exc:
            return ToolResult(
                status="failed",
                error_code="invalid_arguments",
                message=str(exc),
            )

        except Exception:
            return ToolResult(
                status="failed",
                error_code="calendar_operation_failed",
                message="The Calendar operation could not be completed.",
            )


def register_google_workspace_providers(registry) -> None:
    """Register Gmail and Calendar providers with the tool registry."""

    registry.register(GmailToolProvider())
    registry.register(GoogleCalendarToolProvider())
