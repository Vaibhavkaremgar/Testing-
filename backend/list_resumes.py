from app.database import SessionLocal
from app.models import Candidate

db = SessionLocal()

candidates = db.query(Candidate).all()

print("\n" + "="*80)
print(f"TOTAL RESUMES IN DATABASE: {len(candidates)}")
print("="*80 + "\n")

if candidates:
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate.name}")
        print(f"   Email: {candidate.email or 'N/A'}")
        print(f"   Phone: {candidate.phone or 'N/A'}")
        print(f"   Job: {candidate.job.title if candidate.job else 'No job assigned'}")
        print(f"   Score: {candidate.resume_score if candidate.resume_score else 'Not scored'}")
        print(f"   Stage: {candidate.stage.value if candidate.stage else 'N/A'}")
        print(f"   Skills: {', '.join(candidate.skills[:3]) if candidate.skills else 'None'}{'...' if candidate.skills and len(candidate.skills) > 3 else ''}")
        print(f"   Resume File: {'Yes' if candidate.resume_file_path else 'No'}")
        print(f"   Created: {candidate.created_at.strftime('%Y-%m-%d %H:%M') if candidate.created_at else 'N/A'}")
        print("-" * 80)
else:
    print("❌ No resumes found in database!")
    print("\nTo add resumes:")
    print("1. Start the backend server")
    print("2. Start the frontend")
    print("3. Go to Resumes page and upload resumes")

db.close()

print("\n" + "="*80)
print(f"SUMMARY: {len(candidates)} total resumes")
print("="*80)
