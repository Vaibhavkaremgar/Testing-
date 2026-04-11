from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, load_only

from app.auth import get_current_active_user
from app.database import SessionLocal, get_db
from app.models import Agency, Candidate, JobDescription, User, UserRole
from app.routes.auth import _resolve_pagination as resolve_user_pagination
from app.routes.candidates import (
    _apply_candidate_list_scope,
    _apply_client_filter,
    _apply_candidate_created_at_filters,
    build_safe_candidate_response,
    normalize_legacy_candidate_stages,
    sanitize_candidate_email,
    sanitize_candidate_location,
)
from app.routes.jobs import _apply_job_list_scope, _resolve_pagination as resolve_job_pagination

router = APIRouter(tags=["Dashboard"])


def _resolve_user_snapshot(current_user: User) -> SimpleNamespace:
    return SimpleNamespace(
        id=current_user.id,
        agency_id=current_user.agency_id,
        role=current_user.role,
    )


def _serialize_candidate(candidate: Candidate):
    from app.routes.candidates import _compute_field_confidence
    return build_safe_candidate_response(
        {
            "id": candidate.id,
            "name": candidate.name or "",
            "email": sanitize_candidate_email(candidate.email),
            "phone": candidate.phone,
            "current_company": candidate.current_company,
            "current_role": candidate.current_role,
            "experience_years": candidate.experience_years,
            "location": sanitize_candidate_location(candidate.location),
            "linkedin_url": candidate.linkedin_url,
            "resume_file_path": candidate.resume_file_path,
            "resume_text": candidate.resume_text,
            "parsing_status": candidate.parsing_status,
            "resume_score": candidate.resume_score,
            "score_threshold": candidate.score_threshold,
            "skills": candidate.skills,
            "education": candidate.education,
            "work_experience": candidate.work_experience,
            "stage": candidate.stage,
            "stage_updated_at": candidate.stage_updated_at,
            "stage_entered_at": candidate.stage_entered_at,
            "applied_at": candidate.applied_at,
            "job_id": candidate.job_id,
            "job_title": candidate.job.title if candidate.job else None,
            "summary": candidate.summary,
            "internal_notes": candidate.internal_notes,
            "predefined_questions": candidate.predefined_questions,
            "created_at": candidate.created_at,
        }
    ).model_dump()


def _fetch_candidates(
    current_user: SimpleNamespace,
    client: Optional[str],
    page: Optional[int],
    limit: Optional[int],
    offset: Optional[int],
    from_date: Optional[str],
    to_date: Optional[str],
):
    db = SessionLocal()
    try:
        normalize_legacy_candidate_stages(db)
        query = _apply_candidate_list_scope(db.query(Candidate), current_user)
        query = _apply_client_filter(query, client)
        query = _apply_candidate_created_at_filters(
            query,
            from_date=from_date,
            to_date=to_date,
        )
        query = query.options(
            load_only(
                Candidate.id,
                Candidate.name,
                Candidate.email,
                Candidate.phone,
                Candidate.current_company,
                Candidate.current_role,
                Candidate.experience_years,
                Candidate.location,
                Candidate.linkedin_url,
                Candidate.resume_file_path,
                Candidate.resume_text,
                Candidate.parsing_status,
                Candidate.resume_score,
                Candidate.score_threshold,
                Candidate.skills,
                Candidate.education,
                Candidate.work_experience,
                Candidate.stage,
                Candidate.stage_updated_at,
                Candidate.stage_entered_at,
                Candidate.applied_at,
                Candidate.job_id,
                Candidate.summary,
                Candidate.internal_notes,
                Candidate.predefined_questions,
                Candidate.created_at,
            ),
            joinedload(Candidate.job).load_only(JobDescription.id, JobDescription.title),
        ).order_by(Candidate.created_at.desc())

        effective_limit, effective_offset = resolve_job_pagination(page, limit, offset)
        if effective_limit is not None:
            query = query.offset(effective_offset).limit(effective_limit)

        return [_serialize_candidate(candidate) for candidate in query.all()]
    finally:
        db.close()


def _fetch_jobs(current_user: SimpleNamespace, client: Optional[str], page: Optional[int], limit: Optional[int], offset: Optional[int]):
    db = SessionLocal()
    try:
        query = _apply_job_list_scope(db.query(JobDescription), current_user, db)
        if client:
            query = query.filter(func.lower(func.trim(JobDescription.company_name)) == client.strip().lower())
        query = query.order_by(JobDescription.created_at.desc())

        effective_limit, effective_offset = resolve_job_pagination(page, limit, offset)
        if effective_limit is not None:
            query = query.offset(effective_offset).limit(effective_limit)

        jobs = query.all()
        job_ids = [job.id for job in jobs]
        candidate_count_query = db.query(Candidate.job_id, func.count(Candidate.id).label("candidate_count")).filter(
            Candidate.job_id.in_(job_ids)
        )
        if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            candidate_count_query = candidate_count_query.filter(Candidate.assigned_to_user_id == current_user.id)
        candidate_counts = {
            row.job_id: row.candidate_count
            for row in candidate_count_query.group_by(Candidate.job_id).all()
        } if job_ids else {}

        result = []
        for job in jobs:
            result.append(
                {
                    "id": job.id,
                    "job_id": job.job_id,
                    "company_name": job.company_name,
                    "title": job.title,
                    "department": job.department,
                    "location": job.location,
                    "employment_type": job.employment_type,
                    "experience_required": job.experience_required,
                    "salary_range": job.salary_range,
                    "vacancies": job.vacancies,
                    "min_passing_score": job.min_passing_score,
                    "description": job.description,
                    "requirements": job.requirements,
                    "responsibilities": job.responsibilities,
                    "skills": job.skills,
                    "interview_questions": job.interview_questions,
                    "is_active": job.is_active,
                    "created_at": job.created_at,
                    "candidate_count": candidate_counts.get(job.id, 0),
                }
            )
        return result
    finally:
        db.close()


def _fetch_users(current_user: SimpleNamespace, page: Optional[int], limit: Optional[int], offset: Optional[int]):
    db = SessionLocal()
    try:
        if current_user.role not in {UserRole.ADMIN, UserRole.SUPER_ADMIN}:
            return []

        query = db.query(User).order_by(User.created_at.desc())
        if current_user.role != UserRole.SUPER_ADMIN:
            query = query.filter(User.agency_id == current_user.agency_id)

        effective_limit, effective_offset = resolve_user_pagination(page, limit, offset)
        if effective_limit is not None:
            query = query.offset(effective_offset).limit(effective_limit)

        agency_map = {str(agency.id): agency.name for agency in db.query(Agency).all()}
        now = datetime.utcnow()
        users = []
        for user in query.all():
            is_online = bool(user.last_login_at and (now - user.last_login_at.replace(tzinfo=None)) < timedelta(minutes=15))
            users.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role,
                    "phone": user.phone,
                    "department": user.department,
                    "bio": user.bio,
                    "agency_id": user.agency_id,
                    "agency_name": agency_map.get(str(user.agency_id), None) if user.agency_id else None,
                    "avatar_url": user.avatar_url,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "last_login_at": user.last_login_at,
                    "is_online": is_online,
                }
            )
        return users
    finally:
        db.close()


def _fetch_scores(current_user: SimpleNamespace, client: Optional[str], page: Optional[int], limit: Optional[int], offset: Optional[int]):
    db = SessionLocal()
    try:
        query = _apply_job_list_scope(db.query(JobDescription), current_user, db)
        if client:
            query = query.filter(func.lower(func.trim(JobDescription.company_name)) == client.strip().lower())
        query = query.order_by(JobDescription.created_at.desc())

        effective_limit, effective_offset = resolve_job_pagination(page, limit, offset)
        if effective_limit is not None:
            query = query.offset(effective_offset).limit(effective_limit)

        return [
            {
                "job_id": job.id,
                "job_code": job.job_id,
                "title": job.title,
                "min_passing_score": job.min_passing_score or 60,
            }
            for job in query.all()
        ]
    finally:
        db.close()


@router.get("/dashboard-data")
def get_dashboard_data(
    client: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    candidate_page: Optional[int] = None,
    candidate_limit: Optional[int] = None,
    candidate_offset: Optional[int] = None,
    job_page: Optional[int] = None,
    job_limit: Optional[int] = None,
    job_offset: Optional[int] = None,
    user_page: Optional[int] = None,
    user_limit: Optional[int] = None,
    user_offset: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # The request-scoped DB session exists for auth and dependency wiring; worker queries use isolated sessions.
    del db
    user_snapshot = _resolve_user_snapshot(current_user)

    with ThreadPoolExecutor(max_workers=4) as executor:
        candidates_future = executor.submit(
            _fetch_candidates,
            user_snapshot,
            client,
            candidate_page,
            candidate_limit,
            candidate_offset,
            from_date,
            to_date,
        )
        jobs_future = executor.submit(
            _fetch_jobs,
            user_snapshot,
            client,
            job_page,
            job_limit,
            job_offset,
        )
        users_future = executor.submit(
            _fetch_users,
            user_snapshot,
            user_page,
            user_limit,
            user_offset,
        )
        scores_future = executor.submit(
            _fetch_scores,
            user_snapshot,
            client,
            job_page,
            job_limit,
            job_offset,
        )

        return {
            "candidates": candidates_future.result(),
            "jobs": jobs_future.result(),
            "users": users_future.result(),
            "scores": scores_future.result(),
        }
