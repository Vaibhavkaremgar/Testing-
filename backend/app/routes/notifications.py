from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, get_current_admin_user
from app.database import get_db
from app.models import Candidate, CandidateStage, Interview, User
from app.notification_service import (
    build_workflow_url,
    compact_notification_payload,
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


def _normalize_workflow_payload(payload: dict) -> dict:
    normalized = dict(payload or {})

    resume_text = normalized.get("resumeText") or normalized.get("resume_text") or ""
    job_description = normalized.get("jobDescription") or normalized.get("job_description") or ""
    predefined_questions = (
        normalized.get("predefinedQuestions")
        or normalized.get("predefined_questions")
        or normalized.get("interviewQuestions")
        or normalized.get("interview_questions")
        or normalized.get("async_questions")
        or []
    )

    normalized["resume_text"] = resume_text
    normalized["resumeText"] = resume_text
    normalized["job_description"] = job_description
    normalized["jobDescription"] = job_description
    normalized["predefined_questions"] = predefined_questions
    normalized["predefinedQuestions"] = predefined_questions
    normalized["interview_questions"] = normalized.get("interview_questions") or predefined_questions
    normalized["interviewQuestions"] = normalized.get("interviewQuestions") or normalized["interview_questions"]
    normalized["meeting_link"] = normalized.get("meeting_link") or normalized.get("meetingLink") or ""
    normalized["meetingLink"] = normalized["meeting_link"]

    return normalized


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

    return WorkflowTokenResolveResponse(
        token_type=token_record.token_type,
        payload=_normalize_workflow_payload(token_record.payload),
        expires_at=token_record.expires_at,
        consumed_at=token_record.consumed_at,
        is_active=token_record.is_active,
    )


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

    slot_token.payload = compact_notification_payload({
        **slot_token.payload,
        "interview_date": request.interview_date,
        "interview_time": request.interview_time,
        "timezone": request.timezone or "",
        "slot_selection_confirmed_at": datetime.utcnow().isoformat(),
        "slot_notes": request.notes or "",
    })
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
    candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
    candidate.stage_updated_at = datetime.utcnow()
    candidate.stage_entered_at = datetime.utcnow()

    db_interview = Interview(
        agency_id=candidate.agency_id,
        candidate_id=candidate.id,
        interview_type="async_ai_bot",
        scheduled_at=datetime.fromisoformat(f"{request.interview_date}T{request.interview_time}:00"),
        duration_minutes=60,
        meeting_link=meeting_link,
        is_async=True,
        async_link=meeting_link,
        async_token=invitation_result["workflow_token"],
    )
    db.add(db_interview)
    db.commit()

    background_tasks.add_task(send_email_task, confirmation_result["communication_id"])
    background_tasks.add_task(send_email_task, invitation_result["communication_id"])

    return {
        "message": "Slot confirmed and interview link generated",
        "meeting_link": meeting_link,
        "confirmation_communication_id": confirmation_result["communication_id"],
        "invitation_communication_id": invitation_result["communication_id"],
    }
