#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.database import SessionLocal
from app.models import Candidate, CandidateStage
import random

db = SessionLocal()

# Decline reasons
decline_reasons = [
    "Lack of Skills",
    "Experience Mismatch", 
    "Cultural Fit",
    "Salary Expectations",
    "Communication Issues"
]

# Get all candidates
candidates = db.query(Candidate).all()
print(f"Total candidates: {len(candidates)}")

# Count by stage
for stage in CandidateStage:
    count = db.query(Candidate).filter(Candidate.stage == stage).count()
    print(f"{stage.value}: {count}")

# Get rejected candidates
rejected = db.query(Candidate).filter(Candidate.stage == CandidateStage.REJECTED).all()
print(f"\nRejected candidates: {len(rejected)}")

# Add decline reasons to rejected candidates
if len(rejected) > 0:
    for candidate in rejected:
        if not candidate.decline_reason:
            candidate.decline_reason = random.choice(decline_reasons)
    
    db.commit()
    print(f"Added decline reasons to {len(rejected)} rejected candidates")
    
    # Show distribution
    print("\nDecline Reasons Distribution:")
    for reason in decline_reasons:
        count = db.query(Candidate).filter(Candidate.decline_reason == reason).count()
        if count > 0:
            print(f"  {reason}: {count}")

db.close()
