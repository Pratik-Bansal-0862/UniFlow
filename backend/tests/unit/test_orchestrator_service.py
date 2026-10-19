import pytest

from app.services.orchestrator_service import OrchestratorService


def valid_payload():
    return {
        "steps": [
            {
                "step_id": "review",
                "description": "Review the available evidence.",
                "tool_name": None,
                "requires_approval": False,
                "depends_on": [],
            },
            {
                "step_id": "prepare",
                "description": "Prepare a draft using verified information.",
                "tool_name": None,
                "requires_approval": False,
                "depends_on": ["review"],
            },
        ],
        "warnings": ["Confirm missing details."],
    }


def test_parse_valid_json_plan():
    payload = OrchestratorService._parse_response(
        __import__("json").dumps(valid_payload())
    )
    assert len(payload["steps"]) == 2


def test_parse_json_inside_markdown_fence():
    import json

    response = "```json\n" + json.dumps(valid_payload()) + "\n```"
    assert len(OrchestratorService._parse_response(response)["steps"]) == 2


@pytest.mark.parametrize(
    "raw",
    [
        "not json",
        '{"steps": []}',
        '{"steps": [{"step_id": "only-one"}]}',
        '["not", "an", "object"]',
    ],
)
def test_rejects_invalid_plan_json(raw):
    with pytest.raises((ValueError, TypeError)):
        OrchestratorService._parse_response(raw)


def test_rejects_duplicate_step_ids():
    from app.schemas.agent_plan import PlannedStep

    steps = [
        PlannedStep(step_id="same", description="First"),
        PlannedStep(step_id="same", description="Second"),
    ]
    with pytest.raises(ValueError, match="unique"):
        OrchestratorService._validate_steps(steps)


def test_rejects_unknown_dependency():
    from app.schemas.agent_plan import PlannedStep

    steps = [
        PlannedStep(
            step_id="prepare",
            description="Prepare draft",
            depends_on=["missing"],
        ),
        PlannedStep(step_id="review", description="Review evidence"),
    ]
    with pytest.raises(ValueError, match="unknown dependency"):
        OrchestratorService._validate_steps(steps)


def test_rejects_dependency_cycle():
    from app.schemas.agent_plan import PlannedStep

    steps = [
        PlannedStep(
            step_id="first",
            description="First step",
            depends_on=["second"],
        ),
        PlannedStep(
            step_id="second",
            description="Second step",
            depends_on=["first"],
        ),
    ]
    with pytest.raises(ValueError, match="cycle"):
        OrchestratorService._validate_steps(steps)
