from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Agency, Candidate, EmailCommunication, EmailTemplate, Interview, JobDescription


def get_default_template_variables() -> list[str]:
    return [
        "candidate_name",
        "candidate_email",
        "candidate_phone",
        "job_title",
        "company_name",
        "agency_name",
        "resume_score",
        "score_threshold",
        "interview_date",
        "slot_booking_url",
        "interview_details_url",
        "current_date",
        "candidate_stage",
    ]


def render_template_content(content: str, context: dict) -> str:
    rendered = content or ""
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value if value is not None else ""))
    return rendered


def get_template_for_agency(
    db: Session,
    agency_id,
    *,
    template_id: Optional[int] = None,
    template_type: Optional[str] = None,
    trigger_stage: Optional[str] = None,
    automation_only: bool = False,
) -> Optional[EmailTemplate]:
    query = db.query(EmailTemplate).filter(EmailTemplate.is_active == True)

    if agency_id:
        query = query.filter(EmailTemplate.agency_id == agency_id)
    else:
        query = query.filter(EmailTemplate.agency_id.is_(None))

    if template_id is not None:
        query = query.filter(EmailTemplate.id == template_id)

    if template_type:
        query = query.filter(EmailTemplate.template_type == template_type)

    if trigger_stage:
        query = query.filter(EmailTemplate.trigger_stage == trigger_stage)

    if automation_only:
        query = query.filter(EmailTemplate.automation_enabled == True)

    return query.order_by(EmailTemplate.created_at.desc()).first()


def build_candidate_email_context(db: Session, candidate: Candidate) -> dict:
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first() if candidate.job_id else None
    agency = db.query(Agency).filter(Agency.id == candidate.agency_id).first() if candidate.agency_id else None
    latest_interview = db.query(Interview).filter(
        Interview.candidate_id == candidate.id
    ).order_by(Interview.scheduled_at.desc()).first()

    interview_date = ""
    if latest_interview and latest_interview.scheduled_at:
        interview_date = latest_interview.scheduled_at.strftime("%B %d, %Y %I:%M %p")

    params = {
        "candidateId": candidate.id,
        "name": candidate.name,
        "email": candidate.email or "",
        "resumeText": candidate.resume_text or "",
    }
    if job:
        params["jobId"] = job.id
        params["jobTitle"] = job.title
        params["jobDescription"] = job.description or ""

    return {
        "candidate_name": candidate.name or "",
        "candidate_email": candidate.email or "",
        "candidate_phone": candidate.phone or "",
        "job_title": job.title if job else "",
        "company_name": job.company_name if job else "",
        "agency_name": agency.name if agency else "",
        "resume_score": candidate.resume_score or "",
        "score_threshold": candidate.score_threshold or "",
        "interview_date": interview_date,
        "slot_booking_url": settings.SLOT_BOOKING_URL or "",
        "interview_details_url": f"{settings.FRONTEND_URL}/interview?{urlencode(params)}" if settings.FRONTEND_URL else "",
        "current_date": datetime.utcnow().strftime("%B %d, %Y"),
        "candidate_stage": candidate.stage.value if candidate.stage else "",
    }


def render_email_template(db: Session, template: EmailTemplate, candidate: Candidate) -> dict:
    context = build_candidate_email_context(db, candidate)
    subject = render_template_content(template.subject, context)
    body = render_template_content(template.body, context)
    return {
        "subject": subject,
        "body": body,
        "variables": context,
    }


def _build_html_body(body: str) -> str:
    return f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 640px; margin: 0 auto; padding: 24px; white-space: pre-line;">
            {body.replace(chr(10), '<br>')}
        </div>
    </body>
    </html>
    """


def _log_email_attempt(
    db: Session,
    *,
    candidate: Candidate,
    template: Optional[EmailTemplate],
    email_type: str,
    subject: str,
    body: str,
    status: str,
    trigger_stage: Optional[str],
    trigger_source: str,
    error_message: Optional[str] = None,
) -> EmailCommunication:
    email_comm = EmailCommunication(
        agency_id=candidate.agency_id,
        candidate_id=candidate.id,
        template_id=template.id if template else None,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=email_type,
        subject=subject,
        body=body,
        trigger_stage=trigger_stage,
        trigger_source=trigger_source,
        error_message=error_message,
        status=status,
        sent_at=datetime.utcnow() if status == "sent" else None,
    )
    db.add(email_comm)
    return email_comm


def send_email_using_template(
    db: Session,
    *,
    candidate: Candidate,
    template: EmailTemplate,
    trigger_source: str = "manual",
) -> dict:
    rendered = render_email_template(db, template, candidate)
    subject = rendered["subject"]
    body = rendered["body"]
    email_type = template.name or template.template_type or "Custom Email"

    if not candidate.email:
        _log_email_attempt(
            db,
            candidate=candidate,
            template=template,
            email_type=email_type,
            subject=subject,
            body=body,
            status="failed",
            trigger_stage=template.trigger_stage,
            trigger_source=trigger_source,
            error_message="Candidate email is missing",
        )
        return {"success": False, "error": "Candidate email is missing"}

    if not settings.SENDGRID_API_KEY:
        _log_email_attempt(
            db,
            candidate=candidate,
            template=template,
            email_type=email_type,
            subject=subject,
            body=body,
            status="failed",
            trigger_stage=template.trigger_stage,
            trigger_source=trigger_source,
            error_message="SendGrid is not configured",
        )
        return {"success": False, "error": "SendGrid is not configured"}

    try:
        mail_message = Mail(
            from_email=(settings.FROM_EMAIL, settings.FROM_NAME),
            to_emails=candidate.email,
            subject=subject,
            html_content=_build_html_body(body),
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(mail_message)

        _log_email_attempt(
            db,
            candidate=candidate,
            template=template,
            email_type=email_type,
            subject=subject,
            body=body,
            status="sent",
            trigger_stage=template.trigger_stage,
            trigger_source=trigger_source,
        )
        return {
            "success": True,
            "subject": subject,
            "body": body,
            "template_id": template.id,
            "candidate_email": candidate.email,
        }
    except Exception as exc:
        _log_email_attempt(
            db,
            candidate=candidate,
            template=template,
            email_type=email_type,
            subject=subject,
            body=body,
            status="failed",
            trigger_stage=template.trigger_stage,
            trigger_source=trigger_source,
            error_message=str(exc),
        )
        return {"success": False, "error": str(exc), "subject": subject, "body": body}


def trigger_stage_automation(
    db: Session,
    *,
    candidate: Candidate,
    previous_stage: Optional[str],
    trigger_source: str,
) -> Optional[dict]:
    current_stage = candidate.stage.value if candidate.stage else None
    if not current_stage or current_stage == previous_stage:
        return None

    template = get_template_for_agency(
        db,
        candidate.agency_id,
        trigger_stage=current_stage,
        automation_only=True,
    )
    if not template:
        return None

    return send_email_using_template(
        db,
        candidate=candidate,
        template=template,
        trigger_source=trigger_source,
    )
