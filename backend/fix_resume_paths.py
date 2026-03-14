"""
Fix resume file paths in database to match actual file locations
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models import Candidate
from app.config import settings

# Create database connection
engine = create_engine("sqlite:///./recruitment.db")
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def fix_paths():
    """Fix resume file paths to use only filename"""
    candidates = db.query(Candidate).filter(Candidate.resume_file_path.isnot(None)).all()
    
    fixed_count = 0
    missing_count = 0
    
    for candidate in candidates:
        old_path = candidate.resume_file_path
        
        # Extract just the filename
        filename = os.path.basename(old_path)
        
        # Check if file exists in uploads directory
        full_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        if os.path.exists(full_path):
            # Update to just store filename (relative to uploads dir)
            candidate.resume_file_path = filename
            fixed_count += 1
            print(f"✓ Fixed: {old_path} -> {filename}")
        else:
            missing_count += 1
            print(f"✗ Missing file: {filename} (candidate: {candidate.name})")
    
    db.commit()
    
    print(f"\n{'='*50}")
    print(f"Fixed: {fixed_count} paths")
    print(f"Missing: {missing_count} files")
    print(f"{'='*50}")

if __name__ == "__main__":
    try:
        fix_paths()
        db.close()
    except Exception as e:
        print(f"Error: {e}")
        db.rollback()
        db.close()
