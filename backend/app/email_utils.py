from __future__ import annotations

from datetime import datetime
from typing import Optional
from urllib.parse import urlencode

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.mailer import is_email_configured, send_html_email
from app.models import Agency, Candidate, EmailCommunication, EmailTemplate, Interview, JobDescription


EMAIL_TEMPLATE_LABELS = {
    "resume_shortlisted_slot_selection": "Resume Shortlisted With Slot Selection",
    "resume_rejected": "Resume Rejected",
    "interview_scheduled": "Interview Scheduled",
    "selected": "Selected",
    "rejected": "Rejected",
}


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
    ]


def render_template_content(content: str, context: dict) -> str:
    rendered = content or ""
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value if value is not None else ""))
    return rendered


def get_template_for_agency(db: Session, agency_id, template_type: str) -> Optional[EmailTemplate]:
    if not agency_id:
        return None

    return db.query(EmailTemplate).filter(
        EmailTemplate.agency_id == agency_id,
        EmailTemplate.template_type == template_type,
        EmailTemplate.is_active == True
    ).order_by(EmailTemplate.created_at.desc()).first()


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
    }
    if job:
        params["jobId"] = job.id
        params["jobTitle"] = job.title

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
    }


def send_candidate_email_from_template(
    *,
    db: Session,
    candidate: Candidate,
    template_type: str,
    fallback_subject: Optional[str] = None,
    fallback_body: Optional[str] = None,
) -> dict:
    if not candidate.email:
        raise HTTPException(status_code=400, detail="Candidate email is missing")

    if not is_email_configured():
        raise HTTPException(status_code=500, detail="Email service is not configured")

    template = get_template_for_agency(db, candidate.agency_id, template_type)
    if not template and not (fallback_subject and fallback_body):
        raise HTTPException(status_code=404, detail=f"No active template found for {template_type}")

    context = build_candidate_email_context(db, candidate)
    subject = render_template_content(template.subject if template else fallback_subject, context)
    body = render_template_content(template.body if template else fallback_body, context)
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; white-space: pre-line;">
            {body.replace(chr(10), '<br>')}
        </div>
    </body>
    </html>
    """

    provider_message_id = send_html_email(
        to_email=candidate.email,
        subject=subject,
        html_content=html_body,
    )

    email_comm = EmailCommunication(
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=EMAIL_TEMPLATE_LABELS.get(template_type, template_type),
        status="sent",
        sent_at=datetime.utcnow(),
        provider_message_id=provider_message_id,
    )
    db.add(email_comm)

    return {
        "success": True,
        "subject": subject,
        "body": body,
        "template_id": template.id if template else None,
        "template_type": template_type,
    }
