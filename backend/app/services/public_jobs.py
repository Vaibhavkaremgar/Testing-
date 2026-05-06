from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.configuration import settings
from app.models import FeedAccessLog, JobApplication, JobDescription

def is_public_job_open(job: JobDescription) -> bool:
    return bool(job.is_active) and str(job.status or "open").strip().lower() in {
        "active",
        "open",
        "published",
    }


def build_public_job_url(job: JobDescription) -> str:
    return f"{settings.PUBLIC_BASE_URL.rstrip('/')}/jobs/{job.id}"


def build_public_apply_url(job: JobDescription) -> str:
    return f"{build_public_job_url(job)}/apply"


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
