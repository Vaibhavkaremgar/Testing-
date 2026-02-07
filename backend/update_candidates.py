#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import Candidate

def update_candidates():
    db = SessionLocal()
    try:
        # Update all candidates that don't have a score_threshold
        candidates = db.query(Candidate).filter(Candidate.score_threshold.is_(None)).all()
        
        for candidate in candidates:
            candidate.score_threshold = 60.0  # Default threshold
        
        db.commit()
        print(f"Updated {len(candidates)} candidates with default score_threshold")
        
    except Exception as e:
        print(f"Error updating candidates: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    update_candidates()