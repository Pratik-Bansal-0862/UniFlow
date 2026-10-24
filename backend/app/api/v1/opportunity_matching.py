from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_student, get_db
from app.models.opportunity import Opportunity
from app.models.student import Student
from app.models.student_profile import StudentProfile
from app.services.opportunity_matching_service import OpportunityMatchingService

router = APIRouter()


@router.post("/match")
def match_student_opportunities(
    current_student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    # Always use the authenticated student's saved, corrected profile.
    profile_row = db.get(StudentProfile, current_student.id)
    if profile_row is None:
        return {
            "profile_status": "not_generated",
            "opportunity_count": 0,
            "opportunities": [],
        }

    profile_result = {
        "profile": profile_row.profile or {},
        "status": profile_row.status,
    }

    opportunities = (
        db.query(Opportunity)
        .filter(Opportunity.student_id == current_student.id)
        .order_by(Opportunity.created_at.desc())
        .all()
    )

    matcher = OpportunityMatchingService()
    matched_opportunities = []

    for opportunity in opportunities:
        # An opportunity without searchable text cannot be scored.
        searchable_text = " ".join(
            str(value or "")
            for value in (
                opportunity.title,
                opportunity.description,
                opportunity.organization,
                opportunity.location,
            )
        )
        metadata = opportunity.source_metadata or {}
        tags = metadata.get("tags", [])
        if isinstance(tags, list):
            searchable_text += " " + " ".join(str(tag) for tag in tags)

        if not searchable_text.strip():
            continue

        match = matcher.match(
            profile_result,
            {
                "title": opportunity.title,
                "description": opportunity.description,
                "organization": opportunity.organization,
                "location": opportunity.location,
                "tags": tags,
            },
        )

        matched_opportunities.append(
            {
                "id": str(opportunity.id),
                "title": opportunity.title,
                "organization": opportunity.organization,
                "description": opportunity.description,
                "application_url": opportunity.application_url,
                "location": opportunity.location,
                "deadline": (
                    opportunity.deadline.isoformat()
                    if opportunity.deadline else None
                ),
                "status": opportunity.status,
                **match,
            }
        )

    matched_opportunities.sort(
        key=lambda item: (
            item["match_score"] is not None,
            item["match_score"] if item["match_score"] is not None else -1,
        ),
        reverse=True,
    )

    return {
        "profile_status": profile_row.status,
        "opportunity_count": len(matched_opportunities),
        "opportunities": matched_opportunities,
    }
