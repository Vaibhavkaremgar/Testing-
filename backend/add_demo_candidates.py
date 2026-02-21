"""
Add demo candidates to all pipeline stages
Run: python add_demo_candidates.py
"""
from app.database import SessionLocal
from app.models import Candidate, CandidateStage, ParsingStatus
from datetime import datetime

db = SessionLocal()

demo_candidates = [
    {"name": "Amit Kumar", "email": "amit.k@email.com", "phone": "+91-9876543210", "stage": CandidateStage.APPLIED, "resume_score": 75, "skills": ["Python", "Django", "PostgreSQL"]},
    {"name": "Priya Sharma", "email": "priya.s@email.com", "phone": "+91-9876543211", "stage": CandidateStage.APPLIED, "resume_score": 68, "skills": ["Java", "Spring Boot", "MySQL"]},
    {"name": "Rahul Verma", "email": "rahul.v@email.com", "phone": "+91-9876543212", "stage": CandidateStage.SHORTLISTED, "resume_score": 82, "skills": ["Python", "FastAPI", "Docker"]},
    {"name": "Sneha Patel", "email": "sneha.p@email.com", "phone": "+91-9876543213", "stage": CandidateStage.SHORTLISTED, "resume_score": 79, "skills": ["Node.js", "React", "MongoDB"]},
    {"name": "Vikram Singh", "email": "vikram.s@email.com", "phone": "+91-9876543214", "stage": CandidateStage.RESUME_REJECTED, "resume_score": 42, "skills": ["HTML", "CSS"]},
    {"name": "Anjali Reddy", "email": "anjali.r@email.com", "phone": "+91-9876543215", "stage": CandidateStage.RESUME_REJECTED, "resume_score": 38, "skills": ["JavaScript"]},
    {"name": "Karthik Rao", "email": "karthik.r@email.com", "phone": "+91-9876543216", "stage": CandidateStage.INTERVIEW_SCHEDULED, "resume_score": 85, "skills": ["Python", "AWS", "Kubernetes"]},
    {"name": "Divya Nair", "email": "divya.n@email.com", "phone": "+91-9876543217", "stage": CandidateStage.INTERVIEW_SCHEDULED, "resume_score": 77, "skills": ["Java", "Microservices", "Redis"]},
    {"name": "Arjun Mehta", "email": "arjun.m@email.com", "phone": "+91-9876543218", "stage": CandidateStage.INTERVIEW_RESCHEDULED, "resume_score": 73, "skills": ["PHP", "Laravel", "MySQL"]},
    {"name": "Pooja Gupta", "email": "pooja.g@email.com", "phone": "+91-9876543219", "stage": CandidateStage.INTERVIEWED, "resume_score": 88, "skills": ["Python", "Django", "PostgreSQL", "Docker"]},
    {"name": "Sanjay Kumar", "email": "sanjay.k@email.com", "phone": "+91-9876543220", "stage": CandidateStage.INTERVIEWED, "resume_score": 81, "skills": ["Java", "Spring Boot", "Kafka"]},
    {"name": "Neha Joshi", "email": "neha.j@email.com", "phone": "+91-9876543221", "stage": CandidateStage.NO_SHOW, "resume_score": 70, "skills": ["Node.js", "Express"]},
    {"name": "Ravi Desai", "email": "ravi.d@email.com", "phone": "+91-9876543222", "stage": CandidateStage.SELECTED, "resume_score": 92, "skills": ["Python", "FastAPI", "PostgreSQL", "AWS", "Docker"]},
    {"name": "Kavita Shah", "email": "kavita.s@email.com", "phone": "+91-9876543223", "stage": CandidateStage.SELECTED, "resume_score": 89, "skills": ["Java", "Spring Boot", "Microservices", "Kubernetes"]},
    {"name": "Manish Agarwal", "email": "manish.a@email.com", "phone": "+91-9876543224", "stage": CandidateStage.REJECTED, "resume_score": 65, "skills": ["Python", "Flask"]},
    {"name": "Deepa Iyer", "email": "deepa.i@email.com", "phone": "+91-9876543225", "stage": CandidateStage.REJECTED, "resume_score": 58, "skills": ["PHP", "MySQL"]},
]

try:
    # Check if demo candidates already exist
    existing = db.query(Candidate).filter(Candidate.candidate_id.like('DEM%')).first()
    if existing:
        print("Demo candidates already exist. Delete them first or use different IDs.")
        db.close()
        exit()
    
    for i, candidate_data in enumerate(demo_candidates, 1):
        candidate = Candidate(
            candidate_id=f"DEM{i}",
            name=candidate_data["name"],
            email=candidate_data["email"],
            phone=candidate_data["phone"],
            stage=candidate_data["stage"],
            resume_score=candidate_data["resume_score"],
            skills=candidate_data["skills"],
            parsing_status=ParsingStatus.COMPLETED,
            job_id=1,
            created_by=1,
            experience_years=3.0,
            location="India"
        )
        db.add(candidate)
    
    db.commit()
    print(f"[OK] Added {len(demo_candidates)} demo candidates across all pipeline stages")
    
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
