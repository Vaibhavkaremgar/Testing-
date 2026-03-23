from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user, get_current_admin_user
from app.database import get_db
from app.models import Candidate, EmailTemplate, User, UserRole
from app.notification_service import (
    EMAIL_TEMPLATE_STATUSES,
    SUPPORTED_PLACEHOLDERS,
    build_rendered_notification,
    ensure_default_email_templates,
)
from app.schemas import (
    EmailTemplateCreate,
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
    EmailTemplateResponse,
    EmailTemplateUpdate,
)

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])


def _apply_scope(query, current_user: User, agency_id: Optional[UUID] = None):
    if current_user.role == UserRole.SUPER_ADMIN:
        if agency_id is not None:
            return query.filter(EmailTemplate.agency_id == agency_id)
        return query

    if current_user.agency_id:
        return query.filter(EmailTemplate.agency_id == current_user.agency_id)
    return query.filter(EmailTemplate.agency_id.is_(None))


@router.get("/meta")
def get_template_meta(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ensure_default_email_templates(db)
    return {
        "statuses": EMAIL_TEMPLATE_STATUSES,
        "placeholders": SUPPORTED_PLACEHOLDERS,
        "can_manage": current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN],
    }


@router.get("", response_model=List[EmailTemplateResponse])
def get_templates(
    agency_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ensure_default_email_templates(db)
    query = _apply_scope(db.query(EmailTemplate), current_user, agency_id=agency_id)
    if status:
        query = query.filter(EmailTemplate.status == status)
    return query.order_by(EmailTemplate.is_default.desc(), EmailTemplate.created_at.desc()).all()


@router.get("/agency/{agency_id}/status/{status}", response_model=List[EmailTemplateResponse])
def get_templates_for_agency_status(
    agency_id: UUID,
    status: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    ensure_default_email_templates(db)
    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id != agency_id:
        raise HTTPException(status_code=403, detail="Outside your agency scope")

    agency_templates = db.query(EmailTemplate).filter(
        EmailTemplate.agency_id == agency_id,
        EmailTemplate.status == status,
    ).all()
    default_templates = db.query(EmailTemplate).filter(
        EmailTemplate.agency_id.is_(None),
        EmailTemplate.status == status,
    ).all()
    return agency_templates + [template for template in default_templates if template.id not in {item.id for item in agency_templates}]


@router.post("", response_model=EmailTemplateResponse)
def create_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    ensure_default_email_templates(db)
    agency_id = template.agency_id if current_user.role == UserRole.SUPER_ADMIN else current_user.agency_id
    is_default = bool(template.is_default and current_user.role == UserRole.SUPER_ADMIN and agency_id is None)
    db_template = EmailTemplate(
        **template.model_dump(exclude={"agency_id", "is_default"}),
        agency_id=agency_id,
        created_by_user_id=current_user.id,
        is_default=is_default,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.put("/{template_id}", response_model=EmailTemplateResponse)
def update_template(
    template_id: int,
    template_update: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user),
):
    db_template = _apply_scope(db.query(EmailTemplate), current_user).filter(EmailTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = template_update.model_dump(exclude_unset=True)
    if "is_default" in update_data and current_user.role != UserRole.SUPER_ADMIN:
        update_data.pop("is_default")

    for field, value in update_data.items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)
    return db_template


@router.post("/preview", response_model=EmailTemplatePreviewResponse)
def preview_template(
    request: EmailTemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    candidate = None
    if request.candidate_id:
        candidate = db.query(Candidate).filter(Candidate.id == request.candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id and candidate.agency_id != current_user.agency_id:
            raise HTTPException(status_code=403, detail="Candidate is outside your agency scope")
    else:
        candidate = Candidate(
            id=None,
            agency_id=request.agency_id if current_user.role == UserRole.SUPER_ADMIN else current_user.agency_id,
            candidate_id="PREVIEW-001",
            name="Preview Candidate",
            email="preview@example.com",
            phone="",
            resume_text="Preview resume text",
            skills=["Python", "FastAPI"],
            current_role="Software Engineer",
            created_by=current_user.id,
        )

    rendered = build_rendered_notification(
        db,
        candidate=candidate,
        status=request.status,
        user_id=request.user_id or current_user.id,
        extra_payload=request.payload,
    )
    db.rollback()

    return EmailTemplatePreviewResponse(
        subject=rendered["subject"],
        body=rendered["body"],
        payload=rendered["payload"],
        template_id=rendered["template"].id,
        used_default_template=rendered["used_default"],
    )
