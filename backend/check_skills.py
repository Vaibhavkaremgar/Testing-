"""Check what skills are in the database"""
from app.database import SessionLocal
from app.models import Candidate
from collections import Counter

db = SessionLocal()

candidates = db.query(Candidate).all()
print(f"Total candidates: {len(candidates)}")

all_skills = []
for candidate in candidates:
    if candidate.skills:
        print(f"\n{candidate.name}: {candidate.skills}")
        all_skills.extend(candidate.skills)

if all_skills:
    print(f"\n\nAll unique skills ({len(set(all_skills))}):")
    skill_counts = Counter(all_skills)
    for skill, count in skill_counts.most_common(30):
        print(f"  {skill}: {count}")
else:
    print("\nNo skills found in database")

db.close()
