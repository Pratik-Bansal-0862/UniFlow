import html
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.opportunity import Opportunity
from app.models.student import Student

GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards"
ARBEITNOW_API = "https://www.arbeitnow.com/api/job-board-api"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"
REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)

STUDENT_ROLE_TERMS = (
    "intern", "internship", "co-op", "apprentice", "apprenticeship",
    "new grad", "new graduate", "graduate program", "university graduate",
    "working student", "student researcher", "research intern",
    "entry level", "entry-level", "junior", "trainee", "campus hire",
    "graduate engineer", "graduate analyst",
)
# Explicitly not a complete list of every eligible role; sources and titles vary.
MAX_JOBS_PER_SOURCE = 100


def configured_boards() -> list[str]:
    """Optional server-controlled Greenhouse boards; public APIs work without this."""
    raw = getattr(settings, "greenhouse_boards", "") or ""
    return list(dict.fromkeys(
        slug.strip().lower()
        for slug in raw.split(",")
        if slug.strip() and re.fullmatch(r"[a-z0-9_-]{1,100}", slug.strip().lower())
    ))


def is_student_role(title: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", title.casefold()).strip()
    return any(
        re.sub(r"[^a-z0-9]+", " ", term.casefold()).strip() in normalized
        for term in STUDENT_ROLE_TERMS
    )


def clean_description(value: Any, max_length: int = 12000) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length] or None


def _safe_https_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.netloc:
        return None
    return value.strip()[:2000]


def _get_json(client: httpx.Client, url: str, params: dict | None = None) -> Any:
    response = client.get(url, params=params)
    response.raise_for_status()
    return response.json()


def fetch_board(client: httpx.Client, slug: str) -> tuple[str | None, list[dict], str | None]:
    """Fetch one optional Greenhouse board, retaining the legacy helper interface."""
    try:
        board_data = _get_json(client, f"{GREENHOUSE_API}/{slug}")
        organization = board_data.get("name")
        if not isinstance(organization, str) or not organization.strip():
            return None, [], "Board response did not include an organization name"
        jobs_data = _get_json(
            client, f"{GREENHOUSE_API}/{slug}/jobs", {"content": "true"}
        )
        jobs = jobs_data.get("jobs")
        if not isinstance(jobs, list):
            return organization, [], "Jobs response did not contain a jobs list"
        return organization.strip(), jobs, None
    except (httpx.HTTPError, ValueError, AttributeError):
        return None, [], "Public Greenhouse board could not be fetched"


def _fetch_arbeitnow(client: httpx.Client) -> tuple[list[dict], str | None]:
    try:
        data = _get_json(client, ARBEITNOW_API)
        jobs = data.get("data") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return [], "Provider response did not contain a jobs list"
        normalized = []
        for job in jobs[:MAX_JOBS_PER_SOURCE]:
            if not isinstance(job, dict):
                continue
            normalized.append({
                "id": job.get("slug") or job.get("url"),
                "title": job.get("title"),
                "company": job.get("company_name"),
                "description": job.get("description"),
                "url": job.get("url"),
                "location": job.get("location"),
                "tags": job.get("tags") if isinstance(job.get("tags"), list) else [],
                "updated_at": job.get("created_at"),
                "provider": "Arbeitnow public Job Board API",
            })
        return normalized, None
    except (httpx.HTTPError, ValueError, AttributeError):
        return [], "Arbeitnow public API could not be fetched"


def _fetch_remotive(client: httpx.Client) -> tuple[list[dict], str | None]:
    try:
        data = _get_json(client, REMOTIVE_API, {"limit": str(MAX_JOBS_PER_SOURCE)})
        jobs = data.get("jobs") if isinstance(data, dict) else None
        if not isinstance(jobs, list):
            return [], "Provider response did not contain a jobs list"
        normalized = []
        for job in jobs[:MAX_JOBS_PER_SOURCE]:
            if not isinstance(job, dict):
                continue
            normalized.append({
                "id": job.get("id") or job.get("url"),
                "title": job.get("title"),
                "company": job.get("company_name"),
                "description": job.get("description"),
                "url": job.get("url"),
                "location": job.get("candidate_required_location"),
                "tags": job.get("tags") if isinstance(job.get("tags"), list) else [],
                "updated_at": job.get("publication_date"),
                "provider": "Remotive public Remote Jobs API",
            })
        return normalized, None
    except (httpx.HTTPError, ValueError, AttributeError):
        return [], "Remotive public API could not be fetched"


def _normalize_greenhouse(organization: str, slug: str, job: dict) -> dict:
    location_data = job.get("location")
    location = location_data.get("name") if isinstance(location_data, dict) else None
    departments = job.get("departments")
    tags = [
        item.get("name") for item in departments
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ] if isinstance(departments, list) else []
    return {
        "id": job.get("id"),
        "title": job.get("title"),
        "company": organization,
        "description": job.get("content"),
        "url": job.get("absolute_url"),
        "location": location,
        "tags": tags,
        "updated_at": job.get("updated_at"),
        "provider": "Greenhouse Job Board API",
        "board_slug": slug,
    }


def _save_jobs(
    db: Session,
    student: Student,
    jobs: list[dict],
    provider_key: str,
) -> tuple[int, int]:
    added = skipped = 0
    for job in jobs:
        if not isinstance(job, dict):
            skipped += 1
            continue
        title = job.get("title")
        url = _safe_https_url(job.get("url"))
        external_id = job.get("id")
        if (
            not isinstance(title, str) or not title.strip()
            or not is_student_role(title)
            or external_id is None or not url
        ):
            skipped += 1
            continue

        source_id = f"{provider_key}:{str(external_id)[:450]}"
        exists = db.scalar(select(Opportunity.id).where(
            Opportunity.student_id == student.id,
            Opportunity.source == "external",
            Opportunity.source_id == source_id,
        ))
        if exists is not None:
            skipped += 1
            continue

        company = job.get("company")
        location = job.get("location")
        tags = job.get("tags")
        tags = [str(tag)[:100] for tag in tags[:30]] if isinstance(tags, list) else []
        item = Opportunity(
            student_id=student.id,
            source="external",
            source_id=source_id,
            title=title.strip()[:250],
            organization=company.strip()[:250] if isinstance(company, str) and company.strip() else None,
            description=clean_description(job.get("description")),
            application_url=url,
            location=location.strip()[:250] if isinstance(location, str) and location.strip() else None,
            opportunity_type="Internship / entry-level role",
            status="discovered",
            # Do not fabricate a profile match score. Personalization is a separate ranking step.
            match_score=None,
            match_rationale=(
                "Matched a student/early-career title keyword from a public listing. "
                "Personalized eligibility and profile fit have not yet been assessed."
            ),
            missing_requirements=[],
            source_metadata={
                "provider": str(job.get("provider") or provider_key)[:120],
                "provider_key": provider_key,
                "external_job_id": str(external_id)[:450],
                "updated_at": job.get("updated_at"),
                "tags": tags,
                **({"board_slug": job["board_slug"]} if job.get("board_slug") else {}),
            },
        )
        try:
            with db.begin_nested():
                db.add(item)
                db.flush()
            added += 1
        except IntegrityError:
            skipped += 1
    return added, skipped


def discover_and_save(db: Session, student: Student) -> dict:
    """Discover genuine public listings across no-key APIs and optional Greenhouse boards.

    LinkedIn and Naukri are not scraped here: their listings require approved or
    otherwise permitted access. This function does not invent jobs or fit scores.
    """
    added = skipped = checked = 0
    errors: list[dict[str, str]] = []
    successful_sources: list[str] = []

    with httpx.Client(
        timeout=REQUEST_TIMEOUT,
        follow_redirects=True,
        headers={"User-Agent": "UniFlow/1.0 (public opportunity discovery)"},
    ) as client:
        for name, fetcher in (
            ("arbeitnow", _fetch_arbeitnow),
            ("remotive", _fetch_remotive),
        ):
            checked += 1
            jobs, error = fetcher(client)
            if error:
                errors.append({"source": name, "error": error})
                continue
            successful_sources.append(name)
            new_count, skip_count = _save_jobs(db, student, jobs, name)
            added += new_count
            skipped += skip_count

        for slug in configured_boards():
            checked += 1
            organization, board_jobs, error = fetch_board(client, slug)
            source_name = f"greenhouse:{slug}"
            if error:
                errors.append({"source": source_name, "error": error})
                continue
            successful_sources.append(source_name)
            normalized = [
                _normalize_greenhouse(organization or slug, slug, job)
                for job in board_jobs if isinstance(job, dict)
            ]
            new_count, skip_count = _save_jobs(db, student, normalized, source_name)
            added += new_count
            skipped += skip_count

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    if not successful_sources and errors:
        message = "No public job sources responded successfully. See source_errors."
    elif errors:
        message = "Discovery completed with partial source failures; see source_errors."
    elif added == 0:
        message = "Sources checked successfully; no new matching student/early-career listings were found."
    else:
        message = "Discovery completed."

    return {
        "added": added,
        "skipped": skipped,
        "sources_checked": checked,
        "sources_succeeded": successful_sources,
        "source_errors": errors,
        "message": message,
    }
