"""Clean non-skill terms from candidate skills in database"""
from app.database import SessionLocal
from app.models import Candidate
import json

# Blacklist of non-skill terms
BLACKLIST = {
    'engineering', 'communication', 'course', 'institute', 'university', 'board', 'year', 'of',
    'telangana', 'state', 'andhra', 'pradesh', 'karnataka', 'maharashtra', 'tamil', 'nadu',
    'delhi', 'mumbai', 'bangalore', 'hyderabad', 'chennai', 'kolkata', 'pune', 'ahmedabad',
    'education', 'experience', 'projects', 'summary', 'objective', 'profile', 'resume',
    'curriculum', 'vitae', 'personal', 'details', 'information', 'contact', 'address',
    'date', 'birth', 'gender', 'nationality', 'marital', 'status', 'languages', 'hobbies',
    'interests', 'references', 'declaration', 'certifications', 'achievements', 'awards',
    'responsibilities', 'duties', 'role', 'position', 'designation', 'company', 'organization',
    'duration', 'period', 'from', 'to', 'present', 'current', 'previous', 'former',
    'bachelor', 'master', 'degree', 'diploma', 'phd', 'doctorate', 'undergraduate', 'graduate',
    'cgpa', 'percentage', 'marks', 'grade', 'score', 'result', 'passed', 'completed',
    'school', 'college', 'university', 'institution', 'academy', 'center', 'centre',
    'instituteuniversity', 'boardyear', 'enginnering', 'year of', 'institute university',
    'enginnering)', 'course  institute  university/board  year  of', 'telangana state',
    'board of', 'achieve  objectives.', 'narayana', '(electroins and', 'academic  qualifications:  -',
    'junior  college', 'passing  gpa  /', 'jntuh', 'intermediate', 'inter(mpc)', 'cmr engineering',
    'b. tech', 'b.tech', 'tech', 'mpc', 'qualifications', 'objectives', 'electroins', 'gpa'
}

def clean_skills():
    db = SessionLocal()
    try:
        # Get all candidates
        candidates = db.query(Candidate).all()
        
        cleaned_count = 0
        total_removed = 0
        
        for candidate in candidates:
            if candidate.skills:
                original_count = len(candidate.skills)
                # Filter out blacklisted skills (case-insensitive, strip whitespace)
                cleaned_skills = [
                    skill.strip() for skill in candidate.skills 
                    if skill and skill.strip().lower() not in BLACKLIST and len(skill.strip()) > 2
                ]
                
                if len(cleaned_skills) != original_count:
                    candidate.skills = cleaned_skills
                    removed = original_count - len(cleaned_skills)
                    total_removed += removed
                    cleaned_count += 1
                    print(f"Cleaned {candidate.name}: {original_count} -> {len(cleaned_skills)} skills (removed {removed})")
        
        db.commit()
        print(f"\nCleaned {cleaned_count} candidates")
        print(f"Removed {total_removed} non-skill terms total")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("Starting skill cleanup...")
    clean_skills()
    print("Done!")
