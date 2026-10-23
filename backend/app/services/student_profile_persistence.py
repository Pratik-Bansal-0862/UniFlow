from __future__ import annotations

from typing import Any

from app.services.student_profile_service import PROFILE_FIELDS


def validate_corrected_profile(
    profile: Any,
    allowed_evidence_ids: set[str],
) -> dict[str, list[dict[str, Any]]]:
    """Validate user corrections while preserving verified evidence references."""
    if not isinstance(profile, dict):
        raise ValueError("Profile must be an object.")

    unexpected = set(profile) - set(PROFILE_FIELDS)
    if unexpected:
        raise ValueError("Profile contains unsupported fields.")

    corrected: dict[str, list[dict[str, Any]]] = {}

    for field in PROFILE_FIELDS:
        items = profile.get(field, [])
        if not isinstance(items, list):
            raise ValueError(f"Profile field {field!r} must be a list.")

        clean_items: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in items:
            if not isinstance(item, dict):
                raise ValueError(f"Invalid item in profile field {field!r}.")

            value = item.get("value")
            evidence_ids = item.get("evidence_ids", [])

            if not isinstance(value, str) or not value.strip():
                raise ValueError("Profile item value must be non-empty.")

            if not isinstance(evidence_ids, list) or not all(
                isinstance(evidence_id, str)
                and evidence_id in allowed_evidence_ids
                for evidence_id in evidence_ids
            ):
                raise ValueError("Profile item contains unknown evidence IDs.")

            normalized = " ".join(value.split())
            fingerprint = normalized.casefold()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)

            clean_items.append(
                {
                    "value": normalized,
                    "evidence_ids": list(dict.fromkeys(evidence_ids)),
                }
            )

        corrected[field] = clean_items

    return corrected
