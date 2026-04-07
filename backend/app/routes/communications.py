from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from app.database import get_db
from app.models import EmailCommunication, Candidate, UserRole
from app.schemas import EmailCommunicationCreate, EmailCommunicationResponse, EmailCommunicationUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/api/communications", tags=["communications"])

@router.get("", response_model=List[EmailCommunicationResponse])
def get_communications(
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    email_type: Optional[str] = None,
    client: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    offset: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    from app.models import JobDescription
    query = db.query(EmailCommunication)
    
    # Filter by assigned candidates for non-admin users
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        query = query.join(Candidate).filter(Candidate.assigned_to_user_id == current_user.id)
    elif current_user.role == UserRole.ADMIN and current_user.agency_id:
        query = query.filter(EmailCommunication.agency_id == current_user.agency_id)
    
    if candidate_id:
        query = query.filter(EmailCommunication.candidate_id == candidate_id)
    if status:
        query = query.filter(EmailCommunication.status == status)
    if email_type:
        query = query.filter(EmailCommunication.email_type == email_type)
    if client:
        if current_user.role == UserRole.ADMIN:
            query = query.join(Candidate).join(JobDescription).filter(JobDescription.company_name == client)
        else:
            query = query.join(JobDescription).filter(JobDescription.company_name == client)
    
    effective_offset = offset if offset is not None else max(0, (page - 1) * limit)
    return query.order_by(desc(EmailCommunication.created_at)).offset(effective_offset).limit(limit).all()


@router.delete("/{comm_id}")
def delete_communication(
    comm_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    comm = db.query(EmailCommunication).filter(EmailCommunication.id == comm_id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")

    if current_user.role == UserRole.ADMIN and current_user.agency_id and comm.agency_id != current_user.agency_id:
        raise HTTPException(status_code=403, detail="Communication is outside your agency scope")
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        candidate = db.query(Candidate).filter(Candidate.id == comm.candidate_id).first()
        if not candidate or candidate.assigned_to_user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Communication is outside your scope")

    db.delete(comm)
    db.commit()
    return {"message": "Communication deleted successfully"}

@router.post("", response_model=EmailCommunicationResponse)
def create_communication(
    comm: EmailCommunicationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == comm.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_comm = EmailCommunication(
        agency_id=candidate.agency_id,
        candidate_id=comm.candidate_id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=comm.email_type,
        status="pending"
    )
    db.add(db_comm)
    db.commit()
    db.refresh(db_comm)
    return db_comm

@router.patch("/{comm_id}", response_model=EmailCommunicationResponse)
def update_communication(
    comm_id: int,
    update: EmailCommunicationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    comm = db.query(EmailCommunication).filter(EmailCommunication.id == comm_id).first()
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    
    if update.status:
        comm.status = update.status
        if update.status == "sent":
            comm.sent_at = datetime.utcnow()
    
    db.commit()
    db.refresh(comm)
    return comm

@router.post("/webhook/n8n")
def n8n_webhook(payload: dict, db: Session = Depends(get_db)):
    """N8N webhook endpoint to trigger email communications"""
    from app.models import CandidateStage
    
    candidate_id = payload.get("candidate_id")
    candidate_string_id = payload.get("candidate_string_id")
    email_type = payload.get("email_type")
    
    if not email_type:
        return {"success": False, "error": "email_type required"}
    
    candidate = None
    if candidate_id:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    elif candidate_string_id:
        candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_string_id).first()
    
    if not candidate:
        return {"success": False, "error": f"Candidate not found"}
    
    comm = EmailCommunication(
        agency_id=candidate.agency_id,
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=email_type,
        status="sent",
        sent_at=datetime.utcnow()
    )
    db.add(comm)
    
    if email_type == "slot_selection":
        candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
    elif email_type == "rejection":
        candidate.stage = CandidateStage.REJECTED
    
    db.commit()
    
    return {
        "success": True,
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "email_type": email_type
    }
