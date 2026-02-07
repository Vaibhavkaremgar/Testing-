#!/usr/bin/env python3
"""
Add decline reasons and source data to candidates
"""
import sys
sys.path.append('.')

from app.database import SessionLocal
from app.models import Candidate, CandidateStage
import random

def add_decline_and_source_data():
    db = SessionLocal()
    try:
        # Decline reasons (changed Skills Gap to Lack of Skills)
        decline_reasons = [
            "Lack of Skills",
            "Experience Mismatch",
            "Cultural Fit",
            "Salary Expectations",
            "Communication Issues"
        ]
        
        # Source options
        sources = [
            "LinkedIn",
            "Indeed",
            "Company Website",
            "Referral",
            "Job Board"
        ]
        
        # Get all candidates
        candidates = db.query(Candidate).all()
        
        updated_decline = 0
        updated_source = 0
        
        for candidate in candidates:
            # Add decline reason for rejected candidates
            if candidate.stage == CandidateStage.REJECTED and not candidate.decline_reason:
                candidate.decline_reason = random.choice(decline_reasons)
                updated_decline += 1
            
            # Update existing "Skills Gap" to "Lack of Skills"
            if candidate.decline_reason == "Skills Gap":
                candidate.decline_reason = "Lack of Skills"
                updated_decline += 1
            
            # Add source for all candidates if missing
            if not candidate.source:
                candidate.source = random.choice(sources)
                updated_source += 1
        
        db.commit()
        
        print(f"Updated {updated_decline} candidates with decline reasons")
        print(f"Updated {updated_source} candidates with source data")
        
        # Show distribution
        print("\nDecline Reasons Distribution:")
        for reason in decline_reasons:
            count = db.query(Candidate).filter(Candidate.decline_reason == reason).count()
            print(f"  {reason}: {count}")
        
        print("\nSource Distribution:")
        for source in sources:
            count = db.query(Candidate).filter(Candidate.source == source).count()
            print(f"  {source}: {count}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    add_decline_and_source_data()
