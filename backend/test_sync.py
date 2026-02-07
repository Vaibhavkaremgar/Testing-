from app.database import SessionLocal
from app.models import Candidate
from app.google_sheets import sheets_service

db = SessionLocal()

# Get unsynced candidates
unsynced = db.query(Candidate).filter(
    (Candidate.synced_to_sheets == False) | 
    (Candidate.synced_to_sheets == None)
).all()

print(f"Found {len(unsynced)} unsynced candidates")

for c in unsynced:
    print(f"\nCandidate: {c.name}")
    print(f"  ID: {c.candidate_id}")
    print(f"  Job ID: {c.job_id}")
    print(f"  Job: {c.job.title if c.job else 'None'}")
    print(f"  Resume text length: {len(c.resume_text) if c.resume_text else 0}")

if unsynced:
    print("\n" + "="*50)
    print("Testing sync...")
    print("="*50)
    result = sheets_service.sync_candidates_to_sheet(unsynced)
    print(f"\nResult: {result}")

db.close()
