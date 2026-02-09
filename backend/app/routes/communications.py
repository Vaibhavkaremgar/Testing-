from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List
from datetime import datetime
from app.database import get_db
from app.models import EmailCommunication, Candidate
from app.schemas import EmailCommunicationCreate, EmailCommunicationResponse, EmailCommunicationUpdate
from app.auth import get_current_user

router = APIRouter(prefix="/api/communications", tags=["communications"])

@router.get("", response_model=List[EmailCommunicationResponse])
def get_communications(
    candidate_id: int = None,
    status: str = None,
    email_type: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(EmailCommunication)
    if candidate_id:
        query = query.filter(EmailCommunication.candidate_id == candidate_id)
    if status:
        query = query.filter(EmailCommunication.status == status)
    if email_type:
        query = query.filter(EmailCommunication.email_type == email_type)
    return query.order_by(desc(EmailCommunication.created_at)).all()

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
    candidate_id = payload.get("candidate_id")
    candidate_string_id = payload.get("candidate_string_id")  # For Candidate_ID from sheets
    email_type = payload.get("email_type")
    
    if not email_type:
        raise HTTPException(status_code=400, detail="email_type required")
    
    # Find candidate by database ID or Candidate_ID string
    candidate = None
    if candidate_id:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    elif candidate_string_id:
        candidate = db.query(Candidate).filter(Candidate.candidate_id == candidate_string_id).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    comm = EmailCommunication(
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=email_type,
        status="sent",
        sent_at=datetime.utcnow()
    )
    db.add(comm)
    db.commit()
    
    return {
        "success": True,
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "email_type": email_type
    }
