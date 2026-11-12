
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
from app.api.v1.actions import router as actions_router
from app.api.v1.approvals import router as approvals_router


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

    assert (
        first_list.json()[0]["id"]
        != second_list.json()[0]["id"]
    )
