from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from pathlib import Path
import base64
import binascii
import mimetypes
import random
import psycopg2
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
    result = db.execute(text(
        "UPDATE candidates "
        "SET stage = 'INTERVIEWED' "
        "WHERE stage::text = 'INTERVIEW_REVIEW'"
    ))
    if result.rowcount:
        print(f"Normalized legacy candidate stages before interview query: rows_updated={result.rowcount}")
        db.commit()


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


def _apply_interview_scope(query, current_user):
    from app.models import JobDescription, UserRole

    if current_user.role == UserRole.SUPER_ADMIN:
        return query

    if current_user.role == UserRole.ADMIN and current_user.agency_id:
        return query.join(Candidate).outerjoin(JobDescription, Candidate.job_id == JobDescription.id).filter(
            or_(
                Candidate.agency_id == current_user.agency_id,
                JobDescription.agency_id == current_user.agency_id,
            )
        )

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
    try:
        query = db.query(Interview).filter(Interview.id == UUID(session_id))
    except ValueError:
        query = db.query(Interview).filter(Interview.async_token == session_id)

    query = _apply_interview_scope(query, current_user)
    return query.first()


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


def _normalize_recording_path(recording_path: Optional[str]) -> Optional[Path]:
    if not recording_path:
        return None

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    candidate_path = Path(recording_path)
    if not candidate_path.is_absolute():
        candidate_path = upload_root / candidate_path

    try:
        resolved_path = candidate_path.resolve()
        resolved_path.relative_to(upload_root)
    except Exception:
        raise HTTPException(status_code=404, detail="Interview recording not found")

    if not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Interview recording not found")

    return resolved_path


def _guess_recording_media_type(recording_path: Optional[str], fallback: str = "video/mp4") -> str:
    guessed_media_type, _ = mimetypes.guess_type(recording_path or "")
    return guessed_media_type or fallback


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
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name,),
    )
    return {row[0] for row in cursor.fetchall()}


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
    limit: int = 10,
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
    
    interviews = query.order_by(Interview.scheduled_at.desc()).offset((page - 1) * limit).limit(limit).all()
    recording_availability = _fetch_recording_availability(interviews)
    
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
    
    return result


@router.get("/video/{session_id}")
def stream_interview_video(
    session_id: str,
    token: Optional[str] = Query(None),
    range_header: Optional[str] = Header(None, alias="Range"),
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    normalize_legacy_candidate_stages(db)
    connection = None
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
    if not interview:
        raise HTTPException(status_code=404, detail="Interview session not found")

    try:
        connection = psycopg2.connect(settings.DATABASE_URL)
        with connection:
            with connection.cursor() as cursor:
                session_keys = [session_id, str(interview.id)]
                if interview.async_token:
                    session_keys.append(interview.async_token)

                recording_record, configured_media_type = _fetch_interview_recording(cursor, session_keys)
    except HTTPException:
        raise
    except Exception as exc:
        print(f"Interview video query failed for session {session_id}: {exc}")
        raise HTTPException(status_code=500, detail="Failed to load interview recording")
    finally:
        try:
            connection.close()
        except Exception:
            pass

    recording_path = recording_record.get("recording_path") if recording_record else None
    recording_data = recording_record.get("recording_data") if recording_record else None
    _log_recording_debug(
        "stream_interview_video.lookup",
        interview_id=interview.id,
        async_token=interview.async_token,
        recording_path=recording_path,
        configured_media_type=configured_media_type,
        payload=_describe_recording_payload(recording_data),
    )

    if recording_data:
        video_bytes = _coerce_recording_bytes(recording_data)
        media_type = _normalize_recording_media_type(configured_media_type, video_bytes)
        _log_recording_debug(
            "stream_interview_video.bytes",
            byte_length=len(video_bytes),
            detected_media_type=_detect_video_media_type(video_bytes, fallback="unknown"),
            response_media_type=media_type,
            signature=video_bytes[:16].hex(),
        )
        return _build_video_stream_response(video_bytes, media_type, range_header)

    if not recording_path:
        raise HTTPException(status_code=404, detail="Interview recording not found")

    resolved_path = _normalize_recording_path(recording_path)
    media_type = configured_media_type or _guess_recording_media_type(str(resolved_path))
    _log_recording_debug(
        "stream_interview_video.file",
        resolved_path=resolved_path,
        response_media_type=media_type,
    )
    return FileResponse(
        path=resolved_path,
        media_type=media_type,
        filename=resolved_path.name,
        headers={
            "Content-Disposition": f'inline; filename="{resolved_path.name}"',
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "bytes",
        },
    )


@recording_router.get("/{session_token}")
def stream_candidate_recording(
    session_token: str,
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
        "stream_candidate_recording.request",
        session_token=session_token,
        has_query_token=bool(token),
        has_bearer_token=bool(bearer_token),
        range_header=bool(range_header),
        user_id=current_user.id,
    )

    connection = None
    try:
        connection = psycopg2.connect(settings.DATABASE_URL)
        with connection:
            with connection.cursor() as cursor:
                session_row = _fetch_interview_session_row_by_session_token(cursor, session_token)

        interview = None
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
                break

        if not interview:
            raise HTTPException(status_code=404, detail="Interview session not found")

        recording_path = session_row.get("recording_path")
        recording_data = session_row.get("recording_data")
        if not recording_path and not recording_data:
            raise HTTPException(status_code=404, detail="Interview recording not found")

        configured_media_type = None
        for candidate_column in ("mime_type", "content_type", "recording_mime_type", "video_format"):
            if session_row.get(candidate_column):
                configured_media_type = session_row.get(candidate_column)
                break
        _log_recording_debug(
            "stream_candidate_recording.lookup",
            interview_id=interview.id if interview else None,
            async_token=interview.async_token if interview else None,
            recording_path=recording_path,
            configured_media_type=configured_media_type,
            payload=_describe_recording_payload(recording_data),
        )
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

    if recording_data:
        video_bytes = _coerce_recording_bytes(recording_data)
        media_type = _normalize_recording_media_type(configured_media_type, video_bytes)
        _log_recording_debug(
            "stream_candidate_recording.bytes",
            byte_length=len(video_bytes),
            detected_media_type=_detect_video_media_type(video_bytes, fallback="unknown"),
            response_media_type=media_type,
            signature=video_bytes[:16].hex(),
        )
        return _build_video_stream_response(video_bytes, media_type, range_header)

    resolved_path = _normalize_recording_path(recording_path)
    media_type = configured_media_type or _guess_recording_media_type(str(resolved_path))
    _log_recording_debug(
        "stream_candidate_recording.file",
        resolved_path=resolved_path,
        response_media_type=media_type,
    )
    return FileResponse(
        path=resolved_path,
        media_type=media_type,
        filename=resolved_path.name,
        headers={
            "Content-Disposition": f'inline; filename="{resolved_path.name}"',
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "bytes",
        },
    )

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
    
    # Deduct 1 credit from agency admin wallet
    from app.models import UserRole, WalletTransaction, TransactionType, JobDescription
    agency_id = None
    if candidate and candidate.job_id:
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            agency_id = job.agency_id
    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.agency_id == agency_id
    ).first()
    if admin:
        admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
        db.add(WalletTransaction(
            user_id=admin.id,
            agency_id=agency_id,
            amount=1,
            transaction_type=TransactionType.DEBIT,
            description=f"Interview completed - Candidate ID {db_interview.candidate_id}",
            balance_after=admin.wallet_balance
        ))
    db.commit()
    return {"message": "Interview completed and analyzed", "interview_id": interview_id, "wallet_balance": admin.wallet_balance if admin else None}

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

    # Deduct 1 credit from agency admin wallet
    from app.models import UserRole, WalletTransaction, TransactionType, JobDescription
    agency_id = None
    if candidate and candidate.job_id:
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            agency_id = job.agency_id
    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.agency_id == agency_id
    ).first()
    if admin:
        admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
        db.add(WalletTransaction(
            user_id=admin.id,
            agency_id=agency_id,
            amount=1,
            transaction_type=TransactionType.DEBIT,
            description=f"Interview completed - Candidate ID {db_interview.candidate_id}",
            balance_after=admin.wallet_balance
        ))

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
