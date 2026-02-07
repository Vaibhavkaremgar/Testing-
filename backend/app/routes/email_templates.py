from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.database import get_db
from app.models import EmailTemplate, User
from app.schemas import EmailTemplateCreate, EmailTemplateUpdate, EmailTemplateResponse
from app.auth import get_current_active_user

router = APIRouter(prefix="/email-templates", tags=["Email Templates"])

@router.get("", response_model=List[EmailTemplateResponse])
def get_email_templates(
    skip: int = 0,
    limit: int = 100,
    template_type: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(EmailTemplate)
    
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
    template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template

@router.post("", response_model=EmailTemplateResponse)
def create_email_template(
    template: EmailTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_template = EmailTemplate(**template.model_dump())
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
    db_template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
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
    db_template = db.query(EmailTemplate).filter(EmailTemplate.id == template_id).first()
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(db_template)
    db.commit()
    return {"message": "Template deleted successfully"}
