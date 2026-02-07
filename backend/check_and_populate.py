#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.database import SessionLocal, engine
from app.models import Base, Candidate, User, JobDescription, CandidateStage, ParsingStatus, UserRole
from app.auth import get_password_hash
from sqlalchemy import text
import random

def check_and_populate_db():
    """Check database and populate with test data if needed"""
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check candidates count
        count = db.query(Candidate).count()
        print(f'Current candidates count: {count}')
        
        if count == 0:
            print("No candidates found. Creating test data...")
            
            # Create a test user if none exists
            user_count = db.query(User).count()
            if user_count == 0:
                test_user = User(
                    email="recruiter@talentai.com",
                    hashed_password=get_password_hash("recruiter123"),
                    full_name="Test Recruiter",
                    role=UserRole.RECRUITER
                )
                db.add(test_user)
                db.commit()
                print("Created test user")
            
            # Create a test job if none exists
            job_count = db.query(JobDescription).count()
            if job_count == 0:
                test_job = JobDescription(
                    title="Software Engineer",
                    department="Engineering",
                    location="San Francisco, CA",
                    employment_type="Full-time",
                    experience_required="3+ years",
                    salary_range="$120,000 - $160,000",
                    description="Looking for a skilled software engineer",
                    requirements="Bachelor's degree, 3+ years experience",
                    responsibilities="Develop software applications",
                    skills=["Python", "JavaScript", "React", "SQL"]
                )
                db.add(test_job)
                db.commit()
                print("Created test job")
            
            # Create test candidates
            test_candidates = [
                ("John Smith", "john.smith@email.com", "+1-555-123-4567"),
                ("Jane Doe", "jane.doe@email.com", "+1-555-234-5678"),
                ("Mike Johnson", "mike.j@email.com", "+1-555-345-6789"),
                ("Sarah Wilson", "sarah.w@email.com", "+1-555-456-7890"),
                ("David Brown", "david.b@email.com", "+1-555-567-8901"),
            ]
            
            for name, email, phone in test_candidates:
                candidate = Candidate(
                    name=name,
                    email=email,
                    phone=phone,
                    current_company="Tech Corp",
                    current_role="Software Engineer",
                    experience_years=random.randint(2, 8),
                    location="San Francisco, CA",
                    parsing_status=ParsingStatus.COMPLETED,
                    resume_score=round(random.uniform(70, 95), 1),
                    skills=["Python", "JavaScript", "React"],
                    stage=CandidateStage.UPLOADED,
                    job_id=1,
                    created_by=1,
                    synced_to_sheets=False  # Not synced yet
                )
                db.add(candidate)
            
            db.commit()
            print(f"Created {len(test_candidates)} test candidates")
        
        # Check final count and sync status
        total = db.query(Candidate).count()
        unsynced = db.query(Candidate).filter(
            (Candidate.synced_to_sheets == False) | 
            (Candidate.synced_to_sheets == None)
        ).count()
        
        print(f"Total candidates: {total}")
        print(f"Unsynced candidates: {unsynced}")
        
        # Show some candidates
        candidates = db.query(Candidate).limit(3).all()
        for c in candidates:
            print(f"- {c.name} (ID: {c.id}, Candidate_ID: {c.candidate_id}, Synced: {c.synced_to_sheets})")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    check_and_populate_db()