import json

import pytest

from app.services.student_profile_service import StudentProfileService


class FakeLLM:
    def __init__(self, response):
        self.response = response

    def generate(self, *, system_prompt, user_prompt):
        return self.response


def test_profile_uses_only_personal_evidence():
    response = {
        "education": [
            {"value": "Computer Science", "evidence_ids": ["E1"]}
        ],
        "skills": [],
        "projects": [],
        "experience": [],
        "certifications": [],
        "interests": [],
        "goals": [],
    }
    service = StudentProfileService(FakeLLM(json.dumps(response)))

    result = service.extract_profile([
        {
            "category": "personal",
            "text": "Studying Computer Science",
            "document_id": "doc-1",
            "filename": "resume.pdf",
            "chunk_index": 0,
        },
        {
            "category": "reference",
            "text": "Reference document says expert in Python",
            "document_id": "doc-2",
            "filename": "example.pdf",
            "chunk_index": 0,
        },
    ])

    assert result["status"] == "generated"
    assert result["profile"]["education"][0]["value"] == "Computer Science"
    assert result["sources"]["E1"]["filename"] == "resume.pdf"
    assert "E2" not in result["sources"]


def test_no_personal_evidence_does_not_call_llm():
    service = StudentProfileService(FakeLLM("should not be used"))

    result = service.extract_profile([
        {"category": "reference", "text": "Example resume"}
    ])

    assert result["status"] == "no_personal_evidence"
    assert all(not items for items in result["profile"].values())


def test_unknown_evidence_id_is_rejected():
    response = {
        "education": [
            {"value": "Computer Science", "evidence_ids": ["E999"]}
        ]
    }
    service = StudentProfileService(FakeLLM(json.dumps(response)))

    with pytest.raises(ValueError, match="unknown evidence"):
        service.extract_profile([
            {"category": "personal", "text": "Studying Computer Science"}
        ])
