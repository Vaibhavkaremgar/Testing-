from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import secrets
from app.database import get_db
from app.models import Interview, Candidate, JobDescription, User
from app.auth import get_current_active_user
from pydantic import BaseModel

router = APIRouter(prefix="/api/async-interviews", tags=["async_interviews"])

class AsyncInterviewCreate(BaseModel):
    candidate_id: int
    interview_type: str = "async"
    duration_minutes: int = 60
    expires_in_days: int = 7

class AsyncAnswerSubmit(BaseModel):
    question_id: int
    answer: str
    time_taken_seconds: Optional[int] = None

@router.post("/create")
def create_async_interview(
    data: AsyncInterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Create async interview and generate unique link for candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == data.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if not candidate.job_id:
        raise HTTPException(status_code=400, detail="Candidate must be associated with a job")
    
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
    if not job or not job.interview_questions:
        raise HTTPException(status_code=400, detail="Job has no interview questions configured")
    
    # Generate unique token
    token = secrets.token_urlsafe(32)
<<<<<<< HEAD
    # async_link = f"http://localhost:5173/async-interview/{token}"
    async_link = f"https://glistening-youth-production.up.railway.app/async-interview/{token}"
=======
    async_link = f"http://localhost:5173/async-interview/{token}"
>>>>>>> 8c388104a03f506429820a154d4322d9bf5b4396
    expires_at = datetime.utcnow() + timedelta(days=data.expires_in_days)
    
    interview = Interview(
        candidate_id=data.candidate_id,
        interview_type=data.interview_type,
        duration_minutes=data.duration_minutes,
        is_async=True,
        async_token=token,
        async_link=async_link,
        async_expires_at=expires_at,
        status="scheduled"
    )
    
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    return {
        "interview_id": interview.id,
        "async_link": async_link,
        "expires_at": expires_at,
        "candidate_name": candidate.name,
        "candidate_email": candidate.email
    }

@router.get("/token/{token}")
def get_async_interview_by_token(token: str, db: Session = Depends(get_db)):
    """Candidate accesses interview via unique token (no auth required)"""
    interview = db.query(Interview).filter(Interview.async_token == token).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if interview.async_expires_at < datetime.utcnow():
        interview.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Interview link has expired")
    
    if interview.status == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")
    
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
    
    # Mark as in_progress on first access
    if interview.status == "scheduled" and not interview.async_started_at:
        interview.status = "in_progress"
        interview.async_started_at = datetime.utcnow()
        db.commit()
    
    return {
        "interview_id": interview.id,
        "candidate_name": candidate.name,
        "job_title": job.title,
        "company_name": job.company_name,
        "questions": job.interview_questions,
        "duration_minutes": interview.duration_minutes,
        "started_at": interview.async_started_at,
        "status": interview.status
    }

@router.post("/token/{token}/submit")
def submit_async_answers(
    token: str,
    answers: List[AsyncAnswerSubmit],
    db: Session = Depends(get_db)
):
    """Candidate submits answers (no auth required)"""
    interview = db.query(Interview).filter(Interview.async_token == token).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    if interview.status == "completed":
        raise HTTPException(status_code=400, detail="Interview already completed")
    
    if interview.async_expires_at < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Interview link has expired")
    
    # Store answers
    interview.async_answers = [ans.model_dump() for ans in answers]
    interview.async_completed_at = datetime.utcnow()
    interview.status = "completed"
    
    db.commit()
    
    return {"message": "Answers submitted successfully", "completed_at": interview.async_completed_at}

@router.get("/candidate/{candidate_id}")
def get_candidate_async_interviews(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get all async interviews for a candidate"""
    interviews = db.query(Interview).filter(
        Interview.candidate_id == candidate_id,
        Interview.is_async == True
    ).all()
    
    return [{
        "id": i.id,
        "status": i.status,
        "async_link": i.async_link,
        "created_at": i.created_at,
        "started_at": i.async_started_at,
        "completed_at": i.async_completed_at,
        "expires_at": i.async_expires_at,
        "answers": i.async_answers
    } for i in interviews]

@router.get("/{interview_id}/answers")
def get_interview_answers(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Recruiter views candidate's answers"""
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
    
    return {
        "interview_id": interview.id,
        "candidate_name": candidate.name,
        "job_title": job.title,
        "questions": job.interview_questions,
        "answers": interview.async_answers,
        "started_at": interview.async_started_at,
        "completed_at": interview.async_completed_at,
        "status": interview.status
    }
