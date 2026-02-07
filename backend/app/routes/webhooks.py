from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
from app.database import get_db
from app.models import Candidate, EmailCommunication, CandidateStage
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
    
    # Update stage based on threshold
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
        "stage": candidate.stage.value
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
    db.commit()
    
    return {
        "success": True,
        "candidate_id": candidate.candidate_id,
        "email_type": request.email_type,
        "status": request.status
    }

@router.get("/communications")
async def get_communications(
    db: Session = Depends(get_db)
):
    """
    Get all email communications for Communications tab
    """
    communications = db.query(EmailCommunication).order_by(
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
