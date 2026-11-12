
import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_action import AgentAction
from app.models.approval import Approval


class ApprovalError(Exception):
    """Raised when an approval cannot safely be created or changed."""


def calculate_payload_hash(
    tool_name: str,
    arguments: dict,
) -> str:
    """Create a deterministic hash of the exact action being approved."""
    payload = {
        "tool_name": tool_name,
        "arguments": arguments,
    }

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        canonical_payload.encode("utf-8")
    ).hexdigest()


def _verify_action_hash(action: AgentAction) -> None:
    expected_hash = calculate_payload_hash(
        action.tool_name,
        action.arguments or {},
    )

    if action.payload_hash != expected_hash:
        raise ApprovalError(
            "Action payload has changed or its hash is invalid."
        )


def create_approval(
    db: Session,
    action: AgentAction,
    expires_at: datetime | None = None,
) -> Approval:
    """Create one pending approval for an unchanged action."""

    if action.status != "pending_approval":
        raise ApprovalError(
            "Only actions pending approval can be submitted for approval."
        )

    _verify_action_hash(action)

    existing = db.execute(
        select(Approval).where(
            Approval.action_id == action.id
        )
    ).scalar_one_or_none()

    if existing is not None:
        raise ApprovalError(
            "An approval already exists for this action."
        )

    approval = Approval(
        action_id=action.id,
        student_id=action.student_id,
        payload_hash=action.payload_hash,
        status="pending",
        expires_at=expires_at,
    )

    db.add(approval)
    db.flush()

    return approval


def decide_approval(
    db: Session,
    approval_id: UUID,
    student_id: UUID,
    decision: str,
) -> Approval:
    """Approve or reject an action after verifying ownership and integrity."""

    if decision not in {"approve", "reject"}:
        raise ApprovalError("Decision must be approve or reject.")

    approval = db.execute(
        select(Approval)
        .where(
            Approval.id == approval_id,
            Approval.student_id == student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if approval is None:
        raise ApprovalError("Approval not found.")

    if approval.status != "pending":
        raise ApprovalError(
            "This approval is no longer pending."
        )

    now = datetime.now(timezone.utc)

    if approval.expires_at is not None:
        expiry = approval.expires_at

        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if expiry <= now:
            approval.status = "expired"
            approval.reviewed_at = now
            db.flush()
            return approval

    action = db.execute(
        select(AgentAction)
        .where(
            AgentAction.id == approval.action_id,
            AgentAction.student_id == student_id,
        )
        .with_for_update()
    ).scalar_one_or_none()

    if action is None:
        raise ApprovalError("Associated action not found.")

    if action.status != "pending_approval":
        raise ApprovalError(
            "The associated action is no longer awaiting approval."
        )

    _verify_action_hash(action)

    if approval.payload_hash != action.payload_hash:
        raise ApprovalError(
            "The action differs from the payload originally reviewed."
        )

    approval.reviewed_at = now

    if decision == "approve":
        approval.status = "approved"
        action.status = "approved"
    else:
        approval.status = "rejected"
        action.status = "rejected"

    db.flush()

    return approval
