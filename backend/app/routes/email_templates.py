from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_active_user
from app.database import get_db
from app.email_utils import get_default_template_variables, render_email_template, send_email_using_template
from app.models import Candidate, CandidateStage, EmailTemplate, User, UserRole
from app.schemas import (
    EmailTemplateCreate,
    EmailTemplatePreviewRequest,
    EmailTemplatePreviewResponse,
    EmailTemplateResponse,
    EmailTemplateSendRequest,
    EmailTemplateUpdate,
)

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])


def _ensure_template_management_access(current_user: User) -> None:
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        raise HTTPException(status_code=403, detail="Only admins can manage email templates")


def _apply_template_scope(query, current_user: User, agency_id: Optional[UUID] = None):
    if current_user.role == UserRole.SUPER_ADMIN:
        if agency_id:
            query = query.filter(EmailTemplate.agency_id == agency_id)
        return query

    if current_user.agency_id:
        return query.filter(EmailTemplate.agency_id == current_user.agency_id)

    return query.filter(EmailTemplate.agency_id.is_(None))


def _get_template_or_404(db: Session, template_id: int, current_user: User) -> EmailTemplate:
    query = _apply_template_scope(db.query(EmailTemplate), current_user)
    template = query.filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("", response_model=List[EmailTemplateResponse])
def get_email_templates(
    skip: int = 0,
    limit: int = 100,
    template_type: Optional[str] = None,
    trigger_stage: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    query = _apply_template_scope(db.query(EmailTemplate), current_user, agency_id=agency_id)

    if template_type:
        query = query.filter(EmailTemplate.template_type == template_type)
    if trigger_stage:
        query = query.filter(EmailTemplate.trigger_stage == trigger_stage)

    return query.order_by(EmailTemplate.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/meta")
def get_email_template_meta(
    current_user: User = Depends(get_current_active_user),
):
    return {
        "default_variables": get_default_template_variables(),
        "candidate_stages": [stage.value for stage in CandidateStage],
        "can_manage": current_user.role in [UserRole.ADMIN, UserRole.SUPER_ADMIN],
    }


@router.get("/{template_id}", response_model=EmailTemplateResponse)
def get_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    return _get_template_or_404(db, template_id, current_user)


@router.post("", response_model=EmailTemplateResponse)
def create_email_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_template_management_access(current_user)

    db_template = EmailTemplate(
        **template.model_dump(),
        agency_id=None if current_user.role == UserRole.SUPER_ADMIN else current_user.agency_id,
        created_by_user_id=current_user.id,
    )
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


@router.put("/{template_id}", response_model=EmailTemplateResponse)
def update_email_template(
    template_id: int,
    template_update: EmailTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_template_management_access(current_user)
    db_template = _get_template_or_404(db, template_id, current_user)

    update_data = template_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_template, field, value)

    db.commit()
    db.refresh(db_template)
    return db_template


@router.post("/{template_id}/preview", response_model=EmailTemplatePreviewResponse)
def preview_email_template(
    template_id: int,
    payload: EmailTemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    template = _get_template_or_404(db, template_id, current_user)
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id and candidate.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Candidate is outside your agency scope")

    rendered = render_email_template(db, template, candidate)
    return EmailTemplatePreviewResponse(**rendered)


@router.post("/{template_id}/send")
def send_email_template_to_candidate(
    template_id: int,
    payload: EmailTemplateSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_template_management_access(current_user)
    template = _get_template_or_404(db, template_id, current_user)
    candidate = db.query(Candidate).filter(Candidate.id == payload.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    if current_user.role != UserRole.SUPER_ADMIN and current_user.agency_id and candidate.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Candidate is outside your agency scope")

    result = send_email_using_template(
        db,
        candidate=candidate,
        template=template,
        trigger_source="manual",
    )
    db.commit()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to send email"))

    return result


@router.delete("/{template_id}")
def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _ensure_template_management_access(current_user)
    db_template = _get_template_or_404(db, template_id, current_user)
    db.delete(db_template)
    db.commit()
    return {"message": "Template deleted successfully"}
