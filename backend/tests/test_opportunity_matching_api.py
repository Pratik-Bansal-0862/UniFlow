from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.opportunity_matching import router
from app.core.dependencies import get_current_student, get_db


def make_client(student, db):
    app = FastAPI()
    app.include_router(router, prefix="/opportunities")
    app.dependency_overrides[get_current_student] = lambda: student
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


def test_match_uses_saved_corrected_profile_without_llm():
    student_id = uuid.uuid4()
    student = SimpleNamespace(id=student_id)
    saved_profile = SimpleNamespace(
        student_id=student_id,
        profile={
            "skills": [{"value": "Python", "evidence_ids": []}],
            "projects": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "interests": [],
            "goals": [],
        },
        status="corrected",
    )
    opportunity = SimpleNamespace(
        id=uuid.uuid4(),
        student_id=student_id,
        title="Python Intern",
        organization="Example",
        description="Build software with Python",
        application_url="https://example.org/apply",
        location="Remote",
        deadline=None,
        status="saved",
        source_metadata={"tags": ["engineering"]},
        created_at=None,
    )
    db = MagicMock()
    db.get.return_value = saved_profile
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
        opportunity
    ]

    client = make_client(student, db)
    with patch(
        "app.services.student_profile_service.StudentProfileService.extract_profile",
        side_effect=AssertionError("Matching must not re-extract the profile."),
    ):
        response = client.post("/opportunities/match")

    assert response.status_code == 200
    body = response.json()
    assert body["profile_status"] == "corrected"
    assert body["opportunity_count"] == 1
    assert body["opportunities"][0]["match_score"] == 100
    assert body["opportunities"][0]["matched_profile_items"] == ["Python"]


def test_match_without_saved_profile_returns_empty_list():
    student = SimpleNamespace(id=uuid.uuid4())
    db = MagicMock()
    db.get.return_value = None

    response = make_client(student, db).post("/opportunities/match")

    assert response.status_code == 200
    assert response.json() == {
        "profile_status": "not_generated",
        "opportunity_count": 0,
        "opportunities": [],
    }


def test_match_queries_only_authenticated_students_opportunities():
    student_id = uuid.uuid4()
    student = SimpleNamespace(id=student_id)
    db = MagicMock()
    db.get.return_value = SimpleNamespace(
        profile={
            "skills": [],
            "projects": [],
            "experience": [],
            "education": [],
            "certifications": [],
            "interests": [],
            "goals": [],
        },
        status="corrected",
    )
    query = db.query.return_value
    filtered = query.filter.return_value
    filtered.order_by.return_value.all.return_value = []

    response = make_client(student, db).post("/opportunities/match")

    assert response.status_code == 200
    from app.models.opportunity import Opportunity
    db.query.assert_called_once_with(Opportunity)
    args = filtered.filter.call_args
    assert args is None  # The ownership predicate is passed to query.filter().
    from unittest.mock import ANY
    query.filter.assert_called_once_with(ANY)
