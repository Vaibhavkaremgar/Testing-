from app.database import SessionLocal
from app.models import Candidate

db = SessionLocal()

# Get candidates with score >= 60
candidates = db.query(Candidate).filter(Candidate.resume_score >= 60).order_by(Candidate.resume_score.desc()).all()

print("\n" + "="*100)
print(f"RESUMES WITH SCORE >= 60: {len(candidates)} found")
print("="*100 + "\n")

if candidates:
    for i, candidate in enumerate(candidates, 1):
        print(f"\n{'#'*100}")
        print(f"#{i}. {candidate.name.upper()}")
        print(f"{'#'*100}\n")
        
        # Basic Info
        print(f"📧 Email: {candidate.email or 'N/A'}")
        print(f"📱 Phone: {candidate.phone or 'N/A'}")
        print(f"💼 Job Applied: {candidate.job.title if candidate.job else 'No job assigned'}")
        print(f"📅 Applied Date: {candidate.created_at.strftime('%Y-%m-%d %H:%M') if candidate.created_at else 'N/A'}")
        
        # Score Breakdown
        print(f"\n{'='*100}")
        print(f"🎯 OVERALL SCORE: {candidate.resume_score}/100 - {candidate.stage.value.upper() if candidate.stage else 'N/A'}")
        print(f"{'='*100}")
        
        # Skills
        print(f"\n💡 SKILLS ({len(candidate.skills) if candidate.skills else 0} total):")
        if candidate.skills:
            for idx, skill in enumerate(candidate.skills, 1):
                print(f"   {idx}. {skill}")
        else:
            print("   No skills extracted")
        
        # Summary
        print(f"\n📝 AI SUMMARY:")
        if candidate.summary:
            # Wrap text at 90 characters
            summary_lines = candidate.summary.split('. ')
            for line in summary_lines:
                if line.strip():
                    print(f"   • {line.strip()}.")
        else:
            print("   No summary available")
        
        # Resume Text Preview
        if candidate.resume_text:
            print(f"\n📄 RESUME PREVIEW (first 500 chars):")
            preview = candidate.resume_text[:500].replace('\n', ' ').strip()
            print(f"   {preview}...")
        
        # File Info
        print(f"\n📎 RESUME FILE:")
        print(f"   Path: {candidate.resume_file_path if candidate.resume_file_path else 'No file'}")
        print(f"   Status: {candidate.parsing_status.value if candidate.parsing_status else 'N/A'}")
        
        # Scoring Details (if available)
        print(f"\n📊 ESTIMATED SCORE BREAKDOWN:")
        score = candidate.resume_score or 0
        
        # Estimate breakdown based on score
        if score >= 75:
            print(f"   ✅ Skills Match: ~35-45/45 (Strong)")
            print(f"   ✅ Experience: ~20-25/25 (Excellent)")
            print(f"   ✅ Projects: ~12-15/15 (Good)")
            print(f"   ✅ Education: ~7-10/10 (Present)")
            print(f"   ✅ Soft Skills: ~3-5/5 (Good)")
        elif score >= 60:
            print(f"   ✅ Skills Match: ~25-35/45 (Good)")
            print(f"   ✅ Experience: ~15-20/25 (Moderate)")
            print(f"   ⚠️  Projects: ~8-12/15 (Fair)")
            print(f"   ✅ Education: ~5-8/10 (Present)")
            print(f"   ⚠️  Soft Skills: ~2-4/5 (Fair)")
        
        print(f"\n{'='*100}")
        print(f"RECOMMENDATION: {'🟢 SHORTLIST - Schedule Interview' if score >= 75 else '🟡 REVIEW - Phone Screening Recommended'}")
        print(f"{'='*100}\n")
        
else:
    print("❌ No resumes found with score >= 60!")
    print("\nPossible reasons:")
    print("1. No resumes uploaded yet")
    print("2. All resumes scored below 60")
    print("3. Resumes not evaluated yet (no job assigned)")

db.close()

print("\n" + "="*100)
print(f"TOTAL HIGH-SCORING RESUMES: {len(candidates)}")
print("="*100 + "\n")
