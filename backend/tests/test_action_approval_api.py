
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.core.dependencies import get_current_student, get_db
from app.models.student import Student
from app.models.agent_action import AgentAction
from app.models.approval import Approval

from app.api.v1 import google_integrations
from app.api.v1.actions import router as actions_router
from app.api.v1.approvals import router as approvals_router

from app.services.action_service import create_action
from app.services.approval_service import create_approval, decide_approval


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
    student = Student(email=f"{uuid.uuid4()}@example.com")
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def make_client(db, student):
    app = FastAPI()

    app.include_router(actions_router, prefix="/actions")
    app.include_router(approvals_router, prefix="/approvals")
    app.include_router(google_integrations.router, prefix="/google")

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_student] = lambda: student

    return TestClient(app)


def action_payload(key=None, subject="Test"):
    return {
        "tool_name": "gmail.create_draft",
        "arguments": {"subject": subject},
        "idempotency_key": key or str(uuid.uuid4()),
    }


def get_approval(db, action_id):
    return db.execute(
        select(Approval).where(Approval.action_id == action_id)
    ).scalar_one()


def make_approved_gmail_action(db, student):
    action = create_action(
        db=db,
        student_id=student.id,
        tool_name="gmail.send",
        arguments={
            "to": "student@example.com",
            "subject": "UniFlow test",
            "body_sha256": "test-hash",
            "draft_id": "test-draft-123",
        },
        idempotency_key=str(uuid.uuid4()),
    )

    approval = create_approval(db, action)

    decide_approval(
        db=db,
        approval_id=approval.id,
        student_id=student.id,
        decision="approve",
    )

    db.commit()
    db.refresh(action)

    return action


# ---------------------------------------------------------------------
# Existing action and approval API tests
# ---------------------------------------------------------------------

def test_create_action_creates_pending_approval(db):
    student = make_student(db)
    client = make_client(db, student)

    response = client.post(
        "/actions",
        json=action_payload(),
    )

    assert response.status_code == 201
    assert response.json()["status"] == "pending_approval"

    action_id = response.json()["id"]
    approval = get_approval(db, uuid.UUID(action_id))

    assert approval.status == "pending"
    assert approval.student_id == student.id


def test_same_idempotency_key_returns_existing_action(db):
    student = make_student(db)
    client = make_client(db, student)
    key = str(uuid.uuid4())
    payload = action_payload(key=key)

    first = client.post("/actions", json=payload)
    second = client.post("/actions", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]

    approval_count = db.execute(
        select(func.count(Approval.id))
    ).scalar_one()

    assert approval_count == 1


def test_reused_idempotency_key_with_different_payload_is_rejected(db):
    student = make_student(db)
    client = make_client(db, student)
    key = str(uuid.uuid4())

    first = client.post(
        "/actions",
        json=action_payload(key=key, subject="First"),
    )

    second = client.post(
        "/actions",
        json=action_payload(key=key, subject="Different"),
    )

    assert first.status_code == 201
    assert second.status_code == 400


def test_approve_decision_updates_action_and_approval(db):
    student = make_student(db)
    client = make_client(db, student)

    response = client.post(
        "/actions",
        json=action_payload(),
    )

    action_id = uuid.UUID(response.json()["id"])
    approval = get_approval(db, action_id)

    decision = client.post(
        f"/approvals/{approval.id}/decision",
        json={"decision": "approve"},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    db.refresh(approval)
    action = db.get(AgentAction, action_id)

    assert approval.status == "approved"
    assert action.status == "approved"


def test_reject_decision_updates_action_and_approval(db):
    student = make_student(db)
    client = make_client(db, student)

    response = client.post(
        "/actions",
        json=action_payload(),
    )

    action_id = uuid.UUID(response.json()["id"])
    approval = get_approval(db, action_id)

    decision = client.post(
        f"/approvals/{approval.id}/decision",
        json={"decision": "reject"},
    )

    assert decision.status_code == 200
    assert decision.json()["status"] == "rejected"

    db.refresh(approval)
    action = db.get(AgentAction, action_id)

    assert approval.status == "rejected"
    assert action.status == "rejected"


def test_student_cannot_read_another_students_action(db):
    owner = make_student(db)
    another_student = make_student(db)

    owner_client = make_client(db, owner)

    response = owner_client.post(
        "/actions",
        json=action_payload(),
    )

    action_id = response.json()["id"]

    another_client = make_client(db, another_student)

    denied = another_client.get(f"/actions/{action_id}")

    assert denied.status_code == 404


def test_student_cannot_approve_another_students_approval(db):
    owner = make_student(db)
    another_student = make_student(db)

    owner_client = make_client(db, owner)

    response = owner_client.post(
        "/actions",
        json=action_payload(),
    )

    action_id = uuid.UUID(response.json()["id"])
    approval = get_approval(db, action_id)

    another_client = make_client(db, another_student)

    denied = another_client.post(
        f"/approvals/{approval.id}/decision",
        json={"decision": "approve"},
    )

    assert denied.status_code == 400
    assert db.get(Approval, approval.id).status == "pending"
    assert db.get(AgentAction, action_id).status == "pending_approval"


def test_list_actions_only_returns_current_students_actions(db):
    first_student = make_student(db)
    second_student = make_student(db)

    first_client = make_client(db, first_student)
    second_client = make_client(db, second_student)

    first_client.post("/actions", json=action_payload())
    second_client.post("/actions", json=action_payload())

    first_list = first_client.get("/actions")
    second_list = second_client.get("/actions")

    assert first_list.status_code == 200
    assert second_list.status_code == 200

    assert len(first_list.json()) == 1
    assert len(second_list.json()) == 1

    assert first_list.json()[0]["id"] != second_list.json()[0]["id"]


# ---------------------------------------------------------------------
# Gmail approved execution tests
# ---------------------------------------------------------------------

def test_unapproved_gmail_action_cannot_execute(db):
    student = make_student(db)
    client = make_client(db, student)

    action = create_action(
        db=db,
        student_id=student.id,
        tool_name="gmail.send",
        arguments={
            "to": "student@example.com",
            "subject": "UniFlow test",
            "body_sha256": "test-hash",
            "draft_id": "test-draft-123",
        },
        idempotency_key=str(uuid.uuid4()),
    )

    create_approval(db, action)
    db.commit()

    response = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    assert response.status_code == 409

    db.refresh(action)
    assert action.status == "pending_approval"


def test_approved_gmail_action_executes_successfully(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_gmail_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    monkeypatch.setattr(
        google_integrations,
        "gmail_send_draft",
        lambda credentials, draft_id: {
            "message_id": "sent-message-123",
            "thread_id": "thread-123",
            "label_ids": ["SENT"],
        },
    )

    response = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["result"]["message_id"] == "sent-message-123"

    db.refresh(action)
    assert action.status == "succeeded"


def test_gmail_action_cannot_execute_twice(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_gmail_action(db, student)

    send_count = {"value": 0}

    def fake_send(credentials, draft_id):
        send_count["value"] += 1
        return {
            "message_id": "sent-message-123",
            "thread_id": "thread-123",
            "label_ids": ["SENT"],
        }

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    monkeypatch.setattr(
        google_integrations,
        "gmail_send_draft",
        fake_send,
    )

    first = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    second = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert send_count["value"] == 1

    db.refresh(action)
    assert action.status == "succeeded"


def test_missing_google_credentials_fail_action(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_gmail_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: None,
    )

    response = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    assert response.status_code == 409

    db.refresh(action)
    assert action.status == "failed"
    assert action.error_code == "google_credentials_unavailable"


def test_gmail_send_failure_is_recorded(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_gmail_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    def failing_send(credentials, draft_id):
        raise RuntimeError("Simulated Gmail API failure")

    monkeypatch.setattr(
        google_integrations,
        "gmail_send_draft",
        failing_send,
    )

    response = client.post(
        f"/google/gmail/actions/{action.id}/execute"
    )

    assert response.status_code == 502

    db.refresh(action)
    assert action.status == "failed"
    assert action.error_code == "gmail_send_outcome_unknown"


# ---------------------------------------------------------------------
# Google Calendar approval and execution tests
# ---------------------------------------------------------------------


def calendar_event_payload(key=None):
    return {
        "summary": "UniFlow Calendar test",
        "start": "2026-12-01T10:00:00+05:30",
        "end": "2026-12-01T11:00:00+05:30",
        "description": "Test event created by UniFlow",
        "location": "Delhi",
        "timezone_name": "Asia/Kolkata",
        "idempotency_key": key or str(uuid.uuid4()),
    }


def make_approved_calendar_action(db, student):
    arguments = {
        "summary": "UniFlow Calendar test",
        "start": "2026-12-01T10:00:00+05:30",
        "end": "2026-12-01T11:00:00+05:30",
        "description": "Test event created by UniFlow",
        "location": "Delhi",
        "timezone_name": "Asia/Kolkata",
    }

    action = create_action(
        db=db,
        student_id=student.id,
        tool_name="calendar.create_event",
        arguments=arguments,
        idempotency_key=str(uuid.uuid4()),
    )

    approval = create_approval(db, action)

    decide_approval(
        db=db,
        approval_id=approval.id,
        student_id=student.id,
        decision="approve",
    )

    db.commit()
    db.refresh(action)

    return action


def test_calendar_event_request_creates_pending_approval_without_google_call(
    db, monkeypatch
):
    student = make_student(db)
    client = make_client(db, student)

    def unexpected_google_call(*args, **kwargs):
        pytest.fail("Google Calendar must not be called before approval.")

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        unexpected_google_call,
    )
    monkeypatch.setattr(
        google_integrations,
        "calendar_create_event",
        unexpected_google_call,
    )

    response = client.post(
        "/google/calendar/events",
        json=calendar_event_payload(),
    )

    assert response.status_code == 201

    action_data = response.json()["action"]
    action_id = uuid.UUID(action_data["id"])

    action = db.get(AgentAction, action_id)
    approval = get_approval(db, action_id)

    assert action.tool_name == "calendar.create_event"
    assert action.status == "pending_approval"
    assert approval.status == "pending"


def test_unapproved_calendar_action_cannot_execute(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = create_action(
        db=db,
        student_id=student.id,
        tool_name="calendar.create_event",
        arguments={
            "summary": "UniFlow Calendar test",
            "start": "2026-12-01T10:00:00+05:30",
            "end": "2026-12-01T11:00:00+05:30",
            "description": "Test event",
            "location": "Delhi",
            "timezone_name": "Asia/Kolkata",
        },
        idempotency_key=str(uuid.uuid4()),
    )

    create_approval(db, action)
    db.commit()

    def unexpected_google_call(*args, **kwargs):
        pytest.fail("Unapproved Calendar action reached Google.")

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        unexpected_google_call,
    )

    response = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )

    assert response.status_code == 409

    db.refresh(action)
    assert action.status == "pending_approval"


def test_approved_calendar_action_executes_successfully(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_calendar_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    monkeypatch.setattr(
        google_integrations,
        "calendar_create_event",
        lambda **kwargs: {
            "id": "calendar-event-123",
            "summary": kwargs["summary"],
            "status": "confirmed",
            "html_link": "https://calendar.google.com/event?id=123",
        },
    )

    response = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["result"]["id"] == "calendar-event-123"

    db.refresh(action)
    assert action.status == "succeeded"


def test_calendar_action_cannot_execute_twice(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_calendar_action(db, student)

    create_count = {"value": 0}

    def fake_create_event(**kwargs):
        create_count["value"] += 1
        return {
            "id": "calendar-event-123",
            "summary": kwargs["summary"],
            "status": "confirmed",
        }

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )
    monkeypatch.setattr(
        google_integrations,
        "calendar_create_event",
        fake_create_event,
    )

    first = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )
    second = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )

    assert first.status_code == 200
    assert second.status_code == 409
    assert create_count["value"] == 1

    db.refresh(action)
    assert action.status == "succeeded"


def test_missing_google_credentials_fail_calendar_action(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_calendar_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: None,
    )

    response = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )

    assert response.status_code == 409

    db.refresh(action)
    assert action.status == "failed"
    assert action.error_code == "google_credentials_unavailable"


def test_calendar_event_creation_failure_is_recorded(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    action = make_approved_calendar_action(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    def failing_create_event(**kwargs):
        raise RuntimeError("Simulated Calendar API failure")

    monkeypatch.setattr(
        google_integrations,
        "calendar_create_event",
        failing_create_event,
    )

    response = client.post(
        f"/google/calendar/actions/{action.id}/execute"
    )

    assert response.status_code == 502

    db.refresh(action)
    assert action.status == "failed"
    assert action.error_code == "calendar_create_outcome_unknown"


def test_calendar_events_can_be_listed(db, monkeypatch):
    student = make_student(db)
    client = make_client(db, student)

    monkeypatch.setattr(
        google_integrations,
        "_get_credentials",
        lambda student_id: object(),
    )

    monkeypatch.setattr(
        google_integrations,
        "calendar_list_events",
        lambda **kwargs: [
            {
                "id": "calendar-event-123",
                "summary": "UniFlow Calendar test",
                "status": "confirmed",
            }
        ],
    )

    response = client.get("/google/calendar/events")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert response.json()["events"][0]["id"] == "calendar-event-123"
