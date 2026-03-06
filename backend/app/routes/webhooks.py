from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import Candidate, EmailCommunication, CandidateStage
from app.auth import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/webhook", tags=["N8N Webhooks"])

class ScoreUpdateRequest(BaseModel):
    candidate_id: str  # Candidate ID from sheet
    score: float

class EmailLogRequest(BaseModel):
    candidate_id: str
    email_type: str  # "offer_letter", "rejection", "interview_invitation"
    status: str  # "sent", "failed"

@router.post("/update-score")
async def update_candidate_score(
    request: ScoreUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    N8N webhook endpoint to update candidate score from Google Sheets
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == request.candidate_id
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Update score
    candidate.resume_score = request.score
    
    # Check if candidate has received any emails (primary method)
    email_sent = db.query(EmailCommunication).filter(
        EmailCommunication.candidate_id == candidate.id,
        EmailCommunication.status == "sent"
    ).first()
    
    # Only update stage based on score if NO email has been sent (fallback)
    if not email_sent:
        if candidate.score_threshold:
            if request.score >= candidate.score_threshold:
                candidate.stage = CandidateStage.SHORTLISTED
            else:
                candidate.stage = CandidateStage.REJECTED
    
    db.commit()
    db.refresh(candidate)
    
    return {
        "success": True,
        "candidate_id": candidate.candidate_id,
        "score": candidate.resume_score,
        "stage": candidate.stage.value,
        "stage_source": "email" if email_sent else "score"
    }

@router.post("/log-email")
async def log_email_communication(
    request: EmailLogRequest,
    db: Session = Depends(get_db)
):
    """
    N8N webhook endpoint to log email communications
    """
    candidate = db.query(Candidate).filter(
        Candidate.candidate_id == request.candidate_id
    ).first()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Create email communication log
    email_comm = EmailCommunication(
        candidate_id=candidate.id,
        candidate_name=candidate.name,
        candidate_email=candidate.email,
        email_type=request.email_type,
        status=request.status,
        sent_at=datetime.utcnow() if request.status == "sent" else None
    )
    
    db.add(email_comm)
    
    # Auto-update candidate stage based on email type when email is sent
    if request.status == "sent":
        email_type_lower = request.email_type.lower().replace(" ", "_")
        if email_type_lower == "slot_selection_email" or request.email_type == "Slot Selection Email":
            candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
            candidate.stage_updated_at = datetime.utcnow()
        elif email_type_lower == "rejection_email" or request.email_type == "Rejection Email":
            candidate.stage = CandidateStage.REJECTED
            candidate.stage_updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "candidate_id": candidate.candidate_id,
        "email_type": request.email_type,
        "status": request.status,
        "stage_updated": candidate.stage.value if request.status == "sent" else None
    }

@router.get("/communications")
async def get_communications(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get all email communications for Communications tab
    Admin sees all, non-admin users see only their assigned candidates
    """
    from app.models import UserRole
    
    query = db.query(EmailCommunication)
    
    # Filter by assigned candidates for non-admin users
    if current_user.role != UserRole.ADMIN:
        query = query.join(Candidate).filter(Candidate.assigned_to_user_id == current_user.id)
    
    communications = query.order_by(
        EmailCommunication.created_at.desc()
    ).all()
    
    return [
        {
            "id": comm.id,
            "candidate": comm.candidate_name,
            "email": comm.candidate_email,
            "type": comm.email_type.replace("_", " ").title(),
            "status": comm.status.title(),
            "date": comm.sent_at.strftime("%Y-%m-%d") if comm.sent_at else comm.created_at.strftime("%Y-%m-%d")
        }
        for comm in communications
    ]

@router.delete("/communications/{comm_id}")
async def delete_communication(
    comm_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete an email communication record
    """
    comm = db.query(EmailCommunication).filter(EmailCommunication.id == comm_id).first()
    
    if not comm:
        raise HTTPException(status_code=404, detail="Communication not found")
    
    db.delete(comm)
    db.commit()
    
    return {"success": True, "message": "Communication deleted successfully"}
