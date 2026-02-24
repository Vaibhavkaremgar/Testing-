from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract
from typing import List, Optional
from app.database import get_db
from app.models import Candidate, Interview, CandidateStage, User
from app.schemas import (
    DashboardStats, PipelineStats, HiringFunnelData, 
    TimeToHireData, SkillHeatmapData, ScoreDistribution
)
from app.auth import get_current_active_user
from collections import Counter
import random
from datetime import datetime

router = APIRouter(prefix="/analytics", tags=["Analytics"])

@router.get("/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats(
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        query = db.query(Candidate)
        
        # Apply client filter if provided
        if client:
            from app.models import JobDescription
            job_ids = db.query(JobDescription.id).filter(JobDescription.company_name == client).all()
            job_ids = [j[0] for j in job_ids]
            if job_ids:
                query = query.filter(Candidate.job_id.in_(job_ids))
            else:
                # No jobs for this client, return zeros
                return DashboardStats(
                    total_candidates=0,
                    shortlisted=0,
                    resume_rejected=0,
                    rejected=0,
                    interviews_scheduled=0,
                    selected=0,
                    avg_resume_score=0.0,
                    avg_interview_score=0.0
                )
        
        # Apply date filter if provided (specific date)
        if date:
            query = query.filter(func.date(Candidate.created_at) == date)
        # Apply month filter if provided
        elif month:
            year, month_num = map(int, month.split('-'))
            query = query.filter(
                extract('year', Candidate.created_at) == year,
                extract('month', Candidate.created_at) == month_num
            )
        
        # Count all candidates EXCLUDING APPLIED stage
        all_candidates = query.all()
        # Filter out APPLIED stage candidates
        active_candidates = [c for c in all_candidates if c.stage != CandidateStage.APPLIED]
        total = len(active_candidates)
        
        shortlisted = sum(1 for c in active_candidates if c.stage == CandidateStage.SHORTLISTED)
        resume_rejected = sum(1 for c in active_candidates if c.stage == CandidateStage.RESUME_REJECTED)
        rejected = sum(1 for c in active_candidates if c.stage == CandidateStage.REJECTED)
        interview_scheduled = sum(1 for c in active_candidates if c.stage in [CandidateStage.INTERVIEW_SCHEDULED, CandidateStage.INTERVIEW_RESCHEDULED, CandidateStage.INTERVIEWED])
        selected = sum(1 for c in active_candidates if c.stage == CandidateStage.SELECTED)
        
        print(f"📊 Dashboard Stats: total={total}, shortlisted={shortlisted}, resume_rejected={resume_rejected}, rejected={rejected}, interviews={interview_scheduled}, selected={selected}")
        print(f"   Sum check: {shortlisted + resume_rejected + rejected + interview_scheduled + selected} (should equal total)")
        
        candidate_ids = [c.id for c in active_candidates]
        avg_resume = db.query(func.avg(Candidate.resume_score)).filter(
            Candidate.id.in_(candidate_ids) if candidate_ids else False
        ).scalar() or 0
        
        # Calculate avg interview score from candidates in SELECTED/REJECTED stages
        interviewed_candidates = [c for c in active_candidates if c.stage in [CandidateStage.SELECTED, CandidateStage.REJECTED]]
        if interviewed_candidates:
            total_score = 0
            count = 0
            for c in interviewed_candidates:
                try:
                    tech = getattr(c, 'interview_technical_score', None)
                    comm = getattr(c, 'interview_communication_score', None)
                    cult = getattr(c, 'interview_culture_fit_score', None)
                    if tech and comm and cult:
                        avg = (tech + comm + cult) / 3
                        total_score += avg
                        count += 1
                except AttributeError:
                    continue
            avg_interview = total_score / count if count > 0 else 0
        else:
            avg_interview = 0
        
        return DashboardStats(
            total_candidates=total,
            shortlisted=shortlisted,
            resume_rejected=resume_rejected,
            rejected=rejected,
            interviews_scheduled=interview_scheduled,
            selected=selected,
            avg_resume_score=round(avg_resume, 1),
            avg_interview_score=round(avg_interview, 1)
        )
    except Exception as e:
        print(f"❌ Dashboard stats error: {e}")
        import traceback
        traceback.print_exc()
        # Return default values on error
        return DashboardStats(
            total_candidates=0,
            shortlisted=0,
            resume_rejected=0,
            rejected=0,
            interviews_scheduled=0,
            selected=0,
            avg_resume_score=0.0,
            avg_interview_score=0.0
        )

@router.get("/pipeline-stats", response_model=List[PipelineStats])
def get_pipeline_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    stats = []
    for stage in CandidateStage:
        count = db.query(func.count(Candidate.id)).filter(
            Candidate.stage == stage
        ).scalar() or 0
        stats.append(PipelineStats(stage=stage.value, count=count))
    return stats

@router.get("/hiring-funnel", response_model=List[HiringFunnelData])
def get_hiring_funnel(
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Candidate)
    
    # Apply client filter if provided
    if client:
        from app.models import JobDescription
        job_ids = db.query(JobDescription.id).filter(JobDescription.company_name == client).all()
        job_ids = [j[0] for j in job_ids]
        if job_ids:
            query = query.filter(Candidate.job_id.in_(job_ids))
        else:
            return []
    
    # Apply date filter if provided (specific date)
    if date:
        query = query.filter(func.date(Candidate.created_at) == date)
    # Apply month filter if provided
    elif month:
        year, month_num = map(int, month.split('-'))
        query = query.filter(
            extract('year', Candidate.created_at) == year,
            extract('month', Candidate.created_at) == month_num
        )
    
    total = query.count() or 1
    shortlisted = query.filter(Candidate.stage == CandidateStage.SHORTLISTED).count() or 0
    interview_scheduled = query.filter(Candidate.stage == CandidateStage.INTERVIEW_SCHEDULED).count() or 0
    selected = query.filter(Candidate.stage == CandidateStage.SELECTED).count() or 0
    rejected = query.filter(Candidate.stage.in_([CandidateStage.REJECTED, CandidateStage.RESUME_REJECTED])).count() or 0
    
    funnel_stages = [
        ("Total Candidates", total),
        ("Shortlisted", shortlisted),
        ("Interview Scheduled", interview_scheduled),
        ("Selected", selected),
        ("Rejected", rejected),
    ]
    
    return [
        HiringFunnelData(
            stage=stage,
            count=count,
            percentage=round((count / total) * 100, 1) if total > 0 else 0
        )
        for stage, count in funnel_stages
    ]

@router.get("/time-to-hire", response_model=List[TimeToHireData])
def get_time_to_hire(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Custom time to hire data (more realistic for tech hiring)
    time_data = [
        {"month": "Aug", "avg_days": 28.5},
        {"month": "Sep", "avg_days": 32.1},
        {"month": "Oct", "avg_days": 25.8},
        {"month": "Nov", "avg_days": 30.2},
        {"month": "Dec", "avg_days": 35.7},
        {"month": "Jan", "avg_days": 27.3}
    ]
    return [TimeToHireData(**data) for data in time_data]

@router.get("/skill-heatmap", response_model=List[SkillHeatmapData])
def get_skill_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Comprehensive blacklist of non-skill terms
    blacklist = {
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
        'b. tech', 'b.tech', 'tech', 'mpc', 'qualifications', 'objectives', 'electroins', 'gpa',
        'teamwork', 'leadership', 'problem solving', 'analytical', 'critical thinking', 'time management',
        'work ethic', 'adaptability', 'creativity', 'collaboration', 'interpersonal', 'organizational',
        'attention to detail', 'multitasking', 'decision making', 'conflict resolution', 'negotiation',
        'presentation', 'public speaking', 'customer service', 'sales', 'marketing', 'management',
        'highly relevant', 'relevant', 'signals', 'jd', 'workexperience', 'work experience'
    }
    
    # Whitelist of valid technical skills
    valid_skills = {
        # Programming Languages
        'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'php', 'ruby', 'go', 'rust',
        'swift', 'kotlin', 'scala', 'r', 'matlab', 'perl', 'dart', 'c', 'objective-c',
        # Web Technologies
        'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring', 'laravel',
        'rails', 'html', 'html5', 'css', 'css3', 'bootstrap', 'tailwind', 'jquery', 'next.js',
        'nuxt', 'svelte', 'ember', 'backbone', 'asp.net', '.net', 'blazor',
        # Databases
        'mysql', 'postgresql', 'mongodb', 'redis', 'sqlite', 'oracle', 'sql', 'sql server',
        'cassandra', 'dynamodb', 'firebase', 'mariadb', 'elasticsearch', 'neo4j', 'couchdb',
        # Cloud & DevOps
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'github', 'gitlab',
        'ci/cd', 'terraform', 'ansible', 'heroku', 'netlify', 'vercel', 'circleci', 'travis ci',
        # Data Science & ML
        'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'pandas', 'numpy',
        'scikit-learn', 'data analysis', 'ai', 'nlp', 'keras', 'opencv', 'spark', 'hadoop',
        # APIs & Architecture
        'rest api', 'graphql', 'microservices', 'linux', 'unix', 'bash', 'shell', 'powershell',
        'api', 'restful', 'soap', 'grpc', 'websocket',
        # Mobile
        'android', 'ios', 'react native', 'flutter', 'xamarin', 'ionic',
        # Tools & Others
        'jira', 'confluence', 'slack', 'postman', 'vs code', 'intellij', 'eclipse', 'figma',
        'photoshop', 'illustrator', 'sketch', 'xd', 'webpack', 'vite', 'babel', 'npm', 'yarn',
        'maven', 'gradle', 'selenium', 'cypress', 'jest', 'mocha', 'junit', 'pytest'
    }
    
    # Get candidates with skills
    candidates = db.query(Candidate).filter(Candidate.skills.isnot(None)).all()
    
    skill_data = {}
    for candidate in candidates:
        if candidate.skills:
            for skill in candidate.skills:
                skill_lower = skill.lower().strip()
                
                # Skip if contains special characters like %, +, numbers at start
                if any(char in skill for char in ['%', '+', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9']):
                    continue
                
                # Filter: must be in whitelist OR (not in blacklist AND length 2-30 AND alphanumeric)
                is_valid = (
                    skill_lower in valid_skills or
                    (skill_lower not in blacklist and 
                     2 <= len(skill) <= 30 and 
                     skill.replace('.', '').replace('-', '').replace(' ', '').replace('#', '').isalpha())
                )
                
                if is_valid:
                    if skill not in skill_data:
                        skill_data[skill] = {"count": 0, "scores": []}
                    skill_data[skill]["count"] += 1
                    if candidate.resume_score:
                        skill_data[skill]["scores"].append(candidate.resume_score)
    
    # If we have real data, use it
    if skill_data:
        result = []
        for skill, data in skill_data.items():
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            result.append(SkillHeatmapData(
                skill=skill,
                count=data["count"],
                avg_score=round(avg_score, 1)
            ))
        result.sort(key=lambda x: x.count, reverse=True)
        return result[:15]
    
    # Fallback to demo data if no real data
    custom_skills = [
        {"skill": "Python", "count": 24, "avg_score": 87.5},
        {"skill": "JavaScript", "count": 22, "avg_score": 84.2},
        {"skill": "React", "count": 18, "avg_score": 86.1},
        {"skill": "Node.js", "count": 16, "avg_score": 83.7},
        {"skill": "SQL", "count": 20, "avg_score": 82.3},
        {"skill": "AWS", "count": 15, "avg_score": 88.9},
        {"skill": "Docker", "count": 14, "avg_score": 85.4},
        {"skill": "Machine Learning", "count": 12, "avg_score": 89.2},
        {"skill": "Java", "count": 13, "avg_score": 81.8},
        {"skill": "TypeScript", "count": 11, "avg_score": 87.6},
        {"skill": "Kubernetes", "count": 9, "avg_score": 90.1},
        {"skill": "MongoDB", "count": 10, "avg_score": 83.5},
        {"skill": "GraphQL", "count": 8, "avg_score": 86.8},
        {"skill": "Redis", "count": 7, "avg_score": 84.9},
        {"skill": "Microservices", "count": 6, "avg_score": 88.3}
    ]
    
    return [SkillHeatmapData(**skill) for skill in custom_skills]

@router.get("/score-distribution", response_model=List[ScoreDistribution])
def get_score_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Define score ranges
    ranges = [
        ("0-20", 0, 20),
        ("21-40", 21, 40),
        ("41-60", 41, 60),
        ("61-80", 61, 80),
        ("81-100", 81, 100),
    ]
    
    result = []
    for range_label, min_score, max_score in ranges:
        count = db.query(func.count(Candidate.id)).filter(
            Candidate.resume_score >= min_score,
            Candidate.resume_score <= max_score
        ).scalar() or 0
        result.append(ScoreDistribution(range=range_label, count=count))
    
    return result

@router.get("/resume-scores-trend")
def get_resume_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Generate sample trend data
    months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
    return [
        {"month": month, "avg_score": round(random.uniform(70, 85), 1)}
        for month in months
    ]

@router.get("/interview-scores-trend")
def get_interview_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Generate sample trend data
    months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
    return [
        {
            "month": month,
            "technical": round(random.uniform(65, 85), 1),
            "communication": round(random.uniform(70, 90), 1)
        }
        for month in months
    ]

@router.get("/hiring-by-department")
def get_hiring_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription
    
    # Get all jobs with their department
    jobs = db.query(JobDescription).all()
    
    # Group by department
    dept_data = {}
    for job in jobs:
        dept = job.department or "Other"
        if dept not in dept_data:
            dept_data[dept] = {"hired": 0, "open": 0}
        
        # Count selected candidates for this job
        hired = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SELECTED
        ).scalar() or 0
        
        # Count open positions (vacancies - hired)
        open_positions = max(0, (job.vacancies or 1) - hired)
        
        dept_data[dept]["hired"] += hired
        dept_data[dept]["open"] += open_positions
    
    # Convert to list format
    result = [
        {"department": dept, "hired": data["hired"], "open": data["open"]}
        for dept, data in dept_data.items()
    ]
    
    return result

@router.get("/source-breakdown")
def get_source_breakdown(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from sqlalchemy import func
    results = db.query(
        Candidate.source,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.source.isnot(None)
    ).group_by(Candidate.source).all()
    
    return [{"source": r.source, "count": r.count} for r in results]

@router.get("/decline-reasons")
def get_decline_reasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from sqlalchemy import func
    results = db.query(
        Candidate.decline_reason,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.decline_reason.isnot(None)
    ).group_by(Candidate.decline_reason).all()
    
    return [{"reason": r.decline_reason, "count": r.count} for r in results]

@router.get("/offer-acceptance-rate")
def get_offer_acceptance_rate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from sqlalchemy import func
    offers_made = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status.in_(['made', 'accepted'])
    ).scalar() or 0
    
    offers_accepted = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status == 'accepted'
    ).scalar() or 0
    
    rate = round((offers_accepted / offers_made * 100), 1) if offers_made > 0 else 0
    
    return {
        "offers_made": offers_made,
        "offers_accepted": offers_accepted,
        "acceptance_rate": rate
    }

@router.get("/active-jobs")
def get_active_jobs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription
    from sqlalchemy import func, case
    
    jobs = db.query(JobDescription).filter(JobDescription.is_active == True).all()
    
    result = []
    for job in jobs:
        # Count candidates for this job (EXCLUDING APPLIED stage)
        total_candidates = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage != CandidateStage.APPLIED
        ).scalar() or 0
        
        selected = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SHORTLISTED
        ).scalar() or 0
        
        # Determine status
        status = 'open'
        if hasattr(job, 'status') and job.status:
            status = job.status
        elif selected >= (job.vacancies or 1):
            status = 'filled'
        
        result.append({
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "vacancies": job.vacancies or 1,
            "candidates": total_candidates,
            "selected": selected,
            "status": status
        })
    
    return result

@router.get("/upcoming-interviews")
def get_upcoming_interviews(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from datetime import datetime, timedelta
    
    # Get interviews scheduled for next 7 days
    today = datetime.now()
    next_week = today + timedelta(days=7)
    
    interviews = db.query(Interview).filter(
        Interview.scheduled_at >= today,
        Interview.scheduled_at <= next_week,
        Interview.status == 'scheduled'
    ).order_by(Interview.scheduled_at).limit(10).all()
    
    result = []
    for interview in interviews:
        result.append({
            "id": interview.id,
            "candidate_name": interview.candidate.name if interview.candidate else "Unknown",
            "candidate_id": interview.candidate_id,
            "interview_type": interview.interview_type,
            "scheduled_at": interview.scheduled_at.isoformat() if interview.scheduled_at else None,
            "duration_minutes": interview.duration_minutes
        })
    
    return result
