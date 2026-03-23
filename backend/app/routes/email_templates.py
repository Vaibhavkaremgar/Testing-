from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import EmailTemplate, User
from app.schemas import EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse
from app.auth import get_current_active_user
from app.email_utils import get_default_template_variables

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])

@router.get("", response_model=List[EmailTemplateResponse])
def get_email_templates(
    skip: int = 0,
    limit: int = 100,
    template_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can access email templates")

    query = db.query(EmailTemplate).filter(EmailTemplate.agency_id == current_user.agency_id)
    
    if template_type:
        query = query.filter(EmailTemplate.template_type == template_type)
    
    templates = query.order_by(EmailTemplate.created_at.desc()).offset(skip).limit(limit).all()
    return templates

@router.get("/{template_id}", response_model=EmailTemplateResponse)
def get_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can access email templates")

    template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.agency_id == current_user.agency_id
    ).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.get("/meta/variables")
def get_email_template_variables(
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can access email template variables")
    return {"variables": get_default_template_variables()}

@router.post("", response_model=EmailTemplateResponse)
def create_email_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can create email templates")

    db_template = EmailTemplate(
        **template.model_dump(exclude={"agency_id"}),
        agency_id=current_user.agency_id,
        created_by_user_id=current_user.id
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
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can update email templates")

    db_template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.agency_id == current_user.agency_id
    ).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    update_data = template_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_template, field, value)
    
    db.commit()
    db.refresh(db_template)
    return db_template

@router.delete("/{template_id}")
def delete_email_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if not current_user.agency_id:
        raise HTTPException(status_code=403, detail="Only agency users can delete email templates")

    db_template = db.query(EmailTemplate).filter(
        EmailTemplate.id == template_id,
        EmailTemplate.agency_id == current_user.agency_id
    ).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(db_template)
    db.commit()
    return {"message": "Template deleted successfully"}
