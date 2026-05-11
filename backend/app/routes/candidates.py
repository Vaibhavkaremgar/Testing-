from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy import String, func, or_, text
from typing import Dict, List, Optional
from uuid import UUID
import hashlib
import os
import re
import uuid
import random
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from time import monotonic, perf_counter
from app.database import SessionLocal, get_db
from app.models import Candidate, CandidateStage, Interview, ParsingStatus, User, JobDescription
from app.plan_dependency import enforce_plan
from app.plan_service import increment_plan_usage
from app.notification_service import queue_notification_for_stage, send_email_task
from app.schemas import (
    CandidateCreate, CandidateUpdate, CandidateResponse, CandidateStageUpdate
)
from app.auth import get_current_active_user
from app.config import settings
from ats.extraction.information_extraction import (
    LANGUAGE_TERMS,
    extract_email,
    extract_education_entries,
    extract_experience_entries,
    extract_skill_keywords,
)
from ats.extraction.experience_extraction import compute_total_experience, extract_date_ranges, parse_date
from ats.extraction.resume_parser import parse_resume
from ats.extraction.skill_intelligence import get_skill_engine
from ats.extraction.summary_generator import generate_summary
from ats.extraction.validation import validate_current_company, validate_current_role
from ats.features import build_feature_vector
from ats.matching import compute_matching_signals
from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import clean_text, clean_text_pipeline
from ats.ranking import compute_ranking_result

router = APIRouter(prefix="/candidates", tags=["Candidates"])
upload_progress_store = {}
ALLOWED_RESUME_EXTENSIONS = {'.pdf', '.doc', '.docx'}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS = 300
_legacy_stage_normalization_lock = Lock()
_legacy_stage_last_checked_at = 0.0
_candidate_scope_last_checked_at = 0.0
UPLOAD_REQUEST_DEDUPLICATION_WINDOW_SECONDS = 180
_recent_upload_requests: dict[tuple[str, str, str, str], tuple[float, str]] = {}
_recent_upload_requests_lock = Lock()
LOCATION_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:managing|managed|operations|including|across|responsible|experience|years|sales|development|engineer|developer|manager|executive|specialist|lead|worked|work|support|project|projects|regional)\b"
)
INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30))


def normalize_legacy_candidate_stages(db: Session) -> None:
    """Self-heal stale enum values that can crash ORM reads on older rows."""
    global _legacy_stage_last_checked_at
    now = monotonic()
    if (now - _legacy_stage_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
        return

    with _legacy_stage_normalization_lock:
        now = monotonic()
        if (now - _legacy_stage_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
            return
        _legacy_stage_last_checked_at = now

    # Map every known legacy value to its valid replacement
    legacy_stage_map = {
        'INTERVIEW_REVIEW': 'INTERVIEWED',
        'INTERVIEW_FAILED': 'REJECTED',
        'OFFER_MADE': 'SELECTED',
        'OFFER_ACCEPTED': 'SELECTED',
        'OFFER_REJECTED': 'REJECTED',
        'WITHDRAWN': 'REJECTED',
        'ON_HOLD': 'REVIEW',
    }
    valid_stages = {s.value for s in CandidateStage}
    total_updated = 0
    for legacy_value, replacement in legacy_stage_map.items():
        result = db.execute(text(
            f"UPDATE candidates SET stage = '{replacement}' "
            f"WHERE stage::text = '{legacy_value}'"
        ))
        total_updated += result.rowcount
    # Catch-all: any remaining unknown value → REVIEW
    result = db.execute(text(
        "UPDATE candidates SET stage = 'REVIEW' "
        "WHERE stage::text NOT IN ("
        + ", ".join(f"'{v}'" for v in valid_stages)     
        + ")"
    ))
    total_updated += result.rowcount
    if total_updated:
        print(f"Normalized legacy candidate stages: rows_updated={total_updated}")
        db.commit()
    normalize_candidate_scope_metadata(db)


def normalize_candidate_scope_metadata(db: Session) -> None:
    """Backfill missing candidate scope metadata from existing workflow/job ownership records."""
    global _candidate_scope_last_checked_at
    now = monotonic()
    if (now - _candidate_scope_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
        return

    with _legacy_stage_normalization_lock:
        now = monotonic()
        if (now - _candidate_scope_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
            return
        _candidate_scope_last_checked_at = now

    result = db.execute(text(
        """
        WITH latest_workflow AS (
            SELECT DISTINCT ON (candidate_id)
                candidate_id,
                job_id,
                agency_id,
                user_id
            FROM notification_workflow_tokens
            WHERE candidate_id IS NOT NULL
            ORDER BY candidate_id, created_at DESC
        ),
        latest_booking AS (
            SELECT DISTINCT ON (candidate_id)
                candidate_id,
                job_id,
                agency_id,
                user_id
            FROM booking_links
            WHERE candidate_id IS NOT NULL
            ORDER BY candidate_id, created_at DESC
        ),
        candidate_fallbacks AS (
            SELECT
                c.id AS candidate_id,
                COALESCE(c.assigned_to_user_id, lw.user_id, lb.user_id, c.created_by) AS resolved_assigned_to_user_id,
                COALESCE(c.job_id, lw.job_id, lb.job_id) AS resolved_job_id,
                COALESCE(
                    c.agency_id,
                    job.agency_id,
                    lw.agency_id,
                    lb.agency_id,
                    assignee.agency_id,
                    creator.agency_id
                ) AS resolved_agency_id
            FROM candidates c
            LEFT JOIN latest_workflow lw ON lw.candidate_id = c.id
            LEFT JOIN latest_booking lb ON lb.candidate_id = c.id
            LEFT JOIN users creator ON creator.id = c.created_by
            LEFT JOIN users assignee ON assignee.id = COALESCE(c.assigned_to_user_id, lw.user_id, lb.user_id, c.created_by)
            LEFT JOIN job_descriptions job ON job.id = COALESCE(c.job_id, lw.job_id, lb.job_id)
            WHERE c.assigned_to_user_id IS NULL OR c.agency_id IS NULL OR c.job_id IS NULL
        )
        UPDATE candidates c
        SET
            assigned_to_user_id = COALESCE(c.assigned_to_user_id, f.resolved_assigned_to_user_id),
            job_id = COALESCE(c.job_id, f.resolved_job_id),
            agency_id = COALESCE(c.agency_id, f.resolved_agency_id)
        FROM candidate_fallbacks f
        WHERE c.id = f.candidate_id
          AND (
              (c.assigned_to_user_id IS NULL AND f.resolved_assigned_to_user_id IS NOT NULL)
              OR (c.job_id IS NULL AND f.resolved_job_id IS NOT NULL)
              OR (c.agency_id IS NULL AND f.resolved_agency_id IS NOT NULL)
          )
        """
    ))
    if result.rowcount:
        print(f"Normalized candidate scope metadata: rows_updated={result.rowcount}")
        db.commit()


def _perf_log(endpoint: str, total_start: float, **fields) -> None:
    parts = [f"{key}={value}" for key, value in fields.items()]
    parts.append(f"total={perf_counter() - total_start:.4f}s")
    print(f"[PERF] {endpoint} " + " ".join(parts))


def _ats_timing_log(**fields) -> None:
    ordered_labels = [
        ("Resume Name", "resume_name"),
        ("File Upload", "file_upload_ms"),
        ("PDF Parse", "pdf_parse_ms"),
        ("DOCX Parse", "docx_parse_ms"),
        ("Section Detection", "section_detection_ms"),
        ("Name Extraction", "name_extraction_ms"),
        ("Experience Extraction", "experience_extraction_ms"),
        ("Skill Extraction", "skill_extraction_ms"),
        ("spaCy Execution", "spacy_execution_ms"),
        ("Regex Processing", "regex_processing_ms"),
        ("OCR Triggered", "ocr_triggered"),
        ("OCR Time", "ocr_time_ms"),
        ("OCR Timed Out", "ocr_timed_out"),
        ("Pages Processed", "pages_processed"),
        ("Warmup Used", "warmup_used"),
        ("Models Loaded", "models_loaded"),
        ("Database Save", "database_save_ms"),
        ("Processing Time", "total_time_ms"),
        ("Slowest Component", "slowest_component"),
        ("Bottleneck Time", "bottleneck_time_ms"),
        ("Bottleneck > 3s", "bottleneck_exceeds_threshold"),
    ]
    lines = ["[ATS TIMING]"]
    for label, key in ordered_labels:
        if key in fields:
            value = fields[key]
            suffix = " ms" if isinstance(value, (int, float)) and label not in {"OCR Triggered", "Warmup Used", "Models Loaded", "Resume Name", "Slowest Component"} else ""
            lines.append(f"{label}: {value}{suffix}")
    print("\n".join(lines))


def _cleanup_recent_upload_requests(now: Optional[float] = None) -> None:
    current_time = now if now is not None else monotonic()
    expired_keys = [
        key for key, (created_at, _upload_id) in _recent_upload_requests.items()
        if (current_time - created_at) > UPLOAD_REQUEST_DEDUPLICATION_WINDOW_SECONDS
    ]
    for key in expired_keys:
        _recent_upload_requests.pop(key, None)


def _register_recent_upload_request(
    *,
    current_user: User,
    job_id: Optional[UUID],
    original_filename: str,
    file_bytes: bytes,
    upload_id: str,
) -> Optional[str]:
    fingerprint = hashlib.sha256(file_bytes).hexdigest()
    dedupe_key = (
        str(current_user.id),
        str(job_id or ""),
        str(original_filename or "").strip().lower(),
        fingerprint,
    )
    now = monotonic()

    with _recent_upload_requests_lock:
        _cleanup_recent_upload_requests(now)
        existing = _recent_upload_requests.get(dedupe_key)
        if existing is not None:
            return existing[1]

        _recent_upload_requests[dedupe_key] = (now, upload_id)
        return None


def _resolve_pagination(page: Optional[int], limit: Optional[int], offset: Optional[int]) -> tuple[Optional[int], int]:
    """Support page/limit while keeping legacy unpaginated calls working."""
    if offset is not None or limit is not None or page is not None:
        safe_limit = max(1, min(limit or 20, 200))
        safe_page = max(page or 1, 1)
        effective_offset = offset if offset is not None else (safe_page - 1) * safe_limit
        return safe_limit, max(0, effective_offset)
    return None, 0


def _get_india_today() -> date:
    """Use the slot-booking local date so interview_slots.slot_date maps consistently on hosted servers."""
    return datetime.now(timezone.utc).astimezone(INDIA_TIMEZONE).date()


def _get_india_local_date(value: Optional[datetime]) -> Optional[date]:
    """Normalize interview timestamps to the slot-booking local date when timezone data exists."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.date()
    return value.astimezone(INDIA_TIMEZONE).date()


def _build_slot_candidate_lookup(
    db: Session,
    candidate_ids: List[UUID],
) -> dict[str, UUID]:
    """Support slot tables that store either candidate UUIDs or external candidate_id strings."""
    if not candidate_ids:
        return {}

    rows = (
        db.query(Candidate.id, Candidate.candidate_id)
        .filter(Candidate.id.in_(candidate_ids))
        .all()
    )

    lookup: dict[str, UUID] = {}
    for candidate_uuid, candidate_code in rows:
        lookup[str(candidate_uuid)] = candidate_uuid
        if candidate_code:
            lookup[str(candidate_code).strip()] = candidate_uuid
    return lookup


def _apply_candidate_list_scope(query, current_user):
    from sqlalchemy.orm import aliased
    from app.models import JobDescription, User, UserRole

    if current_user.role == UserRole.SUPER_ADMIN:
        return query

    creator = aliased(User)
    assignee = aliased(User)

    if current_user.role == UserRole.ADMIN and current_user.agency_id:
        return query.outerjoin(JobDescription, Candidate.job_id == JobDescription.id).outerjoin(
            creator, Candidate.created_by == creator.id
        ).outerjoin(
            assignee, Candidate.assigned_to_user_id == assignee.id
        ).filter(
            or_(
                Candidate.agency_id == current_user.agency_id,
                JobDescription.agency_id == current_user.agency_id,
                creator.agency_id == current_user.agency_id,
                assignee.agency_id == current_user.agency_id,
            )
        )

    if current_user.role != UserRole.ADMIN:
        return query.filter(Candidate.assigned_to_user_id == current_user.id)

    return query


def _apply_client_filter(query, client: Optional[str]):
    if not client:
        return query

    normalized_client = client.strip().lower()
    if not normalized_client:
        return query

    return query.filter(
        Candidate.job.has(
            func.lower(func.trim(JobDescription.company_name)) == normalized_client
        )
    )


def _apply_candidate_search_filter(query, search: Optional[str]):
    normalized_search = str(search or "").strip()
    if not normalized_search:
        return query

    pattern = f"%{normalized_search}%"
    return query.filter(
        or_(
            Candidate.name.ilike(pattern),
            Candidate.email.ilike(pattern),
            Candidate.current_role.ilike(pattern),
            Candidate.current_company.ilike(pattern),
            Candidate.skills.cast(String).ilike(pattern),
            Candidate.job.has(
                or_(
                    JobDescription.title.ilike(pattern),
                    JobDescription.company_name.ilike(pattern),
                    JobDescription.location.ilike(pattern),
                    JobDescription.department.ilike(pattern),
                )
            ),
        )
    )


def _apply_candidate_created_at_filters(
    query,
    *,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    if from_date:
        query = query.filter(func.date(Candidate.created_at) >= from_date)
    if to_date:
        query = query.filter(func.date(Candidate.created_at) <= to_date)
    return query


def _normalize_candidate_duplicate_name(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).lower()


def _normalize_candidate_duplicate_email(value: Optional[str]) -> str:
    return str(value or "").strip().lower()


def _find_duplicate_candidate_for_job(
    db: Session,
    *,
    name: Optional[str],
    email: Optional[str],
    job_id: Optional[UUID],
):
    normalized_name = _normalize_candidate_duplicate_name(name)
    normalized_email = _normalize_candidate_duplicate_email(email)
    if not normalized_name or not normalized_email or not job_id:
        return None

    candidates = db.query(Candidate).filter(Candidate.job_id == job_id).all()
    for candidate in candidates:
        if (
            _normalize_candidate_duplicate_name(candidate.name) == normalized_name
            and _normalize_candidate_duplicate_email(candidate.email) == normalized_email
        ):
            return candidate
    return None


def get_bulk_processing_workers(item_count: int) -> int:
    """Keep worker count bounded so batch uploads scale without exhausting the host."""
    cpu_count = os.cpu_count() or 4
    return max(2, min(8, cpu_count, item_count or 1))


def sanitize_candidate_location(value: Optional[str]) -> Optional[str]:
    """Keep only compact location strings so resume narrative text never leaks into UI fields."""
    if not value:
        return None

    cleaned = re.sub(r"\s+", " ", value).strip(" ,.-")
    if not cleaned:
        return None
    if len(cleaned) > 80 or LOCATION_NOISE_PATTERN.search(cleaned):
        return None
    if any(char.isdigit() for char in cleaned):
        return None
    if len(cleaned.split()) > 5:
        return None
    if re.match(r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*(?:,\s*[A-Za-z]+(?:[\s-][A-Za-z]+)*){0,2}$", cleaned):
        return cleaned
    return None


def sanitize_candidate_email(value: Optional[str]) -> Optional[str]:
    """Return only a valid compact email string so bad legacy values don't crash API responses."""
    if not value:
        return None

    cleaned = re.sub(r"\s+", "", value).strip(".,;:|")
    if not cleaned:
        return None

    extracted = extract_email(cleaned)
    if extracted:
        return extracted

    return None


def sanitize_resume_skills(skills: Optional[List[str]], languages: Optional[List[str]] = None) -> List[str]:
    """Remove spoken-language entries from extracted skills for all upload modes."""
    language_terms = {str(term).strip().lower() for term in LANGUAGE_TERMS}
    language_terms.update(str(language).strip().lower() for language in (languages or []) if str(language).strip())
    language_terms.update({
        "language",
        "languages",
        "known languages",
        "spoken languages",
        "english",
        "hindi",
        "tamil",
        "telugu",
        "malayalam",
        "kannada",
        "marathi",
        "gujarati",
        "bengali",
        "urdu",
        "punjabi",
    })

    sanitized_skills: List[str] = []
    seen: set[str] = set()
    for skill in skills or []:
        normalized = re.sub(r"\s+", " ", str(skill or "")).strip()
        lowered = normalized.lower()
        if not normalized or lowered in language_terms:
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        sanitized_skills.append(normalized)

    return sanitized_skills



def _compute_field_confidence(candidate) -> dict:
    """Compute per-field confidence scores for Step 7/8/10 of the ATS spec."""
    try:
        name = candidate.name or ""
        role = candidate.current_role or ""
        location = candidate.location or ""
        exp_years = candidate.experience_years
        has_skills = bool(candidate.skills)
        has_email = bool(candidate.email)

        # Simple inline scoring — no external imports needed
        name_score = 85 if (name and len(name.split()) >= 2 and not name.lower().startswith("unknown")) else (40 if name else 0)
        role_score = 85 if (role and any(kw in role.lower() for kw in ["engineer","developer","manager","analyst","architect","qa","automation","backend","frontend","tester","specialist","consultant","lead"])) else (50 if role else 0)
        location_score = 85 if (location and "," in location) else (60 if location else 0)
        experience_score = 85 if (exp_years is not None and exp_years > 0) else (50 if exp_years == 0 else 0)
        skills_score = 90 if has_skills else 0
        email_score = 100 if has_email else 0

        scores = {
            "name": name_score,
            "role": role_score,
            "location": location_score,
            "experience": experience_score,
            "skills": skills_score,
            "email": email_score,
        }
        # Step 8: fields with confidence >= 80 are shown, < 60 are hidden
        scores["display_fields"] = [f for f, v in scores.items() if isinstance(v, int) and v >= 80]
        scores["hidden_fields"] = [f for f, v in scores.items() if isinstance(v, int) and v < 60]
        return scores
    except Exception:
        return {}

def build_safe_candidate_response(candidate_dict: Dict) -> CandidateResponse:
    """Construct candidate responses defensively so one bad legacy field never crashes the API."""
    try:
        return CandidateResponse(**candidate_dict)
    except ValidationError:
        safe_candidate_dict = dict(candidate_dict)
        safe_candidate_dict["email"] = None
        safe_candidate_dict["parsing_status"] = candidate_dict.get("parsing_status") or ParsingStatus.PENDING
        safe_candidate_dict["stage"] = candidate_dict.get("stage") or (
            CandidateStage.REVIEW if candidate_dict.get("job_id") else CandidateStage.APPLIED
        )
        safe_candidate_dict["stage_updated_at"] = (
            candidate_dict.get("stage_updated_at")
            or candidate_dict.get("stage_entered_at")
            or candidate_dict.get("applied_at")
            or candidate_dict.get("created_at")
            or datetime.utcnow()
        )
        return CandidateResponse(**safe_candidate_dict)


def resolve_current_company_for_storage(
    work_experience: Optional[List[dict]],
    fallback_company: Optional[str],
    experience_text: str,
) -> Optional[str]:
    """Persist only a text company value from the most recent valid experience entry."""
    for entry in work_experience or []:
        company_value = entry.get("company") if isinstance(entry, dict) else None
        if not isinstance(company_value, str):
            continue
        validated = validate_current_company(company_value, experience_text or "")
        if validated:
            return validated

    if isinstance(fallback_company, str):
        return validate_current_company(fallback_company, experience_text or "") or None
    return None


def resolve_current_role_for_storage(
    work_experience: Optional[List[dict]],
    fallback_role: Optional[str],
    skills: Optional[List[str]],
) -> Optional[str]:
    """Persist only a valid text role from the most recent experience entry."""
    normalized_skills = skills or []
    for entry in work_experience or []:
        role_value = None
        if isinstance(entry, dict):
            role_value = entry.get("role") or entry.get("title")
        if not isinstance(role_value, str):
            continue
        validated = validate_current_role(role_value, normalized_skills)
        if validated:
            return validated

    if isinstance(fallback_role, str):
        return validate_current_role(fallback_role, normalized_skills) or None
    return None


def assign_resume_pipeline_stage(candidate: Candidate, score: Optional[float], threshold: Optional[float]) -> CandidateStage:
    """Apply the agreed resume stage bands: shortlisted, in review, or resume rejected."""
    effective_threshold = threshold or candidate.score_threshold or 60
    effective_score = score if score is not None else candidate.resume_score

    if effective_score is None:
        candidate.stage = CandidateStage.REVIEW if candidate.job_id else CandidateStage.APPLIED
        return candidate.stage

    if effective_score >= effective_threshold:
        candidate.stage = CandidateStage.SHORTLISTED
    elif effective_score > (effective_threshold - 10):
        candidate.stage = CandidateStage.REVIEW
    else:
        candidate.stage = CandidateStage.RESUME_REJECTED

    return candidate.stage


def resolve_pipeline_display_stage(candidate: Candidate, latest_interview: Optional[Interview], today) -> CandidateStage:
    """Derive the pipeline column using candidate-owned and interview-owned stages."""
    candidate_owned_stages = {
        CandidateStage.REVIEW,
        CandidateStage.SHORTLISTED,
        CandidateStage.RESUME_REJECTED,
        CandidateStage.INTERVIEW_RESCHEDULED,
        CandidateStage.NO_SHOW,
    }
    interview_owned_stages = {
        CandidateStage.INTERVIEW_SCHEDULED,
        CandidateStage.INTERVIEWED,
        CandidateStage.SELECTED,
        CandidateStage.REJECTED,
    }

    if candidate.stage in {CandidateStage.INTERVIEW_RESCHEDULED, CandidateStage.NO_SHOW}:
        return candidate.stage

    if latest_interview:
        interview_status = (latest_interview.status or "").strip().lower()

        if interview_status == "completed":
            return CandidateStage.INTERVIEWED

        if interview_status == "ongoing":
            return CandidateStage.INTERVIEWED

        if interview_status == "scheduled":
            return CandidateStage.INTERVIEW_SCHEDULED

    effective_threshold = candidate.score_threshold or 60
    if candidate.resume_score is not None and candidate.resume_score <= (effective_threshold - 10):
        return CandidateStage.RESUME_REJECTED

    if candidate.stage in candidate_owned_stages:
        return candidate.stage

    if candidate.stage in interview_owned_stages:
        return candidate.stage

    return candidate.stage


def is_interview_rejected(latest_interview: Optional[Interview]) -> bool:
    if not latest_interview:
        return False

    interview_status = (latest_interview.status or "").strip().lower()
    return interview_status == "rejected"


def resolve_reporting_pipeline_stage(candidate: Candidate, latest_interview: Optional[Interview], today) -> CandidateStage:
    if candidate.stage == CandidateStage.RESUME_REJECTED:
        return CandidateStage.RESUME_REJECTED

    if is_interview_rejected(latest_interview):
        return CandidateStage.REJECTED

    display_stage = resolve_pipeline_display_stage(candidate, latest_interview, today)
    if display_stage == CandidateStage.RESUME_REJECTED:
        return candidate.stage

    return display_stage


def resolve_slot_backed_pipeline_stage(
    candidate: Candidate,
    display_stage: CandidateStage,
    slot_stage: Optional[CandidateStage],
) -> CandidateStage:
    if slot_stage in {CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEWED}:
        return slot_stage

    return display_stage


def resolve_pipeline_rejected_stage(
    candidate: Candidate,
    display_stage: CandidateStage,
    latest_interview: Optional[Interview],
) -> CandidateStage:
    if display_stage != CandidateStage.REJECTED:
        return display_stage

    if latest_interview:
        interview_status = (latest_interview.status or "").strip().lower()
        if interview_status == "rejected":
            return CandidateStage.REJECTED
        if interview_status in {"completed", "ongoing"}:
            return CandidateStage.INTERVIEWED
        if interview_status in {"scheduled", "rescheduled"}:
            interview_date = latest_interview.scheduled_at.date() if latest_interview.scheduled_at else None
            if interview_date == datetime.now().date():
                return CandidateStage.INTERVIEWED
            return CandidateStage.INTERVIEW_SCHEDULED

    effective_threshold = candidate.score_threshold or 60
    if candidate.resume_score is not None and candidate.resume_score <= (effective_threshold - 10):
        return CandidateStage.RESUME_REJECTED

    if candidate.stage in {
        CandidateStage.REVIEW,
        CandidateStage.SHORTLISTED,
        CandidateStage.INTERVIEW_RESCHEDULED,
        CandidateStage.NO_SHOW,
        CandidateStage.SELECTED,
    }:
        return candidate.stage

    return CandidateStage.SHORTLISTED


def _get_interview_slot_pipeline_stages(db: Session, candidate_ids: List[UUID], today) -> Dict[UUID, CandidateStage]:
    if not candidate_ids:
        return {}

    candidate_lookup = _build_slot_candidate_lookup(db, candidate_ids)
    if not candidate_lookup:
        return {}

    columns = db.execute(text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'interview_slots'
        """
    )).fetchall()
    column_names = {row[0] for row in columns}
    if not column_names or "slot_date" not in column_names:
        return {}

    normalized_column_lookup = {
        column_name.lower().replace("_", ""): column_name
        for column_name in column_names
    }
    candidate_column = next(
        (
            normalized_column_lookup.get(candidate_key)
            for candidate_key in ("candidate_id", "candidateid", "candidate")
            if normalized_column_lookup.get(candidate_key)
        ),
        None,
    )
    if not candidate_column:
        return {}

    rows = db.execute(
        text(f"""
            SELECT
                {candidate_column}::text AS candidate_id,
                CASE
                    WHEN slot_date::date = :today THEN 'today'
                    WHEN slot_date::date > :today THEN 'future'
                    ELSE 'past'
                END AS slot_timing
            FROM interview_slots
            WHERE {candidate_column} IS NOT NULL
              AND slot_date IS NOT NULL
              AND {candidate_column}::text = ANY(:candidate_ids)
              AND slot_date::date >= :today
            ORDER BY {candidate_column}::text
        """),
        {
            "candidate_ids": list(candidate_lookup.keys()),
            "today": today,
        },
    ).mappings().all()

    slot_stage_by_candidate: Dict[UUID, CandidateStage] = {}
    for row in rows:
        candidate_id_raw = row.get("candidate_id")
        slot_timing = row.get("slot_timing")
        if not candidate_id_raw or not slot_timing:
            continue

        candidate_id = candidate_lookup.get(str(candidate_id_raw).strip())
        if not candidate_id:
            continue

        if candidate_id in slot_stage_by_candidate:
            continue

        if slot_timing == "today":
            slot_stage_by_candidate[candidate_id] = CandidateStage.INTERVIEWED
            continue

        if slot_timing == "future":
            slot_stage_by_candidate[candidate_id] = CandidateStage.INTERVIEW_SCHEDULED

    return slot_stage_by_candidate


def sync_rescheduled_candidate_stages_from_slots(
    db: Session,
    candidate_ids: Optional[List[UUID]] = None,
) -> int:
    target_query = db.query(Candidate.id).filter(
        Candidate.stage == CandidateStage.INTERVIEW_RESCHEDULED
    )
    if candidate_ids:
        target_query = target_query.filter(Candidate.id.in_(candidate_ids))

    rescheduled_candidate_ids = [candidate_id for (candidate_id,) in target_query.all()]
    if not rescheduled_candidate_ids:
        return 0

    slot_stage_by_candidate = _get_interview_slot_pipeline_stages(
        db,
        rescheduled_candidate_ids,
        _get_india_today(),
    )
    if not slot_stage_by_candidate:
        return 0

    now = datetime.utcnow()
    updated_count = 0
    candidates = (
        db.query(Candidate)
        .filter(Candidate.id.in_(list(slot_stage_by_candidate.keys())))
        .all()
    )
    for candidate in candidates:
        target_stage = slot_stage_by_candidate.get(candidate.id)
        if target_stage not in {CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEWED}:
            continue
        if candidate.stage == target_stage:
            continue
        candidate.stage = target_stage
        candidate.stage_updated_at = now
        candidate.stage_entered_at = now
        updated_count += 1

    if updated_count:
        db.commit()
        try:
            from app.routes.analytics import clear_analytics_cache
            clear_analytics_cache()
        except Exception:
            pass

    return updated_count


NO_SHOW_GRACE_PERIOD_MINUTES = 30


def sync_no_show_candidate_stages(db: Session) -> int:
    now_utc = datetime.now(timezone.utc)
    no_show_cutoff = now_utc - timedelta(minutes=NO_SHOW_GRACE_PERIOD_MINUTES)

    active_interviews = (
        db.query(Interview)
        .filter(Interview.scheduled_at.isnot(None))
        .filter(Interview.scheduled_at <= no_show_cutoff)
        .filter(func.lower(func.trim(Interview.status)).in_(["scheduled", "rescheduled"]))
        .order_by(
            Interview.candidate_id.asc(),
            func.coalesce(Interview.scheduled_at, Interview.created_at).desc(),
            Interview.created_at.desc(),
        )
        .all()
    )
    if not active_interviews:
        return 0

    latest_interview_by_candidate: dict[UUID, Interview] = {}
    for interview in active_interviews:
        if interview.candidate_id not in latest_interview_by_candidate:
            latest_interview_by_candidate[interview.candidate_id] = interview

    candidate_ids = list(latest_interview_by_candidate.keys())
    candidates = (
        db.query(Candidate)
        .filter(Candidate.id.in_(candidate_ids))
        .all()
    )
    candidate_by_id = {candidate.id: candidate for candidate in candidates}

    updated_count = 0
    status_changed = False
    now = datetime.utcnow()
    for candidate_id, interview in latest_interview_by_candidate.items():
        candidate = candidate_by_id.get(candidate_id)
        if not candidate:
            continue

        interview_started = bool(
            interview.async_started_at
            or interview.async_completed_at
            or interview.transcript
            or interview.ai_summary
            or interview.video_url
            or interview.interview_score is not None
            or (interview.status or "").strip().lower() in {"ongoing", "completed", "selected", "rejected", "no_show"}
        )
        if interview_started:
            continue

        if (interview.status or "").strip().lower() != "no_show":
            interview.status = "no_show"
            status_changed = True

        if candidate.stage != CandidateStage.NO_SHOW:
            candidate.stage = CandidateStage.NO_SHOW
            candidate.stage_updated_at = now
            candidate.stage_entered_at = now
            updated_count += 1

    if updated_count or status_changed:
        db.commit()
        try:
            from app.routes.analytics import clear_analytics_cache
            clear_analytics_cache()
        except Exception:
            pass

    return updated_count


def _get_interview_slot_candidate_ids_by_timing(
    db: Session,
    candidate_ids: List[UUID],
    today,
) -> tuple[set[UUID], set[UUID]]:
    if not candidate_ids:
        return set(), set()

    candidate_lookup = _build_slot_candidate_lookup(db, candidate_ids)
    if not candidate_lookup:
        return _get_interview_candidate_ids_by_interview_timing(db, candidate_ids, today)

    columns = db.execute(text(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'interview_slots'
        """
    )).fetchall()
    column_names = {row[0] for row in columns}
    if not column_names or "slot_date" not in column_names:
        return _get_interview_candidate_ids_by_interview_timing(db, candidate_ids, today)

    normalized_column_lookup = {
        column_name.lower().replace("_", ""): column_name
        for column_name in column_names
    }
    candidate_column = next(
        (
            normalized_column_lookup.get(candidate_key)
            for candidate_key in ("candidate_id", "candidateid", "candidate")
            if normalized_column_lookup.get(candidate_key)
        ),
        None,
    )
    if not candidate_column:
        return _get_interview_candidate_ids_by_interview_timing(db, candidate_ids, today)

    rows = db.execute(
        text(f"""
            SELECT
                {candidate_column}::text AS candidate_id,
                CASE
                    WHEN slot_date::date = :today THEN 'today'
                    WHEN slot_date::date > :today THEN 'future'
                    ELSE 'past'
                END AS slot_timing
            FROM interview_slots
            WHERE {candidate_column} IS NOT NULL
              AND slot_date IS NOT NULL
              AND {candidate_column}::text = ANY(:candidate_ids)
              AND slot_date::date >= :today
            ORDER BY {candidate_column}::text
        """),
        {
            "candidate_ids": list(candidate_lookup.keys()),
            "today": today,
        },
    ).mappings().all()

    today_candidate_ids: set[UUID] = set()
    future_candidate_ids: set[UUID] = set()
    for row in rows:
        candidate_id_raw = row.get("candidate_id")
        slot_timing = row.get("slot_timing")
        if not candidate_id_raw or not slot_timing:
            continue

        candidate_id = candidate_lookup.get(str(candidate_id_raw).strip())
        if not candidate_id:
            continue

        if candidate_id in today_candidate_ids or candidate_id in future_candidate_ids:
            continue

        if slot_timing == "today":
            today_candidate_ids.add(candidate_id)
        elif slot_timing == "future":
            future_candidate_ids.add(candidate_id)

    remaining_candidate_ids = [
        candidate_id
        for candidate_id in candidate_ids
        if candidate_id not in today_candidate_ids and candidate_id not in future_candidate_ids
    ]
    if not remaining_candidate_ids:
        return today_candidate_ids, future_candidate_ids

    fallback_today_candidate_ids, fallback_future_candidate_ids = _get_interview_candidate_ids_by_interview_timing(
        db,
        remaining_candidate_ids,
        today,
    )
    today_candidate_ids.update(fallback_today_candidate_ids)
    future_candidate_ids.update(fallback_future_candidate_ids)

    return today_candidate_ids, future_candidate_ids


def _classify_interview_timing_bucket(
    *,
    status_value: Optional[str],
    scheduled_at: Optional[datetime],
    today: date,
) -> Optional[str]:
    normalized_status = (status_value or "").strip().lower()
    interview_date = _get_india_local_date(scheduled_at)

    if normalized_status in {"completed", "ongoing"}:
        return "today"

    if normalized_status != "scheduled":
        return None

    if interview_date is None:
        return "future"
    if interview_date < today:
        return None
    if interview_date == today:
        return "today"
    return "future"


def _get_interview_candidate_ids_by_interview_timing(
    db: Session,
    candidate_ids: List[UUID],
    today: date,
) -> tuple[set[UUID], set[UUID]]:
    if not candidate_ids:
        return set(), set()

    interview_rows = (
        db.query(
            Interview.candidate_id,
            Interview.status,
            Interview.scheduled_at,
            Interview.created_at,
        )
        .filter(Interview.candidate_id.in_(candidate_ids))
        .order_by(
            Interview.candidate_id.asc(),
            func.coalesce(Interview.scheduled_at, Interview.created_at).desc(),
            Interview.created_at.desc(),
        )
        .all()
    )

    today_candidate_ids: set[UUID] = set()
    future_candidate_ids: set[UUID] = set()
    seen_candidate_ids: set[UUID] = set()

    for candidate_id, status_value, scheduled_at, _created_at in interview_rows:
        if candidate_id in seen_candidate_ids:
            continue
        seen_candidate_ids.add(candidate_id)

        timing_bucket = _classify_interview_timing_bucket(
            status_value=status_value,
            scheduled_at=scheduled_at,
            today=today,
        )
        if timing_bucket == "today":
            today_candidate_ids.add(candidate_id)
        elif timing_bucket == "future":
            future_candidate_ids.add(candidate_id)

    return today_candidate_ids, future_candidate_ids


def _get_interview_candidate_ids_by_status(
    db: Session,
    candidate_ids: List[UUID],
) -> tuple[set[UUID], set[UUID], set[UUID]]:
    if not candidate_ids:
        return set(), set(), set()

    interview_rows = (
        db.query(Interview.candidate_id, Interview.status)
        .filter(Interview.candidate_id.in_(candidate_ids))
        .all()
    )

    completed_candidate_ids: set[UUID] = set()
    selected_candidate_ids: set[UUID] = set()
    rejected_candidate_ids: set[UUID] = set()

    for candidate_id, status_value in interview_rows:
        normalized_status = (status_value or "").strip().lower()
        if normalized_status == "completed":
            completed_candidate_ids.add(candidate_id)
        elif normalized_status == "selected":
            selected_candidate_ids.add(candidate_id)
        elif normalized_status == "rejected":
            rejected_candidate_ids.add(candidate_id)

    return completed_candidate_ids, selected_candidate_ids, rejected_candidate_ids


def enqueue_stage_notification(
    background_tasks: BackgroundTasks,
    db: Session,
    candidate: Candidate,
    stage_value: str,
    user_id=None,
    extra_payload: Optional[dict] = None,
):
    try:
        notification = queue_notification_for_stage(
            db,
            candidate=candidate,
            stage_value=stage_value,
            user_id=user_id,
            extra_payload=extra_payload,
        )
        if notification:
            db.commit()
            print(
                f"Notification queued: candidate_id={candidate.id}, "
                f"stage={stage_value}, communication_id={notification['communication_id']}"
            )
            send_email_task(notification["communication_id"])
    except Exception as exc:
        db.rollback()
        print(f"Notification enqueue failed for stage {stage_value}: {exc}")

def generate_candidate_id(name: str, job_id: int = None) -> str:
    """Generate unique candidate ID: FirstName + JobID"""
    if not name:
        first_name = "Unknown"
    else:
        # Extract first name and clean it
        first_name = name.split()[0].replace(" ", "").replace("-", "").replace(".", "")
    
    job_suffix = str(job_id) if job_id else "0"
    return f"{first_name}{job_suffix}"


def clean_candidate_name(raw_name: str) -> str:
    """Normalize names extracted from filenames like 'Swapna Resume' -> 'Swapna'."""
    import re

    if not raw_name:
        return "Unknown Candidate"

    stop_words = {
        "resume", "cv", "profile", "updated", "final", "latest", "new",
        "doc", "document", "copy", "version", "v1", "v2", "v3"
    }

    normalized = raw_name.replace('_', ' ').replace('-', ' ')
    normalized = re.sub(r'\([^)]*\)', ' ', normalized)
    normalized = re.sub(r'\[[^\]]*\]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    words = []
    for word in normalized.split():
        cleaned_word = re.sub(r'^\d+|\d+$', '', word).strip()
        if not cleaned_word:
            continue
        if cleaned_word.lower() in stop_words:
            continue
        if any(char.isdigit() for char in cleaned_word):
            continue
        words.append(cleaned_word)

    if words:
        return " ".join(words).title()

    return normalized.title() if normalized else "Unknown Candidate"


def derive_candidate_name_from_filename(original_filename: Optional[str]) -> Optional[str]:
    if not original_filename:
        return None

    filename_without_extension = os.path.splitext(os.path.basename(original_filename))[0]
    normalized_name = clean_candidate_name(filename_without_extension)
    return normalized_name if normalized_name and normalized_name != "Unknown Candidate" else None


def extract_email_from_raw_file(file_path: str) -> Optional[str]:
    """Fallback email extraction for files where text parsing misses the address."""
    import re

    try:
        with open(file_path, "rb") as file_handle:
            raw_content = file_handle.read()
    except Exception as exc:
        print(f"Raw email extraction failed to read file: {exc}")
        return None

    decoded_content = raw_content.decode("utf-8", errors="ignore")
    if "@" not in decoded_content:
        decoded_content = raw_content.decode("latin-1", errors="ignore")

    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, decoded_content, re.IGNORECASE)
    return emails[0] if emails else None

def extract_resume_data(file_path: str, original_filename: str = None, *, fast_mode: bool = True) -> dict:
    """Extract structured resume data using the production ATS parser."""
    parsed_resume = {}
    email = None
    phone = None
    name = None
    location = None
    skills = []
    projects = []
    experience_text = ""
    work_experience = []
    education_text = ""
    education = []
    cleaned_text = ""
    current_role = None
    current_company = None
    experience_level = None
    languages = []
    
    try:
        parsed_resume = parse_resume(file_path, original_filename, fast_mode=fast_mode)
        raw_text = parsed_resume.get("raw_text", "")
        cleaned_text = parsed_resume.get("full_text", "") or (clean_text(raw_text) if raw_text.strip() else "")
        sections = parsed_resume.get("sections") or {}
        email = parsed_resume.get("email") or None
        phone = parsed_resume.get("phone") or None
        name = parsed_resume.get("name") or None
        location = sanitize_candidate_location(parsed_resume.get("location")) or None
        skills = sanitize_resume_skills(parsed_resume.get("skills") or [], parsed_resume.get("languages") or [])
        current_role = parsed_resume.get("designation") or None
        current_company = parsed_resume.get("current_company") or None
        languages = parsed_resume.get("languages") or []
        experience_level = parsed_resume.get("experience_level") or None
        projects = parsed_resume.get("projects") or extract_projects_from_text(raw_text)
        work_experience = parsed_resume.get("experience_entries") or parsed_resume.get("experience") or []
        experience_text = parsed_resume.get("experience_text") or clean_text_pipeline(sections.get("experience", ""))
        current_role = resolve_current_role_for_storage(
            work_experience,
            current_role,
            skills,
        )
        current_company = resolve_current_company_for_storage(
            work_experience,
            current_company,
            experience_text,
        )
        education_text = parsed_resume.get("education_text") or clean_text_pipeline(sections.get("education", ""))
        education = parsed_resume.get("education") or []

        if not email:
            email = extract_email_from_raw_file(file_path)
            if email:
                print(f"   Recovered email via raw file scan: {email}")

        if not name:
            name = derive_candidate_name_from_filename(original_filename)
        if not name and email:
            email_local_part = email.split('@', 1)[0].replace('.', ' ').replace('_', ' ').replace('-', ' ')
            name = clean_candidate_name(email_local_part)
                    
    except Exception as e:
        print(f"Error in resume extraction: {e}")
    
    if name:
        name = clean_candidate_name(name)
    experience_years = parsed_resume.get('total_experience_years') if parsed_resume else None
    if experience_years is None or experience_years <= 0:
        experience_years = estimate_experience_years_from_entries(work_experience)
    if (experience_years is None or experience_years <= 0) and cleaned_text:
        experience_years = estimate_experience_years_from_text(cleaned_text)

    return {
        'name': name,
        'email': email,
        'phone': phone,
        'location': location,
        'current_role': resolve_current_role_for_storage(work_experience, current_role, skills),
        'current_company': resolve_current_company_for_storage(work_experience, current_company, experience_text),
        'skills': skills,
        'projects': projects,
        'experience_text': experience_text,
        'work_experience': work_experience,
        'education_text': education_text,
        'education': education,
        'languages': languages,
        'experience_years': experience_years,
        'experience_level': experience_level,
        'full_text': cleaned_text,  # Store cleaned text for downstream ATS processing
        'document_metadata': parsed_resume.get("document_metadata") or {},
        'layout_signals': parsed_resume.get("layout_signals") or {},
        'pipeline_summary': parsed_resume.get("pipeline_summary") or {},
    }

def extract_skills_from_text(text: str) -> list:
    """Extract resume skills using the shared ATS skill extraction pipeline."""
    skills_text = segment_resume_sections(text).get("skills", "")
    extracted_skills = extract_skill_keywords(text, skills_text)
    if extracted_skills:
        return extracted_skills
    extracted_skills = get_skill_engine().extract_skills(text)[:30]
    print(f"   Extracted {len(extracted_skills)} skills via shared extractor: {extracted_skills[:10]}")
    return extracted_skills

def extract_projects_from_text(text: str) -> list:
    """Extract project information from resume text"""
    import re

    project_text = segment_resume_sections(text).get("projects", "")
    projects = []

    if not project_text:
        return projects

    blocks = [block.strip() for block in re.split(r'\n\s*\n', project_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in project_text.split('\n') if line.strip()]

    for block in blocks:
        if len(block) > 20:
            projects.append(block[:200])

    return projects[:5]  # Limit to 5 projects

def extract_experience_text(text: str) -> str:
    """Extract work experience section from resume"""
    return segment_resume_sections(text).get("experience", "").strip()[:1000]


def extract_work_experience_from_text(text: str) -> list:
    """Extract structured work experience entries from resume text."""
    return extract_experience_entries(text, segment_resume_sections(text).get("experience", ""))


def extract_education_from_text(text: str) -> list:
    """Extract structured education entries from resume text."""
    return extract_education_entries(text, segment_resume_sections(text).get("education", ""))

# Job Configuration (role-specific scoring)
JOB_CONFIG = {
    "default": {
        "required_skills": ["html", "css", "javascript", "python", "sql"],
        "optional_skills": ["react", "git", "api", "docker", "aws"],
        "transferable_signals": ["dashboard", "system", "application", "web", "project"],
        "education_required": False,
        "max_score": 10
    },
    "software engineer": {
        "required_skills": ["programming", "algorithms", "data structures"],
        "optional_skills": ["python", "java", "javascript", "git", "testing"],
        "transferable_signals": ["development", "coding", "software", "application", "system"],
        "education_required": False,
        "max_score": 10
    },
    "web developer": {
        "required_skills": ["html", "css", "javascript"],
        "optional_skills": ["react", "angular", "vue", "node.js", "sql"],
        "transferable_signals": ["website", "web application", "frontend", "backend", "responsive"],
        "education_required": False,
        "max_score": 10
    },
    "data scientist": {
        "required_skills": ["python", "statistics", "machine learning"],
        "optional_skills": ["tensorflow", "pytorch", "pandas", "sql", "visualization"],
        "transferable_signals": ["data analysis", "modeling", "prediction", "analytics", "research"],
        "education_required": False,
        "max_score": 10
    },
    "hr executive": {
        "required_skills": ["recruitment", "employee relations", "hr operations"],
        "optional_skills": ["payroll", "compliance", "performance management"],
        "transferable_signals": ["hiring", "team management", "people management", "entrepreneur", "founder", "leadership"],
        "education_required": False,
        "max_score": 10
    }
}

def get_job_config(job_title: str) -> dict:
    """Get job configuration, fallback to default"""
    if not job_title:
        return JOB_CONFIG["default"]
    
    job_key = job_title.lower().strip()
    return JOB_CONFIG.get(job_key, JOB_CONFIG["default"])

def generate_reasoning(job_role: str, matched_required: list, transferable_hits: list, score: float, decision: str) -> str:
    """Generate 3-line reasoning for the score"""
    lines = []
    
    if matched_required:
        lines.append(f"Matches core requirements for {job_role} with relevant skill alignment.")
    else:
        lines.append(f"Lacks direct role-specific skills but shows adjacent experience.")
    
    if transferable_hits:
        lines.append(f"Transferable experience identified ({', '.join(transferable_hits[:2])}).")
    else:
        lines.append("Limited evidence of transferable responsibilities.")
    
    lines.append(f"Overall assessment results in a {decision.lower()} based on available evidence.")
    
    return " ".join(lines)

def analyze_resume_with_ai(candidate_data: dict, job_description: dict) -> dict:
    """Intelligent ATS evaluation with contextual reasoning"""
    
    # Extract data
    name = candidate_data.get('name', 'Unknown')
    email = candidate_data.get('email', '')
    phone = candidate_data.get('phone', '')
    candidate_location = candidate_data.get('location', '')
    experience_years = candidate_data.get('experience_years', 0.0)
    skills = candidate_data.get('skills', [])
    candidate_roles = candidate_data.get('candidate_roles', [])
    candidate_industries = candidate_data.get('candidate_industries', [])
    experience_text = candidate_data.get('experience_text', '')
    projects = candidate_data.get('projects', [])
    full_text = candidate_data.get('full_text', '')
    
    # Job details
    job_title = job_description.get('title', 'Position')
    job_desc = job_description.get('description', '')
    job_requirements = job_description.get('requirements', '')
    job_skills = job_description.get('skills', [])
    job_location = job_description.get('location', '')
    job_experience_required = job_description.get('experience_required', '')
    industry = job_description.get('industry', '')
    
    # Perform contextual analysis
    evaluation = evaluate_candidate_contextually(
        resume_text=full_text,
        job_title=job_title,
        job_description=job_desc,
        job_requirements=job_requirements,
        candidate_skills=skills,
        experience_text=experience_text,
        projects=projects,
        job_skills=job_skills,
        candidate_location=candidate_location,
        job_location=job_location,
        experience_years=experience_years,
        candidate_roles=candidate_roles,
        candidate_industries=candidate_industries,
        job_experience_required=job_experience_required,
        industry=industry,
    )
    
    return {
        "candidate_name": name,
        "Email": email,
        "Mobile_Number": phone,
        "match_score": evaluation['match_score'],
        "match_label": evaluation['match_label'],
        "candidate_summary": evaluation['candidate_summary'],
        "key_strengths": evaluation['key_strengths'],
        "skill_gaps": evaluation['skill_gaps'],
        "ai_analysis": evaluation['ai_analysis'],
        "jobTitle": job_title,
        "jobDescription": job_desc,
        "resumeText": full_text[:1000],
        "status": evaluation['status']
    }


def get_job_data(db: Session, job_id: Optional[UUID]) -> dict:
    """Load job data once and reuse it across batch processing."""
    if not job_id:
        return {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': [],
            'location': '',
            'experience_required': '',
            'industry': '',
        }

    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        return {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': [],
            'location': '',
            'experience_required': '',
            'industry': '',
        }

    return {
        'title': job.title,
        'description': job.description or '',
        'requirements': job.requirements or '',
        'skills': job.skills or [],
        'location': job.location or '',
        'experience_required': job.experience_required or '',
        'industry': job.department or '',
    }

def generate_unique_candidate_id(db: Session, name: str, job_id: Optional[UUID]) -> str:
    """Generate a unique candidate ID for bulk operations."""
    name_prefix = name[:3].upper() if name else "UNK"
    job_suffix = str(job_id) if job_id else "000"
    candidate_id = f"{name_prefix}{job_suffix}"
    base_id = candidate_id
    counter = 1

    while db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first():
        candidate_id = f"{base_id}{counter}"
        counter += 1

    return candidate_id


def set_upload_progress(upload_id: str, **kwargs):
    progress = upload_progress_store.get(upload_id, {})
    progress.update(kwargs)
    upload_progress_store[upload_id] = progress


def is_valid_resume_upload(file: UploadFile) -> bool:
    return (
        file.content_type in ALLOWED_RESUME_CONTENT_TYPES
        or any(file.filename.lower().endswith(ext) for ext in ALLOWED_RESUME_EXTENSIONS)
    )


def get_default_job_data() -> dict:
    return {
        'title': 'General Position',
        'description': 'General professional role',
        'requirements': 'Professional experience with relevant skills',
        'skills': ['communication', 'teamwork', 'problem solving'],
        'location': '',
    }


def build_batch_candidate_id(name: str, job_id: Optional[UUID]) -> str:
    """Generate a unique batch-safe candidate id without extra database lookups."""
    name_prefix = (name or "UNK")[:3].upper()
    job_token = str(job_id).replace("-", "")[:6].upper() if job_id else "000000"
    return f"{name_prefix}{job_token}{uuid.uuid4().hex[:8].upper()}"


def estimate_experience_years_from_entries(entries: list) -> float:
    """Estimate total experience from structured work-experience entries."""
    from datetime import datetime

    if not entries:
        return 0.0

    current_year = datetime.utcnow().year
    intervals = []

    for entry in entries:
        start_value = str((entry or {}).get("start_date", "")).strip().lower()
        end_value = str((entry or {}).get("end_date", "")).strip().lower()

        start_match = re.search(r"(19|20)\d{2}", start_value)
        end_match = re.search(r"(19|20)\d{2}", end_value)

        if not start_match:
            continue

        start_year = int(start_match.group(0))
        end_year = int(end_match.group(0)) if end_match else current_year

        if end_value in {"present", "current", "now"}:
            end_year = current_year

        if end_year < start_year:
            continue

        intervals.append((start_year, end_year))

    if not intervals:
        return 0.0

    intervals.sort()
    merged = [intervals[0]]
    for start_year, end_year in intervals[1:]:
        last_start, last_end = merged[-1]
        if start_year <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end_year))
        else:
            merged.append((start_year, end_year))

    total_years = sum(end_year - start_year for start_year, end_year in merged)
    return float(max(total_years, 0))


def estimate_experience_years_from_text(text: str) -> float:
    """Fallback estimator for resumes whose dated experience is present outside the parsed section."""
    if not text:
        return 0.0

    normalized_text = str(text)
    ranges = []
    for match in extract_date_ranges(text):
        start_date = parse_date(match.get("start", ""), is_end=False)
        end_date = parse_date(match.get("end", ""), is_end=True)
        if not start_date or not end_date or end_date < start_date:
            continue

        span = match.get("span") or (0, 0)
        start_index, end_index = int(span[0]), int(span[1])
        line_start = normalized_text.rfind("\n", 0, start_index) + 1
        line_end = normalized_text.find("\n", end_index)
        if line_end == -1:
            line_end = len(normalized_text)
        context = normalized_text[line_start:line_end].strip() or str(match.get("matched_text", "") or "")

        if not re.search(
            r"(?i)\b(engineer|developer|manager|analyst|consultant|architect|lead|intern|specialist|executive|company|corp|ltd|llc|inc|technologies|solutions|labs|systems)\b",
            context,
        ):
            continue

        ranges.append((start_date, end_date))

    if not ranges:
        return 0.0

    return round(float(compute_total_experience(ranges)), 1)


def process_saved_resume(file_path: str, original_filename: str, job_data: dict, *, fast_mode: bool = True) -> dict:
    """Run extraction and scoring for one saved resume file."""
    from app.balanced_scoring import extract_years_experience

    total_start = perf_counter()
    extraction_start = perf_counter()
    resume_data = extract_resume_data(file_path, original_filename, fast_mode=fast_mode)
    extraction_time = perf_counter() - extraction_start
    estimated_years = resume_data.get("experience_years")
    if estimated_years is None or estimated_years <= 0:
        estimated_years = estimate_experience_years_from_entries(resume_data.get("work_experience", []))
    if estimated_years is None or estimated_years <= 0:
        estimated_years = estimate_experience_years_from_text(resume_data.get("full_text", ""))
    resume_data["experience_years"] = estimated_years if estimated_years and estimated_years > 0 else extract_years_experience(resume_data.get("full_text", ""))
    scoring_start = perf_counter()
    analysis_data = {
        'name': resume_data['name'],
        'email': resume_data['email'],
        'phone': resume_data['phone'],
        'location': resume_data.get('location', ''),
        'experience_years': resume_data.get('experience_years', 0.0),
        'skills': resume_data['skills'],
        'candidate_roles': [
            entry.get('title') for entry in (resume_data.get('work_experience') or [])
            if (entry or {}).get('title')
        ] or ([resume_data.get('current_role')] if resume_data.get('current_role') else []),
        'candidate_industries': [],
        'experience_text': resume_data['experience_text'],
        'projects': resume_data['projects'],
        'full_text': resume_data['full_text']
    }
    ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
    scoring_time = perf_counter() - scoring_start
    parser_performance = (
        ((resume_data.get("document_metadata") or {}).get("performance"))
        if isinstance(resume_data, dict) else None
    ) or {}
    _perf_log(
        "process_saved_resume",
        total_start,
        file=original_filename or os.path.basename(file_path),
        extraction=f"{extraction_time:.4f}s",
        scoring=f"{scoring_time:.4f}s",
        pdf=f"{parser_performance.get('pdf_extraction_ms', 0.0)}ms",
        docx=f"{parser_performance.get('docx_extraction_ms', 0.0)}ms",
        ocr=f"{parser_performance.get('ocr_ms', 0.0)}ms",
        fast_mode=parser_performance.get("fast_mode", fast_mode),
    )
    return {
        "resume_data": resume_data,
        "ai_analysis": ai_analysis,
    }


def apply_resume_analysis(
    candidate: Candidate,
    ai_analysis: Optional[dict] = None,
    job_title: Optional[str] = None,
    *,
    generate_questions: bool = True,
):
    """Apply analysis results without forcing a commit for every candidate."""
    candidate.parsing_status = ParsingStatus.COMPLETED

    if ai_analysis:
        score = ai_analysis.get('match_score', 0)
        if score == 0 and candidate.resume_text and len(candidate.resume_text.strip()) > 100:
            score = 45

        candidate.resume_score = score
        candidate.summary = ai_analysis.get('candidate_summary', '')

        if generate_questions and candidate.resume_text and job_title:
            try:
                candidate.predefined_questions = generate_interview_questions(
                    candidate.resume_text,
                    job_title,
                    candidate.skills or []
                )
            except Exception as exc:
                print(f"Question generation failed: {exc}")

        assign_resume_pipeline_stage(candidate, score, candidate.score_threshold)
    else:
        candidate.resume_score = 40
        assign_resume_pipeline_stage(candidate, candidate.resume_score, candidate.score_threshold)


def should_defer_resume_refinement(resume_data: dict) -> bool:
    document_metadata = resume_data.get("document_metadata") or {}
    layout_signals = resume_data.get("layout_signals") or {}
    performance = document_metadata.get("performance") or {}
    full_text = (resume_data.get("full_text") or "").strip()
    return bool(
        layout_signals.get("ocr_applied")
        or layout_signals.get("is_scanned_pdf")
        or layout_signals.get("is_multi_column")
        or performance.get("ocr_ms", 0.0) > 0.0
        or len(full_text) < 500
    )


def finalize_batch_notifications(
    background_tasks: Optional[BackgroundTasks],
    db: Session,
    candidates: List[Candidate],
    user_id=None,
):
    pending_notifications = []
    for candidate in candidates:
        if candidate.stage in [CandidateStage.SHORTLISTED, CandidateStage.RESUME_REJECTED]:
            notification = queue_notification_for_stage(
                db,
                candidate=candidate,
                stage_value=candidate.stage.value,
                user_id=user_id,
            )
            if notification:
                pending_notifications.append(notification["communication_id"])

    if pending_notifications:
        try:
            db.commit()
            for communication_id in pending_notifications:
                if background_tasks:
                    background_tasks.add_task(send_email_task, communication_id)
                else:
                    send_email_task(communication_id)
        except Exception:
            db.rollback()
            raise


def process_single_resume_upload(
    upload_id: str,
    file_path: str,
    original_filename: str,
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
    file_upload_ms: float = 0.0,
):
    """Process a single resume after the response so uploads return quickly."""
    db = SessionLocal()
    total_start = perf_counter()

    try:
        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="processing",
            message="Analyzing resume...",
        )

        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")

        processed = process_saved_resume(file_path, original_filename, job_data, fast_mode=True)
        resume_data = processed["resume_data"]
        resume_data["file_upload_ms"] = file_upload_ms
        needs_refinement = should_defer_resume_refinement(resume_data)

        duplicate_candidate = _find_duplicate_candidate_for_job(
            db,
            name=resume_data.get("name"),
            email=resume_data.get("email"),
            job_id=job_id,
        )
        if duplicate_candidate:
            set_upload_progress(
                upload_id,
                current=0,
                total=1,
                status="error",
                message="Application already exists",
                candidate_id=str(duplicate_candidate.id),
            )
            return

        candidate = Candidate(
            name=resume_data['name'],
            email=resume_data['email'],
            phone=resume_data['phone'],
            current_company=resume_data.get('current_company'),
            current_role=resume_data.get('current_role'),
            location=resume_data.get('location'),
            experience_years=resume_data.get('experience_years'),
            skills=resume_data['skills'],
            education=resume_data.get('education'),
            work_experience=resume_data.get('work_experience'),
            resume_file_path=file_path,
            resume_text=resume_data['full_text'],
            candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
            job_id=job_id,
            agency_id=agency_id,
            created_by=current_user_id,
            assigned_to_user_id=current_user_id,
            parsing_status=ParsingStatus.PROCESSING if needs_refinement else ParsingStatus.COMPLETED,
            score_threshold=threshold
        )
        apply_resume_analysis(
            candidate,
            processed["ai_analysis"],
            job_title=job_title,
            generate_questions=not needs_refinement,
        )
        db.add(candidate)
        db_save_started_at = perf_counter()
        db.commit()
        db.refresh(candidate)
        database_save_ms = round((perf_counter() - db_save_started_at) * 1000.0, 2)
        parser_debug = resume_data.get("debug_timings") or {}
        slowest_components = {
            "File Upload": float(resume_data.get("file_upload_ms", 0.0) or 0.0),
            "PDF Parse": float((resume_data.get("document_metadata") or {}).get("performance", {}).get("pdf_extraction_ms", 0.0) or 0.0),
            "DOCX Parse": float((resume_data.get("document_metadata") or {}).get("performance", {}).get("docx_extraction_ms", 0.0) or 0.0),
            "Section Detection": float(parser_debug.get("Section Detection", 0.0) or 0.0),
            "Name Extraction": float(parser_debug.get("Name Extraction", 0.0) or 0.0),
            "Experience Extraction": float(parser_debug.get("Experience Extraction", 0.0) or 0.0),
            "Skill Extraction": float(parser_debug.get("Skill Extraction", 0.0) or 0.0),
            "spaCy Execution": float(parser_debug.get("spaCy Execution", 0.0) or 0.0),
            "Regex Processing": float(parser_debug.get("Regex Processing", 0.0) or 0.0),
            "Database Save": database_save_ms,
        }
        slowest_component = max(slowest_components, key=slowest_components.get)
        bottleneck_component = slowest_component if slowest_components[slowest_component] > 3000.0 else "None > 3s"
        _ats_timing_log(
            resume_name=resume_data.get("name") or "",
            file_upload_ms=resume_data.get("file_upload_ms", 0.0),
            pdf_parse_ms=round(float((resume_data.get("document_metadata") or {}).get("performance", {}).get("pdf_extraction_ms", 0.0) or 0.0), 2),
            docx_parse_ms=round(float((resume_data.get("document_metadata") or {}).get("performance", {}).get("docx_extraction_ms", 0.0) or 0.0), 2),
            section_detection_ms=parser_debug.get("Section Detection", 0.0),
            name_extraction_ms=parser_debug.get("Name Extraction", 0.0),
            experience_extraction_ms=parser_debug.get("Experience Extraction", 0.0),
            skill_extraction_ms=parser_debug.get("Skill Extraction", 0.0),
            spacy_execution_ms=parser_debug.get("spaCy Execution", 0.0),
            regex_processing_ms=parser_debug.get("Regex Processing", 0.0),
            ocr_triggered="Yes" if parser_debug.get("ocr_triggered") else "No",
            ocr_time_ms=round(float((resume_data.get("document_metadata") or {}).get("performance", {}).get("ocr_ms", 0.0) or 0.0), 2),
            ocr_timed_out="Yes" if (resume_data.get("document_metadata") or {}).get("performance", {}).get("ocr_timed_out") else "No",
            pages_processed=int((resume_data.get("document_metadata") or {}).get("performance", {}).get("pages_processed", 0) or 0),
            warmup_used="Yes" if parser_debug.get("warmup_used") else "No",
            models_loaded="Yes" if parser_debug.get("models_loaded") else "No",
            database_save_ms=database_save_ms,
            total_time_ms=round((perf_counter() - total_start) * 1000.0, 2),
            slowest_component=bottleneck_component,
            bottleneck_time_ms=round(float(slowest_components.get(slowest_component, 0.0) or 0.0), 2),
            bottleneck_exceeds_threshold="Yes" if slowest_components.get(slowest_component, 0.0) > 3000.0 else "No",
        )

        set_upload_progress(
            upload_id,
            current=1,
            total=1,
            status="completed",
            message="Resume uploaded successfully" if not needs_refinement else "Resume uploaded. Deep parsing is continuing in the background.",
            candidate_id=str(candidate.id),
        )
        if not needs_refinement:
            finalize_batch_notifications(None, db, [candidate], user_id=current_user_id)

        _perf_log(
            "process_single_resume_upload.fast_pass",
            total_start,
            file=original_filename,
            upload_id=upload_id,
            candidate_id=str(candidate.id),
            refinement=needs_refinement,
        )

        if needs_refinement:
            refinement_start = perf_counter()
            try:
                refined = process_saved_resume(file_path, original_filename, job_data, fast_mode=False)
                refined_resume = refined["resume_data"]
                refined_resume["file_upload_ms"] = file_upload_ms
                candidate.name = refined_resume['name']
                candidate.email = refined_resume['email']
                candidate.phone = refined_resume['phone']
                candidate.current_company = refined_resume.get('current_company')
                candidate.current_role = refined_resume.get('current_role')
                candidate.location = refined_resume.get('location')
                candidate.experience_years = refined_resume.get('experience_years')
                candidate.skills = refined_resume['skills']
                candidate.education = refined_resume.get('education')
                candidate.work_experience = refined_resume.get('work_experience')
                candidate.resume_text = refined_resume['full_text']
                apply_resume_analysis(
                    candidate,
                    refined["ai_analysis"],
                    job_title=job_title,
                    generate_questions=True,
                )
                candidate.parsing_status = ParsingStatus.COMPLETED
                db.commit()
                db.refresh(candidate)
                finalize_batch_notifications(None, db, [candidate], user_id=current_user_id)
                _perf_log(
                    "process_single_resume_upload.refinement",
                    refinement_start,
                    file=original_filename,
                    upload_id=upload_id,
                    candidate_id=str(candidate.id),
                    status="completed",
                )
            except Exception as exc:
                db.rollback()
                candidate.parsing_status = ParsingStatus.FAILED
                db.add(candidate)
                db.commit()
                _perf_log(
                    "process_single_resume_upload.refinement",
                    refinement_start,
                    file=original_filename,
                    upload_id=upload_id,
                    candidate_id=str(candidate.id),
                    status="failed",
                    error=str(exc),
                )
        _perf_log(
            "process_single_resume_upload",
            total_start,
            file=original_filename,
            upload_id=upload_id,
            candidate_id=str(candidate.id),
        )
    except Exception as exc:
        db.rollback()
        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="error",
            message=f"Upload failed: {exc}",
        )
        print(f"Single upload processing failed for {original_filename}: {exc}")
        _perf_log(
            "process_single_resume_upload",
            total_start,
            file=original_filename,
            upload_id=upload_id,
            status="error",
        )
    finally:
        db.close()


def process_bulk_upload_batch(
    upload_id: str,
    saved_files: List[dict],
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
):
    """Process bulk uploads after the response so the request returns quickly."""
    db = SessionLocal()

    try:
        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")
        total_count = len(saved_files)
        processed_count = 0
        processed_candidates = []

        set_upload_progress(
            upload_id,
            current=0,
            total=total_count,
            status="processing",
            message="Screening resumes...",
        )

        worker_count = get_bulk_processing_workers(total_count)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(process_saved_resume, item["file_path"], item["filename"], job_data): item
                for item in saved_files
            }
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    processed = future.result()
                    resume_data = processed["resume_data"]
                    duplicate_candidate = _find_duplicate_candidate_for_job(
                        db,
                        name=resume_data.get("name"),
                        email=resume_data.get("email"),
                        job_id=job_id,
                    )
                    if duplicate_candidate:
                        print(
                            f"Skipping duplicate candidate for bulk upload filename={item['filename']} job_id={job_id}"
                        )
                        continue
                    candidate = Candidate(
                        name=resume_data['name'],
                        email=resume_data['email'],
                        phone=resume_data['phone'],
                        current_company=resume_data.get('current_company'),
                        current_role=resume_data.get('current_role'),
                        location=resume_data.get('location'),
                        experience_years=resume_data.get('experience_years'),
                        skills=resume_data['skills'],
                        education=resume_data.get('education'),
                        work_experience=resume_data.get('work_experience'),
                        resume_file_path=item["file_path"],
                        resume_text=resume_data['full_text'],
                        candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
                        job_id=job_id,
                        agency_id=agency_id,
                        created_by=current_user_id,
                        assigned_to_user_id=current_user_id,
                        parsing_status=ParsingStatus.PROCESSING,
                        score_threshold=threshold
                    )
                    apply_resume_analysis(candidate, processed["ai_analysis"], job_title=job_title)
                    db.add(candidate)
                    processed_candidates.append(candidate)
                except Exception as exc:
                    print(f"Bulk processing failed for {item['filename']}: {exc}")
                finally:
                    processed_count += 1
                    set_upload_progress(
                        upload_id,
                        current=processed_count,
                        total=total_count,
                        status="processing" if processed_count < total_count else "completed",
                        message=f"Screened {processed_count} of {total_count} resumes",
                    )

        if processed_candidates:
            db.commit()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="completed",
                message=f"Completed screening {len(processed_candidates)} of {total_count} resumes",
                processed=len(processed_candidates),
            )
            finalize_batch_notifications(None, db, processed_candidates, user_id=current_user_id)
        else:
            db.rollback()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="error",
                message="No resumes could be processed",
            )
    except Exception as exc:
        db.rollback()
        set_upload_progress(
            upload_id,
            current=0,
            total=len(saved_files),
            status="error",
            message=f"Bulk upload failed: {exc}",
        )
        print(f"Bulk upload background processing failed: {exc}")
    finally:
        db.close()


def process_zip_upload_batch(
    upload_id: str,
    zip_path: str,
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
):
    """Process ZIP uploads after the response so large archives don't time out."""
    db = SessionLocal()

    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")
        processed_count = 0
        total_count = upload_progress_store.get(upload_id, {}).get("total", 0)
        set_upload_progress(upload_id, status="processing", current=0, total=total_count, message="Screening resumes...")
        saved_files = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.filelist:
                file_ext = os.path.splitext(file_info.filename)[1].lower()
                if file_info.is_dir() or file_ext not in ALLOWED_RESUME_EXTENSIONS:
                    continue

                resume_content = zip_ref.read(file_info.filename)
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                with open(file_path, "wb") as resume_file:
                    resume_file.write(resume_content)
                saved_files.append({
                    "file_path": file_path,
                    "filename": file_info.filename,
                })

        processed_candidates = []
        failed_files = []
        worker_count = get_bulk_processing_workers(len(saved_files))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(process_saved_resume, item["file_path"], item["filename"], job_data): item
                for item in saved_files
            }
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    processed = future.result()
                    resume_data = processed["resume_data"]
                    duplicate_candidate = _find_duplicate_candidate_for_job(
                        db,
                        name=resume_data.get("name"),
                        email=resume_data.get("email"),
                        job_id=job_id,
                    )
                    if duplicate_candidate:
                        print(
                            f"Skipping duplicate candidate for zip upload filename={item['filename']} job_id={job_id}"
                        )
                        continue
                    candidate = Candidate(
                        name=resume_data['name'],
                        email=resume_data['email'],
                        phone=resume_data['phone'],
                        current_company=resume_data.get('current_company'),
                        current_role=resume_data.get('current_role'),
                        location=resume_data.get('location'),
                        experience_years=resume_data.get('experience_years'),
                        skills=resume_data['skills'],
                        education=resume_data.get('education'),
                        work_experience=resume_data.get('work_experience'),
                        resume_file_path=item["file_path"],
                        resume_text=resume_data['full_text'],
                        candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
                        job_id=job_id,
                        agency_id=agency_id,
                        created_by=current_user_id,
                        assigned_to_user_id=current_user_id,
                        parsing_status=ParsingStatus.PROCESSING,
                        score_threshold=threshold
                    )
                    apply_resume_analysis(candidate, processed["ai_analysis"], job_title=job_title)
                    db.add(candidate)
                    processed_candidates.append(candidate)
                except Exception as exc:
                    failed_files.append({"filename": item["filename"], "error": str(exc)})
                    print(f"ZIP processing failed for {item['filename']}: {exc}")
                finally:
                    processed_count += 1
                    set_upload_progress(
                        upload_id,
                        current=processed_count,
                        total=total_count,
                        status="processing" if processed_count < total_count else "completed",
                        message=f"Screened {processed_count} of {total_count} resumes"
                    )

        if processed_candidates:
            db.commit()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="completed",
                message=f"Completed screening {processed_count} resumes"
            )
            finalize_batch_notifications(
                None,
                db,
                processed_candidates,
                user_id=current_user_id,
            )
        else:
            db.rollback()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="error",
                message="No resumes could be processed"
            )
    except Exception as exc:
        db.rollback()
        set_upload_progress(upload_id, status="error", message=str(exc))
        print(f"ZIP batch processing failed: {exc}")
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        finally:
            db.close()

def evaluate_candidate_contextually(
    resume_text: str,
    job_title: str,
    job_description: str,
    job_requirements: str,
    candidate_skills: list,
    experience_text: str,
    projects: list,
    job_skills: list = None,
    candidate_location: str = "",
    job_location: str = "",
    experience_years: float = 0.0,
    candidate_roles: list | None = None,
    candidate_industries: list | None = None,
    job_experience_required: str = "",
    industry: str = "",
) -> dict:
    """Evidence-based AI evaluation using LLM with structured scoring"""
    from app.config import settings
    import json
    
    print(f"\n🔍 Using Rule-Based Evaluation (LLM disabled)")
    
    # GROQ/OpenAI LLM code commented out - using only enhanced_fallback_evaluation
    # 
    # print(f"\n🔍 LLM Configuration Check:")
    # print(f"   GROQ_API_KEY: {'✅ SET' if settings.GROQ_API_KEY else '❌ NOT SET'}")
    # print(f"   LLM_PROVIDER: {settings.LLM_PROVIDER}")
    # 
    # # Enhanced prompt with weighted evaluation criteria
    # prompt = f"""You are a senior technical recruiter with 15+ years of experience..."""
    # 
    # try:
    #     # Try LLM analysis
    #     if settings.GROQ_API_KEY and settings.LLM_PROVIDER == "groq":
    #         print(f"   🤖 Using Groq LLM with enhanced evaluation...")
    #         response = call_groq_llm(prompt, settings.GROQ_API_KEY)
    #         print(f"   ✅ Groq LLM response received!")
    #     elif settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
    #         print(f"   🤖 Using OpenAI LLM with enhanced evaluation...")
    #         response = call_openai_llm(prompt, settings.OPENAI_API_KEY)
    #         print(f"   ✅ OpenAI LLM response received!")
    #     else:
    #         print(f"   ⚠️  No LLM configured, using enhanced fallback...")
    #         return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)
    #     
    #     # Parse LLM response
    #     result = json.loads(response)
    #     print(f"   ✅ LLM Score Breakdown:")
    #     
    #     # Support both old and new field names for backward compatibility
    #     if 'skills_score' in result:
    #         # New weighted scoring format
    #         print(f"      Skills Match: {result.get('skills_score', 0)}/45")
    #         print(f"      Experience: {result.get('experience_score', 0)}/25")
    #         print(f"      Projects: {result.get('projects_score', 0)}/15")
    #         print(f"      Education: {result.get('education_score', 0)}/10")
    #         print(f"      Soft Skills: {result.get('soft_skills_score', 0)}/5")
    #     else:
    #         # Old format (fallback)
    #         print(f"      Technical Depth: {result.get('technical_depth_score', 0)}/30")
    #         print(f"      Project Complexity: {result.get('project_complexity_score', 0)}/20")
    #         print(f"      Relevance: {result.get('relevance_score', 0)}/20")
    #         print(f"      Impact: {result.get('impact_score', 0)}/15")
    #         print(f"      Seniority: {result.get('seniority_score', 0)}/15")
    #     
    #     print(f"      TOTAL: {result.get('match_score', 0)}/100")
    #     return result
    #     
    # except Exception as e:
    #     print(f"   ❌ LLM evaluation failed: {e}")
    #     print(f"   ⚠️  Falling back to enhanced rule-based evaluation...")
    #     return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)
    
    # Always use enhanced fallback evaluation
    return enhanced_fallback_evaluation(
        resume_text,
        job_title,
        job_description,
        job_requirements,
        candidate_skills,
        experience_text,
        projects,
        job_skills,
        candidate_location=candidate_location,
        job_location=job_location,
        experience_years=experience_years,
        candidate_roles=candidate_roles,
        candidate_industries=candidate_industries,
        job_experience_required=job_experience_required,
        industry=industry,
    )

def call_groq_llm(prompt: str, api_key: str) -> str:
    """Call Groq LLM API"""
    import requests
    import re
    
    print(f"   📡 Calling Groq API with key: {api_key[:20]}...")
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",  # Updated to latest model
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            },
            timeout=30
        )
        
        print(f"   📊 Groq API Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Groq API Error: {response.text}")
            raise Exception(f"Groq API returned {response.status_code}: {response.text}")
        
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        
        # Extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return content
        
    except requests.exceptions.Timeout:
        print(f"   ⏱️ Groq API timeout after 30s")
        raise
    except Exception as e:
        print(f"   ❌ Groq API call failed: {str(e)}")
        raise

def call_openai_llm(prompt: str, api_key: str) -> str:
    """Call OpenAI API"""
    import requests
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# JD-Driven Skill Maps
JOB_SKILL_MAPS = {
    "hr executive": {
        "core": ["recruitment", "hiring", "hr operations", "employee relations", "onboarding", "payroll", "compliance", "talent acquisition", "hr management", "human resources", "staffing", "benefits", "compensation"],
        "transferable": ["team management", "people management", "leadership", "coordination", "employee handling", "communication", "organization"],
        "ignore": ["javascript", "python", "java", "programming", "coding", "software", "development", "algorithm", "data structure", "react", "angular", "node", "api", "database", "sql", "html", "css"]
    },
    "software engineer": {
        "core": ["python", "java", "javascript", "react", "node", "sql", "mysql", "mongodb", "api", "rest", "git", "html", "css", "spring", "django", "flask"],
        "transferable": ["problem solving", "teamwork", "analytical", "debugging"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations", "onboarding", "talent acquisition", "human resources", "staffing", "benefits", "compensation"]
    },
    "web developer": {
        "core": ["html", "css", "javascript", "react", "angular", "vue", "node.js", "frontend", "backend", "web development", "responsive", "ui", "ux"],
        "transferable": ["problem solving", "teamwork", "design"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations"]
    },
    "data scientist": {
        "core": ["python", "statistics", "machine learning", "data analysis", "pandas", "numpy", "tensorflow", "pytorch", "sql", "r", "data mining", "modeling", "visualization"],
        "transferable": ["analytical thinking", "research", "problem solving"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations"]
    },
    "data analyst": {
        "core": ["data analysis", "sql", "excel", "tableau", "power bi", "statistics", "python", "r", "data visualization", "reporting"],
        "transferable": ["analytical thinking", "problem solving", "communication"],
        "ignore": ["recruitment", "hr", "hiring", "payroll"]
    },
    "marketing manager": {
        "core": ["marketing", "digital marketing", "seo", "sem", "social media", "content marketing", "brand management", "campaign", "analytics", "advertising"],
        "transferable": ["communication", "creativity", "strategy", "leadership"],
        "ignore": ["programming", "coding", "software development", "javascript", "python"]
    },
    "sales executive": {
        "core": ["sales", "business development", "client relationship", "negotiation", "crm", "lead generation", "closing", "revenue"],
        "transferable": ["communication", "persuasion", "networking"],
        "ignore": ["programming", "coding", "software development", "hr", "recruitment"]
    },
    "finance analyst": {
        "core": ["finance", "financial analysis", "accounting", "budgeting", "forecasting", "excel", "reporting", "variance analysis", "erp", "tally", "tax", "gst"],
        "transferable": ["analytical thinking", "attention to detail", "communication"],
        "ignore": ["programming", "coding", "software development", "javascript", "python", "react", "node", "api"]
    },
    "financial analyst": {
        "core": ["finance", "financial analysis", "accounting", "budgeting", "forecasting", "excel", "reporting", "variance analysis", "erp", "tally", "tax", "gst"],
        "transferable": ["analytical thinking", "attention to detail", "communication"],
        "ignore": ["programming", "coding", "software development", "javascript", "python", "react", "node", "api"]
    },
    "accountant": {
        "core": ["accounting", "bookkeeping", "tally", "gst", "tax", "reconciliation", "ledger", "accounts payable", "accounts receivable", "excel"],
        "transferable": ["attention to detail", "organization", "compliance"],
        "ignore": ["programming", "coding", "software development", "javascript", "python", "react", "node", "api"]
    },
    "default": {"core": [], "transferable": ["communication", "teamwork"], "ignore": []}
}


def calculate_location_score(candidate_location: str, job_location: str, resume_text: str = "") -> float:
    """Return a 0-5 score based on candidate/job location alignment."""
    candidate_value = (candidate_location or "").strip().lower()
    job_value = (job_location or "").strip().lower()
    resume_value = (resume_text or "").strip().lower()

    if not job_value:
        return 2.5

    search_space = " ".join(part for part in [candidate_value, resume_value] if part)
    if not search_space:
        return 0.0

    job_parts = [part.strip() for part in re.split(r"[,/|-]", job_value) if part.strip()]
    if any(part and part in search_space for part in job_parts):
        return 5.0

    if job_value in search_space or search_space in job_value:
        return 5.0

    return 0.0

def enhanced_fallback_evaluation(
    resume_text: str,
    job_title: str,
    job_description: str,
    job_requirements: str,
    candidate_skills: list,
    experience_text: str,
    projects: list,
    job_skills: list = None,
    candidate_location: str = "",
    job_location: str = "",
    experience_years: float = 0.0,
    candidate_roles: list | None = None,
    candidate_industries: list | None = None,
    job_experience_required: str = "",
    industry: str = "",
) -> dict:
    """ATS workflow scoring with feature engineering, extractive summarization, and custom ranking."""
    from app.balanced_scoring import evaluate_resume_balanced, extract_years_experience
    
    print("\nBalanced Scoring System:")
    print(f"   Job: {job_title}")
    
    # Extract years of experience
    years_exp = experience_years if experience_years and experience_years > 0 else extract_years_experience(resume_text)
    
    role_map = JOB_SKILL_MAPS.get(job_title.lower().strip())
    jd_extracted_skills = extract_skills_from_job_text(f"{job_title}\n{job_description}\n{job_requirements}")

    # Prefer explicit JD skills, then role map, then extracted JD keywords.
    if job_skills and len(job_skills) > 0:
        required_skills = job_skills[:10]
        print(f"   Using JD skills: {required_skills}")
    elif role_map:
        required_skills = role_map.get("core", [])[:10]
        print(f"   Using role map skills: {required_skills}")
    elif jd_extracted_skills:
        required_skills = jd_extracted_skills[:10]
        print(f"   Extracted JD skills: {required_skills}")
    else:
        skill_map = JOB_SKILL_MAPS.get(job_title.lower().strip(), JOB_SKILL_MAPS["default"])
        required_skills = skill_map.get("core", [])[:10]
        print(f"   Fallback skills: {required_skills}")
    
    print(f"   Required skills for {job_title}: {required_skills}")
    
    preferred_skills = []
    if job_skills and len(job_skills) > 10:
        preferred_skills = job_skills[10:15]
    elif role_map:
        preferred_skills = role_map.get("transferable", [])[:5]

    # Prepare data for balanced scoring
    resume_data = {
        'full_text': resume_text,
        'years_of_experience': years_exp
    }
    
    # Determine experience range based on job title
    if 'senior' in job_title.lower():
        exp_min, exp_max = 5, 10
    elif 'junior' in job_title.lower() or 'entry' in job_title.lower():
        exp_min, exp_max = 0, 2
    else:
        exp_min, exp_max = 2, 5
    
    job_requirements_data = {
        'required_skills': required_skills,
        'experience_min': exp_min,
        'experience_max': exp_max,
        'description': job_description,
        'title': job_title
    }
    
    # Evaluate using balanced scoring
    result = evaluate_resume_balanced(resume_data, job_requirements_data)
    # FIX 3 — truncate all text to 2000 chars before TF-IDF/BM25 to avoid slow vectorization
    matching_signals = compute_matching_signals(
        resume_text=resume_text[:2000],
        job_title=job_title,
        job_description=job_description[:2000],
        job_requirements=job_requirements[:2000],
    )
    
    # Step 8: feature engineering inputs.
    components = result['components']
    skills_weighted = round((components['skills']['match_percentage'] / 100.0) * 35.0, 2)
    experience_weighted = round((components['experience']['score'] / max(components['experience']['max'], 1)) * 20.0, 2)
    tfidf_weighted = round((matching_signals['tfidf_score'] / 100.0) * 20.0, 2)
    bm25_weighted = round((matching_signals['bm25_score'] / 100.0) * 15.0, 2)
    education_weighted = round((components['education']['score'] / max(components['education']['max'], 1)) * 5.0, 2)
    location_weighted = round(calculate_location_score(candidate_location, job_location, resume_text), 2)
    feature_vector = build_feature_vector(components, matching_signals)
    candidate_summary = generate_summary(
        required_skills=required_skills,
        preferred_skills=preferred_skills,
        required_experience=job_experience_required or f"{exp_min}-{exp_max} years",
        role_title=job_title,
        industry=industry,
        candidate_skills=candidate_skills,
        candidate_experience=years_exp,
        candidate_industries=candidate_industries or [],
        candidate_roles=candidate_roles or [],
    )
    ranking_result = compute_ranking_result(feature_vector)
    final_score = ranking_result['ranking_score_percent']

    ignored_role_terms = role_map.get("ignore", []) if role_map else []
    ignore_hits = sum(1 for term in ignored_role_terms if term in resume_text.lower())
    matched_required_count = len(components['skills']['matched_skills'])
    if required_skills and matched_required_count == 0 and ignore_hits >= 2:
        final_score = min(final_score, 35)
    elif required_skills and matched_required_count <= 1 and ignore_hits >= 3:
        final_score = min(final_score, 45)
    
    print(f"   Skills Match: {skills_weighted}/35")
    print(f"   Experience: {experience_weighted}/20")
    print(f"   TF-IDF Match: {tfidf_weighted}/20")
    print(f"   BM25 Match: {bm25_weighted}/15")
    print(f"   Education: {education_weighted}/5")
    print(f"   Location: {location_weighted}/5")
    print(f"   Ranking Score: {ranking_result['ranking_score']}")
    print(f"   TOTAL: {final_score}/100")
    
    # Determine match label and status
    if final_score >= 80:
        match_label, status = "Strong Fit", "shortlisted"
    elif final_score >= 65:
        match_label, status = "Potential Fit", "shortlisted"
    elif final_score >= 50:
        match_label, status = "Borderline Fit", "review"
    else:
        match_label, status = "Weak Fit", "rejected"
    
    # Build strengths from components
    strengths = []
    if components['skills']['match_percentage'] >= 80:
        strengths.append(f"Excellent skills match: {len(components['skills']['matched_skills'])} of {len(required_skills)} required skills")
    elif components['skills']['match_percentage'] >= 50:
        strengths.append(f"Good skills match: {components['skills']['match_percentage']}%")
    
    if experience_weighted >= 12:
        strengths.append(f"{years_exp} years of relevant experience")

    if education_weighted >= 4:
        strengths.append(f"Education: {components['education']['relevance']}")

    if matching_signals['combined_score'] >= 60:
        strengths.append(f"Strong resume-to-JD similarity: {matching_signals['combined_score']}%")

    if location_weighted >= 5:
        strengths.append("Location aligns with job requirement")
    
    if not strengths:
        strengths.append("Basic qualifications present")
    
    # Build gaps
    gaps = []
    if components['skills']['match_percentage'] < 50:
        missing_count = len(required_skills) - len(components['skills']['matched_skills'])
        gaps.append(f"Missing {missing_count} key skills from requirements")
    
    if experience_weighted < 8:
        gaps.append("Experience level appears below the role expectation")

    if education_weighted < 2.5:
        gaps.append("Education background not clearly relevant")

    if job_location and location_weighted == 0:
        gaps.append("Location does not align with job requirement")
    
    if not gaps:
        gaps.append("No significant gaps identified")
    
    # AI analysis
    ai_analysis = f"Workflow: ingestion -> extraction -> cleaning -> segmentation -> information extraction -> skill intelligence -> matching -> features -> summary -> ranking. "
    ai_analysis += f"Feature vector: skill {feature_vector['skill_score']}, "
    ai_analysis += f"experience {feature_vector['experience_score']}, "
    ai_analysis += f"tfidf {feature_vector['tfidf_score']}, "
    ai_analysis += f"bm25 {feature_vector['bm25_score']}, "
    ai_analysis += f"education {feature_vector['education_score']}. "
    ai_analysis += f"Ranking score: {ranking_result['ranking_score']}. "
    ai_analysis += f"Overall: {match_label} ({final_score}/100)."
    
    return {
        'match_score': round(final_score, 1),
        'match_label': match_label,
        'candidate_summary': candidate_summary,
        'key_strengths': strengths[:5],
        'skill_gaps': gaps[:5],
        'ai_analysis': ai_analysis,
        'status': status,
        'components': components,
        'matching_signals': matching_signals,
        'feature_vector': feature_vector,
        'ranking_result': ranking_result,
        'workflow_steps': [
            'Document Ingestion',
            'Text Extraction',
            'Text Cleaning & Normalization',
            'Section Segmentation',
            'Information Extraction',
            'Skill Intelligence Layer',
            'Matching Engine',
            'Feature Engineering',
            'Summary Generator',
            'Ranking Engine',
        ],
        'weighted_breakdown': {
            'skills_match': skills_weighted,
            'experience': experience_weighted,
            'tfidf_similarity': tfidf_weighted,
            'bm25_score': bm25_weighted,
            'education': education_weighted,
            'location': location_weighted,
        },
    }

def extract_skills_from_job_text(job_text: str) -> list:
    """Extract JD skills using the same shared ATS skill extraction pipeline."""
    return get_skill_engine().extract_skills(job_text)[:30]

def simulate_resume_parsing(
    candidate: Candidate,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
    ai_analysis: dict = None,
    user_id=None,
):
    """Resume parsing with AI scoring, stage assignment, and auto-email for shortlisted"""
    
    candidate.parsing_status = ParsingStatus.COMPLETED
    
    if ai_analysis:
        # Set score from AI analysis
        score = ai_analysis.get('match_score', 0)
        
        # CRITICAL FIX: Never allow 0 score for valid resumes
        if score == 0 and candidate.resume_text and len(candidate.resume_text.strip()) > 100:
            print(f"⚠️ WARNING: Score is 0 but resume has {len(candidate.resume_text)} chars. Setting minimum score.")
            score = 45  # Minimum "Borderline Fit" score
        
        candidate.resume_score = score
        
        # Set summary from AI analysis
        candidate.summary = ai_analysis.get('candidate_summary', '')
        
        # Generate predefined interview questions based on resume and job
        if candidate.resume_text and candidate.job_id:
            try:
                from app.models import JobDescription
                job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
                if job:
                    questions = generate_interview_questions(candidate.resume_text, job.title, candidate.skills or [])
                    candidate.predefined_questions = questions
            except Exception as e:
                print(f"⚠️ Question generation failed: {e}")
        
        # NEW LOGIC: Set stage based on score thresholds with 10-point range
        threshold = candidate.score_threshold or 60
        
        if score >= threshold:
            # SHORTLISTED: Auto-send email
            candidate.stage = CandidateStage.SHORTLISTED
            
            # Auto-send email to shortlisted candidates
            try:
                from app.config import settings
                from app.mailer import is_email_configured, send_html_email
                from app.models import EmailCommunication, JobDescription, UserRole
                from urllib.parse import urlencode

                # Check admin wallet balance before sending email
                admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
                if not admin or (admin.wallet_balance or 0) <= 0:
                    print(f"⚠️ Email blocked: Admin wallet has 0 credits")
                    raise Exception("Insufficient credits to send email")
                
                if is_email_configured() and candidate.email:
                    # Get job details
                    job = None
                    if candidate.job_id:
                        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
                    
                    # Build interview URL
                    params = {
                        'candidateId': candidate.id,
                        'name': candidate.name,
                        'email': candidate.email,
                    }
                    if job:
                        params['jobId'] = job.id
                        params['jobTitle'] = job.title
                    
                    interview_url = f"{settings.FRONTEND_URL}/interview?{urlencode(params)}"
                    
                    # Email content
                    subject = f"Interview Invitation - {job.title if job else 'Position'}"
                    message = f"Dear {candidate.name},\n\nCongratulations! Your resume has been shortlisted for the {job.title if job else 'position'}. Please book your interview slot using the button below."
                    
                    html_body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                            <p>{message.replace(chr(10), '<br>')}</p>
                            <div style="margin: 30px 0; text-align: center;">
                                <a href="{settings.SLOT_BOOKING_URL}" 
                                   style="display: inline-block; padding: 15px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                                    Book Your Slot
                                </a>
                            </div>
                            <p style="font-size: 12px; color: #666; margin-top: 30px;">
                                View your interview details: <a href="{interview_url}">{interview_url}</a>
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    # Send email
                    provider_message_id = send_html_email(
                        to_email=candidate.email,
                        subject=subject,
                        html_content=html_body
                    )

                    # Create EmailCommunication record
                    email_comm = EmailCommunication(
                        candidate_id=candidate.id,
                        candidate_name=candidate.name,
                        candidate_email=candidate.email,
                        email_type="Slot Selection Email",
                        status="sent",
                        sent_at=datetime.utcnow(),
                        provider_message_id=provider_message_id
                    )
                    db.add(email_comm)
                    
                    print(f"✅ Auto-email sent to {candidate.email} (SHORTLISTED)")
            except Exception as e:
                print(f"⚠️ Auto-email failed: {e}")
        
        else:
            assign_resume_pipeline_stage(candidate, score, threshold)
        
        print(f"✓ Candidate {candidate.name}: Score={candidate.resume_score}, Threshold={threshold}, Stage={candidate.stage.value}")
    else:
        # No AI analysis - set minimum score and move out of APPLIED
        candidate.resume_score = 40
        # If candidate has a job, put in REVIEW so they show in dashboard
        assign_resume_pipeline_stage(candidate, candidate.resume_score, candidate.score_threshold)
        print(f"⚠ Candidate {candidate.name}: No AI analysis, score=40")
    
    db.commit()
    db.refresh(candidate)

def generate_interview_questions(resume_text: str, job_title: str, skills: list) -> str:
    """Generate 3-5 interview questions based on resume and job"""
    import random
    
    questions = []
    
    # Technical questions based on skills
    if skills:
        top_skills = skills[:3]
        for skill in top_skills:
            tech_questions = [
                f"Can you describe a project where you used {skill} and the challenges you faced?",
                f"How would you rate your proficiency in {skill} and what's your experience with it?",
                f"Tell me about a time when you had to learn {skill} quickly for a project."
            ]
            questions.append(random.choice(tech_questions))
    
    # Role-specific questions
    role_questions = {
        'software engineer': [
            "Describe your approach to debugging a complex production issue.",
            "How do you ensure code quality in your projects?",
            "Tell me about a time you optimized application performance."
        ],
        'backend': [
            "How do you design scalable APIs?",
            "Explain your experience with database optimization.",
            "Describe a challenging integration you've implemented."
        ],
        'frontend': [
            "How do you approach responsive design?",
            "Describe your experience with state management.",
            "How do you optimize frontend performance?"
        ]
    }
    
    job_lower = job_title.lower()
    for key, qs in role_questions.items():
        if key in job_lower:
            questions.extend(random.sample(qs, min(2, len(qs))))
            break
    
    # Generic behavioral questions
    behavioral = [
        "Tell me about a challenging project you worked on and how you overcame obstacles.",
        "Describe a situation where you had to work with a difficult team member.",
        "How do you prioritize tasks when working on multiple projects?"
    ]
    questions.append(random.choice(behavioral))
    
    # Return top 5 questions
    return "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions[:5])])


def simulate_resume_parsing(
    candidate: Candidate,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
    ai_analysis: dict = None,
    user_id=None,
    job_title: Optional[str] = None,
):
    """Override legacy parser flow with stage assignment and secure notification enqueueing."""
    apply_resume_analysis(candidate, ai_analysis, job_title=job_title)

    db.commit()
    db.refresh(candidate)

    if background_tasks and candidate.stage in [CandidateStage.SHORTLISTED, CandidateStage.RESUME_REJECTED]:
        enqueue_stage_notification(background_tasks, db, candidate, candidate.stage.value, user_id=user_id)

@router.get("/upload-progress/{upload_id}")
def get_upload_progress(
    upload_id: str,
    current_user: User = Depends(get_current_active_user)
):
    progress = upload_progress_store.get(upload_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Upload progress not found")

    return progress


@router.get("/count")
def get_candidates_count(
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[UUID] = None,
    min_score: Optional[float] = None,
    client: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole
    normalize_legacy_candidate_stages(db)
    sync_rescheduled_candidate_stages_from_slots(db)
    query = db.query(Candidate)
    if current_user.role == UserRole.SUPER_ADMIN:
        if agency_id:
            query = query.filter(Candidate.agency_id == agency_id)
    else:
        query = _apply_candidate_list_scope(query, current_user)
    if client:
        query = query.join(JobDescription).filter(JobDescription.company_name == client)
    query = _apply_candidate_search_filter(query, search)
    if stage:
        query = query.filter(Candidate.stage == stage)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if min_score is not None:
        query = query.filter(Candidate.resume_score >= min_score)
    query = _apply_candidate_created_at_filters(
        query,
        from_date=from_date,
        to_date=to_date,
    )
    return {"count": query.count()}

@router.get("", response_model=List[CandidateResponse])
def get_candidates(
    page: Optional[int] = None,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[UUID] = None,
    min_score: Optional[float] = None,
    client: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole
    total_start = perf_counter()
    normalization_start = perf_counter()
    normalize_legacy_candidate_stages(db)
    sync_rescheduled_candidate_stages_from_slots(db)
    normalization_time = perf_counter() - normalization_start
    query = db.query(Candidate)

    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(Candidate.agency_id == agency_id)
    else:
        query = _apply_candidate_list_scope(query, current_user)
    
    query = _apply_client_filter(query, client)
    query = _apply_candidate_search_filter(query, search)
    if stage:
        query = query.filter(Candidate.stage == stage)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if min_score is not None:
        query = query.filter(Candidate.resume_score >= min_score)
    query = _apply_candidate_created_at_filters(
        query,
        from_date=from_date,
        to_date=to_date,
    )
    effective_limit, effective_offset = _resolve_pagination(page, limit, offset)
    query_start = perf_counter()
    query = (
        query.options(
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
        )
        .order_by(Candidate.created_at.desc())
    )
    if effective_limit is not None:
        query = query.offset(effective_offset).limit(effective_limit)
    candidates = query.all()
    query_time = perf_counter() - query_start
    print(f"[DB PERF] candidates query={query_time:.4f}s")
    
    # Add job title to response
    serialization_start = perf_counter()
    result = []
    for c in candidates:
        candidate_dict = {
            "id": c.id,
            "name": c.name,
            "email": sanitize_candidate_email(c.email),
            "phone": c.phone,
            "current_company": c.current_company,
            "current_role": c.current_role,
            "experience_years": c.experience_years,
            "location": sanitize_candidate_location(c.location),
            "linkedin_url": c.linkedin_url,
            "resume_file_path": c.resume_file_path,
            "resume_text": c.resume_text,
            "parsing_status": c.parsing_status,
            "resume_score": c.resume_score,
            "score_threshold": c.score_threshold,
            "skills": c.skills,
            "education": c.education,
            "work_experience": c.work_experience,
            "stage": c.stage,
            "stage_updated_at": c.stage_updated_at,
            "stage_entered_at": c.stage_entered_at,
            "applied_at": c.applied_at,
            "job_id": c.job_id,
            "job_title": c.job.title if c.job else None,
            "summary": c.summary,
            "internal_notes": c.internal_notes,
            "predefined_questions": c.predefined_questions,
            "created_at": c.created_at,
            "field_confidence": _compute_field_confidence(c),
        }
        result.append(build_safe_candidate_response(candidate_dict))
    _perf_log(
        "candidates",
        total_start,
        normalization=f"{normalization_time:.4f}s",
        query=f"{query_time:.4f}s",
        serialization=f"{perf_counter() - serialization_start:.4f}s",
        row_count=len(result),
        limit=effective_limit or "all",
        offset=effective_offset,
    )
    return result

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate_dict = {
        "id": candidate.id,
        "name": candidate.name,
        "email": sanitize_candidate_email(candidate.email),
        "phone": candidate.phone,
        "current_company": candidate.current_company,
        "current_role": candidate.current_role,
        "experience_years": candidate.experience_years,
        "location": sanitize_candidate_location(candidate.location),
        "linkedin_url": candidate.linkedin_url,
        "resume_file_path": candidate.resume_file_path,
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
        "predefined_questions": candidate.predefined_questions,
        "created_at": candidate.created_at
    }
    return build_safe_candidate_response(candidate_dict)

@router.post("", response_model=CandidateResponse)
def create_candidate(
    candidate: CandidateCreate,
    background_tasks: BackgroundTasks,
    subscription=Depends(enforce_plan("resume_score")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        duplicate_candidate = _find_duplicate_candidate_for_job(
            db,
            name=candidate.name,
            email=candidate.email,
            job_id=candidate.job_id,
        )
        if duplicate_candidate:
            raise HTTPException(status_code=409, detail="Application already exists")

        db_candidate = Candidate(
            **candidate.model_dump(),
            agency_id=current_user.agency_id,
            created_by=current_user.id,
            assigned_to_user_id=current_user.id,
            parsing_status=ParsingStatus.PENDING
        )
        db.add(db_candidate)
        db.flush()
        
        # Simulate resume parsing
        simulate_resume_parsing(db_candidate, db, background_tasks=background_tasks, user_id=current_user.id)
        increment_plan_usage(db, current_user, "resume_score", subscription=subscription)
        db.commit()
        db.refresh(db_candidate)
        
        return db_candidate
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    subscription=Depends(enforce_plan("resume_score")),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    print(f"Upload received - job_id: {job_id}, file: {file.filename}, threshold: {threshold}")
    upload_started_at = perf_counter()
    file_path = None
    
    try:
        # Validate file type - PDF and Word documents
        valid_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        valid_extensions = ['.pdf', '.doc', '.docx']
        
        is_valid = (file.content_type in valid_types or 
                   any(file.filename.lower().endswith(ext) for ext in valid_extensions))
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Only PDF and Word documents (.pdf, .doc, .docx) are allowed")
        
        # Create upload directory if not exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Save file
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        file_upload_ms = round((perf_counter() - upload_started_at) * 1000.0, 2)
        
        upload_id = str(uuid.uuid4())
        existing_upload_id = _register_recent_upload_request(
            current_user=current_user,
            job_id=job_id,
            original_filename=file.filename,
            file_bytes=content,
            upload_id=upload_id,
        )
        if existing_upload_id:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except OSError:
                pass
            existing_progress = upload_progress_store.get(existing_upload_id) or {}
            return {
                "message": "Duplicate upload ignored. Returning the existing upload job.",
                "upload_id": existing_upload_id,
                "queued": 0,
                "duplicate": True,
                "status": existing_progress.get("status", "queued"),
            }

        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="queued",
            message="Resume queued for analysis",
        )
        background_tasks.add_task(
            process_single_resume_upload,
            upload_id,
            file_path,
            file.filename,
            job_id,
            threshold,
            current_user.agency_id,
            current_user.id,
            file_upload_ms,
        )
        increment_plan_usage(db, current_user, "resume_score", subscription=subscription)
        db.commit()

        return {
            "message": "Resume upload accepted and queued for analysis.",
            "upload_id": upload_id,
            "queued": 1,
            "file_upload_ms": file_upload_ms,
        }
        
    except HTTPException:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.rollback()
        raise
    except Exception as e:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError:
                pass
        db.rollback()
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/bulk-upload")
async def bulk_upload_resumes(
    files: List[UploadFile] = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    print(f"Bulk upload received - job_id: {job_id}, files: {len(files)}")
    results = []

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_files = []

    for file in files:
        try:
            if not is_valid_resume_upload(file):
                results.append({"filename": file.filename, "status": "failed", "error": "Invalid file type"})
                continue

            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            saved_files.append({
                "filename": file.filename,
                "file_path": file_path,
            })
        except Exception as e:
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})

    if not saved_files:
        return {"results": results}

    upload_id = str(uuid.uuid4())
    queued_files = [{"filename": item["filename"], "status": "queued"} for item in saved_files]
    queued_files.extend(results)
    set_upload_progress(
        upload_id,
        current=0,
        total=len(saved_files),
        status="queued",
        message=f"Queued {len(saved_files)} resumes for screening",
    )
    background_tasks.add_task(
        process_bulk_upload_batch,
        upload_id,
        saved_files,
        job_id,
        threshold,
        current_user.agency_id,
        current_user.id,
    )

    return {
        "message": f"Bulk upload accepted. {len(saved_files)} resumes queued for background processing.",
        "upload_id": upload_id,
        "queued": len(saved_files),
        "results": queued_files,
    }

@router.post("/zip-upload")
async def zip_upload_resumes(
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Validate ZIP file
    if file.content_type != "application/zip" and not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

    try:
        # Save ZIP file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            content = await file.read()
            temp_zip.write(content)
            temp_zip_path = temp_zip.name

        upload_id = str(uuid.uuid4())

        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            queued_files = [
                {"filename": file_info.filename, "status": "queued"}
                for file_info in zip_ref.filelist
                if not file_info.is_dir() and os.path.splitext(file_info.filename)[1].lower() in ALLOWED_RESUME_EXTENSIONS
            ]

        set_upload_progress(
            upload_id,
            current=0,
            total=len(queued_files),
            status="queued",
            message=f"Queued {len(queued_files)} resumes for screening"
        )

        background_tasks.add_task(
            process_zip_upload_batch,
            upload_id,
            temp_zip_path,
            job_id,
            threshold,
            current_user.agency_id,
            current_user.id,
        )

        return {
            "message": f"ZIP upload accepted. {len(queued_files)} resumes queued for background processing.",
            "upload_id": upload_id,
            "queued": len(queued_files),
            "results": queued_files,
        }
    except Exception as e:
        if 'temp_zip_path' in locals() and os.path.exists(temp_zip_path):
            os.unlink(temp_zip_path)
        raise HTTPException(status_code=500, detail=f"ZIP upload failed: {str(e)}")

@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: UUID,
    candidate_update: CandidateUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.model_dump(exclude_unset=True)
    
    if "stage" in update_data:
        update_data["stage_updated_at"] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(db_candidate, field, value)
    
    db.commit()
    db.refresh(db_candidate)
    if "stage" in update_data:
        from app.routes.analytics import clear_analytics_cache
        clear_analytics_cache()
        enqueue_stage_notification(background_tasks, db, db_candidate, db_candidate.stage.value, user_id=current_user.id)
    return db_candidate

@router.patch("/{candidate_id}/stage", response_model=CandidateResponse)
def update_candidate_stage(
    candidate_id: UUID,
    stage_update: CandidateStageUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_candidate.stage = stage_update.stage
    db_candidate.stage_updated_at = datetime.utcnow()
    db_candidate.stage_entered_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_candidate)
    from app.routes.analytics import clear_analytics_cache
    clear_analytics_cache()
    if not stage_update.suppress_notification:
        enqueue_stage_notification(background_tasks, db, db_candidate, db_candidate.stage.value, user_id=current_user.id)
    candidate_dict = {
        "id": db_candidate.id,
        "name": db_candidate.name,
        "email": sanitize_candidate_email(db_candidate.email),
        "phone": db_candidate.phone,
        "current_company": db_candidate.current_company,
        "current_role": db_candidate.current_role,
        "experience_years": db_candidate.experience_years,
        "location": sanitize_candidate_location(db_candidate.location),
        "linkedin_url": db_candidate.linkedin_url,
        "resume_file_path": db_candidate.resume_file_path,
        "parsing_status": db_candidate.parsing_status,
        "resume_score": db_candidate.resume_score,
        "score_threshold": db_candidate.score_threshold,
        "skills": db_candidate.skills,
        "education": db_candidate.education,
        "work_experience": db_candidate.work_experience,
        "stage": db_candidate.stage,
        "stage_updated_at": db_candidate.stage_updated_at,
        "stage_entered_at": db_candidate.stage_entered_at,
        "applied_at": db_candidate.applied_at,
        "job_id": db_candidate.job_id,
        "job_title": db_candidate.job.title if db_candidate.job else None,
        "summary": db_candidate.summary,
        "internal_notes": db_candidate.internal_notes,
        "predefined_questions": db_candidate.predefined_questions,
        "created_at": db_candidate.created_at,
    }
    return build_safe_candidate_response(candidate_dict)







@router.delete("/{candidate_id}")
def delete_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole

    try:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Only agency admins can delete resumes")

        db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not db_candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Store candidate_id for sheets deletion
        sheets_candidate_id = db_candidate.candidate_id
        
        # Delete dependent records first to satisfy foreign key constraints
        from app.models import EmailCommunication, Interview, NotificationWorkflowToken
        db.query(Interview).filter(Interview.candidate_id == candidate_id).delete()
        db.query(EmailCommunication).filter(EmailCommunication.candidate_id == candidate_id).delete()
        db.query(NotificationWorkflowToken).filter(NotificationWorkflowToken.candidate_id == candidate_id).delete()
        
        # Try to delete resume file if exists (skip if fails on Railway)
        if db_candidate.resume_file_path:
            try:
                if os.path.exists(db_candidate.resume_file_path):
                    os.remove(db_candidate.resume_file_path)
            except Exception as e:
                print(f"File deletion skipped: {e}")
        
        # Delete candidate from database
        db.delete(db_candidate)
        db.commit()
        

        
        return {"message": "Candidate deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/{candidate_id}/resume-file")
async def get_resume_file(
    candidate_id: UUID,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """View resume file - supports PDF and Word documents"""
    from app.auth import verify_token
    from fastapi.responses import Response, HTMLResponse
    import base64
    
    try:
        if not token:
            raise HTTPException(status_code=401, detail="Token required")
        
        token_data = verify_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user = db.query(User).filter(User.email == token_data.email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if not candidate.resume_file_path:
            raise HTTPException(status_code=404, detail="No resume file uploaded for this candidate")
        
        # Convert relative path to absolute path
        from app.config import settings
        
        # Handle different path formats
        print(f"🔍 Looking for resume file:")
        print(f"   Database path: {candidate.resume_file_path}")
        print(f"   UPLOAD_DIR setting: {settings.UPLOAD_DIR}")
        print(f"   Current working dir: {os.getcwd()}")
        
        if os.path.isabs(candidate.resume_file_path):
            file_path = candidate.resume_file_path
        else:
            # Try multiple possible locations
            filename = os.path.basename(candidate.resume_file_path)
            possible_paths = [
                candidate.resume_file_path,  # Try exact path first
                os.path.join(settings.UPLOAD_DIR, filename),
                os.path.join("/data", filename),
                os.path.join("/data/uploads", filename),
                os.path.join("/app/uploads", filename),
                os.path.join("/app/backend/uploads", filename),
                os.path.join(os.getcwd(), "uploads", filename)
            ]
            
            file_path = None
            for path in possible_paths:
                print(f"   Checking: {path} - Exists: {os.path.exists(path) if path else False}")
                if path and os.path.exists(path):
                    file_path = path
                    print(f"   ✅ Found at: {file_path}")
                    break
            
            if not file_path:
                # List what's actually in the upload directory
                try:
                    if os.path.exists(settings.UPLOAD_DIR):
                        files = os.listdir(settings.UPLOAD_DIR)
                        print(f"   Files in {settings.UPLOAD_DIR}: {files[:10]}")
                except:
                    pass
                raise HTTPException(status_code=404, detail=f"Resume file not found. Database path: {candidate.resume_file_path}. Upload dir: {settings.UPLOAD_DIR}. File doesn't exist on server - upload it after deployment.")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Resume file not found at path: {file_path}")
        
        file_ext = os.path.splitext(candidate.resume_file_path)[1].lower()
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Convert Word to PDF for viewing, or return PDF directly
        if file_ext == '.pdf':
            return Response(
                content=file_content,
                media_type='application/pdf',
                headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume.pdf"'}
            )
        elif file_ext in ['.doc', '.docx']:
            # Try to convert Word to PDF for inline viewing
            try:
                import subprocess
                import tempfile
                
                # Create temp PDF file
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                    temp_pdf_path = temp_pdf.name
                
                # Try LibreOffice conversion (if available)
                try:
                    subprocess.run(
                        ['soffice', '--headless', '--convert-to', 'pdf', '--outdir', 
                         os.path.dirname(temp_pdf_path), candidate.resume_file_path],
                        check=True, timeout=30, capture_output=True
                    )
                    converted_pdf = os.path.join(os.path.dirname(temp_pdf_path), 
                                                os.path.splitext(os.path.basename(candidate.resume_file_path))[0] + '.pdf')
                    
                    if os.path.exists(converted_pdf):
                        with open(converted_pdf, 'rb') as f:
                            pdf_content = f.read()
                        os.unlink(converted_pdf)
                        os.unlink(temp_pdf_path)
                        return Response(
                            content=pdf_content,
                            media_type='application/pdf',
                            headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume.pdf"'}
                        )
                except:
                    pass
                
                os.unlink(temp_pdf_path)
            except:
                pass
            
            # Fallback: download Word file
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if file_ext == '.docx' else 'application/msword'
            return Response(
                content=file_content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{candidate.name}_resume{file_ext}"'}
            )
        else:
            # Other file types
            return Response(
                content=file_content,
                media_type='application/octet-stream',
                headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume{file_ext}"'}
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Resume file error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load resume: {str(e)}")

@router.get("/{candidate_id}/ai-analysis")
def get_ai_analysis(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get AI-powered resume analysis with structured data"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get job description
    job_data = None
    if candidate.job_id:
        from app.models import JobDescription
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            job_data = {
                'title': job.title,
                'description': job.description or '',
                'requirements': job.requirements or '',
                'skills': job.skills or []
            }
    
    if not job_data:
        job_data = {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': []
        }
    
    # Prepare candidate data
    candidate_data = {
        'name': candidate.name,
        'email': candidate.email,
        'phone': candidate.phone,
        'skills': candidate.skills or [],
        'experience_text': '',
        'projects': [],
        'full_text': candidate.resume_text or ''
    }
    
    # Get AI analysis
    analysis = analyze_resume_with_ai(candidate_data, job_data)
    
    return analysis

@router.get("/{candidate_id}/resume-summary")
def get_resume_summary(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    job_title = candidate.job.title if candidate.job else ""
    job_skills = candidate.job.skills if candidate.job else []
    job_experience_required = candidate.job.experience_required if candidate.job else ""
    industry = candidate.job.department if candidate.job else ""
    candidate_roles = [
        entry.get("title") for entry in (candidate.work_experience or [])
        if (entry or {}).get("title")
    ] or ([candidate.current_role] if candidate.current_role else [])
    summary = generate_summary(
        required_skills=job_skills or [],
        preferred_skills=[],
        required_experience=job_experience_required,
        role_title=job_title,
        industry=industry,
        candidate_skills=candidate.skills or [],
        candidate_experience=candidate.experience_years or 0.0,
        candidate_industries=[],
        candidate_roles=candidate_roles,
    )

    return {"summary": summary}

@router.get("/pipeline/stages")
def get_pipeline_stages(
    client: Optional[str] = None,
    job_id: Optional[UUID] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates grouped by stage for Kanban board"""
    from app.models import JobDescription, UserRole
    completed_stage_key = "COMPLETED"
    normalize_legacy_candidate_stages(db)
    sync_rescheduled_candidate_stages_from_slots(db)
    query = db.query(Candidate)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(Candidate.agency_id == agency_id)
    else:
        query = _apply_candidate_list_scope(query, current_user)
    query = _apply_client_filter(query, client)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)

    candidates = query.all()
    stages = {stage.value: [] for stage in CandidateStage}
    stages.setdefault(completed_stage_key, [])
    candidate_ids = [candidate.id for candidate in candidates]
    today = _get_india_today()
    interview_today_candidate_ids, interview_scheduled_candidate_ids = _get_interview_slot_candidate_ids_by_timing(
        db,
        candidate_ids,
        today,
    )
    completed_candidate_ids, selected_candidate_ids, rejected_candidate_ids = _get_interview_candidate_ids_by_status(
        db,
        candidate_ids,
    )

    for candidate in candidates:
        display_stage = None
        display_stage_key = None

        # Keep a candidate in a single board column while preferring slot-booking
        # timing and falling back to real interview records when slots are absent.
        if candidate.id in interview_today_candidate_ids:
            display_stage = CandidateStage.INTERVIEWED
            display_stage_key = display_stage.value
        elif candidate.id in interview_scheduled_candidate_ids:
            display_stage = CandidateStage.INTERVIEW_SCHEDULED
            display_stage_key = display_stage.value
        elif candidate.stage == CandidateStage.INTERVIEW_RESCHEDULED:
            display_stage = CandidateStage.INTERVIEW_RESCHEDULED
            display_stage_key = display_stage.value
        elif candidate.id in selected_candidate_ids:
            display_stage = CandidateStage.SELECTED
            display_stage_key = display_stage.value
        elif candidate.id in rejected_candidate_ids:
            display_stage = CandidateStage.REJECTED
            display_stage_key = display_stage.value
        elif candidate.id in completed_candidate_ids:
            display_stage_key = completed_stage_key
        elif candidate.stage == CandidateStage.APPLIED:
            display_stage = CandidateStage.APPLIED
            display_stage_key = display_stage.value
        elif candidate.stage == CandidateStage.REVIEW:
            display_stage = CandidateStage.REVIEW
            display_stage_key = display_stage.value
        elif candidate.stage == CandidateStage.SHORTLISTED:
            display_stage = CandidateStage.SHORTLISTED
            display_stage_key = display_stage.value
        elif candidate.stage == CandidateStage.RESUME_REJECTED:
            display_stage = CandidateStage.RESUME_REJECTED
            display_stage_key = display_stage.value
        elif candidate.stage == CandidateStage.NO_SHOW:
            display_stage = CandidateStage.NO_SHOW
            display_stage_key = display_stage.value

        if not display_stage_key:
            continue

        stages[display_stage_key].append(
            {
                "id": candidate.id,
                "name": candidate.name,
                "current_role": candidate.current_role,
                "current_company": candidate.current_company,
                "resume_score": candidate.resume_score,
                "job_title": candidate.job.title if candidate.job else None,
                "company_name": candidate.job.company_name if candidate.job else None,
                "stage": display_stage_key,
                "stage_entered_at": candidate.stage_entered_at.isoformat() if candidate.stage_entered_at else None,
                "applied_at": candidate.applied_at.isoformat() if candidate.applied_at else None
            }
        )
    return stages

@router.post("/bulk-assign")
def bulk_assign_candidates(
    assignment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk assign candidates to a user (Admin only)"""
    from app.models import UserRole, ReviewStatus
    
    # Admin only
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate_ids = assignment_data.get('candidate_ids', [])
    user_id = assignment_data.get('user_id')
    
    if not candidate_ids or not user_id:
        raise HTTPException(status_code=400, detail="Missing candidate_ids or user_id")
    
    # Verify user exists
    assigned_user = db.query(User).filter(User.id == user_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update candidates and collect names
    updated_count = 0
    candidate_names = []
    for candidate_id in candidate_ids:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if candidate:
            candidate.assigned_to_user_id = user_id
            candidate.review_status = ReviewStatus.PENDING
            candidate_names.append(candidate.name)
            updated_count += 1
    
    db.commit()
    
    return {"message": f"Successfully assigned {updated_count} candidates to {assigned_user.full_name}", "updated_count": updated_count}

@router.post("/send-email")
def send_email(
    email_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Send email to candidate with interview details link and slot booking button"""
    from app.config import settings
    from app.mailer import is_email_configured, send_html_email
    from urllib.parse import urlencode
    from app.models import EmailCommunication
    
    try:
        candidate_id = email_data.get('candidate_id')
        subject = email_data.get('subject')
        message = email_data.get('message')
        
        if not all([candidate_id, subject, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: candidate_id, subject, message")
        
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Get job details
        job = None
        if candidate.job_id:
            from app.models import JobDescription
            job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        
        # Check if email service is configured
        if not is_email_configured():
            error_msg = (
                "Email service is not configured. Set RESEND_API_KEY "
                "(or SENDGRID_API_KEY for fallback), FROM_EMAIL, and FROM_NAME "
                "in Railway environment variables."
            )
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Build interview details URL with query parameters (including job description and resume text)
        params = {
            'candidateId': candidate.id,
            'name': candidate.name,
            'email': candidate.email,
        }
        if job:
            params['jobId'] = job.id
            params['jobTitle'] = job.title
        
        interview_url = f"{settings.FRONTEND_URL}/interview?{urlencode(params)}"
        
        # Build HTML email with slot booking button
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <p>{message.replace(chr(10), '<br>')}</p>
                
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{settings.SLOT_BOOKING_URL}" 
                       style="display: inline-block; padding: 15px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Book Your Slot
                    </a>
                </div>
                
                <p style="font-size: 12px; color: #666; margin-top: 30px;">
                    View your interview details: <a href="{interview_url}">{interview_url}</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email via configured provider
        provider_message_id = send_html_email(
            to_email=candidate.email,
            subject=subject,
            html_content=html_body
        )
        
        # Determine email type based on subject
        email_type = "Slot Selection Email"
        if "reject" in subject.lower() or "decline" in subject.lower():
            email_type = "Rejection Email"
        elif "reschedule" in subject.lower():
            email_type = "Interview Rescheduled"
        
        # Create EmailCommunication record
        email_comm = EmailCommunication(
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            candidate_email=candidate.email,
            email_type=email_type,
            status="sent",
            sent_at=datetime.utcnow(),
            provider_message_id=provider_message_id
        )
        db.add(email_comm)

        if email_type == "Slot Selection Email":
            candidate.stage = CandidateStage.SHORTLISTED
            candidate.stage_updated_at = datetime.utcnow()
            candidate.stage_entered_at = datetime.utcnow()
        elif email_type == "Rejection Email":
            candidate.stage = CandidateStage.REJECTED
            candidate.stage_updated_at = datetime.utcnow()
            candidate.stage_entered_at = datetime.utcnow()

        db.commit()
        
        print(f" Email sent to {candidate.email} - Message-ID: {provider_message_id}")
        print(f"  Email type: {email_type}")
        print(f"   Interview URL: {interview_url}")
        print(f"   Slot Booking: {settings.SLOT_BOOKING_URL}")
        
        return {
            "success": True,
            "message": f"Email sent to {candidate.email}",
            "interview_url": interview_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")









@router.patch("/{candidate_id}/notes")
def update_candidate_notes(
    candidate_id: UUID,
    notes_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update internal notes for a candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate.internal_notes = notes_data.get('notes', '')
    db.commit()
    db.refresh(candidate)
    
    return {"message": "Notes updated successfully", "notes": candidate.internal_notes}


@router.post("/{candidate_id}/assign")
def assign_candidate_to_user(
    candidate_id: UUID,
    assign_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign candidate to a user for review (Admin only)"""
    from app.models import ReviewStatus
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign resumes")
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    assigned_to_user_id = assign_data.get('assigned_to_user_id')
    if not assigned_to_user_id:
        raise HTTPException(status_code=400, detail="assigned_to_user_id is required")
    
    # Verify user exists
    assigned_user = db.query(User).filter(User.id == assigned_to_user_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")
    
    candidate.assigned_to_user_id = assigned_to_user_id
    candidate.review_status = ReviewStatus.PENDING
    candidate.reviewed_at = None
    candidate.reviewed_by_user_id = None
    
    db.commit()
    db.refresh(candidate)
    
    return {"message": f"Candidate assigned to {assigned_user.full_name}", "candidate_id": candidate.id}

@router.post("/{candidate_id}/review")
def review_candidate(
    candidate_id: UUID,
    review_data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Review candidate - send interview invitation or reject"""
    from app.models import ReviewStatus
    from datetime import datetime
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check if user is assigned to this candidate
    if candidate.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to review this candidate")
    
    action = review_data.get('action')  # "interview" or "reject"
    
    if action == "interview":
        candidate.review_status = ReviewStatus.INTERVIEW_INVITED
        candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
        message = "Interview invitation sent"
    elif action == "reject":
        candidate.review_status = ReviewStatus.REJECTED
        candidate.stage = CandidateStage.REJECTED
        message = "Candidate rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'interview' or 'reject'")
    
    candidate.reviewed_at = datetime.utcnow()
    candidate.reviewed_by_user_id = current_user.id
    
    db.commit()
    db.refresh(candidate)
    enqueue_stage_notification(background_tasks, db, candidate, candidate.stage.value, user_id=current_user.id)
    
    return {"message": message, "candidate_id": candidate.id, "review_status": candidate.review_status.value}

@router.get("/assigned/me")
def get_my_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates assigned to current user"""
    from app.models import ReviewStatus
    
    candidates = db.query(Candidate).filter(
        Candidate.assigned_to_user_id == current_user.id
    ).all()
    
    result = []
    for c in candidates:
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "resume_score": c.resume_score,
            "job_title": c.job.title if c.job else None,
            "review_status": c.review_status.value if c.review_status else "unassigned",
            "assigned_at": c.created_at.isoformat() if c.created_at else None,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None
        })
    
    return result


@router.post("/{candidate_id}/assign-legacy")
def assign_candidate(
    candidate_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign candidate to a user for review (Admin only)"""
    from app.models import ReviewStatus

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    candidate.assigned_to_user_id = user_id
    candidate.review_status = ReviewStatus.PENDING
    db.commit()
    
    return {"message": f"Candidate assigned to {user.full_name}", "assigned_to": user.full_name}

@router.get("/assigned-to-me")
def get_my_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates assigned to current user"""
    candidates = db.query(Candidate).filter(
        Candidate.assigned_to_user_id == current_user.id
    ).all()
    
    return [{
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "resume_score": c.resume_score,
        "job_title": c.job.title if c.job else None,
        "review_status": c.review_status.value if c.review_status else "UNASSIGNED",
        "assigned_at": c.updated_at
    } for c in candidates]


@router.post("/bulk-assign")
def bulk_assign_candidates(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk assign multiple candidates to a user (Admin only)"""
    from app.models import ReviewStatus

    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate_ids = data.get('candidate_ids', [])
    user_id = data.get('user_id')
    
    if not candidate_ids or not user_id:
        raise HTTPException(status_code=400, detail="candidate_ids and user_id are required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    assigned_count = 0
    for cid in candidate_ids:
        candidate = db.query(Candidate).filter(Candidate.id == cid).first()
        if candidate:
            candidate.assigned_to_user_id = user_id
            candidate.review_status = ReviewStatus.PENDING
            assigned_count += 1
    
    db.commit()
    
    return {
        "message": f"{assigned_count} candidates assigned to {user.full_name}",
        "assigned_count": assigned_count,
        "assigned_to": user.full_name
    }



