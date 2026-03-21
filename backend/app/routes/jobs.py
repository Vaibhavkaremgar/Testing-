from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import re
from app.database import get_db
from app.models import JobDescription, Candidate, User
from app.schemas import (
    JobDescriptionCreate, JobDescriptionUpdate, JobDescriptionResponse
)
from app.auth import get_current_active_user, get_current_admin_user

router = APIRouter(prefix="/jobs", tags=["Job Descriptions"])

@router.get("/debug/count")
def debug_job_count(db: Session = Depends(get_db)):
    """Debug endpoint to check job count without auth"""
    total = db.query(JobDescription).count()
    active = db.query(JobDescription).filter(JobDescription.is_active == True).count()
    jobs = db.query(JobDescription).all()
    return {
        "total_jobs": total,
        "active_jobs": active,
        "jobs": [{"id": j.id, "title": j.title, "is_active": j.is_active, "has_interview_questions": j.interview_questions is not None} for j in jobs]
    }

@router.get("/count")
def get_jobs_count(
    is_active: Optional[bool] = None,
    client: Optional[str] = None,
    agency_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole
    query = db.query(JobDescription)
    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(JobDescription.agency_id == agency_id)
    elif current_user.agency_id:
        query = query.filter(JobDescription.agency_id == current_user.agency_id)
    if is_active is not None:
        query = query.filter(JobDescription.is_active == is_active)
    if client:
        query = query.filter(JobDescription.company_name == client)
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        subquery = db.query(Candidate.job_id).filter(Candidate.assigned_to_user_id == current_user.id).subquery()
        query = query.filter(JobDescription.id.in_(subquery))
    return {"count": query.count()}

@router.get("", response_model=List[JobDescriptionResponse])
def get_jobs(
    page: int = 1,
    limit: int = 100,
    is_active: Optional[bool] = None,
    client: Optional[str] = None,
    agency_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole
    query = db.query(JobDescription)

    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(JobDescription.agency_id == agency_id)
    elif current_user.agency_id:
        query = query.filter(JobDescription.agency_id == current_user.agency_id)

    if is_active is not None:
        query = query.filter(JobDescription.is_active == is_active)

    if client:
        query = query.filter(JobDescription.company_name == client)

    jobs = query.order_by(JobDescription.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    print(f"DEBUG: Found {len(jobs)} jobs in database")
    for job in jobs:
        print(f"  - Job {job.id}: {job.title}, is_active={job.is_active}, interview_questions={job.interview_questions}")
    
    # Add candidate count to each job
    result = []
    for job in jobs:
        candidate_query = db.query(func.count(Candidate.id)).filter(
            Candidate.job_id == job.id
        )
        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
            candidate_query = candidate_query.filter(Candidate.assigned_to_user_id == current_user.id)
        candidate_count = candidate_query.scalar()

        if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN] and candidate_count == 0:
            continue
        
        job_dict = {
            "id": job.id,
            "job_id": getattr(job, 'job_id', None),
            "company_name": getattr(job, 'company_name', None),
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "employment_type": job.employment_type,
            "experience_required": job.experience_required,
            "salary_range": job.salary_range,
            "vacancies": job.vacancies,
            "min_passing_score": getattr(job, 'min_passing_score', 60),
            "description": job.description,
            "requirements": job.requirements,
            "responsibilities": job.responsibilities,
            "skills": job.skills,
            "interview_questions": job.interview_questions,
            "is_active": job.is_active,
            "created_at": job.created_at,
            "candidate_count": candidate_count
        }
        result.append(JobDescriptionResponse(**job_dict))
    
    return result

@router.get("/{job_id}", response_model=JobDescriptionResponse)
def get_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import UserRole
    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    candidate_query = db.query(func.count(Candidate.id)).filter(
        Candidate.job_id == job.id
    )
    if current_user.role not in [UserRole.ADMIN, UserRole.SUPER_ADMIN]:
        candidate_query = candidate_query.filter(Candidate.assigned_to_user_id == current_user.id)
    candidate_count = candidate_query.scalar()
    
    job_dict = {
        "id": job.id,
        "job_id": getattr(job, 'job_id', None),
        "company_name": getattr(job, 'company_name', None),
        "title": job.title,
        "department": job.department,
        "location": job.location,
        "employment_type": job.employment_type,
        "experience_required": job.experience_required,
        "salary_range": job.salary_range,
        "vacancies": job.vacancies,
        "min_passing_score": getattr(job, 'min_passing_score', 60),
        "description": job.description,
        "requirements": job.requirements,
        "responsibilities": job.responsibilities,
        "skills": job.skills,
        "interview_questions": job.interview_questions,
        "is_active": job.is_active,
        "created_at": job.created_at,
        "candidate_count": candidate_count
    }
    return JobDescriptionResponse(**job_dict)

@router.post("", response_model=JobDescriptionResponse)
def create_job(
    job: JobDescriptionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        print(f"Creating job with data: {job.model_dump()}")
        
        # Auto-create client if company_name is provided and doesn't exist
        if job.company_name:
            from app.models import Client
            existing_client = db.query(Client).filter(
                Client.company_name == job.company_name
            ).first()
            
            if not existing_client:
                new_client = Client(
                    company_name=job.company_name,
                    total_positions=1,
                    positions_open=1,
                    is_active=True
                )
                db.add(new_client)
                db.commit()
        
        job_data = job.model_dump()
        
        # Auto-generate job_id if not provided to avoid unique constraint violation
        if not job_data.get('job_id'):
            import uuid
            job_data['job_id'] = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        
        db_job = JobDescription(**job_data)
        db_job.agency_id = current_user.agency_id
        db.add(db_job)
        db.commit()
        db.refresh(db_job)
        
        job_dict = {
            "id": db_job.id,
            "job_id": getattr(db_job, 'job_id', None),
            "company_name": getattr(db_job, 'company_name', None),
            "title": db_job.title,
            "department": db_job.department,
            "location": db_job.location,
            "employment_type": db_job.employment_type,
            "experience_required": db_job.experience_required,
            "salary_range": db_job.salary_range,
            "vacancies": db_job.vacancies,
            "min_passing_score": getattr(db_job, 'min_passing_score', 60),
            "description": db_job.description,
            "requirements": db_job.requirements,
            "responsibilities": db_job.responsibilities,
            "skills": db_job.skills,
            "interview_questions": db_job.interview_questions,
            "is_active": db_job.is_active,
            "created_at": db_job.created_at,
            "candidate_count": 0
        }
        return JobDescriptionResponse(**job_dict)
    except Exception as e:
        print(f"Error creating job: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{job_id}", response_model=JobDescriptionResponse)
def update_job(
    job_id: int,
    job_update: JobDescriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    update_data = job_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_job, field, value)
    
    db.commit()
    db.refresh(db_job)
    
    candidate_count = db.query(func.count(Candidate.id)).filter(
        Candidate.job_id == db_job.id
    ).scalar()
    
    job_dict = {
        "id": db_job.id,
        "job_id": getattr(db_job, 'job_id', None),
        "company_name": getattr(db_job, 'company_name', None),
        "title": db_job.title,
        "department": db_job.department,
        "location": db_job.location,
        "employment_type": db_job.employment_type,
        "experience_required": db_job.experience_required,
        "salary_range": db_job.salary_range,
        "vacancies": db_job.vacancies,
        "min_passing_score": getattr(db_job, 'min_passing_score', 60),
        "description": db_job.description,
        "requirements": db_job.requirements,
        "responsibilities": db_job.responsibilities,
        "skills": db_job.skills,
        "interview_questions": db_job.interview_questions,
        "is_active": db_job.is_active,
        "created_at": db_job.created_at,
        "candidate_count": candidate_count
    }
    return JobDescriptionResponse(**job_dict)

@router.post("/extract-data")
async def extract_job_data(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user)
):
    """Extract job data from uploaded file"""
    try:
        content = await file.read()
        text = ""
        
        # Extract text based on file type
        if file.filename.lower().endswith('.txt'):
            text = content.decode('utf-8')
        elif file.filename.lower().endswith('.pdf'):
            try:
                import PyPDF2
                import io
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
                for page in pdf_reader.pages:
                    text += page.extract_text() + '\n'
            except:
                text = content.decode('utf-8', errors='ignore')
        elif file.filename.lower().endswith(('.doc', '.docx')):
            try:
                if file.filename.lower().endswith('.docx'):
                    import docx
                    import io
                    doc = docx.Document(io.BytesIO(content))
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + '\n'
                else:
                    text = content.decode('utf-8', errors='ignore')
            except:
                text = content.decode('utf-8', errors='ignore')
        
        # Extract job information using improved regex patterns
        extracted_data = {
            'department': extract_field(text, ['department', 'team', 'division']),
            'location': extract_field(text, ['location', 'office', 'city', 'remote']),
            'employment_type': extract_employment_type(text),
            'experience_required': extract_experience(text) or extract_field(text, ['experience', 'years', 'minimum', 'exp']),
            'salary_range': extract_salary(text),
            'description': extract_description(text),
            'requirements': extract_section(text, ['requirements', 'qualifications', 'must have', 'required']),
            'responsibilities': extract_responsibilities(text),
            'skills': extract_skills(text)
        }
        
        return extracted_data
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to extract data: {str(e)}")

def extract_field(text, keywords):
    """Extract field value based on keywords"""
    text_lower = text.lower()
    for keyword in keywords:
        pattern = rf'{keyword}[:\s-]*([^\n]+)'
        match = re.search(pattern, text_lower)
        if match:
            value = match.group(1).strip()
            # Clean up common prefixes/suffixes
            value = re.sub(r'^[:\s-]+|[:\s-]+$', '', value)
            return value.title() if len(value) < 50 else value
    return ''

def extract_experience(text):
    """Extract experience requirements"""
    # Simple patterns to catch any mention of years
    patterns = [
        r'(\d+)\s*(?:[-to]\s*)?(\d+)?\s*(?:years?|yrs?)(?:\s*(?:of\s*)?(?:experience|exp))?',
        r'(?:experience|exp)[:\s]*(\d+)\s*(?:[-to]\s*)?(\d+)?\s*(?:years?|yrs?)',
        r'(?:minimum|min|at least|requires?)\s*(\d+)\s*(?:years?|yrs?)',
        r'(\d+)\+\s*(?:years?|yrs?)',
        r'\b(\d+)\s*(?:[-to]\s*)?(\d+)?\s*(?:years?|yrs?)\b'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if isinstance(match, tuple):
                if match[1]:  # Range
                    return f"{match[0]}-{match[1]} years"
                else:  # Single number
                    return f"{match[0]}+ years"
            else:
                return f"{match}+ years"
    
    # Check for entry level
    if re.search(r'entry\s*level|no\s*experience|fresh|0\s*years?', text, re.IGNORECASE):
        return "Entry level"
    
    return ''

def extract_description(text):
    """Extract job description"""
    keywords = ['description', 'about', 'overview', 'summary', 'position', 'role']
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        for keyword in keywords:
            if (keyword in line_lower and 
                (':' in line or line_lower.startswith(keyword) or 
                 line_lower.endswith(keyword))):
                
                content_lines = []
                
                # If content is on same line after colon
                if ':' in line:
                    after_colon = line.split(':', 1)[1].strip()
                    if after_colon:
                        content_lines.append(after_colon)
                
                # Extract following lines until new section
                for j in range(i + 1, min(i + 15, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if any(kw in next_line.lower() for kw in 
                          ['responsibilities', 'requirements', 'qualifications', 'skills', 'benefits']):
                        break
                    content_lines.append(next_line)
                
                if content_lines:
                    description = ' '.join(content_lines)[:800]
                    return description.strip()
    
    # Fallback: take first few sentences
    sentences = re.split(r'[.!?]+', text)
    if len(sentences) > 1:
        return '. '.join(sentences[:3])[:400] + '.'
    
    return ''

def extract_responsibilities(text):
    """Extract job responsibilities"""
    keywords = ['responsibilities', 'duties', 'tasks', 'role', 'you will', 'what you\'ll do']
    
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        for keyword in keywords:
            if keyword in line_lower and (':' in line or line_lower.startswith(keyword)):
                content_lines = []
                
                # If content is on same line after colon
                if ':' in line:
                    after_colon = line.split(':', 1)[1].strip()
                    if after_colon:
                        content_lines.append(after_colon)
                
                # Extract following lines (usually bullet points)
                for j in range(i + 1, min(i + 20, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    if any(kw in next_line.lower() for kw in 
                          ['requirements', 'qualifications', 'skills', 'benefits', 'experience']):
                        break
                    content_lines.append(next_line)
                
                if content_lines:
                    responsibilities = ' '.join(content_lines)[:800]
                    return responsibilities.strip()
    
    return ''

def extract_employment_type(text):
    """Extract employment type"""
    text_lower = text.lower()
    if 'full-time' in text_lower or 'full time' in text_lower:
        return 'Full-time'
    elif 'part-time' in text_lower or 'part time' in text_lower:
        return 'Part-time'
    elif 'contract' in text_lower:
        return 'Contract'
    elif 'internship' in text_lower or 'intern' in text_lower:
        return 'Internship'
    return 'Full-time'

def extract_salary(text):
    """Extract salary information"""
    # Find any number that could be a salary
    numbers = re.findall(r'\d+', text)
    
    for num in numbers:
        # If number is 4+ digits, likely a salary
        if len(num) >= 4:
            return f"${num}"
    
    # If no large numbers, return any number found
    if numbers:
        return f"${numbers[0]}"
    
    return ''

def extract_section(text, keywords):
    """Extract larger text sections"""
    lines = text.split('\n')
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        for keyword in keywords:
            if keyword in line_lower and (':' in line or line_lower.startswith(keyword)):
                # Found keyword, extract following content
                content_lines = []
                
                # If content is on same line after colon
                if ':' in line:
                    after_colon = line.split(':', 1)[1].strip()
                    if after_colon:
                        content_lines.append(after_colon)
                
                # Extract following lines until empty line or new section
                for j in range(i + 1, min(i + 10, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line or any(kw in next_line.lower() for kw in ['responsibilities', 'requirements', 'qualifications', 'skills', 'experience']):
                        break
                    content_lines.append(next_line)
                
                if content_lines:
                    return ' '.join(content_lines)[:500]
    return ''

def extract_skills(text):
    """Extract skills from text"""
    common_skills = [
        'Python', 'Java', 'JavaScript', 'React', 'Node.js', 'SQL', 'AWS', 'Docker',
        'Kubernetes', 'Git', 'HTML', 'CSS', 'TypeScript', 'Angular', 'Vue.js',
        'MongoDB', 'PostgreSQL', 'Redis', 'Linux', 'Agile', 'Scrum'
    ]
    
    found_skills = []
    text_upper = text.upper()
    
    for skill in common_skills:
        if skill.upper() in text_upper:
            found_skills.append(skill)
    
    return found_skills[:10]  # Limit to 10 skills

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    db_job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not db_job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    db.delete(db_job)
    db.commit()
    return {"message": "Job deleted successfully"}
