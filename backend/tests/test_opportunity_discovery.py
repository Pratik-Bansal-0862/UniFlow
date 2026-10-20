import httpx
import pytest
import respx

from app.core.config import settings
from app.services.opportunity_discovery import (
    clean_description,
    configured_boards,
    fetch_board,
    is_student_role,
)


def test_configured_boards_reads_settings_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        settings,
        "greenhouse_boards",
        "Stripe, example-board, stripe, invalid value, _valid",
    )
    assert configured_boards() == ["stripe", "example-board", "_valid"]


def test_empty_board_configuration_disables_discovery_sources(monkeypatch):
    monkeypatch.setattr(settings, "greenhouse_boards", "")
    assert configured_boards() == []


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Software Engineering Intern", True),
        ("Graduate Program Analyst", True),
        ("Student Researcher", True),
        ("Senior Software Engineer", False),
        ("Product Manager", False),
    ],
)
def test_student_role_filter(title, expected):
    assert is_student_role(title) is expected


def test_clean_description_removes_markup_and_decodes_entities():
    assert clean_description(
        "<p>Build &amp; test</p><script>alert(1)</script>"
    ) == "Build & test"


def test_fetch_board_returns_real_provider_jobs():
    with respx.mock(base_url="https://boards-api.greenhouse.io") as router:
        router.get("/v1/boards/example").mock(
            return_value=httpx.Response(200, json={"name": "Example Org"})
        )
        router.get("/v1/boards/example/jobs").mock(
            return_value=httpx.Response(
                200,
                json={"jobs": [{"id": 123, "title": "Intern"}]},
            )
        )
        with httpx.Client() as client:
            org, jobs, error = fetch_board(client, "example")

    assert org == "Example Org"
    assert jobs == [{"id": 123, "title": "Intern"}]
    assert error is None


def test_fetch_board_reports_provider_failure_without_fake_jobs():
    with respx.mock(base_url="https://boards-api.greenhouse.io") as router:
        router.get("/v1/boards/missing").mock(
            return_value=httpx.Response(404)
        )
        with httpx.Client() as client:
            org, jobs, error = fetch_board(client, "missing")

    assert org is None
    assert jobs == []
    assert error is not None
