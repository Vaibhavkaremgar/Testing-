from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, case, extract
from typing import List, Optional
from app.database import get_db
from app.models import Candidate, Interview, CandidateStage, User, UserRole, JobDescription
from app.schemas import (
    DashboardStats, PipelineStats, HiringFunnelData, 
    TimeToHireData, SkillHeatmapData, ScoreDistribution
)
from app.auth import get_current_active_user
from collections import Counter
import random
from datetime import datetime

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _role_name(current_user: User) -> str:
    role = getattr(current_user, "role", None)
    return role.value if hasattr(role, "value") else str(role or "")


def _client_org_name(current_user: User) -> str:
    # Analytics-only client scoping. If a client role exists, use department as org key.
    return (getattr(current_user, "department", None) or "").strip()


def _apply_candidate_visibility(query, current_user: User):
    role_name = _role_name(current_user)

    if role_name == UserRole.ADMIN.value:
        return query

    if role_name == UserRole.RECRUITER.value:
        return query.filter(Candidate.assigned_to_user_id == current_user.id)

    if role_name == "client":
        org_name = _client_org_name(current_user)
        if not org_name:
            return query.filter(Candidate.id == -1)
        return query.join(JobDescription, Candidate.job_id == JobDescription.id).filter(
            JobDescription.company_name == org_name
        )

    # Fallback for non-admin roles in analytics: scoped to assigned candidates.
    return query.filter(Candidate.assigned_to_user_id == current_user.id)


def _apply_job_visibility(query, db: Session, current_user: User):
    role_name = _role_name(current_user)

    if role_name == UserRole.ADMIN.value:
        return query

    if role_name == UserRole.RECRUITER.value:
        assigned_job_ids = db.query(Candidate.job_id).filter(
            Candidate.assigned_to_user_id == current_user.id,
            Candidate.job_id.isnot(None)
        ).distinct()
        return query.filter(JobDescription.id.in_(assigned_job_ids))

    if role_name == "client":
        org_name = _client_org_name(current_user)
        if not org_name:
            return query.filter(JobDescription.id == -1)
        return query.filter(JobDescription.company_name == org_name)

    assigned_job_ids = db.query(Candidate.job_id).filter(
        Candidate.assigned_to_user_id == current_user.id,
        Candidate.job_id.isnot(None)
    ).distinct()
    return query.filter(JobDescription.id.in_(assigned_job_ids))

@router.get("/dashboard-stats", response_model=DashboardStats)
def get_dashboard_stats(
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    client: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        query = _apply_candidate_visibility(db.query(Candidate), current_user)
        role_name = _role_name(current_user)
        
        # Apply client filter if provided
        if client and role_name == UserRole.ADMIN.value:
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
    base_query = _apply_candidate_visibility(db.query(Candidate), current_user)
    for stage in CandidateStage:
        count = base_query.filter(
            Candidate.stage == stage
        ).count() or 0
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
    query = _apply_candidate_visibility(db.query(Candidate), current_user)
    role_name = _role_name(current_user)
    
    # Apply client filter if provided
    if client and role_name == UserRole.ADMIN.value:
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
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.stage == CandidateStage.SELECTED),
        current_user
    ).all()

    month_buckets = {}
    for candidate in candidates:
        if not candidate.created_at:
            continue
        month_key = candidate.created_at.strftime("%b")
        end_date = candidate.stage_updated_at or candidate.updated_at or candidate.created_at
        days = max(1, (end_date - candidate.created_at).days) if end_date else 1
        month_buckets.setdefault(month_key, []).append(days)

    if not month_buckets:
        return [
            TimeToHireData(month="Aug", avg_days=28.5),
            TimeToHireData(month="Sep", avg_days=32.1),
            TimeToHireData(month="Oct", avg_days=25.8),
            TimeToHireData(month="Nov", avg_days=30.2),
            TimeToHireData(month="Dec", avg_days=35.7),
            TimeToHireData(month="Jan", avg_days=27.3),
        ]

    return [
        TimeToHireData(month=month, avg_days=round(sum(days) / len(days), 1))
        for month, days in month_buckets.items()
    ]

@router.get("/skill-heatmap", response_model=List[SkillHeatmapData])
def get_skill_heatmap(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Skill aliases - map variations to canonical form
    SKILL_ALIASES = {
        'js': 'javascript',
        'ts': 'typescript',
        'py': 'python',
        'node': 'node.js',
        'nodejs': 'node.js',
        'react.js': 'react',
        'reactjs': 'react',
        'vue.js': 'vue',
        'vuejs': 'vue',
        'angular.js': 'angular',
        'angularjs': 'angular',
        'next': 'next.js',
        'nextjs': 'next.js',
        'express.js': 'express',
        'expressjs': 'express',
        'mongo': 'mongodb',
        'postgres': 'postgresql',
        'k8s': 'kubernetes',
        'docker-compose': 'docker',
        'git': 'git',
        'github': 'git',
        'gitlab': 'git'
    }
    
    def normalize_skill(skill: str) -> str:
        """Normalize skill name using aliases"""
        skill_lower = skill.lower().strip()
        return SKILL_ALIASES.get(skill_lower, skill_lower)
    
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
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.skills.isnot(None)),
        current_user
    ).all()
    
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
                    # Normalize using aliases, then use as key for aggregation
                    normalized = normalize_skill(skill)
                    if normalized not in skill_data:
                        skill_data[normalized] = {"count": 0, "scores": []}
                    skill_data[normalized]["count"] += 1
                    if candidate.resume_score:
                        skill_data[normalized]["scores"].append(candidate.resume_score)
    
    # If we have real data, use it
    if skill_data:
        result = []
        for skill_lower, data in skill_data.items():
            avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0
            # Capitalize first letter for display
            skill_display = skill_lower.capitalize()
            result.append(SkillHeatmapData(
                skill=skill_display,
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
    base_query = _apply_candidate_visibility(db.query(Candidate), current_user)
    for range_label, min_score, max_score in ranges:
        count = base_query.filter(
            Candidate.resume_score >= min_score,
            Candidate.resume_score <= max_score
        ).count() or 0
        result.append(ScoreDistribution(range=range_label, count=count))
    
    return result

@router.get("/resume-scores-trend")
def get_resume_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidates = _apply_candidate_visibility(
        db.query(Candidate).filter(Candidate.resume_score.isnot(None)),
        current_user
    ).all()

    month_scores = {}
    for candidate in candidates:
        if not candidate.created_at:
            continue
        month_key = candidate.created_at.strftime("%b")
        month_scores.setdefault(month_key, []).append(candidate.resume_score)

    if not month_scores:
        months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
        return [{"month": month, "avg_score": round(random.uniform(70, 85), 1)} for month in months]

    return [
        {"month": month, "avg_score": round(sum(scores) / len(scores), 1)}
        for month, scores in month_scores.items()
    ]

@router.get("/interview-scores-trend")
def get_interview_scores_trend(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    interviews = db.query(Interview).join(Candidate, Interview.candidate_id == Candidate.id)
    interviews = _apply_candidate_visibility(interviews, current_user).all()

    month_scores = {}
    for interview in interviews:
        if not interview.created_at:
            continue
        month_key = interview.created_at.strftime("%b")
        month_scores.setdefault(month_key, {"technical": [], "communication": []})
        if interview.technical_score is not None:
            month_scores[month_key]["technical"].append(interview.technical_score)
        if interview.communication_score is not None:
            month_scores[month_key]["communication"].append(interview.communication_score)

    if not month_scores:
        months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan"]
        return [
            {
                "month": month,
                "technical": round(random.uniform(65, 85), 1),
                "communication": round(random.uniform(70, 90), 1)
            }
            for month in months
        ]

    result = []
    for month, scores in month_scores.items():
        tech = scores["technical"]
        comm = scores["communication"]
        result.append({
            "month": month,
            "technical": round(sum(tech) / len(tech), 1) if tech else 0,
            "communication": round(sum(comm) / len(comm), 1) if comm else 0
        })
    return result

@router.get("/hiring-by-department")
def get_hiring_by_department(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    jobs = _apply_job_visibility(db.query(JobDescription), db, current_user).all()
    
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
        )
        hired = _apply_candidate_visibility(hired, current_user).scalar() or 0
        
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
    results = db.query(
        Candidate.source,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.source.isnot(None)
    )
    results = _apply_candidate_visibility(results, current_user).group_by(Candidate.source).all()
    
    return [{"source": r.source, "count": r.count} for r in results]

@router.get("/decline-reasons")
def get_decline_reasons(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    results = db.query(
        Candidate.decline_reason,
        func.count(Candidate.id).label('count')
    ).filter(
        Candidate.decline_reason.isnot(None)
    )
    results = _apply_candidate_visibility(results, current_user).group_by(Candidate.decline_reason).all()
    
    return [{"reason": r.decline_reason, "count": r.count} for r in results]

@router.get("/offer-acceptance-rate")
def get_offer_acceptance_rate(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    offers_made_query = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status.in_(['made', 'accepted'])
    )
    offers_made = _apply_candidate_visibility(offers_made_query, current_user).scalar() or 0
    
    offers_accepted_query = db.query(func.count(Candidate.id)).filter(
        Candidate.offer_status == 'accepted'
    )
    offers_accepted = _apply_candidate_visibility(offers_accepted_query, current_user).scalar() or 0
    
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
    jobs = _apply_job_visibility(
        db.query(JobDescription).filter(JobDescription.is_active == True),
        db,
        current_user
    ).all()
    role_name = _role_name(current_user)
    
    result = []
    for job in jobs:
        # Count candidates for this job (EXCLUDING APPLIED stage)
        candidate_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage != CandidateStage.APPLIED
        )
        total_candidates = _apply_candidate_visibility(candidate_query, current_user).scalar() or 0
        
        # Skip jobs with no assigned candidates for non-admin users
        if role_name != UserRole.ADMIN.value and total_candidates == 0:
            continue
        
        selected_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id,
            Candidate.stage == CandidateStage.SHORTLISTED
        )
        selected = _apply_candidate_visibility(selected_query, current_user).scalar() or 0
        
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
    
    interview_query = db.query(Interview).filter(
        Interview.scheduled_at >= today,
        Interview.scheduled_at <= next_week,
        Interview.status == 'scheduled'
    )

    if _role_name(current_user) != UserRole.ADMIN.value:
        interview_query = interview_query.join(Candidate, Interview.candidate_id == Candidate.id)
        interview_query = _apply_candidate_visibility(interview_query, current_user)
    
    interviews = interview_query.order_by(Interview.scheduled_at).limit(10).all()
    
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

@router.get("/hiring-intelligence")
def get_hiring_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from datetime import datetime, timedelta
    
    insights = []
    
    # 1. Detect candidates stuck in stages (>7 days)
    stuck_candidates = _apply_candidate_visibility(db.query(Candidate).filter(
        Candidate.stage.in_([CandidateStage.SHORTLISTED, CandidateStage.INTERVIEW_SCHEDULED]),
        Candidate.stage_entered_at.isnot(None)
    ), current_user).all()
    
    stuck_count = 0
    for c in stuck_candidates:
        days_in_stage = (datetime.utcnow() - c.stage_entered_at).days
        if days_in_stage > 7:
            stuck_count += 1
    
    if stuck_count > 0:
        insights.append(f"{stuck_count} candidate{'s' if stuck_count > 1 else ''} waiting over 7 days in pipeline - action needed")
    
    # 2. High-scoring candidates ready for interview
    ready_candidates_query = db.query(Candidate).filter(
        Candidate.stage == CandidateStage.SHORTLISTED,
        Candidate.resume_score >= 85
    )
    ready_candidates = _apply_candidate_visibility(ready_candidates_query, current_user).count()
    
    if ready_candidates > 0:
        insights.append(f"{ready_candidates} high-scoring candidate{'s' if ready_candidates > 1 else ''} (85+) ready for interview scheduling")
    
    # 3. Interviews completed awaiting decision
    interviewed_query = db.query(Candidate).filter(
        Candidate.stage == CandidateStage.INTERVIEWED
    )
    interviewed = _apply_candidate_visibility(interviewed_query, current_user).count()
    
    if interviewed > 0:
        insights.append(f"{interviewed} interview{'s' if interviewed > 1 else ''} completed - pending hiring decision")
    
    # 4. Jobs with no recent activity
    jobs = _apply_job_visibility(
        db.query(JobDescription).filter(JobDescription.is_active == True),
        db,
        current_user
    ).all()
    stale_jobs = []
    for job in jobs:
        recent_candidates_query = db.query(Candidate).filter(
            Candidate.job_id == job.id,
            Candidate.created_at >= datetime.utcnow() - timedelta(days=14)
        )
        recent_candidates = _apply_candidate_visibility(recent_candidates_query, current_user).count()
        if recent_candidates == 0:
            stale_jobs.append(job.title)
    
    if len(stale_jobs) > 0:
        insights.append(f"{len(stale_jobs)} role{'s' if len(stale_jobs) > 1 else ''} with no applications in 14 days - review job posting")
    
    # 5. Offer-ready candidates
    offer_ready_query = db.query(Candidate).filter(
        Candidate.stage == CandidateStage.INTERVIEWED,
        Candidate.resume_score >= 80
    )
    offer_ready = _apply_candidate_visibility(offer_ready_query, current_user).count()
    
    if offer_ready > 0:
        insights.append(f"{offer_ready} strong candidate{'s' if offer_ready > 1 else ''} ready for offer - don't lose them to competitors")
    
    # If no insights, add positive message
    if len(insights) == 0:
        insights.append("Pipeline is healthy - all candidates progressing smoothly")
        insights.append("No urgent actions required today")
    
    return {"insights": insights[:5]}

@router.get("/hiring-metrics")
def get_hiring_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    base_candidates = _apply_candidate_visibility(db.query(Candidate), current_user)
    total_candidates = base_candidates.count() or 0
    selected_count = base_candidates.filter(Candidate.stage == CandidateStage.SELECTED).count() or 0
    shortlisted_count = base_candidates.filter(Candidate.stage == CandidateStage.SHORTLISTED).count() or 0
    offers_made = base_candidates.filter(Candidate.offer_status.in_(['made', 'accepted'])).count() or 0
    offers_accepted = base_candidates.filter(Candidate.offer_status == 'accepted').count() or 0

    acceptance_rate = round((offers_accepted / offers_made * 100), 1) if offers_made > 0 else 0
    conversion_rate = round((selected_count / total_candidates * 100), 1) if total_candidates > 0 else 0

    visible_jobs = _apply_job_visibility(db.query(JobDescription).filter(JobDescription.is_active == True), db, current_user).all()
    total_vacancies = sum((j.vacancies or 1) for j in visible_jobs)
    vacancy_fill_rate = round((selected_count / total_vacancies * 100), 1) if total_vacancies > 0 else 0

    return {
        "all": {
            "time_to_hire": 18,
            "time_to_fill": 25,
            "offer_acceptance_rate": acceptance_rate,
            "withdrawal_rate": 12,
            "cost_per_hire": 3500,
            "hire_conversion": conversion_rate,
            "vacancy_fill_rate": vacancy_fill_rate,
            "weekly_change": {
                "time_to_hire": -2.5,
                "time_to_fill": -3.1,
                "offer_acceptance_rate": 5.2,
                "withdrawal_rate": -1.8,
                "cost_per_hire": -8.3,
                "hire_conversion": 2.1,
                "vacancy_fill_rate": 4.5
            }
        },
        "technical": {
            "days_to_hire": 22,
            "days_to_fill": 30,
            "acceptance_rate": 70,
            "withdrawal_rate": 15
        },
        "non_technical": {
            "days_to_hire": 14,
            "days_to_fill": 20,
            "acceptance_rate": 80,
            "withdrawal_rate": 8
        },
        "pipeline": [
            {
                "role": "Senior Backend Engineer",
                "department": "technical",
                "leads": 150,
                "applicants": 85,
                "first_interview": 25,
                "second_interview": 12,
                "final_interview": 6,
                "offers": 3
            },
            {
                "role": "Frontend Developer",
                "department": "technical",
                "leads": 120,
                "applicants": 70,
                "first_interview": 22,
                "second_interview": 10,
                "final_interview": 5,
                "offers": 2
            },
            {
                "role": "HR Manager",
                "department": "non_technical",
                "leads": 80,
                "applicants": 45,
                "first_interview": 18,
                "second_interview": 8,
                "final_interview": 4,
                "offers": 2
            }
        ],
        "offer_stats": {
            "offers_accepted": offers_accepted,
            "offers_provided": offers_made,
            "rejected_candidates": max(0, total_candidates - shortlisted_count),
            "total_candidates": total_candidates,
            "hired": selected_count,
            "shortlisted": shortlisted_count,
            "vacancies": total_vacancies
        }
    }

@router.get("/time-to-hire-stages")
def get_time_to_hire_stages(
    department: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription
    import random
    
    # Demo data with stage breakdown
    base_data = [
        {"month": "Aug", "screening": 5.2, "scheduling": 3.8, "technical": 12.5, "offer": 7.0, "dropoff": 15},
        {"month": "Sep", "screening": 6.1, "scheduling": 4.2, "technical": 14.8, "offer": 7.0, "dropoff": 18},
        {"month": "Oct", "screening": 4.5, "scheduling": 3.2, "technical": 11.1, "offer": 7.0, "dropoff": 12},
        {"month": "Nov", "screening": 5.8, "scheduling": 4.5, "technical": 13.2, "offer": 6.7, "dropoff": 16},
        {"month": "Dec", "screening": 7.2, "scheduling": 5.5, "technical": 15.5, "offer": 7.5, "dropoff": 22},
        {"month": "Jan", "screening": 4.8, "scheduling": 3.5, "technical": 12.0, "offer": 7.0, "dropoff": 14}
    ]
    
    # Adjust based on filters
    if department == "Engineering":
        for d in base_data:
            d["technical"] *= 1.3
            d["dropoff"] += 5
    elif department == "Sales":
        for d in base_data:
            d["screening"] *= 0.7
            d["technical"] *= 0.6
    
    return base_data
