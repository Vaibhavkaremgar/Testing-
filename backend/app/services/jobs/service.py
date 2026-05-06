import logging
import uuid
from datetime import UTC, datetime
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session

from app.core.configuration import settings
from app.models import JobDescription, JobDistributionLog, JobPortal, JobPortalMapping
from app.schemas import (
    ATSJobCreate,
    ATSJobDetailResponse,
    ATSJobListResponse,
    ATSJobResponse,
    ATSJobUpdate,
)
from app.services.public_jobs import build_location, build_public_apply_url, build_public_job_url, compose_location, normalize_skills

logger = logging.getLogger(__name__)


class JobDistributionService:
    @staticmethod
    def list_jobs(
        db: Session,
        *,
        page: int,
        page_size: int,
        search: Optional[str],
        location: Optional[str],
        skills: Optional[str],
        status_filter: Optional[str],
    ) -> ATSJobListResponse:
        query = db.query(JobDescription)
        query = JobDistributionService._apply_filters(
            query=query,
            search=search,
            location=location,
            skills=skills,
            status_filter=status_filter,
        )

        total = query.count()
        items = (
            query.order_by(JobDescription.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        return ATSJobListResponse(
            items=[JobDistributionService._to_job_response(job) for job in items],
            page=page,
            page_size=page_size,
            total=total,
        )

    @staticmethod
    def get_job_or_404(db: Session, job_id) -> JobDescription:
        job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
        if not job:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
        return job

    @staticmethod
    def get_public_job_detail(db: Session, job_id) -> ATSJobDetailResponse:
        job = JobDistributionService.get_job_or_404(db, job_id)
        return JobDistributionService._to_job_detail_response(job)

    @staticmethod
    def create_job(db: Session, payload: ATSJobCreate) -> ATSJobResponse:
        job = JobDescription(
            job_id=payload.reference_code or f"JOB-{uuid.uuid4().hex[:8].upper()}",
            title=payload.job_title,
            company_name=payload.company_name,
            company_website_url=payload.company_website_url,
            company_logo_url=payload.company_logo_url,
            description=payload.job_description,
            industry=payload.industry,
            location=compose_location(payload.city, payload.state, payload.country, payload.location),
            city=payload.city,
            state=payload.state,
            country=payload.country,
            employment_type=payload.employment_type,
            experience_required=payload.experience,
            salary_range=payload.salary,
            skills=payload.skills,
            category=payload.category,
            remote=payload.remote,
            status=payload.status or settings.JOB_FEED_DEFAULT_STATUS,
            is_active=(payload.status or settings.JOB_FEED_DEFAULT_STATUS).lower() != "inactive",
            valid_through=payload.valid_through,
        )
        db.add(job)
        db.flush()

        JobDistributionService._ensure_portal_mappings(db, job)
        JobDistributionService._log_distribution_event(
            db,
            job_id=job.id,
            status_value="pending",
            message="Job created and queued for XML feed publication.",
        )

        db.commit()
        db.refresh(job)
        logger.info("Created job %s for XML distribution", job.id)
        return JobDistributionService._to_job_response(job)

    @staticmethod
    def update_job(db: Session, job_id, payload: ATSJobUpdate) -> ATSJobResponse:
        job = JobDistributionService.get_job_or_404(db, job_id)
        update_data = payload.model_dump(exclude_unset=True)

        field_mapping = {
            "job_title": "title",
            "job_description": "description",
            "experience": "experience_required",
            "salary": "salary_range",
        }

        for source_field, value in update_data.items():
            target_field = field_mapping.get(source_field, source_field)
            setattr(job, target_field, value)

        if any(field in update_data for field in {"location", "city", "state", "country"}):
            job.location = compose_location(
                getattr(job, "city", None),
                getattr(job, "state", None),
                getattr(job, "country", None),
                getattr(job, "location", None),
            )

        if "status" in update_data:
            job.is_active = str(update_data["status"]).lower() != "inactive"

        JobDistributionService._ensure_portal_mappings(db, job)
        JobDistributionService._log_distribution_event(
            db,
            job_id=job.id,
            status_value="pending",
            message="Job updated and queued for XML feed refresh.",
        )

        db.commit()
        db.refresh(job)
        logger.info("Updated job %s for XML distribution", job.id)
        return JobDistributionService._to_job_response(job)

    @staticmethod
    def delete_job(db: Session, job_id) -> None:
        job = JobDistributionService.get_job_or_404(db, job_id)
        job_identifier = job.id

        JobDistributionService._log_distribution_event(
            db,
            job_id=job_identifier,
            status_value="pending",
            message="Job deletion queued for feed removal.",
        )

        db.query(JobPortalMapping).filter(JobPortalMapping.job_id == job.id).delete()
        db.delete(job)
        db.commit()
        logger.info("Deleted job %s and cleared portal mappings", job_identifier)

    @staticmethod
    def list_active_jobs(db: Session):
        active_statuses = ("active", "published", "open")
        now = datetime.now(UTC)
        return (
            db.query(JobDescription)
            .filter(JobDescription.is_active.is_(True))
            .filter(
                or_(
                    JobDescription.status.is_(None),
                    func.lower(JobDescription.status).in_(active_statuses),
                )
            )
            .filter(
                or_(
                    JobDescription.valid_through.is_(None),
                    JobDescription.valid_through >= now,
                )
            )
            .order_by(JobDescription.created_at.desc())
            .all()
        )

    @staticmethod
    def mark_jobs_as_published(db: Session, portal_name: str, jobs: list[JobDescription]) -> None:
        for job in jobs:
            JobDistributionService._ensure_single_portal_mapping(db, job, portal_name)
            db.add(
                JobDistributionLog(
                    job_id=job.id,
                    portal_name=portal_name,
                    status="published",
                    message=f"Job included in {portal_name} XML feed.",
                )
            )
        db.commit()

    @staticmethod
    def mark_feed_failure(db: Session, portal_name: str, message: str) -> None:
        db.add(
            JobDistributionLog(
                job_id=None,
                portal_name=portal_name,
                status="failed",
                message=message,
            )
        )
        db.commit()

    @staticmethod
    def _apply_filters(query, *, search, location, skills, status_filter):
        if search:
            pattern = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    JobDescription.title.ilike(pattern),
                    JobDescription.company_name.ilike(pattern),
                    JobDescription.description.ilike(pattern),
                    JobDescription.location.ilike(pattern),
                )
            )

        if location:
            location_pattern = f"%{location.strip()}%"
            query = query.filter(
                or_(
                    JobDescription.location.ilike(location_pattern),
                    JobDescription.city.ilike(location_pattern),
                    JobDescription.state.ilike(location_pattern),
                    JobDescription.country.ilike(location_pattern),
                )
            )

        if skills:
            for skill in [item.strip() for item in skills.split(",") if item.strip()]:
                query = query.filter(cast(JobDescription.skills, String).ilike(f"%{skill}%"))

        if status_filter:
            query = query.filter(func.lower(JobDescription.status) == status_filter.strip().lower())

        return query

    @staticmethod
    def _ensure_portal_mappings(db: Session, job: JobDescription) -> None:
        portals = db.query(JobPortal).filter(JobPortal.is_enabled.is_(True)).all()
        for portal in portals:
            JobDistributionService._ensure_single_portal_mapping(db, job, portal.portal_name)

    @staticmethod
    def _ensure_single_portal_mapping(db: Session, job: JobDescription, portal_name: str) -> None:
        mapping = (
            db.query(JobPortalMapping)
            .filter(
                JobPortalMapping.job_id == job.id,
                JobPortalMapping.portal_name == portal_name,
            )
            .first()
        )
        if mapping is None:
            db.add(
                JobPortalMapping(
                    job_id=job.id,
                    portal_name=portal_name,
                )
            )

    @staticmethod
    def _log_distribution_event(
        db: Session,
        *,
        job_id,
        status_value: str,
        message: str,
    ) -> None:
        portals = db.query(JobPortal).filter(JobPortal.is_enabled.is_(True)).all()
        if not portals:
            db.add(
                JobDistributionLog(
                    job_id=job_id,
                    portal_name="internal-feed",
                    status=status_value,
                    message=message,
                )
            )
            return

        for portal in portals:
            db.add(
                JobDistributionLog(
                    job_id=job_id,
                    portal_name=portal.portal_name,
                    status=status_value,
                    message=message,
                )
            )

    @staticmethod
    def _to_job_response(job: JobDescription) -> ATSJobResponse:
        return ATSJobResponse(
            id=job.id,
            job_title=job.title,
            company_name=job.company_name,
            company_website_url=job.company_website_url,
            company_logo_url=job.company_logo_url,
            job_description=job.description,
            industry=job.industry,
            location=build_location(job),
            city=job.city,
            state=job.state,
            country=job.country,
            employment_type=job.employment_type,
            experience=job.experience_required,
            salary=job.salary_range,
            skills=normalize_skills(job.skills),
            category=job.category,
            remote=bool(job.remote),
            status=job.status or settings.JOB_FEED_DEFAULT_STATUS,
            valid_through=job.valid_through,
            created_at=job.created_at,
            updated_at=job.updated_at,
            public_job_url=build_public_job_url(job),
            apply_url=build_public_apply_url(job),
        )

    @staticmethod
    def _to_job_detail_response(job: JobDescription) -> ATSJobDetailResponse:
        payload = JobDistributionService._to_job_response(job).model_dump()
        return ATSJobDetailResponse(**payload)
