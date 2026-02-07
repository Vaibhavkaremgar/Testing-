from app.database import SessionLocal
from app.models import Candidate

db = SessionLocal()

# Get ALL candidates
all_candidates = db.query(Candidate).all()

print(f"Total candidates: {len(all_candidates)}")

for c in all_candidates:
    print(f"\nCandidate: {c.name}")
    print(f"  ID: {c.candidate_id}")
    print(f"  Job ID: {c.job_id}")
    print(f"  Synced: {c.synced_to_sheets}")
    
    # Reset sync status
    c.synced_to_sheets = False

db.commit()
print("\nReset all candidates to unsynced")

db.close()
