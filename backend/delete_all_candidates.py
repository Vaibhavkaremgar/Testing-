"""Delete all candidates and resume files"""
from app.database import SessionLocal
from app.models import Candidate
import os

db = SessionLocal()

try:
    # Get all candidates
    candidates = db.query(Candidate).all()
    
    print(f"Found {len(candidates)} candidates to delete")
    
    # Delete resume files
    deleted_files = 0
    for candidate in candidates:
        if candidate.resume_file_path and os.path.exists(candidate.resume_file_path):
            try:
                os.remove(candidate.resume_file_path)
                deleted_files += 1
                print(f"Deleted file: {candidate.resume_file_path}")
            except Exception as e:
                print(f"Error deleting file {candidate.resume_file_path}: {e}")
    
    # Delete all candidates from database
    db.query(Candidate).delete()
    db.commit()
    
    print(f"\nDeleted {len(candidates)} candidates from database")
    print(f"Deleted {deleted_files} resume files")
    print("Database is now clean!")
    
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
