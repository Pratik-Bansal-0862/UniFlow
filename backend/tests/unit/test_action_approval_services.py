
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.student import Student
from app.models.agent_action import AgentAction
from app.models.approval import Approval
from app.services.action_service import (
    ActionError,
    claim_action_for_execution,
    create_action,
)
from app.services.approval_service import (
    ApprovalError,
    create_approval,
    decide_approval,
)


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(
        engine,
        tables=[
            Student.__table__,
            AgentAction.__table__,
            Approval.__table__,
        ],
    )

    TestingSession = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )

    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(
            engine,
            tables=[
                Approval.__table__,
                AgentAction.__table__,
                Student.__table__,
            ],
        )
        engine.dispose()


def make_student(db):
    student = Student(
        email=f"{uuid.uuid4()}@example.com",
    )
    db.add(student)
    db.flush()
    return student


def make_action(db, student):
    return create_action(
        db=db,
        student_id=student.id,
        tool_name="gmail.create_draft",
        arguments={"subject": "Test"},
        idempotency_key=str(uuid.uuid4()),
    )


def test_create_action_is_idempotent(db):
    student = make_student(db)
    key = str(uuid.uuid4())

    first = create_action(
        db,
        student.id,
        "gmail.create_draft",
        {"subject": "Test"},
        key,
    )

    second = create_action(
        db,
        student.id,
        "gmail.create_draft",
        {"subject": "Test"},
        key,
    )

    assert first.id == second.id


def test_idempotency_key_rejects_different_payload(db):
    student = make_student(db)
    key = str(uuid.uuid4())

    create_action(
        db,
        student.id,
        "gmail.create_draft",
        {"subject": "First"},
        key,
    )

    with pytest.raises(ActionError):
        create_action(
            db,
            student.id,
            "gmail.create_draft",
            {"subject": "Different"},
            key,
        )


def test_approval_and_execution_require_valid_approval(db):
    student = make_student(db)
    action = make_action(db, student)

    approval = create_approval(db, action)

    decide_approval(
        db,
        approval.id,
        student.id,
        "approve",
    )

    claimed = claim_action_for_execution(
        db,
        action.id,
        student.id,
    )

    assert claimed.status == "executing"


def test_another_student_cannot_approve_action(db):
    owner = make_student(db)
    another_student = make_student(db)
    action = make_action(db, owner)
    approval = create_approval(db, action)

    with pytest.raises(ApprovalError):
        decide_approval(
            db,
            approval.id,
            another_student.id,
            "approve",
        )


def test_changed_payload_cannot_be_approved(db):
    student = make_student(db)
    action = make_action(db, student)
    approval = create_approval(db, action)

    action.arguments = {"subject": "Tampered"}

    with pytest.raises(ApprovalError):
        decide_approval(
            db,
            approval.id,
            student.id,
            "approve",
        )


def test_expired_approval_is_marked_expired(db):
    student = make_student(db)
    action = make_action(db, student)

    approval = create_approval(
        db,
        action,
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )

    result = decide_approval(
        db,
        approval.id,
        student.id,
        "approve",
    )

    assert result.status == "expired"
    assert result.reviewed_at is not None
    assert action.status == "pending_approval"
