
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_action import AgentAction
from app.models.approval import Approval
from app.services.approval_service import calculate_payload_hash


class ActionError(Exception):
    """Raised when an action cannot safely be created or executed."""


def create_action(
    db: Session,
    student_id: UUID,
    tool_name: str,
    arguments: dict,
    idempotency_key: str,
) -> AgentAction:
    """Create an action or return an identical existing idempotent action."""

    if not tool_name or not tool_name.strip():
        raise ActionError("Tool name is required.")

    if not idempotency_key or not idempotency_key.strip():
        raise ActionError("Idempotency key is required.")

    if len(tool_name) > 100:
        raise ActionError("Tool name is too long.")

    if len(idempotency_key) > 128:
        raise ActionError("Idempotency key is too long.")

    arguments = arguments or {}
    payload_hash = calculate_payload_hash(tool_name, arguments)

    existing = db.execute(
        select(AgentAction).where(
            AgentAction.student_id == student_id,
            AgentAction.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()

    if existing is not None:
        if existing.payload_hash != payload_hash:
            raise ActionError(
                "Idempotency key was already used for a different action."
            )
        return existing

    action = AgentAction(
        student_id=student_id,
        tool_name=tool_name,
        arguments=arguments,
        payload_hash=payload_hash,
        idempotency_key=idempotency_key,
        status="pending_approval",
    )

    db.add(action)
    db.flush()
    return action


def claim_action_for_execution(
    db: Session,
    action_id: UUID,
    student_id: UUID,
) -> AgentAction:
    """Atomically claim an approved action before external execution."""

    action = db.execute(
        select(AgentAction)
        .where(
            AgentAction.id == action_id,
            AgentAction.student_id == student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if action is None:
        raise ActionError("Action not found.")

    if action.status != "approved":
        raise ActionError(
            "Action is not approved or has already been claimed."
        )

    approval = db.execute(
        select(Approval)
        .where(
            Approval.action_id == action.id,
            Approval.student_id == student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if approval is None:
        raise ActionError("Approval not found.")

    if approval.status != "approved":
        raise ActionError("Approval is not valid.")

    now = datetime.now(timezone.utc)

    if approval.expires_at is not None:
        expiry = approval.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry <= now:
            raise ActionError("Approval has expired.")

    expected_hash = calculate_payload_hash(
        action.tool_name,
        action.arguments or {},
    )

    if action.payload_hash != expected_hash:
        raise ActionError(
            "Action payload has changed since it was created."
        )

    if approval.payload_hash != expected_hash:
        raise ActionError(
            "Approved payload does not match the action payload."
        )

    action.status = "executing"
    db.flush()
    return action


def complete_action(
    db: Session,
    action: AgentAction,
    result: dict,
) -> AgentAction:
    """Record a successful external action."""

    if action.status != "executing":
        raise ActionError("Only executing actions can be completed.")

    action.status = "succeeded"
    action.result = result
    action.error_code = None
    action.executed_at = datetime.now(timezone.utc)
    db.flush()
    return action


def fail_action(
    db: Session,
    action: AgentAction,
    error_code: str,
) -> AgentAction:
    """Record a failed external action without exposing sensitive details."""

    if action.status != "executing":
        raise ActionError("Only executing actions can be failed.")

    action.status = "failed"
    action.result = None
    action.error_code = error_code[:100]
    action.executed_at = datetime.now(timezone.utc)
    db.flush()
    return action
