from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.mailer import is_email_configured, send_html_email
from app.models import (
    Agency,
    Candidate,
    CandidateStage,
    EmailCommunication,
    EmailTemplate,
    JobDescription,
    NotificationDeliveryStatus,
    NotificationWorkflowToken,
    User,
    WorkflowTokenType,
)


EMAIL_TEMPLATE_STATUSES = [
    "resume_shortlisted",
    "resume_rejected",
    "slot_confirmation",
    "interview_selected",
    "interview_rejected",
]

EMAIL_TEMPLATE_STATUS_LABELS = {
    "resume_shortlisted": "Resume Shortlisted",
    "resume_rejected": "Resume Rejected",
    "slot_confirmation": "Interview Slot Confirmation Email",
    "interview_selected": "Interview Selected Email",
    "interview_rejected": "Interview Rejected Email",
}

SUPPORTED_PLACEHOLDERS = [
    "candidate_name",
    "candidate_id",
    "job_id",
    "job_title",
    "job_role",
    "job_description",
    "skills",
    "resume_text",
    "agency_id",
    "user_id",
    "slot_link",
    "meeting_link",
    "interview_date",
    "interview_time",
]

STAGE_TO_NOTIFICATION_STATUS = {
    CandidateStage.SHORTLISTED.value: "resume_shortlisted",
    CandidateStage.RESUME_REJECTED.value: "resume_rejected",
    CandidateStage.INTERVIEW_SCHEDULED.value: "slot_confirmation",
    CandidateStage.SELECTED.value: "interview_selected",
    CandidateStage.REJECTED.value: "interview_rejected",
}

DEFAULT_TEMPLATE_DEFINITIONS = {
    "resume_shortlisted": {
        "name": "Default Resume Shortlisted",
        "subject": "Your Profile got shortlisted",
        "body": (
            "<!DOCTYPE html>"
            "<html>"
            "<head>"
            "<meta charset=\"UTF-8\">"
            "<title>Resume Shortlisted</title>"
            "</head>"
            "<body style=\"margin:0; padding:0; font-family: Arial, sans-serif; background-color:#f4f6f8;\">"
            "<table width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background-color:#f4f6f8; padding:20px;\">"
            "<tr>"
            "<td align=\"center\">"
            "<table width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#ffffff; border-radius:8px; padding:30px;\">"
            "<tr>"
            "<td align=\"center\" style=\"padding-bottom:20px;\">"
            "<h2 style=\"margin:0; color:#333;\">Congratulations!</h2>"
            "</td>"
            "</tr>"
            "<tr>"
            "<td style=\"color:#555; font-size:16px; line-height:1.6;\">"
            "<p>Hi <strong>{{candidate_name}}</strong>,</p>"
            "<p>We&#39;re excited to inform you that your profile has been <strong>shortlisted</strong> for the position of <strong>{{job_title}}</strong>.</p>"
            "<p><strong>Role:</strong> {{job_role}}</p>"
            "<p><strong>Skills:</strong> {{skills}}</p>"
            "<p>{{job_description}}</p>"
            "<p>Please select your preferred interview slot by clicking the button below:</p>"
            "</td>"
            "</tr>"
            "<tr>"
            "<td align=\"center\" style=\"padding:20px 0;\">"
            "<a href=\"{{slot_link}}\" style=\"background-color:#007BFF; color:#ffffff; padding:12px 24px; text-decoration:none; border-radius:5px; font-size:16px; display:inline-block;\">"
            "Select Interview Slot"
            "</a>"
            "</td>"
            "</tr>"
            "<tr>"
            "<td style=\"color:#999; font-size:14px; padding-top:20px; text-align:center;\">"
            "<p>If you have any questions, feel free to contact us.</p>"
            "<p>Best regards,<br/>Recruitment Team</p>"
            "</td>"
            "</tr>"
            "</table>"
            "</td>"
            "</tr>"
            "</table>"
            "</body>"
            "</html>"
        ),
    },
    "resume_rejected": {
        "name": "Default Resume Rejected",
        "subject": "Update on your application for {{job_title}}",
        "body": (
            "<p>Hi {{candidate_name}},</p>"
            "<p>Thank you for applying for {{job_title}}. We appreciate your interest, but we are not moving forward at this stage.</p>"
        ),
    },
    "slot_confirmation": {
        "name": "Default Slot Confirmation",
        "subject": "Interview slot confirmed for {{job_title}}",
        "body": (
            "<p>Hi {{candidate_name}},</p>"
            "<p>Your interview is confirmed for {{interview_date}} at {{interview_time}}.</p>"
            "<p>Interview link: <a href=\"{{meeting_link}}\">Join interview</a></p>"
        ),
    },
    "interview_invitation": {
        "name": "Default Interview Invitation",
        "subject": "Your interview link for {{job_title}}",
        "body": (
            "<p>Hi {{candidate_name}},</p>"
            "<p>Your interview for {{job_title}} is scheduled on {{interview_date}} at {{interview_time}}.</p>"
            "<p>Join here: <a href=\"{{meeting_link}}\">Start interview</a></p>"
        ),
    },
    "interview_selected": {
        "name": "Default Interview Selected",
        "subject": "Congratulations on your interview result",
        "body": (
            "<p>Hi {{candidate_name}},</p>"
            "<p>Congratulations. You have been selected after your interview for {{job_title}}.</p>"
        ),
    },
    "interview_rejected": {
        "name": "Default Interview Rejected",
        "subject": "Interview update for {{job_title}}",
        "body": (
            "<p>Hi {{candidate_name}},</p>"
            "<p>Thank you for interviewing for {{job_title}}. We will not be moving forward at this time.</p>"
        ),
    },
}


def ensure_default_email_templates(db: Session) -> None:
    for status, template in DEFAULT_TEMPLATE_DEFINITIONS.items():
        exists = db.query(EmailTemplate).filter(
            EmailTemplate.agency_id.is_(None),
            EmailTemplate.status == status,
        ).first()
        if exists:
            if exists.is_default:
                exists.name = template["name"]
                exists.subject = template["subject"]
                exists.body = template["body"]
                exists.variables = SUPPORTED_PLACEHOLDERS
                exists.is_html = True
                exists.is_active = True
            continue

        db.add(
            EmailTemplate(
                agency_id=None,
                name=template["name"],
                status=status,
                subject=template["subject"],
                body=template["body"],
                variables=SUPPORTED_PLACEHOLDERS,
                is_default=True,
                is_selected=True,
                is_html=True,
                is_active=True,
            )
        )
    db.commit()

    db.query(EmailTemplate).filter(
        EmailTemplate.agency_id.is_(None),
        EmailTemplate.is_default == True,
        EmailTemplate.is_selected != True,
    ).update({"is_selected": True}, synchronize_session=False)
    db.commit()


def _parse_questions(raw_questions) -> list:
    if raw_questions is None:
        return []
    if isinstance(raw_questions, list):
        return raw_questions
    if isinstance(raw_questions, str):
        try:
            parsed = json.loads(raw_questions)
            return parsed if isinstance(parsed, list) else [raw_questions]
        except Exception:
            return [raw_questions]
    return [raw_questions]


def build_notification_payload(
    db: Session,
    *,
    candidate: Candidate,
    user_id=None,
    extra_payload: Optional[dict] = None,
) -> dict:
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first() if candidate.job_id else None
    agency = db.query(Agency).filter(Agency.id == candidate.agency_id).first() if candidate.agency_id else None

    payload = {
        "candidate_name": candidate.name or "",
        "candidate_id": candidate.candidate_id or str(candidate.id),
        "job_id": job.job_id if job and job.job_id else (str(job.id) if job else ""),
        "job_title": job.title if job else "",
        "job_role": candidate.current_role or (job.title if job else ""),
        "job_description": job.description if job else "",
        "skills": ", ".join(candidate.skills or (job.skills if job else []) or []),
        "resume_text": candidate.resume_text or "",
        "agency_id": str(candidate.agency_id) if candidate.agency_id else "",
        "user_id": str(user_id or candidate.created_by) if (user_id or candidate.created_by) else "",
        "slot_link": settings.SLOT_BOOKING_URL or "",
        "meeting_link": "",
        "interview_date": "",
        "interview_time": "",
        "agency_name": agency.name if agency else "",
        "async_questions": _parse_questions(candidate.predefined_questions) or _parse_questions(job.interview_questions if job else None),
    }

    if extra_payload:
        payload.update(extra_payload)

    return payload


def render_template_content(content: str, payload: dict) -> str:
    rendered = content or ""
    for placeholder, value in payload.items():
        replacement = value
        if isinstance(replacement, (dict, list)):
            replacement = json.dumps(replacement)
        rendered = rendered.replace(f"{{{{{placeholder}}}}}", str(replacement if replacement is not None else ""))
    return rendered


def get_template_for_agency_and_status(db: Session, agency_id, status: str) -> tuple[EmailTemplate, bool]:
    ensure_default_email_templates(db)

    def _find_template(scope_agency_id, selected_only: bool) -> Optional[EmailTemplate]:
        query = db.query(EmailTemplate).filter(
            EmailTemplate.status == status,
            EmailTemplate.is_active == True,
        )
        if scope_agency_id is None:
            query = query.filter(EmailTemplate.agency_id.is_(None))
        else:
            query = query.filter(EmailTemplate.agency_id == scope_agency_id)

        if selected_only:
            query = query.filter(EmailTemplate.is_selected == True)

        return query.order_by(
            EmailTemplate.is_selected.desc(),
            EmailTemplate.is_default.desc(),
            EmailTemplate.updated_at.desc().nullslast(),
            EmailTemplate.created_at.desc(),
        ).first()

    search_order = []
    if agency_id:
        search_order.extend([
            (agency_id, True, False),
            (agency_id, False, False),
        ])
    search_order.extend([
        (None, True, True),
        (None, False, True),
    ])

    for scope_agency_id, selected_only, used_default in search_order:
        template = _find_template(scope_agency_id, selected_only)
        if template:
            return template, used_default

    ensure_default_email_templates(db)
    fallback_template = _find_template(None, False)
    if fallback_template:
        return fallback_template, True

    raise ValueError(f"No active template configured for status '{status}'")


def create_workflow_token(
    db: Session,
    *,
    token_type: str,
    candidate: Candidate,
    payload: dict,
    user_id=None,
    expires_in_hours: int = 72,
) -> NotificationWorkflowToken:
    token_record = NotificationWorkflowToken(
        agency_id=candidate.agency_id,
        candidate_id=candidate.id,
        job_id=candidate.job_id,
        user_id=user_id or candidate.created_by,
        token=secrets.token_urlsafe(32),
        token_type=token_type,
        payload=payload,
        expires_at=datetime.utcnow() + timedelta(hours=expires_in_hours),
        is_active=True,
    )
    db.add(token_record)
    db.flush()
    return token_record


def build_workflow_url(token: str, token_type: str) -> str:
    if token_type == WorkflowTokenType.SLOT_SELECTION.value:
        return f"{settings.FRONTEND_URL}/slot-selection?token={token}"
    return f"{settings.FRONTEND_URL}/interview-room?token={token}"


def build_rendered_notification(
    db: Session,
    *,
    candidate: Candidate,
    status: str,
    user_id=None,
    extra_payload: Optional[dict] = None,
) -> dict:
    payload = build_notification_payload(db, candidate=candidate, user_id=user_id, extra_payload=extra_payload)

    slot_token = None
    interview_token = None

    if status == "slot_selection" and not payload.get("slot_link"):
        slot_payload = dict(payload)
        slot_token = create_workflow_token(
            db,
            token_type=WorkflowTokenType.SLOT_SELECTION.value,
            candidate=candidate,
            payload=slot_payload,
            user_id=user_id,
        )
        payload["slot_link"] = build_workflow_url(slot_token.token, WorkflowTokenType.SLOT_SELECTION.value)

    if status in {"slot_confirmation", "interview_invitation"} and not payload.get("meeting_link"):
        interview_payload = dict(payload)
        interview_token = create_workflow_token(
            db,
            token_type=WorkflowTokenType.INTERVIEW_ACCESS.value,
            candidate=candidate,
            payload=interview_payload,
            user_id=user_id,
        )
        payload["meeting_link"] = build_workflow_url(interview_token.token, WorkflowTokenType.INTERVIEW_ACCESS.value)

    template, used_default = get_template_for_agency_and_status(db, candidate.agency_id, status)
    subject = render_template_content(template.subject, payload)
    body = render_template_content(template.body, payload)

    return {
        "template": template,
        "used_default": used_default,
        "payload": payload,
        "subject": subject,
        "body": body,
        "slot_token": slot_token.token if slot_token else None,
        "meeting_token": interview_token.token if interview_token else None,
        "workflow_token": slot_token.token if slot_token else (interview_token.token if interview_token else None),
    }


def _build_html_body(template: EmailTemplate, body: str) -> str:
    if template.is_html:
        return body
    return (
        "<html><body style=\"font-family: Arial, sans-serif; line-height: 1.6; color: #333;\">"
        f"<div style=\"max-width: 640px; margin: 0 auto; padding: 24px; white-space: pre-line;\">{body.replace(chr(10), '<br>')}</div>"
        "</body></html>"
    )


def send_email_task(communication_id: int) -> None:
    db = SessionLocal()
    try:
        communication = db.query(EmailCommunication).filter(EmailCommunication.id == communication_id).first()
        if not communication:
            print(f"Email send skipped: communication {communication_id} not found")
            return

        if not is_email_configured():
            communication.status = NotificationDeliveryStatus.FAILED.value
            communication.error_message = "SMTP email is not configured"
            db.commit()
            print(f"Email send failed: communication {communication_id} missing SMTP configuration")
            return

        provider_message_id = send_html_email(
            to_email=communication.candidate_email,
            subject=communication.subject or communication.email_type,
            html_content=communication.body or "",
        )
        communication.status = NotificationDeliveryStatus.SENT.value
        communication.sent_at = datetime.utcnow()
        communication.provider_message_id = provider_message_id
        db.commit()
        print(
            f"Email sent: communication_id={communication.id}, "
            f"email_type={communication.email_type}, to={communication.candidate_email}, "
            f"provider_message_id={communication.provider_message_id}"
        )
    except Exception as exc:
        communication = db.query(EmailCommunication).filter(EmailCommunication.id == communication_id).first()
        if communication:
            communication.status = NotificationDeliveryStatus.FAILED.value
            communication.error_message = str(exc)
            db.commit()
            print(
                f"Email send failed: communication_id={communication.id}, "
                f"email_type={communication.email_type}, to={communication.candidate_email}, error={exc}"
            )
        else:
            print(f"Email send failed before communication lookup: communication_id={communication_id}, error={exc}")
    finally:
        db.close()


def queue_notification(
    db: Session,
    *,
    candidate: Candidate,
    status: str,
    user_id=None,
    extra_payload: Optional[dict] = None,
) -> dict:
    rendered = build_rendered_notification(
        db,
        candidate=candidate,
        status=status,
        user_id=user_id,
        extra_payload=extra_payload,
    )

    communication = EmailCommunication(
        agency_id=candidate.agency_id,
        candidate_id=candidate.id,
        template_id=rendered["template"].id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=status,
        subject=rendered["subject"],
        body=_build_html_body(rendered["template"], rendered["body"]),
        placeholder_payload=rendered["payload"],
        workflow_token=rendered["workflow_token"],
        status=NotificationDeliveryStatus.QUEUED.value,
    )
    db.add(communication)
    db.flush()

    return {
        "communication_id": communication.id,
        "template_id": rendered["template"].id,
        "workflow_token": rendered["workflow_token"],
        "subject": rendered["subject"],
        "body": rendered["body"],
        "payload": rendered["payload"],
        "used_default_template": rendered["used_default"],
    }


def queue_notification_for_stage(
    db: Session,
    *,
    candidate: Candidate,
    stage_value: str,
    user_id=None,
    extra_payload: Optional[dict] = None,
) -> Optional[dict]:
    status = STAGE_TO_NOTIFICATION_STATUS.get(stage_value)
    if not status or not candidate.email:
        print(
            f"Notification not queued: candidate_id={candidate.id}, stage={stage_value}, "
            f"mapped_status={status}, has_email={bool(candidate.email)}"
        )
        return None
    print(
        f"Notification queue requested: candidate_id={candidate.id}, "
        f"stage={stage_value}, status={status}, email={candidate.email}"
    )
    return queue_notification(db, candidate=candidate, status=status, user_id=user_id, extra_payload=extra_payload)


def resolve_workflow_token(db: Session, token: str) -> NotificationWorkflowToken:
    token_record = db.query(NotificationWorkflowToken).filter(
        NotificationWorkflowToken.token == token,
        NotificationWorkflowToken.is_active == True,
    ).first()
    if not token_record:
        raise ValueError("Workflow token not found")
    if token_record.expires_at and token_record.expires_at < datetime.utcnow():
        raise ValueError("Workflow token has expired")
    return token_record
