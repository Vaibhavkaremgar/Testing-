from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract, text
from typing import List, Optional
from app.database import get_db
from app.config import settings
from app.models import (
    Candidate,
    Interview,
    CandidateStage,
    User,
    UserRole,
    JobDescription,
    AnalyticsWidget,
    UserDashboardPreference,
)
from app.schemas import (
    DashboardStats, PipelineStats, HiringFunnelData, 
    TimeToHireData, SkillHeatmapData, ScoreDistribution
)
from app.auth import get_current_active_user
from collections import Counter
import random
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

router = APIRouter(prefix="/analytics", tags=["Analytics"])

INTERVIEW_RESULT_THRESHOLD = 6
CANDIDATE_PIPELINE_STAGES = {
    CandidateStage.REVIEW,
    CandidateStage.SHORTLISTED,
    CandidateStage.RESUME_REJECTED,
    CandidateStage.INTERVIEW_RESCHEDULED,
    CandidateStage.NO_SHOW,
}
INTERVIEW_PIPELINE_STAGES = {
    CandidateStage.INTERVIEW_SCHEDULED,
    CandidateStage.INTERVIEWED,
    CandidateStage.SELECTED,
    CandidateStage.REJECTED,
}


def _apply_candidate_dashboard_filters(
    query,
    db: Session,
    current_user: User,
    client: Optional[str] = None,
    month: Optional[str] = None,
    date: Optional[str] = None,
):
    query = _apply_candidate_visibility(query, current_user)

    if client:
        normalized_client = client.strip().lower()
        job_ids = db.query(JobDescription.id).filter(
            func.lower(func.trim(JobDescription.company_name)) == normalized_client
        ).all()
        job_ids = [job_id[0] for job_id in job_ids]
        if job_ids:
            query = query.filter(Candidate.job_id.in_(job_ids))
        else:
            return query.filter(False)

    if date:
        query = query.filter(func.date(Candidate.created_at) == date)
    elif month:
        year, month_num = map(int, month.split('-'))
        query = query.filter(
            extract('year', Candidate.created_at) == year,
            extract('month', Candidate.created_at) == month_num
        )

    return query


def _map_interview_to_pipeline_stage(interview: Interview) -> Optional[CandidateStage]:
    if not interview:
        return None

    interview_status = (interview.status or '').strip().lower()
    if interview_status == 'completed':
        interview_score = interview.interview_score if interview.interview_score is not None else 0
        return CandidateStage.SELECTED if interview_score >= INTERVIEW_RESULT_THRESHOLD else CandidateStage.REJECTED
    if interview_status == 'ongoing':
        return CandidateStage.INTERVIEWED
    if interview_status == 'scheduled':
        return CandidateStage.INTERVIEW_SCHEDULED

    return None


def _get_latest_filtered_interviews_by_candidate(
    db: Session,
    candidate_ids: List,
    month: Optional[str] = None,
    date: Optional[str] = None,
):
    latest_interviews_by_candidate = {}
    if not candidate_ids:
        return latest_interviews_by_candidate

    interview_query = db.query(Interview).filter(Interview.candidate_id.in_(candidate_ids))
    interview_date_field = func.coalesce(Interview.scheduled_at, Interview.created_at)
    if date:
        interview_query = interview_query.filter(func.date(interview_date_field) == date)
    elif month:
        year, month_num = map(int, month.split('-'))
        interview_query = interview_query.filter(
            extract('year', interview_date_field) == year,
            extract('month', interview_date_field) == month_num
        )

    interviews = (
        interview_query
        .order_by(Interview.candidate_id.asc(), Interview.scheduled_at.desc(), Interview.created_at.desc())
        .all()
    )
    for interview in interviews:
        latest_interviews_by_candidate.setdefault(interview.candidate_id, interview)

    return latest_interviews_by_candidate


def _get_table_columns(db: Session, table_name: str) -> set[str]:
    rows = db.execute(text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = :table_name
        """
    ), {"table_name": table_name}).fetchall()
    return {row[0] for row in rows}


def _fetch_interview_session_metadata(db: Session, interviews: List[Interview]) -> dict[str, dict]:
    if not interviews:
        return {}

    columns = _get_table_columns(db, "interview_sessions")
    if not columns:
        return {}

    lookup_columns = [
        column_name
        for column_name in ("session_token", "interview_id", "session_id", "async_token", "token", "id")
        if column_name in columns
    ]
    if not lookup_columns:
        return {}

    metadata_columns = [
        column_name
        for column_name in (
            "recording_path",
            "recording_format",
            "recording_duration_seconds",
            "vapi_recording_url",
            "session_token",
            "recording_size_bytes",
            "created_at",
            "recording_data",
        )
        if column_name in columns
    ]
    if not metadata_columns:
        return {}

    interview_key_map: dict[str, set[str]] = {}
    for interview in interviews:
        interview_id = str(interview.id)
        for key in {interview_id, interview.async_token}:
            if key:
                interview_key_map.setdefault(str(key), set()).add(interview_id)

    all_keys = list(interview_key_map.keys())
    if not all_keys:
        return {}

    where_clauses = []
    params = {"keys": all_keys}
    for index, column_name in enumerate(lookup_columns):
        key_name = f"keys_{index}"
        params[key_name] = all_keys
        where_clauses.append(f"{column_name}::text = ANY(:{key_name})")

    query = text(f"""
        SELECT {", ".join([*(f"{column}::text AS {column}" for column in lookup_columns), *metadata_columns])}
        FROM interview_sessions
        WHERE {" OR ".join(where_clauses)}
    """)

    rows = db.execute(query, params).mappings().all()
    if not rows:
        return {}

    interview_metadata: dict[str, dict] = {}
    for row in rows:
        matched_ids: set[str] = set()
        for column_name in lookup_columns:
            value = row.get(column_name)
            if value and value in interview_key_map:
                matched_ids.update(interview_key_map[value])

        if not matched_ids:
            continue

        for interview_id in matched_ids:
            current = interview_metadata.get(interview_id, {})
            has_candidate_recording = bool(row.get("recording_path")) or row.get("recording_data") is not None
            has_vapi_recording = bool(row.get("vapi_recording_url"))

            if not current or (has_candidate_recording and not current.get("recording_path")) or (has_vapi_recording and not current.get("vapi_recording_url")):
                interview_metadata[interview_id] = {
                    "recording_path": row.get("recording_path"),
                    "recording_format": row.get("recording_format"),
                    "recording_duration_seconds": row.get("recording_duration_seconds"),
                    "vapi_recording_url": row.get("vapi_recording_url"),
                    "session_token": row.get("session_token"),
                    "recording_size_bytes": row.get("recording_size_bytes"),
                    "recording_created_at": row.get("created_at"),
                    "has_candidate_recording": has_candidate_recording and bool(row.get("session_token")),
                    "has_vapi_recording": has_vapi_recording,
                }

    return interview_metadata


ANALYTICS_WIDGET_CATALOG = [
    {"metric_key": "recruitment_funnel", "widget_name": "Recruitment Funnel", "is_default": True},
    {"metric_key": "time_to_hire", "widget_name": "Time to Hire", "is_default": True},
    {"metric_key": "time_to_interview", "widget_name": "Time to Interview", "is_default": False},
    {"metric_key": "offer_acceptance_rate", "widget_name": "Offer Acceptance Rate", "is_default": False},
    {"metric_key": "interview_to_hire_ratio", "widget_name": "Interview to Hire Ratio", "is_default": False},
    {"metric_key": "drop_off_rate", "widget_name": "Drop-off Rate", "is_default": False},
    {"metric_key": "total_hires", "widget_name": "Total Hires", "is_default": False},
    {"metric_key": "applications_per_job", "widget_name": "Applications per Job", "is_default": False},
    {"metric_key": "resume_score_distribution", "widget_name": "Resume Score Distribution", "is_default": True},
    {"metric_key": "ai_interview_average_score", "widget_name": "AI Interview Average Score", "is_default": False},
    {"metric_key": "application_volume_trend", "widget_name": "Application Volume Trend", "is_default": False},
    {"metric_key": "source_of_candidates", "widget_name": "Source of Candidates", "is_default": False},
    {"metric_key": "hires_per_recruiter", "widget_name": "Hires per Recruiter", "is_default": False},
    {"metric_key": "avg_resume_review_time", "widget_name": "Avg Resume Review Time", "is_default": False},
    {"metric_key": "interview_scheduling_delay", "widget_name": "Interview Scheduling Delay", "is_default": False},
    {"metric_key": "recruiter_performance_score", "widget_name": "Recruiter Performance Score", "is_default": False},
    {"metric_key": "top_skills", "widget_name": "Top Skills", "is_default": True},
    {"metric_key": "skill_gap_analysis", "widget_name": "Skill Gap Analysis", "is_default": True},
    {"metric_key": "skill_demand_vs_supply", "widget_name": "Skill Demand vs Supply", "is_default": False},
    {"metric_key": "skill_vs_hire_success_rate", "widget_name": "Skill vs Hire Success Rate", "is_default": False},
]


class DashboardLayoutItem(BaseModel):
    metric_key: str
    position: int = 0
    size: str = "medium"
    is_enabled: bool = True


class DashboardLayoutPayload(BaseModel):
    items: List[DashboardLayoutItem]


def _role_name(current_user: User) -> str:
    role = getattr(current_user, "role", None)
    return role.value if hasattr(role, "value") else str(role or "")


def _client_org_name(current_user: User) -> str:
    # Analytics-only client scoping. If a client role exists, use department as org key.
    return (getattr(current_user, "department", None) or "").strip()


def _apply_candidate_visibility(query, current_user: User):
    role_name = _role_name(current_user)

    if role_name == "super_admin":
        return query

    if role_name == UserRole.ADMIN.value:
        if current_user.agency_id:
            return query.join(JobDescription, Candidate.job_id == JobDescription.id).filter(
                JobDescription.agency_id == current_user.agency_id
            )
        return query

    if role_name == UserRole.RECRUITER.value:
        return query.filter(Candidate.assigned_to_user_id == current_user.id)

    if role_name == "client":
        org_name = _client_org_name(current_user)
        if not org_name:
            return query.filter(Candidate.id == -1)
        return query.join(JobDescription, Candidate.job_id == JobDescription.id).filter(
            JobDescription.company_name == org_name
        )

    # Fallback for non-admin roles in analytics: scoped to assigned candidates.
    return query.filter(Candidate.assigned_to_user_id == current_user.id)


def _apply_job_visibility(query, db: Session, current_user: User):
    role_name = _role_name(current_user)

    if role_name == "super_admin":
        return query

    if role_name == UserRole.ADMIN.value:
        if current_user.agency_id:
            return query.filter(JobDescription.agency_id == current_user.agency_id)
        return query

    if role_name == UserRole.RECRUITER.value:
        assigned_job_ids = db.query(Candidate.job_id).filter(
            Candidate.assigned_to_user_id == current_user.id,
            Candidate.job_id.isnot(None)
        ).distinct()
        return query.filter(JobDescription.id.in_(assigned_job_ids))

    if role_name == "client":
        org_name = _client_org_name(current_user)
        if not org_name:
            return query.filter(JobDescription.id == -1)
        return query.filter(JobDescription.company_name == org_name)

    assigned_job_ids = db.query(Candidate.job_id).filter(
        Candidate.assigned_to_user_id == current_user.id,
        Candidate.job_id.isnot(None)
    ).distinct()
    return query.filter(JobDescription.id.in_(assigned_job_ids))


def _apply_analytics_filters(
    query,
    db: Session,
    current_user: User,
    date_range: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    recruiter: Optional[str] = None,
    client: Optional[str] = None,
    department: Optional[str] = None
):
    role_name = _role_name(current_user)

    if date_range in {"last_7_days", "last_30_days", "last_3_months", "last_6_months"}:
        now = datetime.utcnow()
        delta_map = {
            "last_7_days": timedelta(days=7),
            "last_30_days": timedelta(days=30),
            "last_3_months": timedelta(days=90),
            "last_6_months": timedelta(days=180),
        }
        query = query.filter(Candidate.created_at >= (now - delta_map[date_range]))
    elif date_range == "custom":
        if start_date:
            query = query.filter(func.date(Candidate.created_at) >= start_date)
        if end_date:
            query = query.filter(func.date(Candidate.created_at) <= end_date)

    if role_name == UserRole.ADMIN.value and recruiter and recruiter != "all":
        try:
            from uuid import UUID as _UUID
            query = query.filter(Candidate.assigned_to_user_id == _UUID(recruiter))
        except (TypeError, ValueError):
            pass

    if role_name == UserRole.ADMIN.value and client and client != "all":
        job_ids = db.query(JobDescription.id).filter(JobDescription.company_name == client)
        query = query.filter(Candidate.job_id.in_(job_ids))

    if department and department != "all":
        dept_job_ids = db.query(JobDescription.id).filter(JobDescription.department == department)
        query = query.filter(Candidate.job_id.in_(dept_job_ids))

    return query


def _resolve_period_windows(
    date_range: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
):
    now = datetime.now(timezone.utc)

    if date_range == "last_7_days":
        current_start = now - timedelta(days=7)
        current_end = now
    elif date_range == "last_30_days" or not date_range:
        current_start = now - timedelta(days=30)
        current_end = now
    elif date_range == "last_3_months":
        current_start = now - timedelta(days=90)
        current_end = now
    elif date_range == "last_6_months":
        current_start = now - timedelta(days=180)
        current_end = now
    elif date_range == "custom" and start_date and end_date:
        try:
            current_start = datetime.fromisoformat(start_date + "T00:00:00")
            current_end = datetime.fromisoformat(end_date + "T23:59:59")
        except ValueError:
            current_start = now - timedelta(days=30)
            current_end = now
    else:
        current_start = now - timedelta(days=30)
        current_end = now

    window_duration = current_end - current_start
    previous_end = current_start
    previous_start = previous_end - window_duration

    return current_start, current_end, previous_start, previous_end


def _apply_scope_filters_only(
    query,
    db: Session,
    current_user: User,
    recruiter: Optional[str] = None,
    client: Optional[str] = None,
    department: Optional[str] = None
):
    role_name = _role_name(current_user)

    if role_name == UserRole.ADMIN.value and recruiter and recruiter != "all":
        try:
            from uuid import UUID as _UUID
            query = query.filter(Candidate.assigned_to_user_id == _UUID(recruiter))
        except (TypeError, ValueError):
            pass

    if role_name == UserRole.ADMIN.value and client and client != "all":
        job_ids = db.query(JobDescription.id).filter(JobDescription.company_name == client)
        query = query.filter(Candidate.job_id.in_(job_ids))

    if department and department != "all":
        dept_job_ids = db.query(JobDescription.id).filter(JobDescription.department == department)
        query = query.filter(Candidate.job_id.in_(dept_job_ids))

    return query


def _ensure_analytics_widgets(db: Session):
    existing = {
        row.metric_key: row
        for row in db.query(AnalyticsWidget).all()
    }

    created = False
    for widget in ANALYTICS_WIDGET_CATALOG:
        if widget["metric_key"] not in existing:
            db.add(
                AnalyticsWidget(
                    widget_name=widget["widget_name"],
                    metric_key=widget["metric_key"],
                    role_access="all",
                    is_default=widget["is_default"],
                )
            )
            created = True

    if created:
        db.commit()


@router.get("/widgets/catalog")
def get_widget_catalog(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_analytics_widgets(db)
    widgets = db.query(AnalyticsWidget).order_by(AnalyticsWidget.id.asc()).all()
    return [
        {
            "id": widget.id,
            "widget_name": widget.widget_name,
            "metric_key": widget.metric_key,
            "role_access": widget.role_access,
            "is_default": widget.is_default,
        }
        for widget in widgets
    ]


@router.get("/widgets/layout")
def get_widget_layout(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_analytics_widgets(db)

    prefs = (
        db.query(UserDashboardPreference, AnalyticsWidget)
        .join(AnalyticsWidget, UserDashboardPreference.widget_id == AnalyticsWidget.id)
        .filter(UserDashboardPreference.user_id == current_user.id)
        .order_by(UserDashboardPreference.position.asc())
        .all()
    )

    if not prefs:
        defaults = (
            db.query(AnalyticsWidget)
            .filter(AnalyticsWidget.is_default == True)
            .order_by(AnalyticsWidget.id.asc())
            .all()
        )
        return {
            "items": [
                {
                    "widget_id": widget.id,
                    "metric_key": widget.metric_key,
                    "widget_name": widget.widget_name,
                    "position": idx,
                    "size": "medium",
                    "is_enabled": True,
                }
                for idx, widget in enumerate(defaults)
            ]
        }

    return {
        "items": [
            {
                "widget_id": widget.id,
                "metric_key": widget.metric_key,
                "widget_name": widget.widget_name,
                "position": pref.position or 0,
                "size": pref.size or "medium",
                "is_enabled": bool(pref.is_enabled),
            }
            for pref, widget in prefs
        ]
    }


@router.post("/widgets/layout")
def save_widget_layout(
    payload: DashboardLayoutPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_analytics_widgets(db)

    widget_map = {
        w.metric_key: w.id
        for w in db.query(AnalyticsWidget).all()
    }

    db.query(UserDashboardPreference).filter(
        UserDashboardPreference.user_id == current_user.id
    ).delete()

    for item in payload.items:
        widget_id = widget_map.get(item.metric_key)
        if not widget_id:
            continue
        db.add(
            UserDashboardPreference(
                user_id=current_user.id,
                widget_id=widget_id,
                position=item.position,
                size=item.size,
                is_enabled=item.is_enabled,
            )
        )

    db.commit()
    return {"status": "success", "saved_items": len(payload.items)}

@router.get("/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats(
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        query = _apply_candidate_dashboard_filters(
            db.query(Candidate),
            db,
            current_user,
            client=client,
            month=month,
            date=date,
        )

        all_candidates = query.all()
        active_candidates = [c for c in all_candidates if c.stage != CandidateStage.APPLIED]
        total = len(active_candidates)

        shortlisted = sum(1 for c in active_candidates if c.stage == CandidateStage.SHORTLISTED)
        resume_rejected = sum(1 for c in active_candidates if c.stage == CandidateStage.RESUME_REJECTED)

        latest_interviews_by_candidate = _get_latest_filtered_interviews_by_candidate(
            db,
            [candidate.id for candidate in active_candidates],
            month=month,
            date=date,
        )
        interview_stages = {
            candidate_id: _map_interview_to_pipeline_stage(interview)
            for candidate_id, interview in latest_interviews_by_candidate.items()
        }

        interview_scheduled = sum(
            1
            for stage in interview_stages.values()
            if stage in {CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEWED}
        )
        selected = sum(1 for stage in interview_stages.values() if stage == CandidateStage.SELECTED)
        rejected = sum(1 for stage in interview_stages.values() if stage == CandidateStage.REJECTED)

        candidate_ids = [c.id for c in active_candidates]
        avg_resume = db.query(func.avg(Candidate.resume_score)).filter(
            Candidate.id.in_(candidate_ids) if candidate_ids else False
        ).scalar() or 0

        interview_scores = [
            interview.interview_score
            for interview in latest_interviews_by_candidate.values()
            if interview and interview.interview_score is not None
        ]
        avg_interview = (sum(interview_scores) / len(interview_scores)) if interview_scores else 0

        return DashboardStats(
            total_candidates=total,
            shortlisted=shortlisted,
            resume_rejected=resume_rejected,
            rejected=rejected,
            interviews_scheduled=interview_scheduled,
            selected=selected,
            avg_resume_score=round(avg_resume, 1),
            avg_interview_score=round(avg_interview, 1)
        )
    except Exception as e:
        print(f"❌ Dashboard stats error: {e}")
        import traceback
        traceback.print_exc()
        # Return default values on error
        return DashboardStats(
            total_candidates=0,
            shortlisted=0,
            resume_rejected=0,
            rejected=0,
            interviews_scheduled=0,
            selected=0,
            avg_resume_score=0.0,
            avg_interview_score=0.0
        )

@router.get("/pipeline-stats", response_model=List[PipelineStats])
def get_pipeline_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    stats = []
    base_query = _apply_candidate_visibility(db.query(Candidate), current_user)
    for stage in CandidateStage:
        count = base_query.filter(
            Candidate.stage == stage
        ).count() or 0
        stats.append(PipelineStats(stage=stage.value, count=count))
    return stats

@router.get("/hiring-funnel", response_model=List[HiringFunnelData])
def get_hiring_funnel(
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = _apply_candidate_dashboard_filters(
        db.query(Candidate),
        db,
        current_user,
        client=client,
        month=month,
        date=date,
    )

    candidates = query.all()
    active_candidates = [candidate for candidate in candidates if candidate.stage != CandidateStage.APPLIED]
    total = len(active_candidates) or 1
    shortlisted = sum(1 for candidate in active_candidates if candidate.stage == CandidateStage.SHORTLISTED)

    latest_interviews_by_candidate = _get_latest_filtered_interviews_by_candidate(
        db,
        [candidate.id for candidate in active_candidates],
        month=month,
        date=date,
    )
    interview_stages = [
        _map_interview_to_pipeline_stage(interview)
        for interview in latest_interviews_by_candidate.values()
    ]
    interview_scheduled = sum(
        1 for stage in interview_stages if stage in {CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEWED}
    )
    selected = sum(1 for stage in interview_stages if stage == CandidateStage.SELECTED)
    rejected = sum(1 for stage in interview_stages if stage == CandidateStage.REJECTED)
    
    funnel_stages = [
        ("Total Candidates", total),
        ("Shortlisted", shortlisted),
        ("Interview Scheduled", interview_scheduled),
        ("Selected", selected),
        ("Rejected", rejected),
    ]
    
    return [
        HiringFunnelData(
            stage=stage,
            count=count,
            percentage=round((count / total) * 100, 1) if total > 0 else 0
        )
        for stage, count in funnel_stages
    ]


@router.get("/recruitment-funnel")
def get_recruitment_funnel(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = _apply_candidate_visibility(db.query(Candidate), current_user)
    query = _apply_analytics_filters(
        query,
        db,
        current_user,
        date_range=date_range,
        start_date=start_date,
        end_date=end_date,
        recruiter=recruiter,
        client=client,
        department=department,
    )
    candidates = query.all()
    now = datetime.now(timezone.utc)

    def _avg_days(rows):
        if not rows:
            return 0.0
        durations = []
        for c in rows:
            start = c.stage_entered_at or c.stage_updated_at or c.created_at
            if not start:
                continue
            normalized_start = start
            if normalized_start.tzinfo is None:
                normalized_start = normalized_start.replace(tzinfo=timezone.utc)
            durations.append(max(0, (now - normalized_start).days))
        return round(sum(durations) / len(durations), 1) if durations else 0.0

    applied_rows = list(candidates)
    screened_rows = [c for c in candidates if c.stage != CandidateStage.APPLIED]
    shortlisted_rows = [
        c for c in candidates
        if c.stage in {
            CandidateStage.SHORTLISTED,
            CandidateStage.INTERVIEW_SCHEDULED,
            CandidateStage.INTERVIEW_RESCHEDULED,
            CandidateStage.INTERVIEWED,
            CandidateStage.SELECTED,
            CandidateStage.REJECTED,
        }
    ]
    interviewed_rows = [
        c for c in candidates
        if c.stage in {
            CandidateStage.INTERVIEW_SCHEDULED,
            CandidateStage.INTERVIEW_RESCHEDULED,
            CandidateStage.INTERVIEWED,
            CandidateStage.SELECTED,
            CandidateStage.REJECTED,
        }
    ]
    selected_rows = [c for c in candidates if c.stage == CandidateStage.SELECTED]
    offered_rows = [c for c in candidates if (c.offer_status or "").lower() in {"made", "accepted"}]
    hired_rows = [c for c in candidates if (c.offer_status or "").lower() == "accepted"]

    stage_data = [
        ("Applied", applied_rows),
        ("Screened", screened_rows),
        ("Shortlisted", shortlisted_rows),
        ("Interviewed", interviewed_rows),
        ("Selected", selected_rows),
        ("Offered", offered_rows),
        ("Hired", hired_rows),
    ]

    result = []
    prev_count = None
    for stage_name, rows in stage_data:
        count = len(rows)
        if prev_count in (None, 0):
            conversion = 100.0 if count > 0 else 0.0
            dropoff = 0.0
        else:
            conversion = round((count / prev_count) * 100, 1)
            dropoff = round(100 - conversion, 1)

        result.append({
            "stage": stage_name,
            "count": count,
            "conversion_percentage": conversion,
            "dropoff_percentage": max(0.0, dropoff),
            "avg_time_days": _avg_days(rows),
        })
        prev_count = count

    return result


@router.get("/kpi-summary")
def get_kpi_summary(
    date_range: Optional[str] = Query("last_30_days"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    recruiter: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    current_start, current_end, previous_start, previous_end = _resolve_period_windows(
        date_range, start_date, end_date
    )

    def _build_candidate_query(period_start, period_end):
        q = _apply_candidate_visibility(db.query(Candidate), current_user)
        q = _apply_scope_filters_only(
            q,
            db,
            current_user,
            recruiter=recruiter,
            client=client,
            department=department,
        )
        return q.filter(Candidate.created_at >= period_start, Candidate.created_at <= period_end)

    def _compute_metrics(period_start, period_end):
        cq = _build_candidate_query(period_start, period_end)
        candidates = cq.all()
        candidate_ids = [c.id for c in candidates]

        total_candidates = len(candidates)
        selected_candidates = [c for c in candidates if c.stage == CandidateStage.SELECTED]
        interviewed_candidates = [
            c for c in candidates
            if c.stage in {
                CandidateStage.INTERVIEW_SCHEDULED,
                CandidateStage.INTERVIEW_RESCHEDULED,
                CandidateStage.INTERVIEWED,
                CandidateStage.SELECTED,
                CandidateStage.REJECTED,
            }
        ]
        offers_released = [c for c in candidates if (c.offer_status or "").lower() in {"made", "accepted"}]
        offers_accepted = [c for c in candidates if (c.offer_status or "").lower() == "accepted"]

        # If accepted offers are not tracked consistently, fallback to selected.
        total_hires = len(offers_accepted) if offers_accepted else len(selected_candidates)

        avg_time_to_hire = 0.0
        if selected_candidates:
            days = []
            for c in selected_candidates:
                start = c.created_at
                end = c.stage_updated_at or c.updated_at or c.created_at
                if start and end:
                    days.append(max(0, (end - start).days))
            avg_time_to_hire = round(sum(days) / len(days), 1) if days else 0.0

        offer_acceptance_rate = round(
            (len(offers_accepted) / len(offers_released) * 100), 1
        ) if offers_released else 0.0

        interview_to_hire_ratio = round(
            (len(interviewed_candidates) / total_hires), 2
        ) if total_hires > 0 else 0.0

        open_jobs_query = _apply_job_visibility(
            db.query(JobDescription).filter(JobDescription.is_active == True),
            db,
            current_user
        )
        if _role_name(current_user) == UserRole.ADMIN.value and client and client != "all":
            open_jobs_query = open_jobs_query.filter(JobDescription.company_name == client)
        if department and department != "all":
            open_jobs_query = open_jobs_query.filter(JobDescription.department == department)
        total_open_jobs = open_jobs_query.count()

        active_interviews = 0
        if candidate_ids:
            active_interviews = db.query(Interview).filter(
                Interview.candidate_id.in_(candidate_ids),
                Interview.status.in_(["scheduled", "in_progress"])
            ).count()

        return {
            "total_open_jobs": total_open_jobs,
            "total_candidates": total_candidates,
            "active_interviews": active_interviews,
            "offers_released": len(offers_released),
            "offers_accepted": len(offers_accepted),
            "total_hires": total_hires,
            "avg_time_to_hire": avg_time_to_hire,
            "offer_acceptance_rate": offer_acceptance_rate,
            "interview_to_hire_ratio": interview_to_hire_ratio,
        }

    current_metrics = _compute_metrics(current_start, current_end)
    previous_metrics = _compute_metrics(previous_start, previous_end)

    def _delta(current, previous):
        if previous == 0:
            if current == 0:
                return 0.0
            return 100.0
        return round(((current - previous) / abs(previous)) * 100, 1)

    labels = {
        "total_open_jobs": "Total Open Jobs",
        "total_candidates": "Total Candidates",
        "active_interviews": "Active Interviews",
        "offers_released": "Offers Released",
        "offers_accepted": "Offers Accepted",
        "total_hires": "Total Hires",
        "avg_time_to_hire": "Avg Time to Hire",
        "offer_acceptance_rate": "Offer Acceptance Rate",
        "interview_to_hire_ratio": "Interview-to-Hire Ratio",
    }

    kpis = []
    for key, label in labels.items():
        current_val = current_metrics[key]
        prev_val = previous_metrics.get(key, 0)
        change_pct = _delta(current_val, prev_val)
        trend = "up" if change_pct > 0 else "down" if change_pct < 0 else "flat"
        kpis.append({
            "key": key,
            "label": label,
            "value": current_val,
            "change_pct": change_pct,
            "trend": trend
        })

    return {
        "period": {
            "current_start": current_start.isoformat(),
            "current_end": current_end.isoformat(),
            "previous_start": previous_start.isoformat(),
            "previous_end": previous_end.isoformat(),
        },
        "kpis": kpis
    }

@router.get("/time-to-hire", response_model=List[TimeToHireData])
def get_time_to_hire(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.stage == CandidateStage.SELECTED),
        current_user
    ).all()

    month_buckets = {}
    for candidate in candidates:
        if not candidate.created_at:
            continue
        month_key = candidate.created_at.strftime("%b")
        end_date = candidate.stage_updated_at or candidate.updated_at or candidate.created_at
        days = max(1, (end_date - candidate.created_at).days) if end_date else 1
        month_buckets.setdefault(month_key, []).append(days)

    if not month_buckets:
        return [
            TimeToHireData(month="Aug", avg_days=28.5),
            TimeToHireData(month="Sep", avg_days=32.1),
            TimeToHireData(month="Oct", avg_days=25.8),
            TimeToHireData(month="Nov", avg_days=30.2),
            TimeToHireData(month="Dec", avg_days=35.7),
            TimeToHireData(month="Jan", avg_days=27.3),
        ]

    return [
        TimeToHireData(month=month, avg_days=round(sum(days) / len(days), 1))
        for month, days in month_buckets.items()
    ]

@router.get("/skill-heatmap", response_model=List[SkillHeatmapData])
def get_skill_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Skill aliases - map variations to canonical form
    SKILL_ALIASES = {
        'js': 'javascript',
        'ts': 'typescript',
        'py': 'python',
        'node': 'node.js',
        'nodejs': 'node.js',
        'react.js': 'react',
        'reactjs': 'react',
        'vue.js': 'vue',
        'vuejs': 'vue',
        'angular.js': 'angular',
        'angularjs': 'angular',
        'next': 'next.js',
        'nextjs': 'next.js',
        'express.js': 'express',
        'expressjs': 'express',
        'mongo': 'mongodb',
        'postgres': 'postgresql',
        'k8s': 'kubernetes',
        'docker-compose': 'docker',
        'git': 'git',
        'github': 'git',
        'gitlab': 'git'
    }
    
    def normalize_skill(skill: str) -> str:
        """Normalize skill name using aliases"""
        skill_lower = skill.lower().strip()
        return SKILL_ALIASES.get(skill_lower, skill_lower)
    
    # Comprehensive blacklist of non-skill terms
    blacklist = {
        'engineering', 'communication', 'course', 'institute', 'university', 'board', 'year', 'of',
        'telangana', 'state', 'andhra', 'pradesh', 'karnataka', 'maharashtra', 'tamil', 'nadu',
        'delhi', 'mumbai', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'pune', 'ahmedabad',
        'education', 'experience', 'projects', 'summary', 'objective', 'profile', 'resume',
        'curriculum', 'vitae', 'personal', 'details', 'information', 'contact', 'address',
        'date', 'birth', 'gender', 'nationality', 'marital', 'status', 'languages', 'hobbies',
        'interests', 'references', 'declaration', 'certifications', 'achievements', 'awards',
        'responsibilities', 'duties', 'role', 'position', 'designation', 'company', 'organization',
        'duration', 'period', 'from', 'to', 'present', 'current', 'previous', 'former',
        'bachelor', 'master', 'degree', 'diploma', 'phd', 'doctorate', 'undergraduate', 'graduate',
        'cgpa', 'percentage', 'marks', 'grade', 'score', 'result', 'passed', 'completed',
        'school', 'college', 'university', 'institution', 'academy', 'center', 'centre',
        'instituteuniversity', 'boardyear', 'enginnering', 'year of', 'institute university',
        'enginnering)', 'course  institute  university/board  year  of', 'telangana state',
        'board of', 'achieve  objectives.', 'narayana', '(electroins and', 'academic  qualifications:  -',
        'junior  college', 'passing  gpa  /', 'jntuh', 'intermediate', 'inter(mpc)', 'cmr engineering',
        'b. tech', 'b.tech', 'tech', 'mpc', 'qualifications', 'objectives', 'electroins', 'gpa',
        'teamwork', 'leadership', 'problem solving', 'analytical', 'critical thinking', 'time management',
        'work ethic', 'adaptability', 'creativity', 'collaboration', 'interpersonal', 'organizational',
        'attention to detail', 'multitasking', 'decision making', 'conflict resolution', 'negotiation',
        'presentation', 'public speaking', 'customer service', 'sales', 'marketing', 'management',
        'highly relevant', 'relevant', 'signals', 'jd', 'workexperience', 'work experience'
    }
    
    # Whitelist of valid technical skills
    valid_skills = {
        # Programming Languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust',
        'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl', 'dart', 'c', 'objective-c',
        # Web Technologies
        'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel',
        'rails', 'html', 'html5', 'css', 'css3', 'bootstrap', 'tailwind', 'jquery', 'next.js',
        'nuxt', 'svelte', 'ember', 'backbone', 'asp.net', '.net', 'blazor',
        # Databases
        'mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle', 'sql', 'sql server',
        'cassandra', 'dynamodb', 'firebase', 'mariadb', 'elasticsearch', 'neo4j', 'couchdb',
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'github', 'gitlab',
        'ci/cd', 'terraform', 'ansible', 'heroku', 'netlify', 'vercel', 'circleci', 'travis ci',
        # Data Science & ML
        'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'pandas', 'numpy',
        'scikit-learn', 'data analysis', 'ai', 'nlp', 'keras', 'opencv', 'spark', 'hadoop',
        # APIs & Architecture
        'rest api', 'graphql', 'microservices', 'linux', 'unix', 'bash', 'shell', 'powershell',
        'api', 'restful', 'soap', 'grpc', 'websocket',
        # Mobile
        'android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic',
        # Tools & Others
        'jira', 'confluence', 'slack', 'postman', 'vs code', 'intellij', 'eclipse', 'figma',
        'photoshop', 'illustrator', 'sketch', 'xd', 'webpack', 'vite', 'babel', 'npm', 'yarn',
        'maven', 'gradle', 'selenium', 'cypress', 'jest', 'mocha', 'junit', 'pytest'
    }
    
    # Get candidates with skills
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.skills.isnot(None)),
        current_user
    ).all()
    
    skill_data = {}
    for candidate in candidates:
        if candidate.skills:
            for skill in candidate.skills:
                skill_lower = skill.lower().strip()
                
                # Skip if contains special characters like %, +, numbers at start
                if any(char in skill for char in ['%', '+', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']):
                    continue
                
                # Filter: must be in whitelist OR (not in blacklist AND length 2-30 AND alphanumeric)
                is_valid = (
                    skill_lower in valid_skills or
                    (skill_lower not in blacklist and 
                     2 <= len(skill) <= 30 and 
                     skill.replace('.', '').replace('-', '').replace(' ', '').replace('#', '').isalpha())
                )
                
                if is_valid:
                    # Normalize using aliases, then use as key for aggregation
                    normalized = normalize_skill(skill)
                    if normalized not in skill_data:
                        skill_data[normalized] = {"count": 0, "scores": []}
                    skill_data[normalized]["count"] += 1
                    if candidate.resume_score:
                        skill_data[normalized]["scores"].append(candidate.resume_score)
    
    # If we have real data, use it
    if skill_data:
        result = []
        for skill_lower, data in skill_data.items():
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            # Capitalize first letter for display
            skill_display = skill_lower.capitalize()
            result.append(SkillHeatmapData(
                skill=skill_display,
                count=data["count"],
                avg_score=round(avg_score, 1)
            ))
        result.sort(key=lambda x: x.count, reverse=True)
        return result[:15]
    
    # Fallback to demo data if no real data
    custom_skills = [
        {"skill": "Python", "count": 24, "avg_score": 87.5},
        {"skill": "JavaScript", "count": 22, "avg_score": 84.2},
        {"skill": "React", "count": 18, "avg_score": 86.1},
        {"skill": "Node.js", "count": 16, "avg_score": 83.7},
        {"skill": "SQL", "count": 20, "avg_score": 82.3},
        {"skill": "AWS", "count": 15, "avg_score": 88.9},
        {"skill": "Docker", "count": 14, "avg_score": 85.4},
        {"skill": "Machine Learning", "count": 12, "avg_score": 89.2},
        {"skill": "Java", "count": 13, "avg_score": 81.8},
        {"skill": "TypeScript", "count": 11, "avg_score": 87.6},
        {"skill": "Kubernetes", "count": 9, "avg_score": 90.1},
        {"skill": "MongoDB", "count": 10, "avg_score": 83.5},
        {"skill": "GraphQL", "count": 8, "avg_score": 86.8},
        {"skill": "Redis", "count": 7, "avg_score": 84.9},
        {"skill": "Microservices", "count": 6, "avg_score": 88.3}
    ]
    
    return [SkillHeatmapData(**skill) for skill in custom_skills]

@router.get("/score-distribution", response_model=List[ScoreDistribution])
def get_score_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Define score ranges
    ranges = [
        ("0-20", 0, 20),
        ("21-40", 21, 40),
        ("41-60", 41, 60),
        ("61-80", 61, 80),
        ("81-100", 81, 100),
    ]
    
    result = []
    base_query = _apply_candidate_visibility(db.query(Candidate), current_user)
    for range_label, min_score, max_score in ranges:
        count = base_query.filter(
            Candidate.resume_score >= min_score,
            Candidate.resume_score <= max_score
        ).count() or 0
        result.append(ScoreDistribution(range=range_label, count=count))
    
    return result

@router.get("/resume-scores-trend")
def get_resume_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.resume_score.isnot(None)),
        current_user
    ).all()

    month_scores = {}
    for candidate in candidates:
        if not candidate.created_at:
            continue
        month_key = candidate.created_at.strftime("%b")
        month_scores.setdefault(month_key, []).append(candidate.resume_score)

    if not month_scores:
        months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
        return [{"month": month, "avg_score": round(random.uniform(70, 85), 1)} for month in months]

    return [
        {"month": month, "avg_score": round(sum(scores) / len(scores), 1)}
        for month, scores in month_scores.items()
    ]

@router.get("/interview-scores-trend")
def get_interview_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    interviews = db.query(Interview).join(Candidate, Interview.candidate_id == Candidate.id)
    interviews = _apply_candidate_visibility(interviews, current_user).all()

    month_scores = {}
    for interview in interviews:
        if not interview.created_at:
            continue
        month_key = interview.created_at.strftime("%b")
        month_scores.setdefault(month_key, {"technical": [], "communication": []})
        if interview.technical_score is not None:
            month_scores[month_key]["technical"].append(interview.technical_score)
        if interview.communication_score is not None:
            month_scores[month_key]["communication"].append(interview.communication_score)

    if not month_scores:
        months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
        return [
            {
                "month": month,
                "technical": round(random.uniform(65, 85), 1),
                "communication": round(random.uniform(70, 90), 1)
            }
            for month in months
        ]

    result = []
    for month, scores in month_scores.items():
        tech = scores["technical"]
        comm = scores["communication"]
        result.append({
            "month": month,
            "technical": round(sum(tech) / len(tech), 1) if tech else 0,
            "communication": round(sum(comm) / len(comm), 1) if comm else 0
        })
    return result

@router.get("/hiring-by-department")
def get_hiring_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    jobs = _apply_job_visibility(db.query(JobDescription), db, current_user).all()
    
    # Group by department
    dept_data = {}
    for job in jobs:
        dept = job.department or "Other"
        if dept not in dept_data:
            dept_data[dept] = {"hired": 0, "open": 0}
        
        # Count selected candidates for this job
        hired = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SELECTED
        )
        hired = _apply_candidate_visibility(hired, current_user).scalar() or 0
        
        # Count open positions (vacancies - hired)
        open_positions = max(0, (job.vacancies or 1) - hired)
        
        dept_data[dept]["hired"] += hired
        dept_data[dept]["open"] += open_positions
    
    # Convert to list format
    result = [
        {"department": dept, "hired": data["hired"], "open": data["open"]}
        for dept, data in dept_data.items()
    ]
    
    return result

@router.get("/source-breakdown")
def get_source_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        Candidate.source,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.source.isnot(None)
    )
    results = _apply_candidate_visibility(results, current_user).group_by(Candidate.source).all()
    
    return [{"source": r.source, "count": r.count} for r in results]

@router.get("/decline-reasons")
def get_decline_reasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        Candidate.decline_reason,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.decline_reason.isnot(None)
    )
    results = _apply_candidate_visibility(results, current_user).group_by(Candidate.decline_reason).all()
    
    return [{"reason": r.decline_reason, "count": r.count} for r in results]

@router.get("/offer-acceptance-rate")
def get_offer_acceptance_rate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    offers_made_query = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status.in_(['made', 'accepted'])
    )
    offers_made = _apply_candidate_visibility(offers_made_query, current_user).scalar() or 0
    
    offers_accepted_query = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status == 'accepted'
    )
    offers_accepted = _apply_candidate_visibility(offers_accepted_query, current_user).scalar() or 0
    
    rate = round((offers_accepted / offers_made * 100), 1) if offers_made > 0 else 0
    
    return {
        "offers_made": offers_made,
        "offers_accepted": offers_accepted,
        "acceptance_rate": rate
    }

@router.get("/active-jobs")
def get_active_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    jobs = _apply_job_visibility(
        db.query(JobDescription).filter(JobDescription.is_active == True),
        db,
        current_user
    ).all()
    role_name = _role_name(current_user)
    
    result = []
    for job in jobs:
        # Count candidates for this job (EXCLUDING APPLIED stage)
        candidate_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage != CandidateStage.APPLIED
        )
        total_candidates = _apply_candidate_visibility(candidate_query, current_user).scalar() or 0
        
        # Skip jobs with no assigned candidates for non-admin users
        if role_name != UserRole.ADMIN.value and total_candidates == 0:
            continue
        
        selected_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SHORTLISTED
        )
        selected = _apply_candidate_visibility(selected_query, current_user).scalar() or 0
        
        # Determine status
        status = 'open'
        if hasattr(job, 'status') and job.status:
            status = job.status
        elif selected >= (job.vacancies or 1):
            status = 'filled'
        
        result.append({
            "id": job.id,
            "title": job.title,
            "company_name": job.company_name,
            "department": job.department,
            "vacancies": job.vacancies or 1,
            "candidates": total_candidates,
            "selected": selected,
            "status": status
        })
    
    return result

@router.get("/upcoming-interviews")
def get_upcoming_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from datetime import datetime, timedelta
    
    # Get interviews scheduled for next 7 days
    today = datetime.now()
    next_week = today + timedelta(days=7)
    
    interview_query = db.query(Interview).filter(
        Interview.scheduled_at >= today,
        Interview.scheduled_at <= next_week,
        Interview.status == 'scheduled'
    )

    if _role_name(current_user) != UserRole.ADMIN.value:
        interview_query = interview_query.join(Candidate, Interview.candidate_id == Candidate.id)
        interview_query = _apply_candidate_visibility(interview_query, current_user)
    
    interviews = interview_query.order_by(Interview.scheduled_at).limit(10).all()
    recording_metadata = _fetch_interview_session_metadata(db, interviews)
    
    result = []
    for interview in interviews:
        recording = recording_metadata.get(str(interview.id), {})
        result.append({
            "id": interview.id,
            "candidate_name": interview.candidate.name if interview.candidate else "Unknown",
            "candidate_id": interview.candidate_id,
            "interview_type": interview.interview_type,
            "scheduled_at": interview.scheduled_at.isoformat() if interview.scheduled_at else None,
            "duration_minutes": interview.duration_minutes,
            "recording_path": recording.get("recording_path"),
            "recording_format": recording.get("recording_format"),
            "recording_duration_seconds": recording.get("recording_duration_seconds"),
            "vapi_recording_url": recording.get("vapi_recording_url"),
            "session_token": recording.get("session_token"),
            "recording_size_bytes": recording.get("recording_size_bytes"),
            "recording_created_at": recording.get("recording_created_at"),
            "has_candidate_recording": recording.get("has_candidate_recording", False),
            "has_vapi_recording": recording.get("has_vapi_recording", False),
        })
    
    return result

@router.get("/hiring-intelligence")
def get_hiring_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from datetime import datetime, timedelta
    
    insights = []
    
    # 1. Detect candidates stuck in stages (>7 days)
    stuck_candidates = _apply_candidate_visibility(db.query(Candidate).filter(
        Candidate.stage.in_([CandidateStage.SHORTLISTED, CandidateStage.INTERVIEW_SCHEDULED]),
        Candidate.stage_entered_at.isnot(None)
    ), current_user).all()
    
    stuck_count = 0
    for c in stuck_candidates:
        days_in_stage = (datetime.utcnow() - c.stage_entered_at).days
        if days_in_stage > 7:
            stuck_count += 1
    
    if stuck_count > 0:
        insights.append(f"{stuck_count} candidate{'s' if stuck_count > 1 else ''} waiting over 7 days in pipeline - action needed")
    
    # 2. High-scoring candidates ready for interview
    ready_candidates_query = db.query(Candidate).filter(
        Candidate.stage == CandidateStage.SHORTLISTED,
        Candidate.resume_score >= 85
    )
    ready_candidates = _apply_candidate_visibility(ready_candidates_query, current_user).count()
    
    if ready_candidates > 0:
        insights.append(f"{ready_candidates} high-scoring candidate{'s' if ready_candidates > 1 else ''} (85+) ready for interview scheduling")
    
    visible_candidates = _apply_candidate_visibility(db.query(Candidate), current_user).all()
    visible_candidate_ids = [candidate.id for candidate in visible_candidates]
    latest_interviews_by_candidate = _get_latest_filtered_interviews_by_candidate(db, visible_candidate_ids)

    # 3. Interviews completed awaiting decision
    interviewed = sum(
        1
        for interview in latest_interviews_by_candidate.values()
        if interview and (interview.status or '').strip().lower() == 'completed'
    )
    
    if interviewed > 0:
        insights.append(f"{interviewed} interview{'s' if interviewed > 1 else ''} completed - pending hiring decision")
    
    # 4. Jobs with no recent activity
    jobs = _apply_job_visibility(
        db.query(JobDescription).filter(JobDescription.is_active == True),
        db,
        current_user
    ).all()
    stale_jobs = []
    for job in jobs:
        recent_candidates_query = db.query(Candidate).filter(
            Candidate.job_id == job.id,
            Candidate.created_at >= datetime.utcnow() - timedelta(days=14)
        )
        recent_candidates = _apply_candidate_visibility(recent_candidates_query, current_user).count()
        if recent_candidates == 0:
            stale_jobs.append(job.title)
    
    if len(stale_jobs) > 0:
        insights.append(f"{len(stale_jobs)} role{'s' if len(stale_jobs) > 1 else ''} with no applications in 14 days - review job posting")
    
    # 5. Offer-ready candidates
    candidate_map = {candidate.id: candidate for candidate in visible_candidates}
    offer_ready = sum(
        1
        for candidate_id, interview in latest_interviews_by_candidate.items()
        if interview
        and (interview.status or '').strip().lower() == 'completed'
        and (interview.interview_score or 0) >= INTERVIEW_RESULT_THRESHOLD
        and (candidate_map.get(candidate_id).resume_score or 0) >= 80
    )
    
    if offer_ready > 0:
        insights.append(f"{offer_ready} strong candidate{'s' if offer_ready > 1 else ''} ready for offer - don't lose them to competitors")
    
    # If no insights, add positive message
    if len(insights) == 0:
        insights.append("Pipeline is healthy - all candidates progressing smoothly")
        insights.append("No urgent actions required today")
    
    return {"insights": insights[:5]}

@router.get("/hiring-metrics")
def get_hiring_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    base_candidates = _apply_candidate_visibility(db.query(Candidate), current_user)
    total_candidates = base_candidates.count() or 0
    selected_count = base_candidates.filter(Candidate.stage == CandidateStage.SELECTED).count() or 0
    shortlisted_count = base_candidates.filter(Candidate.stage == CandidateStage.SHORTLISTED).count() or 0
    offers_made = base_candidates.filter(Candidate.offer_status.in_(['made', 'accepted'])).count() or 0
    offers_accepted = base_candidates.filter(Candidate.offer_status == 'accepted').count() or 0

    acceptance_rate = round((offers_accepted / offers_made * 100), 1) if offers_made > 0 else 0
    conversion_rate = round((selected_count / total_candidates * 100), 1) if total_candidates > 0 else 0

    visible_jobs = _apply_job_visibility(db.query(JobDescription).filter(JobDescription.is_active == True), db, current_user).all()
    total_vacancies = sum((j.vacancies or 1) for j in visible_jobs)
    vacancy_fill_rate = round((selected_count / total_vacancies * 100), 1) if total_vacancies > 0 else 0

    return {
        "all": {
            "time_to_hire": 18,
            "time_to_fill": 25,
            "offer_acceptance_rate": acceptance_rate,
            "withdrawal_rate": 12,
            "cost_per_hire": 3500,
            "hire_conversion": conversion_rate,
            "vacancy_fill_rate": vacancy_fill_rate,
            "weekly_change": {
                "time_to_hire": -2.5,
                "time_to_fill": -3.1,
                "offer_acceptance_rate": 5.2,
                "withdrawal_rate": -1.8,
                "cost_per_hire": -8.3,
                "hire_conversion": 2.1,
                "vacancy_fill_rate": 4.5
            }
        },
        "technical": {
            "days_to_hire": 22,
            "days_to_fill": 30,
            "acceptance_rate": 70,
            "withdrawal_rate": 15
        },
        "non_technical": {
            "days_to_hire": 14,
            "days_to_fill": 20,
            "acceptance_rate": 80,
            "withdrawal_rate": 8
        },
        "pipeline": [
            {
                "role": "Senior Backend Engineer",
                "department": "technical",
                "leads": 150,
                "applicants": 85,
                "first_interview": 25,
                "second_interview": 12,
                "final_interview": 6,
                "offers": 3
            },
            {
                "role": "Frontend Developer",
                "department": "technical",
                "leads": 120,
                "applicants": 70,
                "first_interview": 22,
                "second_interview": 10,
                "final_interview": 5,
                "offers": 2
            },
            {
                "role": "HR Manager",
                "department": "non_technical",
                "leads": 80,
                "applicants": 45,
                "first_interview": 18,
                "second_interview": 8,
                "final_interview": 4,
                "offers": 2
            }
        ],
        "offer_stats": {
            "offers_accepted": offers_accepted,
            "offers_provided": offers_made,
            "rejected_candidates": max(0, total_candidates - shortlisted_count),
            "total_candidates": total_candidates,
            "hired": selected_count,
            "shortlisted": shortlisted_count,
            "vacancies": total_vacancies
        }
    }

@router.get("/time-to-hire-stages")
def get_time_to_hire_stages(
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription
    import random
    
    # Demo data with stage breakdown
    base_data = [
        {"month": "Aug", "screening": 5.2, "scheduling": 3.8, "technical": 12.5, "offer": 7.0, "dropoff": 15},
        {"month": "Sep", "screening": 6.1, "scheduling": 4.2, "technical": 14.8, "offer": 7.0, "dropoff": 18},
        {"month": "Oct", "screening": 4.5, "scheduling": 3.2, "technical": 11.1, "offer": 7.0, "dropoff": 12},
        {"month": "Nov", "screening": 5.8, "scheduling": 4.5, "technical": 13.2, "offer": 6.7, "dropoff": 16},
        {"month": "Dec", "screening": 7.2, "scheduling": 5.5, "technical": 15.5, "offer": 7.5, "dropoff": 22},
        {"month": "Jan", "screening": 4.8, "scheduling": 3.5, "technical": 12.0, "offer": 7.0, "dropoff": 14}
    ]
    
    # Adjust based on filters
    if department == "Engineering":
        for d in base_data:
            d["technical"] *= 1.3
            d["dropoff"] += 5
    elif department == "Sales":
        for d in base_data:
            d["screening"] *= 0.7
            d["technical"] *= 0.6
    
    return base_data
