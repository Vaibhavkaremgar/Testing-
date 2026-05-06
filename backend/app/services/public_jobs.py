from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.configuration import settings
from app.models import FeedAccessLog, JobApplication, JobDescription


_UUID_AT_END_RE = re.compile(
    r"(?P<uuid>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$"
)
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def is_public_job_open(job: JobDescription) -> bool:
    if not (
        bool(job.is_active)
        and str(job.status or "open").strip().lower() in {
        "active",
        "open",
        "published",
        }
    ):
        return False

    if job.valid_through is None:
        return True

    now = datetime.now(UTC)
    valid_through = job.valid_through
    if valid_through.tzinfo is None:
        valid_through = valid_through.replace(tzinfo=UTC)
    return valid_through >= now


def slugify_job_value(value: str | None, *, max_length: int = 80) -> str:
    normalized = _NON_ALNUM_RE.sub("-", str(value or "").strip().lower()).strip("-")
    if not normalized:
        return ""
    return normalized[:max_length].strip("-")


def build_job_slug(job: JobDescription) -> str:
    parts = [
        slugify_job_value(job.title, max_length=64),
        slugify_job_value(job.city or job.location, max_length=32),
    ]
    base_slug = "-".join(part for part in parts if part)
    if not base_slug:
        base_slug = slugify_job_value(job.company_name, max_length=48) or "job"
    return f"{base_slug}-{job.id}"


def extract_job_id(job_reference: str) -> UUID:
    value = str(job_reference or "").strip()
    try:
        return UUID(value)
    except (ValueError, TypeError):
        match = _UUID_AT_END_RE.search(value)
        if match:
            return UUID(match.group("uuid"))
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


def get_job_canonical_path(job: JobDescription) -> str:
    return f"/jobs/{build_job_slug(job)}"


def get_apply_canonical_path(job: JobDescription) -> str:
    return f"{get_job_canonical_path(job)}/apply"


def build_public_job_url(job: JobDescription) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{get_job_canonical_path(job)}"


def build_public_apply_url(job: JobDescription) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}{get_apply_canonical_path(job)}"


def build_location(job: JobDescription) -> str:
    parts = [job.city, job.state, job.country]
    structured_location = ", ".join(part.strip() for part in parts if part and part.strip())
    if structured_location:
        return structured_location
    return (job.location or "").strip()


def compose_location(city: str | None, state: str | None, country: str | None, fallback: str | None = None) -> str | None:
    parts = [city, state, country]
    structured_location = ", ".join(part.strip() for part in parts if part and part.strip())
    if structured_location:
        return structured_location
    fallback_value = (fallback or "").strip()
    return fallback_value or None


def normalize_skills(skills: Any) -> list[str]:
    if isinstance(skills, list):
        return [str(skill).strip() for skill in skills if str(skill).strip()]
    if not skills:
        return []
    return [part.strip() for part in str(skills).split(",") if part.strip()]


def get_public_job_or_404(db: Session, job_id) -> JobDescription:
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if job is None or not is_public_job_open(job):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


def get_public_job_by_reference_or_404(db: Session, job_reference: str) -> JobDescription:
    return get_public_job_or_404(db, extract_job_id(job_reference))


def create_job_application(
    db: Session,
    *,
    job: JobDescription,
    full_name: str,
    email: str,
    phone: str | None,
    original_filename: str | None,
    stored_filename: str | None,
    resume_url: str | None,
    cover_letter: str | None,
) -> JobApplication:
    application = JobApplication(
        job_id=job.id,
        full_name=full_name.strip(),
        email=email.strip().lower(),
        phone=(phone or "").strip() or None,
        original_filename=(original_filename or "").strip() or None,
        stored_filename=(stored_filename or "").strip() or None,
        resume_url=(resume_url or "").strip() or None,
        cover_letter=(cover_letter or "").strip() or None,
    )
    db.add(application)
    db.commit()
    db.refresh(application)
    return application


def log_feed_access(db: Session, request: Request, portal_name: str) -> None:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    ip_address = forwarded_for.split(",")[0].strip() if forwarded_for else None
    if not ip_address and request.client:
        ip_address = request.client.host

    db.add(
        FeedAccessLog(
            portal_name=portal_name,
            ip_address=ip_address,
            user_agent=request.headers.get("user-agent"),
        )
    )
    db.commit()
