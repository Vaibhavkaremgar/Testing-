from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, get_current_admin_user
from app.database import get_db
from app.models import Candidate, CandidateStage, Interview, User
from app.routes.candidates import INDIA_TIMEZONE, derive_candidate_stage_from_selected_slot
from app.notification_service import (
    build_rendered_notification,
    build_workflow_url,
    queue_rendered_notification,
    queue_notification,
    resolve_workflow_token,
    send_email_task,
)
from app.schemas import (
    NotificationEventRequest,
    NotificationEventResponse,
    SlotSelectionSubmitRequest,
    WorkflowTokenResolveResponse,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _find_reschedulable_interview(db: Session, candidate_id):
    return (
        db.query(Interview)
        .filter(
            Interview.candidate_id == candidate_id,
            ~Interview.status.in_(["selected", "rejected", "completed"]),
        )
        .order_by(Interview.scheduled_at.desc(), Interview.created_at.desc())
        .first()
    )


def _mark_other_active_interviews_rescheduled(db: Session, candidate_id, keep_interview_id=None):
    active_interviews = (
        db.query(Interview)
        .filter(
            Interview.candidate_id == candidate_id,
            ~Interview.status.in_(["selected", "rejected", "completed"]),
        )
        .all()
    )
    for interview in active_interviews:
        if keep_interview_id and str(interview.id) == str(keep_interview_id):
            continue
        interview.status = "rescheduled"


def _resolve_target_interview_for_slot_confirmation(db: Session, candidate: Candidate, payload: dict):
    interview_id = payload.get("reschedule_interview_id")
    if interview_id:
        interview = db.query(Interview).filter(
            Interview.id == interview_id,
            Interview.candidate_id == candidate.id,
        ).first()
        if interview:
            return interview

    return _find_reschedulable_interview(db, candidate.id)


def _normalize_workflow_payload(payload: dict) -> dict:
    normalized = dict(payload or {})

    resume_text = normalized.get("resumeText") or normalized.get("resume_text") or ""
    job_description = normalized.get("jobDescription") or normalized.get("job_description") or ""
    async_questions = (
        normalized.get("predefinedQuestions")
        or normalized.get("predefined_questions")
        or normalized.get("interviewQuestions")
        or normalized.get("interview_questions")
        or normalized.get("async_questions")
        or []
    )

    normalized["resume_text"] = resume_text
    normalized["resumeText"] = resume_text
    normalized["reschedule_interview_id"] = normalized.get("reschedule_interview_id") or normalized.get("rescheduleInterviewId") or ""
    normalized["rescheduleInterviewId"] = normalized["reschedule_interview_id"]
    normalized["job_description"] = job_description
    normalized["jobDescription"] = job_description
    normalized["async_questions"] = async_questions
    normalized["predefined_questions"] = async_questions
    normalized["predefinedQuestions"] = async_questions
    normalized["interview_questions"] = normalized.get("interview_questions") or async_questions
    normalized["interviewQuestions"] = normalized.get("interviewQuestions") or normalized["interview_questions"]
    normalized["meeting_link"] = normalized.get("meeting_link") or normalized.get("meetingLink") or ""
    normalized["meetingLink"] = normalized["meeting_link"]

    return normalized


def _compact_workflow_payload(payload: dict) -> dict:
    normalized = _normalize_workflow_payload(payload)
    return {
        "candidate_name": normalized.get("candidate_name") or normalized.get("candidateName") or "",
        "candidate_email": normalized.get("candidate_email") or normalized.get("candidateEmail") or "",
        "candidate_id": normalized.get("candidate_id") or normalized.get("candidateId") or "",
        "reschedule_interview_id": normalized.get("reschedule_interview_id") or normalized.get("rescheduleInterviewId") or "",
        "job_id": normalized.get("job_id") or normalized.get("jobId") or "",
        "job_title": normalized.get("job_title") or normalized.get("jobTitle") or "",
        "job_role": normalized.get("job_role") or normalized.get("jobRole") or "",
        "job_description": normalized.get("job_description") or normalized.get("jobDescription") or "",
        "skills": normalized.get("skills") or "",
        "resume_text": normalized.get("resume_text") or normalized.get("resumeText") or "",
        "agency_id": normalized.get("agency_id") or "",
        "user_id": normalized.get("user_id") or "",
        "slot_link": normalized.get("slot_link") or normalized.get("slotLink") or "",
        "meeting_link": normalized.get("meeting_link") or normalized.get("meetingLink") or "",
        "interview_date": normalized.get("interview_date") or normalized.get("interviewDate") or "",
        "interview_time": normalized.get("interview_time") or normalized.get("interviewTime") or "",
        "agency_name": normalized.get("agency_name") or normalized.get("agencyName") or "",
        "async_questions": normalized.get("async_questions") or [],
        "timezone": normalized.get("timezone") or "",
        "slot_selection_confirmed_at": normalized.get("slot_selection_confirmed_at") or "",
        "slot_notes": normalized.get("slot_notes") or "",
    }


def _payload_with_canonical_token_ids(
    token_record,
    payload: dict,
    candidate: Candidate,
) -> dict:
    canonical_payload = dict(payload or {})

    if token_record.candidate_id:
        canonical_payload["candidate_id"] = str(token_record.candidate_id)
        canonical_payload["candidateId"] = canonical_payload["candidate_id"]
    elif candidate and candidate.id:
        canonical_payload["candidate_id"] = str(candidate.id)
        canonical_payload["candidateId"] = canonical_payload["candidate_id"]

    if token_record.job_id:
        canonical_payload["job_id"] = str(token_record.job_id)
        canonical_payload["jobId"] = canonical_payload["job_id"]
    elif candidate and candidate.job_id:
        canonical_payload["job_id"] = str(candidate.job_id)
        canonical_payload["jobId"] = canonical_payload["job_id"]

    return canonical_payload


@router.post("/trigger", response_model=NotificationEventResponse)
def trigger_notification_event(
    request: NotificationEventRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    result = queue_notification(
        db,
        candidate=candidate,
        status=request.status,
        user_id=request.user_id or current_user.id,
        extra_payload=request.payload,
    )
    db.commit()
    background_tasks.add_task(send_email_task, result["communication_id"])

    return NotificationEventResponse(
        queued=True,
        candidate_id=candidate.id,
        status=request.status,
        template_id=result["template_id"],
        communication_id=result["communication_id"],
        workflow_token=result["workflow_token"],
    )


@router.get("/workflows/{token}", response_model=WorkflowTokenResolveResponse)
def resolve_notification_workflow(
    token: str,
    db: Session = Depends(get_db),
):
    try:
        token_record = resolve_workflow_token(db, token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    candidate = db.query(Candidate).filter(Candidate.id == token_record.candidate_id).first() if token_record.candidate_id else None
    normalized_payload = _normalize_workflow_payload(
        _payload_with_canonical_token_ids(token_record, token_record.payload, candidate)
    )

    return WorkflowTokenResolveResponse(
        token_type=token_record.token_type,
        payload=normalized_payload,
        expires_at=token_record.expires_at,
        consumed_at=token_record.consumed_at,
        is_active=token_record.is_active,
    )


@router.post("/slot-selection-link")
def create_slot_selection_link(
    request: NotificationEventRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    requested_status = (request.status or "slot_selection").strip().lower() or "slot_selection"
    if requested_status not in {"slot_selection", "interview_rescheduled"}:
        requested_status = "slot_selection"

    compact_payload = _compact_workflow_payload(request.payload or {})
    if requested_status == "interview_rescheduled":
        existing_interview = _find_reschedulable_interview(db, candidate.id)
        if existing_interview:
            compact_payload["reschedule_interview_id"] = str(existing_interview.id)

    rendered = build_rendered_notification(
        db,
        candidate=candidate,
        status=requested_status,
        user_id=request.user_id or current_user.id,
        extra_payload=compact_payload,
    )

    queued_notification = None
    if requested_status == "interview_rescheduled":
        if candidate.email:
            queued_notification = queue_rendered_notification(
                db,
                candidate=candidate,
                status=requested_status,
                rendered=rendered,
            )
        existing_interview = _resolve_target_interview_for_slot_confirmation(db, candidate, rendered["payload"])
        if existing_interview:
            existing_interview.status = "rescheduled"
            _mark_other_active_interviews_rescheduled(db, candidate.id, existing_interview.id)
        candidate.stage = CandidateStage.INTERVIEW_RESCHEDULED
        candidate.stage_updated_at = datetime.utcnow()
        candidate.stage_entered_at = datetime.utcnow()

    db.commit()

    if requested_status == "interview_rescheduled":
        from app.routes.analytics import clear_analytics_cache
        clear_analytics_cache()

    if queued_notification:
        background_tasks.add_task(send_email_task, queued_notification["communication_id"])

    return {
        "candidate_id": candidate.id,
        "status": requested_status,
        "workflow_token": rendered["workflow_token"],
        "slot_link": rendered["payload"].get("slot_link") or (
            build_workflow_url(rendered["workflow_token"], "slot_selection")
            if rendered["workflow_token"]
            else ""
        ),
        "communication_id": queued_notification["communication_id"] if queued_notification else None,
        "payload": _normalize_workflow_payload(rendered["payload"]),
    }


@router.post("/workflows/{token}/slot-confirmation")
def confirm_slot_selection(
    token: str,
    request: SlotSelectionSubmitRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    try:
        slot_token = resolve_workflow_token(db, token)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    candidate = db.query(Candidate).filter(Candidate.id == slot_token.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    slot_token.payload = _payload_with_canonical_token_ids(
        slot_token,
        _compact_workflow_payload({
        **slot_token.payload,
        "interview_date": request.interview_date,
        "interview_time": request.interview_time,
        "timezone": request.timezone or "",
        "slot_selection_confirmed_at": datetime.utcnow().isoformat(),
        "slot_notes": request.notes or "",
        }),
        candidate,
    )
    slot_token.consumed_at = datetime.utcnow()

    confirmation_result = queue_notification(
        db,
        candidate=candidate,
        status="slot_confirmation",
        user_id=slot_token.user_id,
        extra_payload=slot_token.payload,
    )

    invitation_result = queue_notification(
        db,
        candidate=candidate,
        status="interview_invitation",
        user_id=slot_token.user_id,
        extra_payload=slot_token.payload,
    )

    meeting_link = build_workflow_url(invitation_result["workflow_token"], "interview_access") if invitation_result["workflow_token"] else slot_token.payload.get("meeting_link", "")
    selected_slot_ist = datetime.fromisoformat(
        f"{request.interview_date}T{request.interview_time}:00"
    ).replace(tzinfo=INDIA_TIMEZONE)
    candidate.stage = derive_candidate_stage_from_selected_slot(selected_slot_ist)
    candidate.stage_updated_at = datetime.utcnow()
    candidate.stage_entered_at = datetime.utcnow()

    db_interview = _resolve_target_interview_for_slot_confirmation(db, candidate, slot_token.payload)
    if db_interview:
        db_interview.agency_id = candidate.agency_id
        db_interview.interview_type = db_interview.interview_type or "async_ai_bot"
        db_interview.scheduled_at = selected_slot_ist.astimezone(timezone.utc)
        db_interview.duration_minutes = db_interview.duration_minutes or 60
        db_interview.meeting_link = meeting_link
        db_interview.is_async = True
        db_interview.async_link = meeting_link
        db_interview.async_token = invitation_result["workflow_token"]
        db_interview.status = "scheduled"
    else:
        db_interview = Interview(
            agency_id=candidate.agency_id,
            candidate_id=candidate.id,
            interview_type="async_ai_bot",
            scheduled_at=selected_slot_ist.astimezone(timezone.utc),
            duration_minutes=60,
            meeting_link=meeting_link,
            is_async=True,
            async_link=meeting_link,
            async_token=invitation_result["workflow_token"],
            status="scheduled",
        )
        db.add(db_interview)
    _mark_other_active_interviews_rescheduled(db, candidate.id, db_interview.id)
    db.commit()

    from app.routes.analytics import clear_analytics_cache
    clear_analytics_cache()

    background_tasks.add_task(send_email_task, confirmation_result["communication_id"])
    background_tasks.add_task(send_email_task, invitation_result["communication_id"])

    return {
        "message": "Slot confirmed and interview link generated",
        "meeting_link": meeting_link,
        "confirmation_communication_id": confirmation_result["communication_id"],
        "invitation_communication_id": invitation_result["communication_id"],
    }
