from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload, load_only
from sqlalchemy import or_, text
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from threading import Lock
from time import monotonic, perf_counter
import base64
import binascii
import random
import psycopg2
import requests
from app.database import get_db
from app.config import settings
from app.models import Interview, Candidate, CandidateStage, User
from app.notification_service import queue_notification_for_stage, send_email_task
from app.schemas import InterviewCreate, InterviewUpdate, InterviewResponse, InterviewResultsUpdate
from app.auth import get_current_active_user
from app.auth import verify_token


router = APIRouter(prefix="/interviews", tags=["Interviews"])
recording_router = APIRouter(prefix="/recording", tags=["Interviews"])

VIDEO_CHUNK_SIZE = 1024 * 1024
PROXY_STREAM_CHUNK_SIZE = 64 * 1024
FORWARDED_STREAM_RESPONSE_HEADERS = (
    "Accept-Ranges",
    "Content-Length",
    "Content-Range",
    "Content-Type",
)
LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS = 300
_legacy_stage_normalization_lock = Lock()
_legacy_stage_last_checked_at = 0.0
_table_columns_cache: dict[str, set[str]] = {}
_table_columns_cache_lock = Lock()

# Sample AI summaries for demo
SAMPLE_SUMMARIES = [
    "The candidate demonstrated strong technical skills and problem-solving abilities. They showed excellent communication and would be a good cultural fit for the team.",
    "Solid technical background with room for growth. The candidate was enthusiastic about the role and showed good understanding of the domain.",
    "Experienced professional with strong leadership qualities. Would be an asset to the team with their innovative approach to problem-solving.",
    "The candidate showed good potential but may need additional training in some areas. Overall positive impression with strong soft skills."
]

SAMPLE_TRANSCRIPTS = """
[00:00] Interviewer: Thank you for joining us today. Can you start by telling us about yourself?

[00:15] Candidate: Of course! I have over 5 years of experience in software development, specializing in full-stack applications. I'm passionate about building scalable systems and have led several successful projects.

[02:30] Interviewer: Can you walk us through a challenging project you've worked on?

[02:45] Candidate: Certainly. I led the development of a real-time analytics platform that processed millions of events daily. We faced challenges with data consistency and latency, which we solved using event sourcing and CQRS patterns.

[08:15] Interviewer: How do you approach problem-solving in your work?

[08:30] Candidate: I believe in breaking down complex problems into smaller, manageable pieces. I start by understanding the requirements, then research potential solutions, and finally implement with thorough testing.

[15:00] Interviewer: Where do you see yourself in the next few years?

[15:15] Candidate: I'm looking to grow into a technical leadership role where I can mentor others while continuing to contribute to architecture decisions.

[20:00] Interviewer: Do you have any questions for us?

[20:10] Candidate: Yes, I'd love to learn more about the team structure and the technologies you're currently using.
"""


def normalize_legacy_candidate_stages(db: Session) -> None:
    """Self-heal stale candidate enum values before interview queries touch relationships."""
    global _legacy_stage_last_checked_at
    now = monotonic()
    if (now - _legacy_stage_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
        return

    with _legacy_stage_normalization_lock:
        now = monotonic()
        if (now - _legacy_stage_last_checked_at) < LEGACY_STAGE_NORMALIZATION_INTERVAL_SECONDS:
            return
        _legacy_stage_last_checked_at = now

    result = db.execute(text(
        "UPDATE candidates "
        "SET stage = 'INTERVIEWED' "
        "WHERE stage::text = 'INTERVIEW_REVIEW'"
    ))
    if result.rowcount:
        print(f"Normalized legacy candidate stages before interview query: rows_updated={result.rowcount}")
        db.commit()


def _perf_log(endpoint: str, total_start: float, **fields) -> None:
    parts = [f"{key}={value}" for key, value in fields.items()]
    parts.append(f"total={perf_counter() - total_start:.4f}s")
    print(f"[PERF] {endpoint} " + " ".join(parts))


def _derive_candidate_stage_from_interview(interview: Interview) -> Optional[CandidateStage]:
    """Map the latest interview status to the candidate pipeline stage."""
    interview_status = (interview.status or "").strip().lower()
    interview_date = interview.scheduled_at.date() if interview.scheduled_at else None
    today = datetime.now().date()

    if interview_status == "completed":
        interview_score = interview.interview_score if interview.interview_score is not None else 0
        return CandidateStage.SELECTED if interview_score >= 6 else CandidateStage.REJECTED

    status_to_stage = {
        "ongoing": CandidateStage.INTERVIEWED,
        "no_show": CandidateStage.NO_SHOW,
    }
    if interview_status == "scheduled":
        if interview_date == today:
            return CandidateStage.INTERVIEWED
        return CandidateStage.INTERVIEW_SCHEDULED

    if interview_status == "rescheduled":
        if interview_date == today:
            return CandidateStage.INTERVIEWED
        return CandidateStage.INTERVIEW_RESCHEDULED

    return status_to_stage.get(interview_status)


def _sync_candidate_stage_from_interview(candidate: Candidate, interview: Interview) -> None:
    target_stage = _derive_candidate_stage_from_interview(interview)
    if not target_stage:
        return

    candidate.stage = target_stage
    now = datetime.utcnow()
    candidate.stage_updated_at = now
    candidate.stage_entered_at = now


def _resolve_agency_admin_for_candidate(db: Session, candidate: Optional[Candidate]) -> tuple[Optional[User], Optional[UUID]]:
    from app.models import JobDescription, UserRole

    if not candidate:
        return None, None

    agency_id = candidate.agency_id
    if not agency_id and candidate.job_id:
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        agency_id = job.agency_id if job else None
    if not agency_id:
        return None, None

    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.agency_id == agency_id
    ).first()
    return admin, agency_id


def _ensure_interview_scheduling_credits(db: Session, candidate: Candidate) -> None:
    admin, _agency_id = _resolve_agency_admin_for_candidate(db, candidate)
    if not admin or (admin.wallet_balance or 0) <= 0:
        raise HTTPException(status_code=400, detail="Insufficient credits to schedule interviews")


def _deduct_interview_completion_credit(db: Session, interview: Interview, candidate: Optional[Candidate]) -> Optional[int]:
    from app.models import WalletTransaction, TransactionType

    admin, agency_id = _resolve_agency_admin_for_candidate(db, candidate)
    if not admin:
        return None

    transaction_description = f"Interview completed - Interview ID {interview.id}"
    existing_transaction = db.query(WalletTransaction).filter(
        WalletTransaction.user_id == admin.id,
        WalletTransaction.description == transaction_description,
    ).first()
    if existing_transaction:
        return admin.wallet_balance

    admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
    db.add(WalletTransaction(
        user_id=admin.id,
        agency_id=agency_id,
        amount=1,
        transaction_type=TransactionType.DEBIT,
        description=transaction_description,
        balance_after=admin.wallet_balance
    ))
    return admin.wallet_balance


def _is_interview_completion_billable(interview: Interview, has_recording: bool = False) -> bool:
    normalized_status = (interview.status or "").strip().lower()
    return bool(
        normalized_status == "completed"
        or has_recording
        or interview.transcript
        or interview.ai_summary
        or interview.interview_score is not None
    )


def _charge_completed_interview_if_needed(db: Session, interview: Interview, has_recording: bool = False) -> Optional[int]:
    if not _is_interview_completion_billable(interview, has_recording=has_recording):
        return None

    candidate = interview.candidate
    if not candidate:
        candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        return None

    return _deduct_interview_completion_credit(db, interview, candidate)


def _charge_completed_interviews_in_batch(
    db: Session,
    interviews: List[Interview],
    recording_availability: dict[str, dict],
) -> bool:
    from app.models import JobDescription, UserRole, WalletTransaction, TransactionType

    billable_pairs: list[tuple[Interview, Candidate]] = []
    job_ids_missing_agency = set()
    for interview in interviews:
        has_recording = recording_availability.get(str(interview.id), {}).get("has_recording", False)
        if not _is_interview_completion_billable(interview, has_recording=has_recording):
            continue

        candidate = interview.candidate
        if not candidate:
            candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
        if not candidate:
            continue

        billable_pairs.append((interview, candidate))
        if not candidate.agency_id and candidate.job_id:
            job_ids_missing_agency.add(candidate.job_id)

    if not billable_pairs:
        return False

    job_agency_by_id = {}
    if job_ids_missing_agency:
        job_agency_by_id = {
            job_id: agency_id
            for job_id, agency_id in db.query(JobDescription.id, JobDescription.agency_id)
            .filter(JobDescription.id.in_(job_ids_missing_agency))
            .all()
        }

    agency_ids = {
        candidate.agency_id or job_agency_by_id.get(candidate.job_id)
        for _, candidate in billable_pairs
        if candidate.agency_id or job_agency_by_id.get(candidate.job_id)
    }
    if not agency_ids:
        return False

    admin_by_agency = {}
    for admin in (
        db.query(User)
        .filter(User.role == UserRole.ADMIN, User.agency_id.in_(agency_ids))
        .order_by(User.id.asc())
        .all()
    ):
        admin_by_agency.setdefault(admin.agency_id, admin)

    if not admin_by_agency:
        return False

    admin_ids = [admin.id for admin in admin_by_agency.values()]
    descriptions = [f"Interview completed - Interview ID {interview.id}" for interview, _ in billable_pairs]
    existing_transactions = {
        (user_id, description)
        for user_id, description in (
            db.query(WalletTransaction.user_id, WalletTransaction.description)
            .filter(
                WalletTransaction.user_id.in_(admin_ids),
                WalletTransaction.description.in_(descriptions),
            )
            .all()
        )
    }

    credits_checked = False
    for interview, candidate in billable_pairs:
        agency_id = candidate.agency_id or job_agency_by_id.get(candidate.job_id)
        admin = admin_by_agency.get(agency_id)
        if not admin:
            continue

        transaction_description = f"Interview completed - Interview ID {interview.id}"
        transaction_key = (admin.id, transaction_description)
        if transaction_key in existing_transactions:
            continue

        admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
        db.add(WalletTransaction(
            user_id=admin.id,
            agency_id=agency_id,
            amount=1,
            transaction_type=TransactionType.DEBIT,
            description=transaction_description,
            balance_after=admin.wallet_balance
        ))
        existing_transactions.add(transaction_key)
        credits_checked = True

    return credits_checked


def _apply_interview_scope(query, current_user):
    from app.models import JobDescription, UserRole

    if current_user.role == UserRole.SUPER_ADMIN:
        return query

    if current_user.role == UserRole.ADMIN:
        if current_user.agency_id:
            return query.join(Candidate).outerjoin(JobDescription, Candidate.job_id == JobDescription.id).filter(
                or_(
                    Candidate.agency_id == current_user.agency_id,
                    JobDescription.agency_id == current_user.agency_id,
                )
            )
        return query

    return query.join(Candidate).filter(Candidate.assigned_to_user_id == current_user.id)


def _resolve_video_request_user(db: Session, access_token: Optional[str], current_user: Optional[User]) -> User:
    if current_user:
        return current_user

    if not access_token:
        raise HTTPException(status_code=401, detail="Authentication required to access interview recordings")

    token_data = verify_token(access_token)
    if token_data is None:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user = db.query(User).filter(User.email == token_data.email).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication failed")

    return user


def _get_scoped_interview_for_video(db: Session, session_id: str, current_user: User) -> Optional[Interview]:
    normalized_session_id = str(session_id or "").strip()
    if not normalized_session_id:
        return None

    try:
        parsed_uuid = UUID(normalized_session_id)
    except ValueError:
        query = db.query(Interview).filter(Interview.async_token == normalized_session_id)
    else:
        query = db.query(Interview).filter(
            or_(
                Interview.id == parsed_uuid,
                Interview.async_token == normalized_session_id,
            )
        )

    query = _apply_interview_scope(query, current_user)
    return query.first()


def _resolve_scoped_interview_from_session_row(db: Session, session_row: dict, current_user: User) -> Optional[Interview]:
    for possible_key in (
        session_row.get("interview_id"),
        session_row.get("async_token"),
        session_row.get("token"),
        session_row.get("session_id"),
        session_row.get("id"),
    ):
        if not possible_key:
            continue
        try:
            query = db.query(Interview).filter(Interview.id == UUID(str(possible_key)))
        except ValueError:
            query = db.query(Interview).filter(Interview.async_token == str(possible_key))
        interview = _apply_interview_scope(query, current_user).first()
        if interview:
            return interview
    return None


def _get_recording_service_target() -> tuple[str, str]:
    cleaned_base_url = str(settings.RECORDING_BASE_URL or "").strip().rstrip("/")
    return cleaned_base_url, "/api/recording"


def _get_recording_service_token() -> str:
    return str(settings.RECORDING_SERVICE_TOKEN or settings.INTERNAL_SERVICE_TOKEN or "").strip()


def _mask_debug_value(value: Optional[str], *, prefix: int = 6, suffix: int = 4) -> str:
    normalized_value = str(value or "").strip()
    if not normalized_value:
        return ""
    if len(normalized_value) <= (prefix + suffix):
        return normalized_value
    return f"{normalized_value[:prefix]}...{normalized_value[-suffix:]}"


def _normalize_recording_session_token(session_token: str) -> str:
    normalized_token = str(session_token or "").strip()
    lowered_token = normalized_token.lower()
    for extension in (".mp4", ".webm"):
        if lowered_token.endswith(extension):
            return normalized_token[: -len(extension)]
    return normalized_token


def _build_internal_recording_url(base_url: str, path_prefix: str) -> str:
    return f"{base_url}{path_prefix}"


def _request_upstream_recording(
    method: str,
    upstream_url: str,
    upstream_headers: dict[str, str],
    session_token: str,
) -> requests.Response:
    return requests.request(
        method,
        upstream_url,
        headers=upstream_headers,
        params={"session_token": session_token},
        stream=True,
        timeout=(5, 300),
    )


def _collect_upstream_stream_headers(upstream_response: requests.Response) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header_name in FORWARDED_STREAM_RESPONSE_HEADERS:
        header_value = upstream_response.headers.get(header_name)
        if header_value:
            headers[header_name] = header_value
    return headers


def _stream_upstream_response(upstream_response: requests.Response):
    try:
        for chunk in upstream_response.iter_content(chunk_size=PROXY_STREAM_CHUNK_SIZE):
            if chunk:
                yield chunk
    finally:
        upstream_response.close()


def _proxy_recording_stream(session_token: str, request_method: str, range_header: Optional[str]) -> Response:
    session_token = _normalize_recording_session_token(session_token)
    service_token = _get_recording_service_token()
    print("Auth token present:", bool(service_token))
    upstream_headers = {}
    if service_token:
        upstream_headers["Authorization"] = f"Bearer {service_token}"
    if range_header:
        upstream_headers["Range"] = range_header
    print("Proxy auth token:", _mask_debug_value(service_token))
    print("Proxy session_token:", session_token)
    print("Proxy request headers:", upstream_headers)

    upstream_response = None
    last_request_exception = None
    selected_upstream_url = None
    selected_request_method = request_method.upper()
    base_url, path_prefix = _get_recording_service_target()
    upstream_url = _build_internal_recording_url(base_url, path_prefix)
    try:
        _log_recording_debug(
            "proxy_recording_stream.attempt",
            session_token=session_token,
            method=selected_request_method,
            upstream_url=upstream_url,
            has_internal_auth=bool(service_token),
            has_range=bool(range_header),
        )
        upstream_response = _request_upstream_recording(
            selected_request_method,
            upstream_url,
            upstream_headers,
            session_token,
        )
        selected_upstream_url = upstream_url
        _log_recording_debug(
            "proxy_recording_stream.response",
            session_token=session_token,
            method=selected_request_method,
            upstream_url=upstream_url,
            status_code=upstream_response.status_code,
            content_type=upstream_response.headers.get("Content-Type"),
            content_length=upstream_response.headers.get("Content-Length"),
            content_range=upstream_response.headers.get("Content-Range"),
        )
        if selected_request_method == "HEAD" and upstream_response.status_code in (404, 405):
            upstream_response.close()
            fallback_headers = dict(upstream_headers)
            fallback_headers.setdefault("Range", "bytes=0-0")
            _log_recording_debug(
                "proxy_recording_stream.head_fallback",
                session_token=session_token,
                upstream_url=upstream_url,
                fallback_method="GET",
                fallback_range=fallback_headers.get("Range"),
            )
            upstream_response = _request_upstream_recording(
                "GET",
                upstream_url,
                fallback_headers,
                session_token,
            )
            _log_recording_debug(
                "proxy_recording_stream.response",
                session_token=session_token,
                method="GET",
                upstream_url=upstream_url,
                status_code=upstream_response.status_code,
                content_type=upstream_response.headers.get("Content-Type"),
                content_length=upstream_response.headers.get("Content-Length"),
                content_range=upstream_response.headers.get("Content-Range"),
            )
        if upstream_response.status_code not in (200, 206):
            try:
                print("Upstream error body:", upstream_response.text[:1000])
            except Exception:
                print("Upstream error body: <unavailable>")
    except requests.RequestException as exc:
        last_request_exception = exc
        _log_recording_debug(
            "proxy_recording_stream.error",
            session_token=session_token,
            method=selected_request_method,
            upstream_url=upstream_url,
            error=str(exc),
        )

    if upstream_response is None:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to reach recording service: {last_request_exception}",
        ) from last_request_exception

    response_headers = _collect_upstream_stream_headers(upstream_response)
    status_code = upstream_response.status_code
    media_type = upstream_response.headers.get("Content-Type")
    _log_recording_debug(
        "proxy_recording_stream.forward",
        session_token=session_token,
        method=selected_request_method,
        upstream_url=selected_upstream_url,
        status_code=status_code,
        media_type=media_type,
    )

    if selected_request_method == "HEAD":
        upstream_response.close()
        return Response(status_code=status_code, headers=response_headers)

    return StreamingResponse(
        _stream_upstream_response(upstream_response),
        status_code=status_code,
        headers=response_headers,
        media_type=media_type,
    )


def _detect_video_media_type(video_bytes: bytes, fallback: str = "video/webm") -> str:
    if len(video_bytes) >= 12 and video_bytes[4:8] == b"ftyp":
        return "video/mp4"
    if video_bytes.startswith(b"\x1A\x45\xDF\xA3"):
        return "video/webm"
    if video_bytes.startswith(b"OggS"):
        return "video/ogg"
    return fallback


def _describe_recording_payload(recording_data) -> str:
    if recording_data is None:
        return "none"
    if isinstance(recording_data, memoryview):
        return f"memoryview(len={len(recording_data)})"
    if isinstance(recording_data, (bytes, bytearray)):
        return f"{type(recording_data).__name__}(len={len(recording_data)})"
    if isinstance(recording_data, str):
        preview = recording_data[:32].replace("\n", "\\n")
        return f"str(len={len(recording_data)}, preview={preview!r})"
    return type(recording_data).__name__


def _coerce_recording_bytes(recording_data) -> bytes:
    if recording_data is None:
        return b""

    if isinstance(recording_data, memoryview):
        return recording_data.tobytes()

    if isinstance(recording_data, (bytes, bytearray)):
        return bytes(recording_data)

    if isinstance(recording_data, str):
        normalized = recording_data.strip()
        if not normalized:
            return b""

        if normalized.startswith("data:") and "," in normalized:
            normalized = normalized.split(",", 1)[1]

        if normalized.startswith("\\x"):
            try:
                return bytes.fromhex(normalized[2:])
            except ValueError:
                pass

        if normalized.startswith("0x"):
            try:
                return bytes.fromhex(normalized[2:])
            except ValueError:
                pass

        compact = "".join(normalized.split())
        padding = (-len(compact)) % 4
        try:
            return base64.b64decode(compact + ("=" * padding), validate=True)
        except (binascii.Error, ValueError):
            raise HTTPException(status_code=500, detail="Interview recording uses an unsupported binary format")

    raise HTTPException(status_code=500, detail="Interview recording uses an unsupported binary format")


def _log_recording_debug(context: str, **fields) -> None:
    ordered_fields = ", ".join(f"{key}={value}" for key, value in fields.items())
    print(f"[recording-debug] {context}: {ordered_fields}")


def _extract_configured_media_type(row_dict: dict) -> Optional[str]:
    for candidate_column in ("mime_type", "content_type", "recording_mime_type", "video_format"):
        if row_dict.get(candidate_column):
            return row_dict.get(candidate_column)
    return None


def _normalize_recording_media_type(configured_media_type: Optional[str], video_bytes: bytes) -> str:
    detected_media_type = _detect_video_media_type(video_bytes, fallback="video/webm")
    if not configured_media_type:
        return detected_media_type

    normalized = configured_media_type.strip().lower()
    shorthand_map = {
        "mp4": "video/mp4",
        "webm": "video/webm",
        "ogg": "video/ogg",
    }
    if normalized in shorthand_map:
        return shorthand_map[normalized]

    # This endpoint always serves interview recordings for the video player.
    # If the DB stores an audio-only MIME label for a WebM/MP4 container, prefer
    # the detected video MIME so browsers render the picture track when present.
    if normalized.startswith("audio/"):
        return detected_media_type

    return normalized


def _iter_video_chunks(video_bytes: bytes, start: int = 0, end: Optional[int] = None):
    final_end = len(video_bytes) - 1 if end is None else end
    offset = start
    while offset <= final_end:
        chunk_end = min(offset + VIDEO_CHUNK_SIZE, final_end + 1)
        yield video_bytes[offset:chunk_end]
        offset = chunk_end


def _build_video_stream_response(video_bytes: bytes, media_type: str, range_header: Optional[str]) -> Response:
    total_size = len(video_bytes)
    common_headers = {
        "Accept-Ranges": "bytes",
        "Content-Disposition": 'inline; filename="interview-recording"',
        "Cache-Control": "private, max-age=3600",
    }

    if total_size == 0:
        return Response(status_code=204, headers=common_headers)

    if not range_header:
        headers = {
            **common_headers,
            "Content-Length": str(total_size),
        }
        return StreamingResponse(
            _iter_video_chunks(video_bytes),
            media_type=media_type,
            headers=headers,
        )

    try:
        units, byte_range = range_header.strip().split("=", 1)
        if units != "bytes":
            raise ValueError("Unsupported range unit")

        start_str, end_str = byte_range.split("-", 1)
        if start_str == "":
            suffix_length = int(end_str)
            start = max(total_size - suffix_length, 0)
            end = total_size - 1
        else:
            start = int(start_str)
            end = int(end_str) if end_str else total_size - 1

        if start < 0 or end < start or start >= total_size:
            raise ValueError("Invalid byte range")

        end = min(end, total_size - 1)
    except (ValueError, IndexError):
        return Response(
            status_code=416,
            headers={**common_headers, "Content-Range": f"bytes */{total_size}"},
        )

    content_length = (end - start) + 1
    headers = {
        **common_headers,
        "Content-Length": str(content_length),
        "Content-Range": f"bytes {start}-{end}/{total_size}",
    }
    return StreamingResponse(
        _iter_video_chunks(video_bytes, start=start, end=end),
        media_type=media_type,
        status_code=206,
        headers=headers,
    )


def _get_table_columns(cursor, table_name: str) -> set[str]:
    with _table_columns_cache_lock:
        cached_columns = _table_columns_cache.get(table_name)
    if cached_columns is not None:
        return cached_columns

    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    columns = {row[0] for row in cursor.fetchall()}
    with _table_columns_cache_lock:
        _table_columns_cache[table_name] = columns
    return columns


def _fetch_interview_recording(cursor, session_keys: List[str]):
    columns = _get_table_columns(cursor, "interview_sessions")
    if "recording_path" not in columns and "recording_data" not in columns:
        raise HTTPException(status_code=500, detail="No interview recording columns found")

    select_fields = []
    if "recording_path" in columns:
        select_fields.append("recording_path")
    if "recording_data" in columns:
        select_fields.append("recording_data")
    mime_column = None
    for candidate_column in ("mime_type", "content_type", "recording_mime_type", "video_format"):
        if candidate_column in columns:
            mime_column = candidate_column
            select_fields.append(candidate_column)
            break

    lookup_columns = []
    for candidate_column in ("id", "session_id", "session_token", "interview_id", "async_token", "token"):
        if candidate_column in columns:
            lookup_columns.append(candidate_column)

    if not lookup_columns:
        raise HTTPException(status_code=500, detail="No usable lookup column found in interview_sessions")

    deduped_keys = [key for key in dict.fromkeys([k for k in session_keys if k])]
    if not deduped_keys:
        return None, None

    where_clauses = []
    params = []
    for column_name in lookup_columns:
        placeholders = ", ".join(["%s"] * len(deduped_keys))
        where_clauses.append(f"{column_name}::text IN ({placeholders})")
        params.extend(deduped_keys)

    query = f"""
        SELECT {", ".join(select_fields)}
        FROM interview_sessions
        WHERE {" OR ".join(where_clauses)}
        LIMIT 1
    """
    cursor.execute(query, params)
    row = cursor.fetchone()
    if not row:
        return None, None

    row_index = 0
    recording_path = None
    recording_data = None
    if "recording_path" in columns:
        recording_path = row[row_index]
        row_index += 1
    if "recording_data" in columns:
        recording_data = row[row_index]
        row_index += 1

    configured_media_type = row[row_index] if mime_column and len(row) > row_index else None
    return {
        "recording_path": recording_path,
        "recording_data": recording_data,
    }, configured_media_type


def _fetch_interview_session_row_by_session_token(cursor, session_token: str):
    columns = _get_table_columns(cursor, "interview_sessions")
    if "recording_path" not in columns and "recording_data" not in columns:
        raise HTTPException(status_code=404, detail="Interview recording not found")

    select_fields = []
    if "recording_path" in columns:
        select_fields.append("recording_path")
    if "recording_data" in columns:
        select_fields.append("recording_data")
    if "session_token" in columns:
        select_fields.append("session_token")
    for candidate_column in ("mime_type", "content_type", "recording_mime_type", "video_format"):
        if candidate_column in columns:
            select_fields.append(candidate_column)
            break

    for candidate_column in ("interview_id", "async_token", "token", "session_id", "id"):
        if candidate_column in columns:
            select_fields.append(candidate_column)

    where_clauses = []
    params = []
    if "session_token" in columns:
        where_clauses.append("session_token = %s")
        params.append(session_token)
    if "recording_path" in columns:
        where_clauses.append("recording_path = %s")
        params.append(session_token)
        where_clauses.append("recording_path = %s")
        params.append(f"{session_token}.mp4")
        where_clauses.append("regexp_replace(recording_path, '\\.[^.]+$', '') = %s")
        params.append(session_token)

    query = f"""
        SELECT {", ".join(select_fields)}
        FROM interview_sessions
        WHERE {" OR ".join(where_clauses)}
        LIMIT 1
    """
    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    if not row:
        _log_recording_debug(
            "stream_candidate_recording.session_lookup_miss",
            session_token=session_token,
            where_clauses=len(where_clauses),
            has_session_token_column="session_token" in columns,
            has_recording_path_column="recording_path" in columns,
        )
        raise HTTPException(status_code=404, detail="Interview recording not found")

    field_names = select_fields
    return dict(zip(field_names, row))


def _fetch_interview_session_row_by_lookup_key(cursor, lookup_key: str):
    columns = _get_table_columns(cursor, "interview_sessions")
    if "recording_path" not in columns and "recording_data" not in columns:
        raise HTTPException(status_code=404, detail="Interview recording not found")

    select_fields = []
    if "recording_path" in columns:
        select_fields.append("recording_path")
    if "recording_data" in columns:
        select_fields.append("recording_data")
    if "session_token" in columns:
        select_fields.append("session_token")
    for candidate_column in ("mime_type", "content_type", "recording_mime_type", "video_format"):
        if candidate_column in columns:
            select_fields.append(candidate_column)
            break

    lookup_columns = [
        column_name
        for column_name in ("id", "session_id", "session_token", "interview_id", "async_token", "token")
        if column_name in columns
    ]
    for candidate_column in ("interview_id", "async_token", "token", "session_id", "id"):
        if candidate_column in columns and candidate_column not in select_fields:
            select_fields.append(candidate_column)

    if not lookup_columns:
        raise HTTPException(status_code=404, detail="Interview recording not found")

    where_clauses = [f"{column_name}::text = %s" for column_name in lookup_columns]
    params = [lookup_key] * len(lookup_columns)

    query = f"""
        SELECT {", ".join(select_fields)}
        FROM interview_sessions
        WHERE {" OR ".join(where_clauses)}
        LIMIT 1
    """
    cursor.execute(query, tuple(params))
    row = cursor.fetchone()
    if not row:
        _log_recording_debug(
            "stream_interview_video.session_lookup_miss",
            lookup_key=lookup_key,
            lookup_columns="|".join(lookup_columns),
        )
        raise HTTPException(status_code=404, detail="Interview session not found")

    return dict(zip(select_fields, row))


def _fetch_recording_availability(interviews: List[Interview]) -> dict[str, dict]:
    if not interviews:
        return {}

    connection = None
    try:
        connection = psycopg2.connect(settings.DATABASE_URL)
        with connection:
            with connection.cursor() as cursor:
                columns = _get_table_columns(cursor, "interview_sessions")
                has_recording_path = "recording_path" in columns
                has_recording_data = "recording_data" in columns
                if not has_recording_path and not has_recording_data:
                    return {}

                lookup_columns = [
                    column_name
                    for column_name in ("id", "session_id", "session_token", "interview_id", "async_token", "token")
                    if column_name in columns
                ]
                if not lookup_columns:
                    return {}

                value_to_interview_ids: dict[str, set[str]] = {}
                for interview in interviews:
                    interview_id = str(interview.id)
                    candidate_keys = {interview_id}
                    if interview.async_token:
                        candidate_keys.add(interview.async_token)

                    for key in candidate_keys:
                        value_to_interview_ids.setdefault(key, set()).add(interview_id)

                all_keys = list(value_to_interview_ids.keys())
                if not all_keys:
                    return {}

                where_clauses = []
                params = []
                recording_clause_parts = []
                if has_recording_path:
                    recording_clause_parts.append("recording_path IS NOT NULL")
                if has_recording_data:
                    recording_clause_parts.append("recording_data IS NOT NULL")
                recording_clause = " OR ".join(recording_clause_parts)
                for column_name in lookup_columns:
                    placeholders = ", ".join(["%s"] * len(all_keys))
                    where_clauses.append(
                        f"({column_name} IS NOT NULL AND {column_name}::text IN ({placeholders}) AND ({recording_clause}))"
                    )
                    params.extend(all_keys)

                select_fields = [*(f"{column_name}::text" for column_name in lookup_columns)]
                if has_recording_path:
                    select_fields.append("recording_path::text AS recording_path")
                query = f"""
                    SELECT {", ".join(select_fields)}
                    FROM interview_sessions
                    WHERE {" OR ".join(where_clauses)}
                """
                cursor.execute(query, params)

                recording_metadata: dict[str, dict] = {}
                session_token_index = lookup_columns.index("session_token") if "session_token" in lookup_columns else None
                for row in cursor.fetchall():
                    matched_interview_ids: set[str] = set()
                    session_token_value = row[session_token_index] if session_token_index is not None else None
                    recording_path_value = row[-1] if has_recording_path else None
                    lookup_values = row[:-1] if has_recording_path else row
                    for value in lookup_values:
                        if value and value in value_to_interview_ids:
                            matched_interview_ids.update(value_to_interview_ids[value])

                    for interview_id in matched_interview_ids:
                        existing = recording_metadata.get(interview_id, {})
                        recording_metadata[interview_id] = {
                            "has_recording": True,
                            "session_token": existing.get("session_token") or session_token_value,
                            "recording_path": existing.get("recording_path") or recording_path_value,
                        }

                return {
                    str(interview.id): recording_metadata.get(
                        str(interview.id),
                        {"has_recording": False, "session_token": None, "recording_path": None},
                    )
                    for interview in interviews
                }
    except Exception as exc:
        print(f"Failed to fetch interview recording availability: {exc}")
        return {}
    finally:
        try:
            connection.close()
        except Exception:
            pass

@router.get("/count")
def get_interviews_count(
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole, JobDescription
    normalize_legacy_candidate_stages(db)
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if status:
        query = query.filter(Interview.status == status)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == agency_id)
    else:
        query = _apply_interview_scope(query, current_user)
    return {"count": query.count()}

@router.get("", response_model=List[InterviewResponse])
def get_interviews(
    page: int = 1,
    limit: int = 20,
    offset: Optional[int] = None,
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole, JobDescription
    total_start = perf_counter()
    normalization_start = perf_counter()
    normalize_legacy_candidate_stages(db)
    normalization_time = perf_counter() - normalization_start
    query = db.query(Interview)

    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if status:
        query = query.filter(Interview.status == status)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == agency_id)
    else:
        query = _apply_interview_scope(query, current_user)
    
    effective_offset = offset if offset is not None else max(0, (page - 1) * limit)
    query_start = perf_counter()
    interviews = (
        query.options(
            load_only(
                Interview.id,
                Interview.candidate_id,
                Interview.async_token,
                Interview.interview_type,
                Interview.scheduled_at,
                Interview.duration_minutes,
                Interview.meeting_link,
                Interview.status,
                Interview.video_url,
                Interview.transcript,
                Interview.ai_summary,
                Interview.interview_score,
                Interview.feedback,
                Interview.technical_score,
                Interview.communication_score,
                Interview.culture_fit_score,
                Interview.created_at,
            ),
            joinedload(Interview.candidate).load_only(Candidate.id, Candidate.name, Candidate.agency_id, Candidate.job_id),
        )
        .order_by(Interview.scheduled_at.desc())
        .offset(effective_offset)
        .limit(limit)
        .all()
    )
    query_time = perf_counter() - query_start
    print(f"[DB PERF] interviews query={query_time:.4f}s")
    enrichment_start = perf_counter()
    recording_availability = _fetch_recording_availability(interviews)

    credits_checked = _charge_completed_interviews_in_batch(db, interviews, recording_availability)
    if credits_checked:
        db.commit()
    enrichment_time = perf_counter() - enrichment_start
    print(f"[DB PERF] interviews enrichment={enrichment_time:.4f}s")
    
    serialization_start = perf_counter()
    result = []
    for interview in interviews:
        interview_dict = {
            "id": interview.id,
            "candidate_id": interview.candidate_id,
            "candidate_name": interview.candidate.name if interview.candidate else None,
            "async_token": interview.async_token,
            "session_token": recording_availability.get(str(interview.id), {}).get("session_token"),
            "recording_path": recording_availability.get(str(interview.id), {}).get("recording_path"),
            "interview_type": interview.interview_type or "General",
            "scheduled_at": interview.scheduled_at,
            "duration_minutes": interview.duration_minutes if interview.duration_minutes is not None else 60,
            "meeting_link": interview.meeting_link,
            "status": interview.status,
            "has_recording": recording_availability.get(str(interview.id), {}).get("has_recording", False),
            "video_url": interview.video_url,
            "transcript": interview.transcript,
            "ai_summary": interview.ai_summary,
            "interview_score": interview.interview_score,
            "feedback": interview.feedback,
            "technical_score": interview.technical_score,
            "communication_score": interview.communication_score,
            "culture_fit_score": interview.culture_fit_score,
            "created_at": interview.created_at
        }
        result.append(InterviewResponse(**interview_dict))
    _perf_log(
        "interviews",
        total_start,
        normalization=f"{normalization_time:.4f}s",
        query=f"{query_time:.4f}s",
        enrichment=f"{enrichment_time:.4f}s",
        serialization=f"{perf_counter() - serialization_start:.4f}s",
        row_count=len(result),
        limit=limit,
        offset=effective_offset,
    )
    return result


@router.api_route("/video/{session_id}", methods=["GET", "HEAD"])
def stream_interview_video(
    session_id: str,
    request: Request,
    token: Optional[str] = Query(None),
    range_header: Optional[str] = Header(None, alias="Range"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    normalize_legacy_candidate_stages(db)
    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    current_user = _resolve_video_request_user(db, token or bearer_token, None)
    _log_recording_debug(
        "stream_interview_video.request",
        session_id=session_id,
        has_query_token=bool(token),
        has_bearer_token=bool(bearer_token),
        range_header=bool(range_header),
        user_id=current_user.id,
    )
    interview = _get_scoped_interview_for_video(db, session_id, current_user)
    lookup_tokens = [session_id]
    if interview:
        lookup_tokens.extend([str(interview.id), interview.async_token])
    print("Video lookup tokens:", [lookup_token for lookup_token in lookup_tokens if lookup_token])
    print("Video auth token:", _mask_debug_value(token or bearer_token))
    print("Video request headers:", {"Authorization": bool(authorization), "Range": range_header})
    if not interview:
        _log_recording_debug(
            "stream_interview_video.interview_lookup_miss",
            session_id=session_id,
        )
        raise HTTPException(status_code=404, detail="Interview not found")

    session_token = _normalize_recording_session_token(interview.async_token)

    _log_recording_debug(
        "stream_interview_video.lookup",
        interview_id=interview.id,
        async_token=interview.async_token,
        session_token=session_token,
    )

    if not session_token:
        raise HTTPException(status_code=404, detail="Recording not available")

    return _proxy_recording_stream(session_token, request.method, range_header)


@recording_router.api_route("/{session_token}", methods=["GET", "HEAD"])
def stream_candidate_recording(
    session_token: str,
    request: Request,
    token: Optional[str] = Query(None),
    range_header: Optional[str] = Header(None, alias="Range"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    normalize_legacy_candidate_stages(db)
    session_token = _normalize_recording_session_token(session_token)

    bearer_token = None
    if authorization and authorization.lower().startswith("bearer "):
        bearer_token = authorization.split(" ", 1)[1].strip()

    current_user = _resolve_video_request_user(db, token or bearer_token, None)
    _log_recording_debug(
        "stream_candidate_recording.request",
        session_token=session_token,
        has_query_token=bool(token),
        has_bearer_token=bool(bearer_token),
        range_header=bool(range_header),
        user_id=current_user.id,
    )
    print("Recording lookup tokens:", [session_token])
    print("Recording auth token:", _mask_debug_value(token or bearer_token))
    print("Recording request headers:", {"Authorization": bool(authorization), "Range": range_header})

    try:
        interview = _get_scoped_interview_for_video(db, session_token, current_user)
    except AttributeError:
        interview = None
    if interview:
        _log_recording_debug(
            "stream_candidate_recording.lookup",
            interview_id=interview.id,
            async_token=interview.async_token,
            session_token=session_token,
            lookup_strategy="direct_async_token",
        )
        return _proxy_recording_stream(session_token, request.method, range_header)

    connection = None
    try:
        connection = psycopg2.connect(settings.DATABASE_URL)
        with connection:
            with connection.cursor() as cursor:
                session_row = _fetch_interview_session_row_by_session_token(cursor, session_token)

        interview = _resolve_scoped_interview_from_session_row(db, session_row, current_user)
        if not interview:
            _log_recording_debug(
                "stream_candidate_recording.interview_lookup_miss",
                session_token=session_token,
            )
            raise HTTPException(status_code=404, detail="Interview recording not found")
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Candidate recording query failed for session_token {session_token}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load interview recording")
    finally:
        try:
            connection.close()
        except Exception:
            pass

    _log_recording_debug(
        "stream_candidate_recording.lookup",
        interview_id=interview.id if interview else None,
        async_token=interview.async_token if interview else None,
        session_token=session_token,
    )
    return _proxy_recording_stream(session_token, request.method, range_header)

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    normalize_legacy_candidate_stages(db)
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    recording_availability = _fetch_recording_availability([interview])
    has_recording = recording_availability.get(str(interview.id), {}).get("has_recording", False)
    if _charge_completed_interview_if_needed(db, interview, has_recording=has_recording) is not None:
        db.commit()
    
    interview_dict = {
        "id": interview.id,
        "candidate_id": interview.candidate_id,
        "candidate_name": interview.candidate.name if interview.candidate else None,
        "async_token": interview.async_token,
        "session_token": recording_availability.get(str(interview.id), {}).get("session_token"),
        "recording_path": recording_availability.get(str(interview.id), {}).get("recording_path"),
        "interview_type": interview.interview_type or "General",
        "scheduled_at": interview.scheduled_at,
        "duration_minutes": interview.duration_minutes if interview.duration_minutes is not None else 60,
        "meeting_link": interview.meeting_link,
        "status": interview.status,
        "has_recording": has_recording,
        "video_url": interview.video_url,
        "transcript": interview.transcript,
        "ai_summary": interview.ai_summary,
        "interview_score": interview.interview_score,
        "feedback": interview.feedback,
        "technical_score": interview.technical_score,
        "communication_score": interview.communication_score,
        "culture_fit_score": interview.culture_fit_score,
        "created_at": interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.post("/public", response_model=InterviewResponse)
def create_interview_public(
    interview: InterviewCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Public endpoint - no auth required. Create an interview record."""
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    db_interview = Interview(**interview.model_dump())
    db.add(db_interview)
    _sync_candidate_stage_from_interview(candidate, db_interview)
    db.commit()
    db.refresh(db_interview)
    try:
        result = queue_notification_for_stage(db, candidate=candidate, stage_value=CandidateStage.INTERVIEW_SCHEDULED.value)
        db.commit()
        if result:
            background_tasks.add_task(send_email_task, result["communication_id"])
    except Exception as exc:
        print(f"Failed to queue interview invitation: {exc}")

    return InterviewResponse(
        id=db_interview.id,
        candidate_id=db_interview.candidate_id,
        candidate_name=candidate.name,
        async_token=db_interview.async_token,
        recording_path=None,
        interview_type=db_interview.interview_type,
        scheduled_at=db_interview.scheduled_at,
        duration_minutes=db_interview.duration_minutes,
        meeting_link=db_interview.meeting_link,
        status=db_interview.status,
        video_url=db_interview.video_url,
        transcript=db_interview.transcript,
        ai_summary=db_interview.ai_summary,
        interview_score=db_interview.interview_score,
        feedback=db_interview.feedback,
        technical_score=db_interview.technical_score,
        communication_score=db_interview.communication_score,
        culture_fit_score=db_interview.culture_fit_score,
        created_at=db_interview.created_at
    )

@router.post("", response_model=InterviewResponse)
def create_interview(
    interview: InterviewCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    _ensure_interview_scheduling_credits(db, candidate)
    
    db_interview = Interview(**interview.model_dump())
    db.add(db_interview)
    
    # Keep candidate stage aligned with interview status.
    _sync_candidate_stage_from_interview(candidate, db_interview)
    
    db.commit()
    db.refresh(db_interview)
    try:
        result = queue_notification_for_stage(
            db,
            candidate=candidate,
            stage_value=CandidateStage.INTERVIEW_SCHEDULED.value,
            user_id=current_user.id,
            extra_payload={"meeting_link": db_interview.meeting_link or ""},
        )
        db.commit()
        if result:
            background_tasks.add_task(send_email_task, result["communication_id"])
    except Exception as exc:
        print(f"Failed to queue interview invitation: {exc}")
    
    interview_dict = {
        "id": db_interview.id,
        "candidate_id": db_interview.candidate_id,
        "candidate_name": candidate.name,
        "async_token": db_interview.async_token,
        "recording_path": None,
        "interview_type": db_interview.interview_type,
        "scheduled_at": db_interview.scheduled_at,
        "duration_minutes": db_interview.duration_minutes,
        "meeting_link": db_interview.meeting_link,
        "status": db_interview.status,
        "video_url": db_interview.video_url,
        "transcript": db_interview.transcript,
        "ai_summary": db_interview.ai_summary,
        "interview_score": db_interview.interview_score,
        "feedback": db_interview.feedback,
        "technical_score": db_interview.technical_score,
        "communication_score": db_interview.communication_score,
        "culture_fit_score": db_interview.culture_fit_score,
        "created_at": db_interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: UUID,
    interview_update: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    update_data = interview_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_interview, field, value)
    
    candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
    if candidate:
        _sync_candidate_stage_from_interview(candidate, db_interview)
    
    db.commit()
    db.refresh(db_interview)
    
    interview_dict = {
        "id": db_interview.id,
        "candidate_id": db_interview.candidate_id,
        "candidate_name": db_interview.candidate.name if db_interview.candidate else None,
        "async_token": db_interview.async_token,
        "recording_path": None,
        "interview_type": db_interview.interview_type,
        "scheduled_at": db_interview.scheduled_at,
        "duration_minutes": db_interview.duration_minutes,
        "meeting_link": db_interview.meeting_link,
        "status": db_interview.status,
        "video_url": db_interview.video_url,
        "transcript": db_interview.transcript,
        "ai_summary": db_interview.ai_summary,
        "interview_score": db_interview.interview_score,
        "feedback": db_interview.feedback,
        "technical_score": db_interview.technical_score,
        "communication_score": db_interview.communication_score,
        "culture_fit_score": db_interview.culture_fit_score,
        "created_at": db_interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark interview as completed and generate AI analysis"""
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Simulate AI analysis
    db_interview.status = "completed"
    db_interview.transcript = SAMPLE_TRANSCRIPTS
    db_interview.ai_summary = random.choice(SAMPLE_SUMMARIES)
    db_interview.interview_score = round(random.uniform(65, 95), 1)
    db_interview.technical_score = round(random.uniform(60, 98), 1)
    db_interview.communication_score = round(random.uniform(70, 95), 1)
    db_interview.culture_fit_score = round(random.uniform(65, 95), 1)
    db_interview.video_url = "https://example.com/interview-recording.mp4"
    
    candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
    if candidate:
        _sync_candidate_stage_from_interview(candidate, db_interview)

    wallet_balance = _deduct_interview_completion_credit(db, db_interview, candidate)
    db.commit()
    return {"message": "Interview completed and analyzed", "interview_id": interview_id, "wallet_balance": wallet_balance}

@router.post("/{interview_id}/results", response_model=InterviewResponse)
def receive_interview_results(
    interview_id: UUID,
    results: InterviewResultsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Receive video recording, transcript and AI analysis from external interview server"""
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    for field, value in results.model_dump(exclude_unset=True).items():
        setattr(db_interview, field, value)

    db_interview.status = "completed"

    candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
    if candidate:
        _sync_candidate_stage_from_interview(candidate, db_interview)

    _deduct_interview_completion_credit(db, db_interview, candidate)

    db.commit()
    db.refresh(db_interview)

    return InterviewResponse(
        id=db_interview.id,
        candidate_id=db_interview.candidate_id,
        candidate_name=candidate.name if candidate else None,
        async_token=db_interview.async_token,
        interview_type=db_interview.interview_type,
        scheduled_at=db_interview.scheduled_at,
        duration_minutes=db_interview.duration_minutes,
        meeting_link=db_interview.meeting_link,
        status=db_interview.status,
        video_url=db_interview.video_url,
        transcript=db_interview.transcript,
        ai_summary=db_interview.ai_summary,
        interview_score=db_interview.interview_score,
        feedback=db_interview.feedback,
        technical_score=db_interview.technical_score,
        communication_score=db_interview.communication_score,
        culture_fit_score=db_interview.culture_fit_score,
        created_at=db_interview.created_at
    )

@router.delete("/{interview_id}")
def delete_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    db.delete(db_interview)
    db.commit()
    return {"message": "Interview deleted successfully"}
