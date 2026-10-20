from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class OpportunityCreate(BaseModel):
    source: str = Field(pattern="^(gmail|external|manual)$")
    source_id: str | None = Field(default=None, max_length=500)
    title: str = Field(min_length=1, max_length=250)
    organization: str | None = Field(default=None, max_length=250)
    description: str | None = None
    application_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    opportunity_type: str | None = Field(default=None, max_length=80)
    deadline: datetime | None = None
    match_score: int | None = Field(default=None, ge=0, le=100)
    match_rationale: str | None = None
    missing_requirements: list[str] = Field(default_factory=list)
    source_metadata: dict = Field(default_factory=dict)


class OpportunityUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    organization: str | None = Field(default=None, max_length=250)
    description: str | None = None
    application_url: HttpUrl | None = None
    location: str | None = Field(default=None, max_length=250)
    opportunity_type: str | None = Field(default=None, max_length=80)
    deadline: datetime | None = None
    status: str | None = Field(
        default=None,
        pattern="^(discovered|saved|applied|dismissed|expired)$",
    )


class OpportunityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: UUID
    source: str
    source_id: str | None
    title: str
    organization: str | None
    description: str | None
    application_url: str | None
    location: str | None
    opportunity_type: str | None
    deadline: datetime | None
    status: str
    match_score: int | None
    match_rationale: str | None
    missing_requirements: list[str]
    source_metadata: dict
    created_at: datetime
    updated_at: datetime
