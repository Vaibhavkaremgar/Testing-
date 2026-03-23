from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from uuid import UUID
import random
from app.database import get_db
from app.models import Interview, Candidate, CandidateStage, User
from app.schemas import InterviewCreate, InterviewUpdate, InterviewResponse, InterviewResultsUpdate
from app.auth import get_current_active_user

router = APIRouter(prefix="/interviews", tags=["Interviews"])

# Sample AI summaries for demo
SAMPLE_SUMMARIES = [
    "The candidate demonstrated strong technical skills and problem-solving abilities. They showed excellent communication and would be a good cultural fit for the team.",
    "Solid technical background with room for growth. The candidate was enthusiastic about the role and showed good understanding of the domain.",
    "Experienced professional with strong leadership qualities. Would be an asset to the team with their innovative approach to problem-solving.",
    "The candidate showed good potential but may need additional training in some areas. Overall positive impression with strong soft skills."
]

SAMPLE_TRANSCRIPTS = """
[00:00] Interviewer: Thank you for joining us today. Can you start by telling us about yourself?

[00:15] Candidate: Of course! I have over 5 years of experience in software development, specializing in full-stack applications. I'm passionate about building scalable systems and have led several successful projects.

[02:30] Interviewer: Can you walk us through a challenging project you've worked on?

[02:45] Candidate: Certainly. I led the development of a real-time analytics platform that processed millions of events daily. We faced challenges with data consistency and latency, which we solved using event sourcing and CQRS patterns.

[08:15] Interviewer: How do you approach problem-solving in your work?

[08:30] Candidate: I believe in breaking down complex problems into smaller, manageable pieces. I start by understanding the requirements, then research potential solutions, and finally implement with thorough testing.

[15:00] Interviewer: Where do you see yourself in the next few years?

[15:15] Candidate: I'm looking to grow into a technical leadership role where I can mentor others while continuing to contribute to architecture decisions.

[20:00] Interviewer: Do you have any questions for us?

[20:10] Candidate: Yes, I'd love to learn more about the team structure and the technologies you're currently using.
"""

@router.get("/count")
def get_interviews_count(
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole, JobDescription
    query = db.query(Interview)
    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if status:
        query = query.filter(Interview.status == status)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == agency_id)
    elif current_user.role == UserRole.ADMIN and current_user.agency_id:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == current_user.agency_id)
    elif current_user.role != UserRole.ADMIN:
        query = query.join(Candidate).filter(Candidate.assigned_to_user_id == current_user.id)
    return {"count": query.count()}

@router.get("", response_model=List[InterviewResponse])
def get_interviews(
    page: int = 1,
    limit: int = 10,
    candidate_id: Optional[UUID] = None,
    status: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole, JobDescription
    query = db.query(Interview)

    if candidate_id:
        query = query.filter(Interview.candidate_id == candidate_id)
    if status:
        query = query.filter(Interview.status == status)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == agency_id)
    elif current_user.role == UserRole.ADMIN and current_user.agency_id:
        query = query.join(Candidate).join(JobDescription, Candidate.job_id == JobDescription.id).filter(JobDescription.agency_id == current_user.agency_id)
    elif current_user.role != UserRole.ADMIN:
        query = query.join(Candidate).filter(Candidate.assigned_to_user_id == current_user.id)
    
    interviews = query.order_by(Interview.scheduled_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    result = []
    for interview in interviews:
        interview_dict = {
            "id": interview.id,
            "candidate_id": interview.candidate_id,
            "candidate_name": interview.candidate.name if interview.candidate else None,
            "interview_type": interview.interview_type,
            "scheduled_at": interview.scheduled_at,
            "duration_minutes": interview.duration_minutes,
            "meeting_link": interview.meeting_link,
            "status": interview.status,
            "video_url": interview.video_url,
            "transcript": interview.transcript,
            "ai_summary": interview.ai_summary,
            "interview_score": interview.interview_score,
            "feedback": interview.feedback,
            "technical_score": interview.technical_score,
            "communication_score": interview.communication_score,
            "culture_fit_score": interview.culture_fit_score,
            "created_at": interview.created_at
        }
        result.append(InterviewResponse(**interview_dict))
    
    return result

@router.get("/{interview_id}", response_model=InterviewResponse)
def get_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    interview_dict = {
        "id": interview.id,
        "candidate_id": interview.candidate_id,
        "candidate_name": interview.candidate.name if interview.candidate else None,
        "interview_type": interview.interview_type,
        "scheduled_at": interview.scheduled_at,
        "duration_minutes": interview.duration_minutes,
        "meeting_link": interview.meeting_link,
        "status": interview.status,
        "video_url": interview.video_url,
        "transcript": interview.transcript,
        "ai_summary": interview.ai_summary,
        "interview_score": interview.interview_score,
        "feedback": interview.feedback,
        "technical_score": interview.technical_score,
        "communication_score": interview.communication_score,
        "culture_fit_score": interview.culture_fit_score,
        "created_at": interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.post("/public", response_model=InterviewResponse)
def create_interview_public(
    interview: InterviewCreate,
    db: Session = Depends(get_db)
):
    """Public endpoint - no auth required. Create an interview record."""
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    db_interview = Interview(**interview.model_dump())
    db.add(db_interview)
    candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
    candidate.stage_updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_interview)

    return InterviewResponse(
        id=db_interview.id,
        candidate_id=db_interview.candidate_id,
        candidate_name=candidate.name,
        interview_type=db_interview.interview_type,
        scheduled_at=db_interview.scheduled_at,
        duration_minutes=db_interview.duration_minutes,
        meeting_link=db_interview.meeting_link,
        status=db_interview.status,
        video_url=db_interview.video_url,
        transcript=db_interview.transcript,
        ai_summary=db_interview.ai_summary,
        interview_score=db_interview.interview_score,
        feedback=db_interview.feedback,
        technical_score=db_interview.technical_score,
        communication_score=db_interview.communication_score,
        culture_fit_score=db_interview.culture_fit_score,
        created_at=db_interview.created_at
    )

@router.post("", response_model=InterviewResponse)
def create_interview(
    interview: InterviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Verify candidate exists
    candidate = db.query(Candidate).filter(Candidate.id == interview.candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_interview = Interview(**interview.model_dump())
    db.add(db_interview)
    
    # Update candidate stage
    candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
    candidate.stage_updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_interview)
    
    interview_dict = {
        "id": db_interview.id,
        "candidate_id": db_interview.candidate_id,
        "candidate_name": candidate.name,
        "interview_type": db_interview.interview_type,
        "scheduled_at": db_interview.scheduled_at,
        "duration_minutes": db_interview.duration_minutes,
        "meeting_link": db_interview.meeting_link,
        "status": db_interview.status,
        "video_url": db_interview.video_url,
        "transcript": db_interview.transcript,
        "ai_summary": db_interview.ai_summary,
        "interview_score": db_interview.interview_score,
        "feedback": db_interview.feedback,
        "technical_score": db_interview.technical_score,
        "communication_score": db_interview.communication_score,
        "culture_fit_score": db_interview.culture_fit_score,
        "created_at": db_interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.put("/{interview_id}", response_model=InterviewResponse)
def update_interview(
    interview_id: UUID,
    interview_update: InterviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    update_data = interview_update.model_dump(exclude_unset=True)
    
    for field, value in update_data.items():
        setattr(db_interview, field, value)
    
    # If status changed to completed, update candidate stage
    if update_data.get("status") == "completed":
        candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
        if candidate:
            candidate.stage = CandidateStage.INTERVIEWED
            candidate.stage_updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_interview)
    
    interview_dict = {
        "id": db_interview.id,
        "candidate_id": db_interview.candidate_id,
        "candidate_name": db_interview.candidate.name if db_interview.candidate else None,
        "interview_type": db_interview.interview_type,
        "scheduled_at": db_interview.scheduled_at,
        "duration_minutes": db_interview.duration_minutes,
        "meeting_link": db_interview.meeting_link,
        "status": db_interview.status,
        "video_url": db_interview.video_url,
        "transcript": db_interview.transcript,
        "ai_summary": db_interview.ai_summary,
        "interview_score": db_interview.interview_score,
        "feedback": db_interview.feedback,
        "technical_score": db_interview.technical_score,
        "communication_score": db_interview.communication_score,
        "culture_fit_score": db_interview.culture_fit_score,
        "created_at": db_interview.created_at
    }
    return InterviewResponse(**interview_dict)

@router.post("/{interview_id}/complete")
def complete_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Mark interview as completed and generate AI analysis"""
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    # Simulate AI analysis
    db_interview.status = "completed"
    db_interview.transcript = SAMPLE_TRANSCRIPTS
    db_interview.ai_summary = random.choice(SAMPLE_SUMMARIES)
    db_interview.interview_score = round(random.uniform(65, 95), 1)
    db_interview.technical_score = round(random.uniform(60, 98), 1)
    db_interview.communication_score = round(random.uniform(70, 95), 1)
    db_interview.culture_fit_score = round(random.uniform(65, 95), 1)
    db_interview.video_url = "https://example.com/interview-recording.mp4"
    
    # Update candidate stage
    candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
    if candidate:
        candidate.stage = CandidateStage.INTERVIEWED
        candidate.stage_updated_at = datetime.utcnow()
    
    # Deduct 1 credit from agency admin wallet
    from app.models import UserRole, WalletTransaction, TransactionType, JobDescription
    agency_id = None
    if candidate and candidate.job_id:
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            agency_id = job.agency_id
    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.agency_id == agency_id
    ).first()
    if admin:
        admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
        db.add(WalletTransaction(
            user_id=admin.id,
            agency_id=agency_id,
            amount=1,
            transaction_type=TransactionType.DEBIT,
            description=f"Interview completed - Candidate ID {db_interview.candidate_id}",
            balance_after=admin.wallet_balance
        ))
    db.commit()
    return {"message": "Interview completed and analyzed", "interview_id": interview_id, "wallet_balance": admin.wallet_balance if admin else None}

@router.post("/{interview_id}/results", response_model=InterviewResponse)
def receive_interview_results(
    interview_id: UUID,
    results: InterviewResultsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Receive video recording, transcript and AI analysis from external interview server"""
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    for field, value in results.model_dump(exclude_unset=True).items():
        setattr(db_interview, field, value)

    db_interview.status = "completed"

    candidate = db.query(Candidate).filter(Candidate.id == db_interview.candidate_id).first()
    if candidate:
        candidate.stage = CandidateStage.INTERVIEWED
        candidate.stage_updated_at = datetime.utcnow()

    # Deduct 1 credit from agency admin wallet
    from app.models import UserRole, WalletTransaction, TransactionType, JobDescription
    agency_id = None
    if candidate and candidate.job_id:
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            agency_id = job.agency_id
    admin = db.query(User).filter(
        User.role == UserRole.ADMIN,
        User.agency_id == agency_id
    ).first()
    if admin:
        admin.wallet_balance = max(0, (admin.wallet_balance or 0) - 1)
        db.add(WalletTransaction(
            user_id=admin.id,
            agency_id=agency_id,
            amount=1,
            transaction_type=TransactionType.DEBIT,
            description=f"Interview completed - Candidate ID {db_interview.candidate_id}",
            balance_after=admin.wallet_balance
        ))

    db.commit()
    db.refresh(db_interview)

    return InterviewResponse(
        id=db_interview.id,
        candidate_id=db_interview.candidate_id,
        candidate_name=candidate.name if candidate else None,
        interview_type=db_interview.interview_type,
        scheduled_at=db_interview.scheduled_at,
        duration_minutes=db_interview.duration_minutes,
        meeting_link=db_interview.meeting_link,
        status=db_interview.status,
        video_url=db_interview.video_url,
        transcript=db_interview.transcript,
        ai_summary=db_interview.ai_summary,
        interview_score=db_interview.interview_score,
        feedback=db_interview.feedback,
        technical_score=db_interview.technical_score,
        communication_score=db_interview.communication_score,
        culture_fit_score=db_interview.culture_fit_score,
        created_at=db_interview.created_at
    )

@router.delete("/{interview_id}")
def delete_interview(
    interview_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_interview = db.query(Interview).filter(Interview.id == interview_id).first()
    if not db_interview:
        raise HTTPException(status_code=404, detail="Interview not found")
    
    db.delete(db_interview)
    db.commit()
    return {"message": "Interview deleted successfully"}
