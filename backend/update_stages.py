"""Update candidate stages based on new thresholds"""
from app.database import SessionLocal
from app.models import Candidate, CandidateStage

def update_candidate_stages():
    db = SessionLocal()
    try:
        candidates = db.query(Candidate).all()
        updated = 0
        
        for candidate in candidates:
            if candidate.resume_score is None:
                continue
            
            score = candidate.resume_score
            old_stage = candidate.stage
            
            # Apply new thresholds
            if score >= 70:
                new_stage = CandidateStage.SHORTLISTED
            elif score >= 55:
                new_stage = CandidateStage.POTENTIAL_FIT
            elif score >= 35:
                new_stage = CandidateStage.REVIEW
            else:
                new_stage = CandidateStage.REJECTED
            
            if old_stage != new_stage:
                candidate.stage = new_stage
                updated += 1
                print(f"Updated {candidate.name}: {score} -> {old_stage.value} to {new_stage.value}")
        
        db.commit()
        print(f"\nUpdated {updated} candidates with new stage thresholds")
        
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_candidate_stages()
