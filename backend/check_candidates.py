from app.database import SessionLocal
from app.models import Candidate

db = SessionLocal()

# Get all candidates
candidates = db.query(Candidate).all()

print(f"Total candidates: {len(candidates)}")

for c in candidates:
    print(f"\nCandidate: {c.name}")
    print(f"  Candidate ID: {c.candidate_id}")
    print(f"  Email: {c.email}")
    print(f"  Phone: {c.phone}")
    print(f"  Job ID: {c.job_id}")
    print(f"  Job: {c.job.title if c.job else 'None'}")
    print(f"  Synced: {c.synced_to_sheets}")

db.close()
