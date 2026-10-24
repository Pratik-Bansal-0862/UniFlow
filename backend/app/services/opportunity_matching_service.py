from __future__ import annotations

import re
from typing import Any


PROFILE_WEIGHTS = {
    "skills": 3,
    "projects": 2,
    "experience": 2,
    "education": 2,
    "certifications": 1,
    "interests": 1,
    "goals": 1,
}


def _normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9+#.]+", text.lower()))


class OpportunityMatchingService:
    """Explain profile-to-opportunity relevance without claiming eligibility."""

    def match(
        self,
        profile_result: dict[str, Any],
        opportunity: dict[str, Any],
    ) -> dict[str, Any]:
        profile = profile_result.get("profile", {})
        if not isinstance(profile, dict):
            raise ValueError("Profile must be an object.")

        searchable_text = " ".join(
            str(opportunity.get(field) or "")
            for field in ("title", "description", "organization", "location")
        )
        tags = opportunity.get("tags") or []
        if isinstance(tags, list):
            searchable_text += " " + " ".join(str(tag) for tag in tags)

        job_text = _normalize(searchable_text)
        if not job_text:
            raise ValueError("Opportunity must include searchable text.")

        matched: list[str] = []
        considered_weight = 0
        matched_weight = 0

        for field, weight in PROFILE_WEIGHTS.items():
            items = profile.get(field, [])
            if not isinstance(items, list):
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                value = item.get("value")
                if not isinstance(value, str) or not value.strip():
                    continue

                considered_weight += weight
                normalized_value = _normalize(value)
                # Match the complete profile phrase, not isolated common words.
                if normalized_value and normalized_value in job_text:
                    matched_weight += weight
                    matched.append(value.strip())

        score = (
            round(100 * matched_weight / considered_weight)
            if considered_weight
            else None
        )

        if score is None:
            rationale = (
                "A profile match could not be calculated because no usable "
                "profile items were available."
            )
        elif matched:
            rationale = (
                "Profile text overlaps with the opportunity in: "
                + ", ".join(matched[:8])
                + ". This indicates relevance only, not confirmed eligibility."
            )
        else:
            rationale = (
                "No exact profile-phrase overlap was found in the available "
                "opportunity text. This does not establish that the student "
                "is unsuitable."
            )

        return {
            "match_score": score,
            "match_rationale": rationale,
            "matched_profile_items": matched,
            # Requirements must be assessed from explicit, verified source data.
            "missing_requirements": [],
            "eligibility_assessed": False,
        }
