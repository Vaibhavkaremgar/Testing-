from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Candidate, Interview, CandidateStage, ParsingStatus
from datetime import datetime, timedelta
import random

def generate_bulk_data():
    db = SessionLocal()
    
    try:
        print("Generating bulk dummy data...")
        
        # Generate 100 more candidates
        companies = ["Google", "Meta", "Amazon", "Apple", "Microsoft", "Netflix", "Uber", "Airbnb", "Tesla", "Zoom"]
        roles = ["Software Engineer", "Senior Engineer", "Product Manager", "Data Scientist", "UX Designer", "DevOps Engineer"]
        locations = ["San Francisco", "New York", "Seattle", "Austin", "Los Angeles", "Remote"]
        skills_pool = ["Python", "JavaScript", "React", "Node.js", "SQL", "AWS", "Docker", "Kubernetes", "Machine Learning"]
        
        for i in range(100):
            candidate = Candidate(
                name=f"Test User {i+1}",
                email=f"test{i+1}@example.com",
                phone=f"+1-555-{random.randint(100, 999)}-{random.randint(1000, 9999)}",
                current_company=random.choice(companies),
                current_role=random.choice(roles),
                experience_years=random.randint(1, 10),
                location=random.choice(locations),
                parsing_status=ParsingStatus.COMPLETED,
                resume_score=round(random.uniform(50, 100), 1),
                skills=random.sample(skills_pool, k=random.randint(3, 6)),
                stage=random.choice(list(CandidateStage)),
                job_id=random.randint(1, 4),
                created_by=2
            )
            db.add(candidate)
        
        db.commit()
        print("Bulk data generated successfully!")
        
    except Exception as e:
        print(f"Error generating bulk data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    generate_bulk_data()