
import pytest
from pydantic import ValidationError

from app.schemas.agent_plan import AgentPlan, PlannedStep
from app.schemas.tool import ToolRequest, ToolResult


def test_agent_plan_accepts_valid_plan():
    plan = AgentPlan(
        objective="Find relevant scholarship information",
        status="ready",
        steps=[
            PlannedStep(
                step_id="step-1",
                description="Search student documents",
                tool_name="knowledge.search",
            )
        ],
        evidence_ids=["document-1"],
    )

    assert plan.status == "ready"
    assert plan.steps[0].tool_name == "knowledge.search"


def test_agent_plan_rejects_invalid_status():
    with pytest.raises(ValidationError):
        AgentPlan(
            objective="Test",
            status="invalid",
        )


def test_tool_request_requires_idempotency_key():
    with pytest.raises(ValidationError):
        ToolRequest(
            tool_name="calendar.list_events",
            student_id="student-1",
            arguments={},
        )


def test_tool_result_defaults_to_unverified():
    result = ToolResult(status="succeeded")

    assert result.verified is False
    assert result.data == {}
