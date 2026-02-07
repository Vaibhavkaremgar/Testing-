from app.database import SessionLocal
from app.models import Candidate, Interview
import os

db = SessionLocal()

# Delete all interviews first (foreign key constraint)
interviews = db.query(Interview).all()
print(f"Deleting {len(interviews)} interviews...")
for interview in interviews:
    db.delete(interview)
db.commit()

# Get all candidates
candidates = db.query(Candidate).all()
print(f"Deleting {len(candidates)} candidates...")

# Delete resume files
deleted_files = 0
for candidate in candidates:
    if candidate.resume_file_path and os.path.exists(candidate.resume_file_path):
        try:
            os.remove(candidate.resume_file_path)
            deleted_files += 1
            print(f"  Deleted file: {candidate.resume_file_path}")
        except Exception as e:
            print(f"  Error deleting {candidate.resume_file_path}: {e}")
    
    db.delete(candidate)

db.commit()
print(f"\nDeleted {len(candidates)} candidates and {deleted_files} resume files")
print("Database is now clean and ready for fresh data")

db.close()
