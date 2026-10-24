from app.services.opportunity_matching_service import OpportunityMatchingService


def test_match_reports_profile_overlap_without_claiming_eligibility():
    service = OpportunityMatchingService()
    profile = {
        "profile": {
            "skills": [{"value": "Python", "evidence_ids": ["E1"]}],
            "projects": [{"value": "Data analysis", "evidence_ids": ["E2"]}],
            "education": [],
            "experience": [],
            "certifications": [],
            "interests": [],
            "goals": [],
        }
    }
    opportunity = {
        "title": "Python Intern",
        "description": "Work with Python and build reports.",
        "organization": "Example",
        "tags": ["engineering"],
    }

    result = service.match(profile, opportunity)

    assert result["match_score"] == 60
    assert result["matched_profile_items"] == ["Python"]
    assert result["eligibility_assessed"] is False
    assert result["missing_requirements"] == []
    assert "not confirmed eligibility" in result["match_rationale"]


def test_empty_profile_returns_unknown_score():
    result = OpportunityMatchingService().match(
        {"profile": {}},
        {"title": "Graduate Intern", "description": "Learn on the job"},
    )

    assert result["match_score"] is None
    assert result["matched_profile_items"] == []
    assert result["eligibility_assessed"] is False


def test_empty_opportunity_text_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="searchable text"):
        OpportunityMatchingService().match(
            {"profile": {"skills": [{"value": "Python"}]}},
            {"title": "", "description": ""},
        )

