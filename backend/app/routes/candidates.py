from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from typing import List, Optional
from uuid import UUID
import os
import uuid
import random
import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from app.database import SessionLocal, get_db
from app.models import Candidate, CandidateStage, ParsingStatus, User, JobDescription
from app.notification_service import queue_notification_for_stage, send_email_task
from app.schemas import (
    CandidateCreate, CandidateUpdate, CandidateResponse, CandidateStageUpdate
)
from app.auth import get_current_active_user
from app.config import settings

router = APIRouter(prefix="/candidates", tags=["Candidates"])
upload_progress_store = {}
ALLOWED_RESUME_EXTENSIONS = {'.pdf', '.doc', '.docx'}
ALLOWED_RESUME_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


def _apply_candidate_list_scope(query, current_user):
    from sqlalchemy.orm import aliased
    from app.models import JobDescription, User, UserRole

    if current_user.role == UserRole.SUPER_ADMIN:
        return query

    creator = aliased(User)
    assignee = aliased(User)

    if current_user.role == UserRole.ADMIN and current_user.agency_id:
        return query.outerjoin(JobDescription, Candidate.job_id == JobDescription.id).outerjoin(
            creator, Candidate.created_by == creator.id
        ).outerjoin(
            assignee, Candidate.assigned_to_user_id == assignee.id
        ).filter(
            or_(
                Candidate.agency_id == current_user.agency_id,
                JobDescription.agency_id == current_user.agency_id,
                creator.agency_id == current_user.agency_id,
                assignee.agency_id == current_user.agency_id,
            )
        )

    if current_user.role != UserRole.ADMIN:
        return query.filter(Candidate.assigned_to_user_id == current_user.id)

    return query


def get_bulk_processing_workers(item_count: int) -> int:
    """Keep worker count bounded so batch uploads scale without exhausting the host."""
    cpu_count = os.cpu_count() or 4
    return max(2, min(8, cpu_count, item_count or 1))


def enqueue_stage_notification(
    background_tasks: BackgroundTasks,
    db: Session,
    candidate: Candidate,
    stage_value: str,
    user_id=None,
    extra_payload: Optional[dict] = None,
):
    try:
        notification = queue_notification_for_stage(
            db,
            candidate=candidate,
            stage_value=stage_value,
            user_id=user_id,
            extra_payload=extra_payload,
        )
        if notification:
            db.commit()
            print(
                f"Notification queued: candidate_id={candidate.id}, "
                f"stage={stage_value}, communication_id={notification['communication_id']}"
            )
            send_email_task(notification["communication_id"])
    except Exception as exc:
        db.rollback()
        print(f"Notification enqueue failed for stage {stage_value}: {exc}")

def generate_candidate_id(name: str, job_id: int = None) -> str:
    """Generate unique candidate ID: FirstName + JobID"""
    if not name:
        first_name = "Unknown"
    else:
        # Extract first name and clean it
        first_name = name.split()[0].replace(" ", "").replace("-", "").replace(".", "")
    
    job_suffix = str(job_id) if job_id else "0"
    return f"{first_name}{job_suffix}"


def clean_candidate_name(raw_name: str) -> str:
    """Normalize names extracted from filenames like 'Swapna Resume' -> 'Swapna'."""
    import re

    if not raw_name:
        return "Unknown Candidate"

    stop_words = {
        "resume", "cv", "profile", "updated", "final", "latest", "new",
        "doc", "document", "copy", "version", "v1", "v2", "v3"
    }

    normalized = raw_name.replace('_', ' ').replace('-', ' ')
    normalized = re.sub(r'\([^)]*\)', ' ', normalized)
    normalized = re.sub(r'\[[^\]]*\]', ' ', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    words = []
    for word in normalized.split():
        cleaned_word = re.sub(r'^\d+|\d+$', '', word).strip()
        if not cleaned_word:
            continue
        if cleaned_word.lower() in stop_words:
            continue
        if any(char.isdigit() for char in cleaned_word):
            continue
        words.append(cleaned_word)

    if words:
        return " ".join(words).title()

    return normalized.title() if normalized else "Unknown Candidate"


def extract_email_from_raw_file(file_path: str) -> Optional[str]:
    """Fallback email extraction for files where text parsing misses the address."""
    import re

    try:
        with open(file_path, "rb") as file_handle:
            raw_content = file_handle.read()
    except Exception as exc:
        print(f"Raw email extraction failed to read file: {exc}")
        return None

    decoded_content = raw_content.decode("utf-8", errors="ignore")
    if "@" not in decoded_content:
        decoded_content = raw_content.decode("latin-1", errors="ignore")

    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, decoded_content, re.IGNORECASE)
    return emails[0] if emails else None

def extract_resume_data(file_path: str, original_filename: str = None) -> dict:
    """Extract name and email from resume file (PDF or Word)"""
    import os
    import re
    
    email = None
    phone = None
    name = None
    skills = []
    projects = []
    experience_text = ""
    
    try:
        text = ""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.pdf':
            # PDF extraction
            try:
                import PyPDF2
                with open(file_path, 'rb') as file:
                    pdf_reader = PyPDF2.PdfReader(file)
                    for page in pdf_reader.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + '\n'
            except Exception as e:
                print(f"PDF extraction failed: {e}")
        
        elif file_ext in ['.doc', '.docx']:
            # Word document extraction
            try:
                if file_ext == '.docx':
                    import docx
                    doc = docx.Document(file_path)
                    for paragraph in doc.paragraphs:
                        text += paragraph.text + '\n'
                else:
                    # For .doc files, try basic text extraction
                    try:
                        import subprocess
                        result = subprocess.run(['antiword', file_path], capture_output=True, text=True)
                        if result.returncode == 0:
                            text = result.stdout
                    except:
                        # Fallback: treat as binary and extract readable text
                        with open(file_path, 'rb') as f:
                            content = f.read()
                            text = ''.join(chr(b) for b in content if 32 <= b <= 126)
            except Exception as e:
                print(f"Word document extraction failed: {e}")
        
        if text.strip():
            # Extract email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            emails = re.findall(email_pattern, text, re.IGNORECASE)
            email = emails[0] if emails else None
            
            # Extract phone
            phone_patterns = [
                r'\+91[-\s]?\d{5}[-\s]?\d{5}',  # Indian: +91-XXXXX-XXXXX or +91 XXXXX XXXXX
                r'\+91[-\s]?\d{10}',  # Indian: +91-XXXXXXXXXX or +91 XXXXXXXXXX
                r'\d{5}[-\s]?\d{5}',  # Indian without code: XXXXX-XXXXX or XXXXX XXXXX
                r'\+?1?[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}',  # US format
                r'\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}',  # US format without country code
            ]
            for pattern in phone_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    phone = matches[0].strip()
                    break
            
            # Extract name from document content
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            
            # Look for name in first few lines
            for line in lines[:20]:
                # Skip if line is too short or too long
                if len(line) < 3 or len(line) > 60:
                    continue
                    
                words = line.split()
                
                # Name should be 2-4 words only
                if not (2 <= len(words) <= 4):
                    continue
                
                # Skip common headers/keywords and job titles
                skip_keywords = [
                    'resume', 'curriculum', 'vitae', 'profile', 'summary', 'objective',
                    'experience', 'education', 'skills', 'projects', 'work', 'professional',
                    'personal', 'contact', 'information', 'details', 'about', 'career',
                    'employment', 'history', 'background', 'qualifications', 'certifications',
                    'achievements', 'awards', 'references', 'languages', 'interests', 'hobbies',
                    'technical', 'declaration', 'address', 'phone', 'email', 'mobile',
                    'engineer', 'developer', 'manager', 'analyst', 'designer', 'consultant',
                    'specialist', 'executive', 'director', 'lead', 'senior', 'junior',
                    'software', 'web', 'data', 'full', 'stack', 'front', 'back', 'end'
                ]
                
                if any(keyword in line.lower() for keyword in skip_keywords):
                    continue
                
                # Check if line contains email or phone
                if '@' in line or any(char.isdigit() for char in line if len([c for c in line if c.isdigit()]) > 5):
                    continue
                
                # All words must be purely alphabetic and start with capital
                if all(word.isalpha() and word[0].isupper() for word in words):
                    name = line
                    break
            
            # Extract skills (normalized to lowercase)
            skills = extract_skills_from_text(text)
            
            # Extract projects
            projects = extract_projects_from_text(text)
            
            # Extract experience text for matching
            experience_text = extract_experience_text(text)

        if not email:
            email = extract_email_from_raw_file(file_path)
            if email:
                print(f"   Recovered email via raw file scan: {email}")
                    
    except Exception as e:
        print(f"Error in resume extraction: {e}")
    
    # Fallback to filename if no name found in document
    if not name and original_filename:
        name = clean_candidate_name(os.path.splitext(original_filename)[0])
    elif name:
        name = clean_candidate_name(name)
    elif not name:
        name = "Unknown Candidate"
    
    return {
        'name': name,
        'email': email,
        'phone': phone,
        'skills': skills,
        'projects': projects,
        'experience_text': experience_text,
        'full_text': text  # Add full extracted text
    }

def extract_skills_from_text(text: str) -> list:
    """Extract technical skills from resume text - Enhanced version with case normalization"""
    import re
    
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
    
    skills = []
    skill_set = set()  # Use set to avoid duplicates
    
    # Find SKILLS section - stop at next major section
    skills_match = re.search(r'(?:TECHNICAL\s+)?SKILLS?\s*:?\s*[\n\r]+(.*?)(?=\n\s*(?:WORK\s+EXPERIENCE|EXPERIENCE|EDUCATION|PROJECTS?|CERTIFICATIONS?|REFERENCES)\s*:?\s*$|\Z)', text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
    
    if not skills_match:
        print("   No SKILLS section found, using pattern matching...")
        # Fallback to pattern matching
        skill_patterns = [
            r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala|R|MATLAB|Perl|Dart)\b',
            r'\b(?:React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|Rails|HTML5?|CSS3?|Bootstrap|Tailwind|jQuery|Next\.js|Nuxt|FastAPI|Spring Boot)\b',
            r'\b(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Oracle|SQL|SQL Server|Cassandra|DynamoDB|Firebase|MariaDB|Elasticsearch)\b',
            r'\b(?:AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|GitHub|GitLab|CI/CD|Terraform|Ansible|Heroku|Netlify)\b',
            r'\b(?:Machine Learning|Deep Learning|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn|Data Analysis|AI|NLP|Keras|OpenCV)\b',
            r'\b(?:REST API|GraphQL|Microservices|Linux|Unix|Bash|Shell|PowerShell|API|RESTful)\b',
            r'\b(?:Jira|Confluence|Slack|Postman|VS Code|IntelliJ|Eclipse|Figma|Photoshop)\b'
        ]
        
        for pattern in skill_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                skill_set.add(match.strip())  # Keep original casing
        
        skills = list(skill_set)[:30]
        print(f"   Found {len(skills)} skills via pattern matching")
        return skills
    
    skills_text = skills_match.group(1).strip()
    print(f"   Found SKILLS section: {skills_text[:100]}...")
    
    # Filter out section headers
    section_headers = [
        'work experience', 'experience', 'education', 'projects', 'certifications',
        'professional experience', 'employment history', 'work history'
    ]
    
    # Parse all lines in skills section
    lines = skills_text.split('\n')
    
    for line in lines:
        line = line.strip()
        if not line or len(line) < 2:
            continue
        
        # Skip section headers
        if any(header in line.lower() for header in section_headers):
            break
            
        # Check if line has "Category: item1, item2, item3" format
        if ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                category = parts[0].strip()
                items_str = parts[1].strip()
                
                # Skip if category is a section header
                if any(header in category.lower() for header in section_headers):
                    break
                
                # Split by comma and add each skill (keep original)
                items = [item.strip() for item in items_str.split(',')]
                for item in items:
                    if item and len(item) >= 2 and not any(header in item.lower() for header in section_headers):
                        skill_set.add(item)  # Keep original
        else:
            # Simple comma-separated list
            items = [item.strip() for item in line.split(',')]
            for item in items:
                if item and len(item) >= 2 and not any(header in item.lower() for header in section_headers):
                    skill_set.add(item)  # Keep original
    
    skills = list(skill_set)[:30]
    print(f"   Extracted {len(skills)} skills: {skills}")
    return skills

def extract_projects_from_text(text: str) -> list:
    """Extract project information from resume text"""
    import re
    
    projects = []
    
    # Look for project sections
    project_patterns = [
        r'(?:PROJECT|PROJECTS?)\s*:?\s*([^\n]+(?:\n(?!\b(?:EXPERIENCE|EDUCATION|SKILLS|WORK)\b)[^\n]*)*)',
        r'(?:Personal|Side|Open Source)\s+Project[s]?\s*:?\s*([^\n]+)',
    ]
    
    for pattern in project_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            if len(match.strip()) > 20:  # Only meaningful project descriptions
                projects.append(match.strip()[:200])  # Limit length
    
    return projects[:5]  # Limit to 5 projects

def extract_experience_text(text: str) -> str:
    """Extract work experience section from resume"""
    import re
    
    # Look for experience section
    exp_patterns = [
        r'(?:WORK\s+)?EXPERIENCE\s*:?\s*([^\n]+(?:\n(?!\b(?:EDUCATION|SKILLS|PROJECTS?)\b)[^\n]*)*)',
        r'(?:PROFESSIONAL|EMPLOYMENT)\s+(?:EXPERIENCE|HISTORY)\s*:?\s*([^\n]+(?:\n(?!\b(?:EDUCATION|SKILLS|PROJECTS?)\b)[^\n]*)*)',
    ]
    
    for pattern in exp_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1).strip()[:1000]  # Limit to 1000 chars
    
    return ""

# Job Configuration (role-specific scoring)
JOB_CONFIG = {
    "default": {
        "required_skills": ["html", "css", "javascript", "python", "sql"],
        "optional_skills": ["react", "git", "api", "docker", "aws"],
        "transferable_signals": ["dashboard", "system", "application", "web", "project"],
        "education_required": False,
        "max_score": 10
    },
    "software engineer": {
        "required_skills": ["programming", "algorithms", "data structures"],
        "optional_skills": ["python", "java", "javascript", "git", "testing"],
        "transferable_signals": ["development", "coding", "software", "application", "system"],
        "education_required": False,
        "max_score": 10
    },
    "web developer": {
        "required_skills": ["html", "css", "javascript"],
        "optional_skills": ["react", "angular", "vue", "node.js", "sql"],
        "transferable_signals": ["website", "web application", "frontend", "backend", "responsive"],
        "education_required": False,
        "max_score": 10
    },
    "data scientist": {
        "required_skills": ["python", "statistics", "machine learning"],
        "optional_skills": ["tensorflow", "pytorch", "pandas", "sql", "visualization"],
        "transferable_signals": ["data analysis", "modeling", "prediction", "analytics", "research"],
        "education_required": False,
        "max_score": 10
    },
    "hr executive": {
        "required_skills": ["recruitment", "employee relations", "hr operations"],
        "optional_skills": ["payroll", "compliance", "performance management"],
        "transferable_signals": ["hiring", "team management", "people management", "entrepreneur", "founder", "leadership"],
        "education_required": False,
        "max_score": 10
    }
}

def get_job_config(job_title: str) -> dict:
    """Get job configuration, fallback to default"""
    if not job_title:
        return JOB_CONFIG["default"]
    
    job_key = job_title.lower().strip()
    return JOB_CONFIG.get(job_key, JOB_CONFIG["default"])

def generate_reasoning(job_role: str, matched_required: list, transferable_hits: list, score: float, decision: str) -> str:
    """Generate 3-line reasoning for the score"""
    lines = []
    
    if matched_required:
        lines.append(f"Matches core requirements for {job_role} with relevant skill alignment.")
    else:
        lines.append(f"Lacks direct role-specific skills but shows adjacent experience.")
    
    if transferable_hits:
        lines.append(f"Transferable experience identified ({', '.join(transferable_hits[:2])}).")
    else:
        lines.append("Limited evidence of transferable responsibilities.")
    
    lines.append(f"Overall assessment results in a {decision.lower()} based on available evidence.")
    
    return " ".join(lines)

def analyze_resume_with_ai(candidate_data: dict, job_description: dict) -> dict:
    """Intelligent ATS evaluation with contextual reasoning"""
    
    # Extract data
    name = candidate_data.get('name', 'Unknown')
    email = candidate_data.get('email', '')
    phone = candidate_data.get('phone', '')
    skills = candidate_data.get('skills', [])
    experience_text = candidate_data.get('experience_text', '')
    projects = candidate_data.get('projects', [])
    full_text = candidate_data.get('full_text', '')
    
    # Job details
    job_title = job_description.get('title', 'Position')
    job_desc = job_description.get('description', '')
    job_requirements = job_description.get('requirements', '')
    job_skills = job_description.get('skills', [])
    
    # Perform contextual analysis
    evaluation = evaluate_candidate_contextually(resume_text=full_text, job_title=job_title, job_description=job_desc, job_requirements=job_requirements, candidate_skills=skills, experience_text=experience_text, projects=projects, job_skills=job_skills)
    
    return {
        "candidate_name": name,
        "Email": email,
        "Mobile_Number": phone,
        "match_score": evaluation['match_score'],
        "match_label": evaluation['match_label'],
        "candidate_summary": evaluation['candidate_summary'],
        "key_strengths": evaluation['key_strengths'],
        "skill_gaps": evaluation['skill_gaps'],
        "ai_analysis": evaluation['ai_analysis'],
        "jobTitle": job_title,
        "jobDescription": job_desc,
        "resumeText": full_text[:1000],
        "status": evaluation['status']
    }


def get_job_data(db: Session, job_id: Optional[UUID]) -> dict:
    """Load job data once and reuse it across batch processing."""
    if not job_id:
        return {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': []
        }

    job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
    if not job:
        return {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': []
        }

    return {
        'title': job.title,
        'description': job.description or '',
        'requirements': job.requirements or '',
        'skills': job.skills or []
    }


def generate_unique_candidate_id(db: Session, name: str, job_id: Optional[UUID]) -> str:
    """Generate a unique candidate ID for bulk operations."""
    name_prefix = name[:3].upper() if name else "UNK"
    job_suffix = str(job_id) if job_id else "000"
    candidate_id = f"{name_prefix}{job_suffix}"
    base_id = candidate_id
    counter = 1

    while db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first():
        candidate_id = f"{base_id}{counter}"
        counter += 1

    return candidate_id


def set_upload_progress(upload_id: str, **kwargs):
    progress = upload_progress_store.get(upload_id, {})
    progress.update(kwargs)
    upload_progress_store[upload_id] = progress


def is_valid_resume_upload(file: UploadFile) -> bool:
    return (
        file.content_type in ALLOWED_RESUME_CONTENT_TYPES
        or any(file.filename.lower().endswith(ext) for ext in ALLOWED_RESUME_EXTENSIONS)
    )


def get_default_job_data() -> dict:
    return {
        'title': 'General Position',
        'description': 'General professional role',
        'requirements': 'Professional experience with relevant skills',
        'skills': ['communication', 'teamwork', 'problem solving']
    }


def build_batch_candidate_id(name: str, job_id: Optional[UUID]) -> str:
    """Generate a unique batch-safe candidate id without extra database lookups."""
    name_prefix = (name or "UNK")[:3].upper()
    job_token = str(job_id).replace("-", "")[:6].upper() if job_id else "000000"
    return f"{name_prefix}{job_token}{uuid.uuid4().hex[:8].upper()}"


def process_saved_resume(file_path: str, original_filename: str, job_data: dict) -> dict:
    """Run extraction and scoring for one saved resume file."""
    resume_data = extract_resume_data(file_path, original_filename)
    analysis_data = {
        'name': resume_data['name'],
        'email': resume_data['email'],
        'phone': resume_data['phone'],
        'skills': resume_data['skills'],
        'experience_text': resume_data['experience_text'],
        'projects': resume_data['projects'],
        'full_text': resume_data['full_text']
    }
    ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
    return {
        "resume_data": resume_data,
        "ai_analysis": ai_analysis,
    }


def apply_resume_analysis(
    candidate: Candidate,
    ai_analysis: Optional[dict] = None,
    job_title: Optional[str] = None,
):
    """Apply analysis results without forcing a commit for every candidate."""
    candidate.parsing_status = ParsingStatus.COMPLETED

    if ai_analysis:
        score = ai_analysis.get('match_score', 0)
        if score == 0 and candidate.resume_text and len(candidate.resume_text.strip()) > 100:
            score = 45

        candidate.resume_score = score
        candidate.summary = ai_analysis.get('candidate_summary', '')

        if candidate.resume_text and job_title:
            try:
                candidate.predefined_questions = generate_interview_questions(
                    candidate.resume_text,
                    job_title,
                    candidate.skills or []
                )
            except Exception as exc:
                print(f"Question generation failed: {exc}")

        threshold = candidate.score_threshold or 60
        if score >= threshold:
            candidate.stage = CandidateStage.SHORTLISTED
        elif score >= (threshold - 10):
            candidate.stage = CandidateStage.REVIEW
        else:
            candidate.stage = CandidateStage.RESUME_REJECTED
    else:
        candidate.resume_score = 40
        candidate.stage = CandidateStage.REVIEW if candidate.job_id else CandidateStage.APPLIED


def finalize_batch_notifications(
    background_tasks: Optional[BackgroundTasks],
    db: Session,
    candidates: List[Candidate],
    user_id=None,
):
    pending_notifications = []
    for candidate in candidates:
        if candidate.stage in [CandidateStage.SHORTLISTED, CandidateStage.RESUME_REJECTED]:
            notification = queue_notification_for_stage(
                db,
                candidate=candidate,
                stage_value=candidate.stage.value,
                user_id=user_id,
            )
            if notification:
                pending_notifications.append(notification["communication_id"])

    if pending_notifications:
        try:
            db.commit()
            for communication_id in pending_notifications:
                if background_tasks:
                    background_tasks.add_task(send_email_task, communication_id)
                else:
                    send_email_task(communication_id)
        except Exception:
            db.rollback()
            raise


def process_single_resume_upload(
    upload_id: str,
    file_path: str,
    original_filename: str,
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
):
    """Process a single resume after the response so uploads return quickly."""
    db = SessionLocal()

    try:
        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="processing",
            message="Analyzing resume...",
        )

        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")

        processed = process_saved_resume(file_path, original_filename, job_data)
        resume_data = processed["resume_data"]

        candidate = Candidate(
            name=resume_data['name'],
            email=resume_data['email'],
            phone=resume_data['phone'],
            skills=resume_data['skills'],
            resume_file_path=file_path,
            resume_text=resume_data['full_text'],
            candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
            job_id=job_id,
            agency_id=agency_id,
            created_by=current_user_id,
            assigned_to_user_id=current_user_id,
            parsing_status=ParsingStatus.PROCESSING,
            score_threshold=threshold
        )
        apply_resume_analysis(candidate, processed["ai_analysis"], job_title=job_title)
        db.add(candidate)
        db.commit()
        db.refresh(candidate)

        set_upload_progress(
            upload_id,
            current=1,
            total=1,
            status="completed",
            message="Resume analyzed successfully",
            candidate_id=str(candidate.id),
        )
        finalize_batch_notifications(None, db, [candidate], user_id=current_user_id)
    except Exception as exc:
        db.rollback()
        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="error",
            message=f"Upload failed: {exc}",
        )
        print(f"Single upload processing failed for {original_filename}: {exc}")
    finally:
        db.close()


def process_bulk_upload_batch(
    upload_id: str,
    saved_files: List[dict],
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
):
    """Process bulk uploads after the response so the request returns quickly."""
    db = SessionLocal()

    try:
        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")
        total_count = len(saved_files)
        processed_count = 0
        processed_candidates = []

        set_upload_progress(
            upload_id,
            current=0,
            total=total_count,
            status="processing",
            message="Screening resumes...",
        )

        worker_count = get_bulk_processing_workers(total_count)
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(process_saved_resume, item["file_path"], item["filename"], job_data): item
                for item in saved_files
            }
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    processed = future.result()
                    resume_data = processed["resume_data"]
                    candidate = Candidate(
                        name=resume_data['name'],
                        email=resume_data['email'],
                        phone=resume_data['phone'],
                        skills=resume_data['skills'],
                        resume_file_path=item["file_path"],
                        resume_text=resume_data['full_text'],
                        candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
                        job_id=job_id,
                        agency_id=agency_id,
                        created_by=current_user_id,
                        assigned_to_user_id=current_user_id,
                        parsing_status=ParsingStatus.PROCESSING,
                        score_threshold=threshold
                    )
                    apply_resume_analysis(candidate, processed["ai_analysis"], job_title=job_title)
                    db.add(candidate)
                    processed_candidates.append(candidate)
                except Exception as exc:
                    print(f"Bulk processing failed for {item['filename']}: {exc}")
                finally:
                    processed_count += 1
                    set_upload_progress(
                        upload_id,
                        current=processed_count,
                        total=total_count,
                        status="processing" if processed_count < total_count else "completed",
                        message=f"Screened {processed_count} of {total_count} resumes",
                    )

        if processed_candidates:
            db.commit()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="completed",
                message=f"Completed screening {len(processed_candidates)} of {total_count} resumes",
                processed=len(processed_candidates),
            )
            finalize_batch_notifications(None, db, processed_candidates, user_id=current_user_id)
        else:
            db.rollback()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="error",
                message="No resumes could be processed",
            )
    except Exception as exc:
        db.rollback()
        set_upload_progress(
            upload_id,
            current=0,
            total=len(saved_files),
            status="error",
            message=f"Bulk upload failed: {exc}",
        )
        print(f"Bulk upload background processing failed: {exc}")
    finally:
        db.close()


def process_zip_upload_batch(
    upload_id: str,
    zip_path: str,
    job_id: Optional[UUID],
    threshold: float,
    agency_id,
    current_user_id,
):
    """Process ZIP uploads after the response so large archives don't time out."""
    db = SessionLocal()

    try:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        job_data = get_job_data(db, job_id)
        if not job_data.get("title"):
            job_data = get_default_job_data()
        job_title = job_data.get("title", "")
        processed_count = 0
        total_count = upload_progress_store.get(upload_id, {}).get("total", 0)
        set_upload_progress(upload_id, status="processing", current=0, total=total_count, message="Screening resumes...")
        saved_files = []
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.filelist:
                file_ext = os.path.splitext(file_info.filename)[1].lower()
                if file_info.is_dir() or file_ext not in ALLOWED_RESUME_EXTENSIONS:
                    continue

                resume_content = zip_ref.read(file_info.filename)
                unique_filename = f"{uuid.uuid4()}{file_ext}"
                file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                with open(file_path, "wb") as resume_file:
                    resume_file.write(resume_content)
                saved_files.append({
                    "file_path": file_path,
                    "filename": file_info.filename,
                })

        processed_candidates = []
        failed_files = []
        worker_count = get_bulk_processing_workers(len(saved_files))

        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(process_saved_resume, item["file_path"], item["filename"], job_data): item
                for item in saved_files
            }
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    processed = future.result()
                    resume_data = processed["resume_data"]
                    candidate = Candidate(
                        name=resume_data['name'],
                        email=resume_data['email'],
                        phone=resume_data['phone'],
                        skills=resume_data['skills'],
                        resume_file_path=item["file_path"],
                        resume_text=resume_data['full_text'],
                        candidate_id=build_batch_candidate_id(resume_data['name'], job_id),
                        job_id=job_id,
                        agency_id=agency_id,
                        created_by=current_user_id,
                        assigned_to_user_id=current_user_id,
                        parsing_status=ParsingStatus.PROCESSING,
                        score_threshold=threshold
                    )
                    apply_resume_analysis(candidate, processed["ai_analysis"], job_title=job_title)
                    db.add(candidate)
                    processed_candidates.append(candidate)
                except Exception as exc:
                    failed_files.append({"filename": item["filename"], "error": str(exc)})
                    print(f"ZIP processing failed for {item['filename']}: {exc}")
                finally:
                    processed_count += 1
                    set_upload_progress(
                        upload_id,
                        current=processed_count,
                        total=total_count,
                        status="processing" if processed_count < total_count else "completed",
                        message=f"Screened {processed_count} of {total_count} resumes"
                    )

        if processed_candidates:
            db.commit()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="completed",
                message=f"Completed screening {processed_count} resumes"
            )
            finalize_batch_notifications(
                None,
                db,
                processed_candidates,
                user_id=current_user_id,
            )
        else:
            db.rollback()
            set_upload_progress(
                upload_id,
                current=processed_count,
                total=total_count,
                status="error",
                message="No resumes could be processed"
            )
    except Exception as exc:
        db.rollback()
        set_upload_progress(upload_id, status="error", message=str(exc))
        print(f"ZIP batch processing failed: {exc}")
    finally:
        try:
            if os.path.exists(zip_path):
                os.unlink(zip_path)
        finally:
            db.close()

def evaluate_candidate_contextually(resume_text: str, job_title: str, job_description: str, job_requirements: str, candidate_skills: list, experience_text: str, projects: list, job_skills: list = None) -> dict:
    """Evidence-based AI evaluation using LLM with structured scoring"""
    from app.config import settings
    import json
    
    print(f"\n🔍 Using Rule-Based Evaluation (LLM disabled)")
    
    # GROQ/OpenAI LLM code commented out - using only enhanced_fallback_evaluation
    # 
    # print(f"\n🔍 LLM Configuration Check:")
    # print(f"   GROQ_API_KEY: {'✅ SET' if settings.GROQ_API_KEY else '❌ NOT SET'}")
    # print(f"   LLM_PROVIDER: {settings.LLM_PROVIDER}")
    # 
    # # Enhanced prompt with weighted evaluation criteria
    # prompt = f"""You are a senior technical recruiter with 15+ years of experience..."""
    # 
    # try:
    #     # Try LLM analysis
    #     if settings.GROQ_API_KEY and settings.LLM_PROVIDER == "groq":
    #         print(f"   🤖 Using Groq LLM with enhanced evaluation...")
    #         response = call_groq_llm(prompt, settings.GROQ_API_KEY)
    #         print(f"   ✅ Groq LLM response received!")
    #     elif settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
    #         print(f"   🤖 Using OpenAI LLM with enhanced evaluation...")
    #         response = call_openai_llm(prompt, settings.OPENAI_API_KEY)
    #         print(f"   ✅ OpenAI LLM response received!")
    #     else:
    #         print(f"   ⚠️  No LLM configured, using enhanced fallback...")
    #         return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)
    #     
    #     # Parse LLM response
    #     result = json.loads(response)
    #     print(f"   ✅ LLM Score Breakdown:")
    #     
    #     # Support both old and new field names for backward compatibility
    #     if 'skills_score' in result:
    #         # New weighted scoring format
    #         print(f"      Skills Match: {result.get('skills_score', 0)}/45")
    #         print(f"      Experience: {result.get('experience_score', 0)}/25")
    #         print(f"      Projects: {result.get('projects_score', 0)}/15")
    #         print(f"      Education: {result.get('education_score', 0)}/10")
    #         print(f"      Soft Skills: {result.get('soft_skills_score', 0)}/5")
    #     else:
    #         # Old format (fallback)
    #         print(f"      Technical Depth: {result.get('technical_depth_score', 0)}/30")
    #         print(f"      Project Complexity: {result.get('project_complexity_score', 0)}/20")
    #         print(f"      Relevance: {result.get('relevance_score', 0)}/20")
    #         print(f"      Impact: {result.get('impact_score', 0)}/15")
    #         print(f"      Seniority: {result.get('seniority_score', 0)}/15")
    #     
    #     print(f"      TOTAL: {result.get('match_score', 0)}/100")
    #     return result
    #     
    # except Exception as e:
    #     print(f"   ❌ LLM evaluation failed: {e}")
    #     print(f"   ⚠️  Falling back to enhanced rule-based evaluation...")
    #     return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)
    
    # Always use enhanced fallback evaluation
    return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)

def call_groq_llm(prompt: str, api_key: str) -> str:
    """Call Groq LLM API"""
    import requests
    import re
    
    print(f"   📡 Calling Groq API with key: {api_key[:20]}...")
    
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": "llama-3.3-70b-versatile",  # Updated to latest model
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 1000,
                "response_format": {"type": "json_object"}
            },
            timeout=30
        )
        
        print(f"   📊 Groq API Status: {response.status_code}")
        
        if response.status_code != 200:
            print(f"   ❌ Groq API Error: {response.text}")
            raise Exception(f"Groq API returned {response.status_code}: {response.text}")
        
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        
        # Extract JSON from response (in case there's extra text)
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return content
        
    except requests.exceptions.Timeout:
        print(f"   ⏱️ Groq API timeout after 30s")
        raise
    except Exception as e:
        print(f"   ❌ Groq API call failed: {str(e)}")
        raise

def call_openai_llm(prompt: str, api_key: str) -> str:
    """Call OpenAI API"""
    import requests
    
    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens": 1000
        }
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

# JD-Driven Skill Maps
JOB_SKILL_MAPS = {
    "hr executive": {
        "core": ["recruitment", "hiring", "hr operations", "employee relations", "onboarding", "payroll", "compliance", "talent acquisition", "hr management", "human resources", "staffing", "benefits", "compensation"],
        "transferable": ["team management", "people management", "leadership", "coordination", "employee handling", "communication", "organization"],
        "ignore": ["javascript", "python", "java", "programming", "coding", "software", "development", "algorithm", "data structure", "react", "angular", "node", "api", "database", "sql", "html", "css"]
    },
    "software engineer": {
        "core": ["python", "java", "javascript", "react", "node", "sql", "mysql", "mongodb", "api", "rest", "git", "html", "css", "spring", "django", "flask"],
        "transferable": ["problem solving", "teamwork", "analytical", "debugging"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations", "onboarding", "talent acquisition", "human resources", "staffing", "benefits", "compensation"]
    },
    "web developer": {
        "core": ["html", "css", "javascript", "react", "angular", "vue", "node.js", "frontend", "backend", "web development", "responsive", "ui", "ux"],
        "transferable": ["problem solving", "teamwork", "design"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations"]
    },
    "data scientist": {
        "core": ["python", "statistics", "machine learning", "data analysis", "pandas", "numpy", "tensorflow", "pytorch", "sql", "r", "data mining", "modeling", "visualization"],
        "transferable": ["analytical thinking", "research", "problem solving"],
        "ignore": ["recruitment", "hr", "hiring", "payroll", "employee relations"]
    },
    "data analyst": {
        "core": ["data analysis", "sql", "excel", "tableau", "power bi", "statistics", "python", "r", "data visualization", "reporting"],
        "transferable": ["analytical thinking", "problem solving", "communication"],
        "ignore": ["recruitment", "hr", "hiring", "payroll"]
    },
    "marketing manager": {
        "core": ["marketing", "digital marketing", "seo", "sem", "social media", "content marketing", "brand management", "campaign", "analytics", "advertising"],
        "transferable": ["communication", "creativity", "strategy", "leadership"],
        "ignore": ["programming", "coding", "software development", "javascript", "python"]
    },
    "sales executive": {
        "core": ["sales", "business development", "client relationship", "negotiation", "crm", "lead generation", "closing", "revenue"],
        "transferable": ["communication", "persuasion", "networking"],
        "ignore": ["programming", "coding", "software development", "hr", "recruitment"]
    },
    "default": {"core": [], "transferable": ["communication", "teamwork"], "ignore": []}
}

def enhanced_fallback_evaluation(resume_text: str, job_title: str, job_description: str, job_requirements: str, candidate_skills: list, experience_text: str, projects: list, job_skills: list = None) -> dict:
    """Balanced scoring system using 5 components (Experience:35, Skills:30, Projects:20, Education:10, Soft Skills:5)"""
    from app.balanced_scoring import evaluate_resume_balanced, extract_years_experience
    
    print(f"\n📄 Balanced Scoring System:")
    print(f"   Job: {job_title}")
    
    # Extract years of experience
    years_exp = extract_years_experience(resume_text)
    
    # FIX: Use JD skills from database instead of hardcoded map
    if job_skills and len(job_skills) > 0:
        required_skills = job_skills[:10]
        print(f"   Using JD skills: {required_skills}")
    else:
        skill_map = JOB_SKILL_MAPS.get(job_title.lower().strip(), JOB_SKILL_MAPS["default"])
        required_skills = skill_map.get("core", [])[:10]
        print(f"   Fallback skills: {required_skills}")
    
    print(f"   Required skills for {job_title}: {required_skills}")
    
    # Prepare data for balanced scoring
    resume_data = {
        'full_text': resume_text,
        'years_of_experience': years_exp
    }
    
    # Determine experience range based on job title
    if 'senior' in job_title.lower():
        exp_min, exp_max = 5, 10
    elif 'junior' in job_title.lower() or 'entry' in job_title.lower():
        exp_min, exp_max = 0, 2
    else:
        exp_min, exp_max = 2, 5
    
    job_requirements_data = {
        'required_skills': required_skills,
        'experience_min': exp_min,
        'experience_max': exp_max,
        'description': job_description,
        'title': job_title
    }
    
    # Evaluate using balanced scoring
    result = evaluate_resume_balanced(resume_data, job_requirements_data)
    
    # Extract components
    components = result['components']
    final_score = result['total_score']
    
    print(f"   Experience: {components['experience']['score']}/35")
    print(f"   Skills: {components['skills']['score']}/30")
    print(f"   Projects: {components['projects']['score']}/20")
    print(f"   Education: {components['education']['score']}/10")
    print(f"   Soft Skills: {components['soft_skills']['score']}/5")
    print(f"   TOTAL: {final_score}/100")
    
    # Determine match label and status
    if final_score >= 80:
        match_label, status = "Strong Fit", "shortlisted"
    elif final_score >= 65:
        match_label, status = "Potential Fit", "shortlisted"
    elif final_score >= 50:
        match_label, status = "Borderline Fit", "review"
    else:
        match_label, status = "Weak Fit", "rejected"
    
    # Build strengths from components
    strengths = []
    if components['skills']['match_percentage'] >= 80:
        strengths.append(f"Excellent skills match: {len(components['skills']['matched_skills'])} of {len(required_skills)} required skills")
    elif components['skills']['match_percentage'] >= 50:
        strengths.append(f"Good skills match: {components['skills']['match_percentage']}%")
    
    if components['experience']['score'] >= 20:
        strengths.append(f"{years_exp} years experience - {components['experience']['assessment']}")
    
    if components['projects']['score'] >= 15:
        strengths.append("Strong project portfolio with relevant complexity")
    
    if components['education']['score'] >= 8:
        strengths.append(f"Education: {components['education']['relevance']}")
    
    if components['soft_skills']['leadership'] > 0 or components['soft_skills']['collaboration'] > 0:
        strengths.append(f"Leadership/collaboration: {components['soft_skills']['leadership']} + {components['soft_skills']['collaboration']} signals")
    
    if not strengths:
        strengths.append("Basic qualifications present")
    
    # Build gaps
    gaps = []
    if components['skills']['match_percentage'] < 50:
        missing_count = len(required_skills) - len(components['skills']['matched_skills'])
        gaps.append(f"Missing {missing_count} key skills from requirements")
    
    if components['experience']['score'] < 15:
        gaps.append(f"Experience mismatch: {components['experience']['assessment']}")
    
    if components['projects']['score'] < 10:
        gaps.append("Limited project complexity or relevance")
    
    if components['education']['score'] < 5:
        gaps.append("Education background not clearly relevant")
    
    if not gaps:
        gaps.append("No significant gaps identified")
    
    # Use the generated summary from balanced scoring
    candidate_summary = result['summary']
    
    # AI analysis
    ai_analysis = f"Balanced evaluation: Experience {components['experience']['score']}/35, "
    ai_analysis += f"Skills {components['skills']['score']}/30, "
    ai_analysis += f"Projects {components['projects']['score']}/20, "
    ai_analysis += f"Education {components['education']['score']}/10, "
    ai_analysis += f"Soft Skills {components['soft_skills']['score']}/5. "
    ai_analysis += f"Overall: {match_label} ({final_score}/100)."
    
    return {
        'match_score': round(final_score, 1),
        'match_label': match_label,
        'candidate_summary': candidate_summary,
        'key_strengths': strengths[:5],
        'skill_gaps': gaps[:5],
        'ai_analysis': ai_analysis,
        'status': status,
        'components': components  # Include detailed breakdown
    }

def extract_skills_from_job_text(job_text: str) -> list:
    """Extract skills from job description text"""
    import re
    
    # Technical skills patterns
    skill_patterns = [
        r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala|HTML|CSS)\b',
        r'\b(?:React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|Rails|jQuery)\b',
        r'\b(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Oracle|SQL Server|Cassandra|DynamoDB)\b',
        r'\b(?:AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|CI/CD|Terraform|Ansible)\b',
        r'\b(?:Machine Learning|Deep Learning|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn|AI)\b',
        r'\b(?:REST API|GraphQL|Microservices|Agile|Scrum|DevOps|Linux|Windows|macOS)\b'
    ]
    
    skills = set()
    for pattern in skill_patterns:
        matches = re.findall(pattern, job_text, re.IGNORECASE)
        skills.update([match.strip() for match in matches])
    
    return list(skills)

def simulate_resume_parsing(
    candidate: Candidate,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
    ai_analysis: dict = None,
    user_id=None,
):
    """Resume parsing with AI scoring, stage assignment, and auto-email for shortlisted"""
    
    candidate.parsing_status = ParsingStatus.COMPLETED
    
    if ai_analysis:
        # Set score from AI analysis
        score = ai_analysis.get('match_score', 0)
        
        # CRITICAL FIX: Never allow 0 score for valid resumes
        if score == 0 and candidate.resume_text and len(candidate.resume_text.strip()) > 100:
            print(f"⚠️ WARNING: Score is 0 but resume has {len(candidate.resume_text)} chars. Setting minimum score.")
            score = 45  # Minimum "Borderline Fit" score
        
        candidate.resume_score = score
        
        # Set summary from AI analysis
        candidate.summary = ai_analysis.get('candidate_summary', '')
        
        # Generate predefined interview questions based on resume and job
        if candidate.resume_text and candidate.job_id:
            try:
                from app.models import JobDescription
                job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
                if job:
                    questions = generate_interview_questions(candidate.resume_text, job.title, candidate.skills or [])
                    candidate.predefined_questions = questions
            except Exception as e:
                print(f"⚠️ Question generation failed: {e}")
        
        # NEW LOGIC: Set stage based on score thresholds with 10-point range
        threshold = candidate.score_threshold or 60
        
        if score >= threshold:
            # SHORTLISTED: Auto-send email
            candidate.stage = CandidateStage.SHORTLISTED
            
            # Auto-send email to shortlisted candidates
            try:
                from app.config import settings
                from app.mailer import is_email_configured, send_html_email
                from app.models import EmailCommunication, JobDescription, UserRole
                from urllib.parse import urlencode

                # Check admin wallet balance before sending email
                admin = db.query(User).filter(User.role == UserRole.ADMIN).first()
                if not admin or (admin.wallet_balance or 0) <= 0:
                    print(f"⚠️ Email blocked: Admin wallet has 0 credits")
                    raise Exception("Insufficient credits to send email")
                
                if is_email_configured() and candidate.email:
                    # Get job details
                    job = None
                    if candidate.job_id:
                        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
                    
                    # Build interview URL
                    params = {
                        'candidateId': candidate.id,
                        'name': candidate.name,
                        'email': candidate.email,
                    }
                    if job:
                        params['jobId'] = job.id
                        params['jobTitle'] = job.title
                    
                    interview_url = f"{settings.FRONTEND_URL}/interview?{urlencode(params)}"
                    
                    # Email content
                    subject = f"Interview Invitation - {job.title if job else 'Position'}"
                    message = f"Dear {candidate.name},\n\nCongratulations! Your resume has been shortlisted for the {job.title if job else 'position'}. Please book your interview slot using the button below."
                    
                    html_body = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                            <p>{message.replace(chr(10), '<br>')}</p>
                            <div style="margin: 30px 0; text-align: center;">
                                <a href="{settings.SLOT_BOOKING_URL}" 
                                   style="display: inline-block; padding: 15px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                                    Book Your Slot
                                </a>
                            </div>
                            <p style="font-size: 12px; color: #666; margin-top: 30px;">
                                View your interview details: <a href="{interview_url}">{interview_url}</a>
                            </p>
                        </div>
                    </body>
                    </html>
                    """
                    
                    # Send email
                    provider_message_id = send_html_email(
                        to_email=candidate.email,
                        subject=subject,
                        html_content=html_body
                    )

                    # Create EmailCommunication record
                    email_comm = EmailCommunication(
                        candidate_id=candidate.id,
                        candidate_name=candidate.name,
                        candidate_email=candidate.email,
                        email_type="Slot Selection Email",
                        status="sent",
                        sent_at=datetime.utcnow(),
                        provider_message_id=provider_message_id
                    )
                    db.add(email_comm)
                    
                    print(f"✅ Auto-email sent to {candidate.email} (SHORTLISTED)")
            except Exception as e:
                print(f"⚠️ Auto-email failed: {e}")
        
        elif score >= (threshold - 10):
            # REVIEW: Score within 10 points below threshold
            candidate.stage = CandidateStage.REVIEW
        else:
            # RESUME_REJECTED: Score more than 10 points below threshold
            candidate.stage = CandidateStage.RESUME_REJECTED
        
        print(f"✓ Candidate {candidate.name}: Score={candidate.resume_score}, Threshold={threshold}, Stage={candidate.stage.value}")
    else:
        # No AI analysis - set minimum score and move out of APPLIED
        candidate.resume_score = 40
        # If candidate has a job, put in REVIEW so they show in dashboard
        candidate.stage = CandidateStage.REVIEW if candidate.job_id else CandidateStage.APPLIED
        print(f"⚠ Candidate {candidate.name}: No AI analysis, score=40")
    
    db.commit()
    db.refresh(candidate)

def generate_interview_questions(resume_text: str, job_title: str, skills: list) -> str:
    """Generate 3-5 interview questions based on resume and job"""
    import random
    
    questions = []
    
    # Technical questions based on skills
    if skills:
        top_skills = skills[:3]
        for skill in top_skills:
            tech_questions = [
                f"Can you describe a project where you used {skill} and the challenges you faced?",
                f"How would you rate your proficiency in {skill} and what's your experience with it?",
                f"Tell me about a time when you had to learn {skill} quickly for a project."
            ]
            questions.append(random.choice(tech_questions))
    
    # Role-specific questions
    role_questions = {
        'software engineer': [
            "Describe your approach to debugging a complex production issue.",
            "How do you ensure code quality in your projects?",
            "Tell me about a time you optimized application performance."
        ],
        'backend': [
            "How do you design scalable APIs?",
            "Explain your experience with database optimization.",
            "Describe a challenging integration you've implemented."
        ],
        'frontend': [
            "How do you approach responsive design?",
            "Describe your experience with state management.",
            "How do you optimize frontend performance?"
        ]
    }
    
    job_lower = job_title.lower()
    for key, qs in role_questions.items():
        if key in job_lower:
            questions.extend(random.sample(qs, min(2, len(qs))))
            break
    
    # Generic behavioral questions
    behavioral = [
        "Tell me about a challenging project you worked on and how you overcame obstacles.",
        "Describe a situation where you had to work with a difficult team member.",
        "How do you prioritize tasks when working on multiple projects?"
    ]
    questions.append(random.choice(behavioral))
    
    # Return top 5 questions
    return "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions[:5])])


def simulate_resume_parsing(
    candidate: Candidate,
    db: Session,
    background_tasks: Optional[BackgroundTasks] = None,
    ai_analysis: dict = None,
    user_id=None,
    job_title: Optional[str] = None,
):
    """Override legacy parser flow with stage assignment and secure notification enqueueing."""
    apply_resume_analysis(candidate, ai_analysis, job_title=job_title)

    db.commit()
    db.refresh(candidate)

    if background_tasks and candidate.stage in [CandidateStage.SHORTLISTED, CandidateStage.RESUME_REJECTED]:
        enqueue_stage_notification(background_tasks, db, candidate, candidate.stage.value, user_id=user_id)

@router.get("/upload-progress/{upload_id}")
def get_upload_progress(
    upload_id: str,
    current_user: User = Depends(get_current_active_user)
):
    progress = upload_progress_store.get(upload_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Upload progress not found")

    return progress


@router.get("/count")
def get_candidates_count(
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[UUID] = None,
    min_score: Optional[float] = None,
    client: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription, UserRole
    query = db.query(Candidate)
    if current_user.role == UserRole.SUPER_ADMIN:
        if agency_id:
            query = query.filter(Candidate.agency_id == agency_id)
    else:
        query = _apply_candidate_list_scope(query, current_user)
    if client:
        query = query.join(JobDescription).filter(JobDescription.company_name == client)
    if search:
        query = query.filter(or_(Candidate.name.ilike(f"%{search}%"), Candidate.email.ilike(f"%{search}%")))
    if stage:
        query = query.filter(Candidate.stage == stage)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if min_score is not None:
        query = query.filter(Candidate.resume_score >= min_score)
    return {"count": query.count()}

@router.get("", response_model=List[CandidateResponse])
def get_candidates(
    page: int = 1,
    limit: int = 10,
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[UUID] = None,
    min_score: Optional[float] = None,
    client: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription, UserRole
    query = db.query(Candidate)

    if agency_id and current_user.role == UserRole.SUPER_ADMIN:
        query = query.filter(Candidate.agency_id == agency_id)
    else:
        query = _apply_candidate_list_scope(query, current_user)
    
    if client:
        query = query.join(JobDescription).filter(JobDescription.company_name == client)
    if search:
        query = query.filter(
            or_(
                Candidate.name.ilike(f"%{search}%"),
                Candidate.email.ilike(f"%{search}%")
            )
        )
    if stage:
        query = query.filter(Candidate.stage == stage)
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    if min_score is not None:
        query = query.filter(Candidate.resume_score >= min_score)
    candidates = query.order_by(Candidate.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    
    # Add job title to response
    result = []
    for c in candidates:
        candidate_dict = {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "current_company": c.current_company,
            "current_role": c.current_role,
            "experience_years": c.experience_years,
            "location": c.location,
            "linkedin_url": c.linkedin_url,
            "resume_file_path": c.resume_file_path,
            "resume_text": c.resume_text,
            "parsing_status": c.parsing_status,
            "resume_score": c.resume_score,
            "score_threshold": c.score_threshold,
            "skills": c.skills,
            "education": c.education,
            "work_experience": c.work_experience,
            "stage": c.stage,
            "stage_updated_at": c.stage_updated_at,
            "stage_entered_at": c.stage_entered_at,
            "applied_at": c.applied_at,
            "job_id": c.job_id,
            "job_title": c.job.title if c.job else None,
            "summary": c.summary,
            "predefined_questions": c.predefined_questions,
            "created_at": c.created_at
        }
        result.append(CandidateResponse(**candidate_dict))
    
    return result

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate_dict = {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "current_company": candidate.current_company,
        "current_role": candidate.current_role,
        "experience_years": candidate.experience_years,
        "location": candidate.location,
        "linkedin_url": candidate.linkedin_url,
        "resume_file_path": candidate.resume_file_path,
        "parsing_status": candidate.parsing_status,
        "resume_score": candidate.resume_score,
        "score_threshold": candidate.score_threshold,
        "skills": candidate.skills,
        "education": candidate.education,
        "work_experience": candidate.work_experience,
        "stage": candidate.stage,
        "stage_updated_at": candidate.stage_updated_at,
        "stage_entered_at": candidate.stage_entered_at,
        "applied_at": candidate.applied_at,
        "job_id": candidate.job_id,
        "job_title": candidate.job.title if candidate.job else None,
        "summary": candidate.summary,
        "predefined_questions": candidate.predefined_questions,
        "created_at": candidate.created_at
    }
    return CandidateResponse(**candidate_dict)

@router.post("", response_model=CandidateResponse)
def create_candidate(
    candidate: CandidateCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = Candidate(
        **candidate.model_dump(),
        agency_id=current_user.agency_id,
        created_by=current_user.id,
        assigned_to_user_id=current_user.id,
        parsing_status=ParsingStatus.PENDING
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    # Simulate resume parsing
    simulate_resume_parsing(db_candidate, db, background_tasks=background_tasks, user_id=current_user.id)
    
    return db_candidate

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    print(f"Upload received - job_id: {job_id}, file: {file.filename}, threshold: {threshold}")
    
    try:
        # Validate file type - PDF and Word documents
        valid_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ]
        valid_extensions = ['.pdf', '.doc', '.docx']
        
        is_valid = (file.content_type in valid_types or 
                   any(file.filename.lower().endswith(ext) for ext in valid_extensions))
        
        if not is_valid:
            raise HTTPException(status_code=400, detail="Only PDF and Word documents (.pdf, .doc, .docx) are allowed")
        
        # Create upload directory if not exists
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Save file
        file_ext = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        upload_id = str(uuid.uuid4())
        set_upload_progress(
            upload_id,
            current=0,
            total=1,
            status="queued",
            message="Resume queued for analysis",
        )
        background_tasks.add_task(
            process_single_resume_upload,
            upload_id,
            file_path,
            file.filename,
            job_id,
            threshold,
            current_user.agency_id,
            current_user.id,
        )

        return {
            "message": "Resume upload accepted and queued for analysis.",
            "upload_id": upload_id,
            "queued": 1,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/bulk-upload")
async def bulk_upload_resumes(
    files: List[UploadFile] = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    print(f"Bulk upload received - job_id: {job_id}, files: {len(files)}")
    results = []

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_files = []

    for file in files:
        try:
            if not is_valid_resume_upload(file):
                results.append({"filename": file.filename, "status": "failed", "error": "Invalid file type"})
                continue

            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)

            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            saved_files.append({
                "filename": file.filename,
                "file_path": file_path,
            })
        except Exception as e:
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})

    if not saved_files:
        return {"results": results}

    upload_id = str(uuid.uuid4())
    queued_files = [{"filename": item["filename"], "status": "queued"} for item in saved_files]
    queued_files.extend(results)
    set_upload_progress(
        upload_id,
        current=0,
        total=len(saved_files),
        status="queued",
        message=f"Queued {len(saved_files)} resumes for screening",
    )
    background_tasks.add_task(
        process_bulk_upload_batch,
        upload_id,
        saved_files,
        job_id,
        threshold,
        current_user.agency_id,
        current_user.id,
    )

    return {
        "message": f"Bulk upload accepted. {len(saved_files)} resumes queued for background processing.",
        "upload_id": upload_id,
        "queued": len(saved_files),
        "results": queued_files,
    }

@router.post("/zip-upload")
async def zip_upload_resumes(
    file: UploadFile = File(...),
    job_id: Optional[UUID] = Query(None),
    threshold: Optional[float] = Query(60),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Validate ZIP file
    if file.content_type != "application/zip" and not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed")

    try:
        # Save ZIP file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            content = await file.read()
            temp_zip.write(content)
            temp_zip_path = temp_zip.name

        upload_id = str(uuid.uuid4())

        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            queued_files = [
                {"filename": file_info.filename, "status": "queued"}
                for file_info in zip_ref.filelist
                if not file_info.is_dir() and os.path.splitext(file_info.filename)[1].lower() in ALLOWED_RESUME_EXTENSIONS
            ]

        set_upload_progress(
            upload_id,
            current=0,
            total=len(queued_files),
            status="queued",
            message=f"Queued {len(queued_files)} resumes for screening"
        )

        background_tasks.add_task(
            process_zip_upload_batch,
            upload_id,
            temp_zip_path,
            job_id,
            threshold,
            current_user.agency_id,
            current_user.id,
        )

        return {
            "message": f"ZIP upload accepted. {len(queued_files)} resumes queued for background processing.",
            "upload_id": upload_id,
            "queued": len(queued_files),
            "results": queued_files,
        }
    except Exception as e:
        if 'temp_zip_path' in locals() and os.path.exists(temp_zip_path):
            os.unlink(temp_zip_path)
        raise HTTPException(status_code=500, detail=f"ZIP upload failed: {str(e)}")

@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: UUID,
    candidate_update: CandidateUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    update_data = candidate_update.model_dump(exclude_unset=True)
    
    if "stage" in update_data:
        update_data["stage_updated_at"] = datetime.utcnow()
    
    for field, value in update_data.items():
        setattr(db_candidate, field, value)
    
    db.commit()
    db.refresh(db_candidate)
    if "stage" in update_data:
        enqueue_stage_notification(background_tasks, db, db_candidate, db_candidate.stage.value, user_id=current_user.id)
    return db_candidate

@router.patch("/{candidate_id}/stage", response_model=CandidateResponse)
def update_candidate_stage(
    candidate_id: UUID,
    stage_update: CandidateStageUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_candidate.stage = stage_update.stage
    db_candidate.stage_updated_at = datetime.utcnow()
    db_candidate.stage_entered_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_candidate)
    enqueue_stage_notification(background_tasks, db, db_candidate, db_candidate.stage.value, user_id=current_user.id)
    return db_candidate







@router.delete("/{candidate_id}")
def delete_candidate(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not db_candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Store candidate_id for sheets deletion
        sheets_candidate_id = db_candidate.candidate_id
        
        # Delete dependent records first to satisfy foreign key constraints
        from app.models import EmailCommunication, Interview, NotificationWorkflowToken
        db.query(Interview).filter(Interview.candidate_id == candidate_id).delete()
        db.query(EmailCommunication).filter(EmailCommunication.candidate_id == candidate_id).delete()
        db.query(NotificationWorkflowToken).filter(NotificationWorkflowToken.candidate_id == candidate_id).delete()
        
        # Try to delete resume file if exists (skip if fails on Railway)
        if db_candidate.resume_file_path:
            try:
                if os.path.exists(db_candidate.resume_file_path):
                    os.remove(db_candidate.resume_file_path)
            except Exception as e:
                print(f"File deletion skipped: {e}")
        
        # Delete candidate from database
        db.delete(db_candidate)
        db.commit()
        

        
        return {"message": "Candidate deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/{candidate_id}/resume-file")
async def get_resume_file(
    candidate_id: UUID,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """View resume file - supports PDF and Word documents"""
    from app.auth import verify_token
    from fastapi.responses import Response, HTMLResponse
    import base64
    
    try:
        if not token:
            raise HTTPException(status_code=401, detail="Token required")
        
        token_data = verify_token(token)
        if not token_data:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        
        user = db.query(User).filter(User.email == token_data.email).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        if not candidate.resume_file_path:
            raise HTTPException(status_code=404, detail="No resume file uploaded for this candidate")
        
        # Convert relative path to absolute path
        from app.config import settings
        
        # Handle different path formats
        print(f"🔍 Looking for resume file:")
        print(f"   Database path: {candidate.resume_file_path}")
        print(f"   UPLOAD_DIR setting: {settings.UPLOAD_DIR}")
        print(f"   Current working dir: {os.getcwd()}")
        
        if os.path.isabs(candidate.resume_file_path):
            file_path = candidate.resume_file_path
        else:
            # Try multiple possible locations
            filename = os.path.basename(candidate.resume_file_path)
            possible_paths = [
                candidate.resume_file_path,  # Try exact path first
                os.path.join(settings.UPLOAD_DIR, filename),
                os.path.join("/data", filename),
                os.path.join("/data/uploads", filename),
                os.path.join("/app/uploads", filename),
                os.path.join("/app/backend/uploads", filename),
                os.path.join(os.getcwd(), "uploads", filename)
            ]
            
            file_path = None
            for path in possible_paths:
                print(f"   Checking: {path} - Exists: {os.path.exists(path) if path else False}")
                if path and os.path.exists(path):
                    file_path = path
                    print(f"   ✅ Found at: {file_path}")
                    break
            
            if not file_path:
                # List what's actually in the upload directory
                try:
                    if os.path.exists(settings.UPLOAD_DIR):
                        files = os.listdir(settings.UPLOAD_DIR)
                        print(f"   Files in {settings.UPLOAD_DIR}: {files[:10]}")
                except:
                    pass
                raise HTTPException(status_code=404, detail=f"Resume file not found. Database path: {candidate.resume_file_path}. Upload dir: {settings.UPLOAD_DIR}. File doesn't exist on server - upload it after deployment.")
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail=f"Resume file not found at path: {file_path}")
        
        file_ext = os.path.splitext(candidate.resume_file_path)[1].lower()
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Convert Word to PDF for viewing, or return PDF directly
        if file_ext == '.pdf':
            return Response(
                content=file_content,
                media_type='application/pdf',
                headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume.pdf"'}
            )
        elif file_ext in ['.doc', '.docx']:
            # Try to convert Word to PDF for inline viewing
            try:
                import subprocess
                import tempfile
                
                # Create temp PDF file
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
                    temp_pdf_path = temp_pdf.name
                
                # Try LibreOffice conversion (if available)
                try:
                    subprocess.run(
                        ['soffice', '--headless', '--convert-to', 'pdf', '--outdir', 
                         os.path.dirname(temp_pdf_path), candidate.resume_file_path],
                        check=True, timeout=30, capture_output=True
                    )
                    converted_pdf = os.path.join(os.path.dirname(temp_pdf_path), 
                                                os.path.splitext(os.path.basename(candidate.resume_file_path))[0] + '.pdf')
                    
                    if os.path.exists(converted_pdf):
                        with open(converted_pdf, 'rb') as f:
                            pdf_content = f.read()
                        os.unlink(converted_pdf)
                        os.unlink(temp_pdf_path)
                        return Response(
                            content=pdf_content,
                            media_type='application/pdf',
                            headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume.pdf"'}
                        )
                except:
                    pass
                
                os.unlink(temp_pdf_path)
            except:
                pass
            
            # Fallback: download Word file
            media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if file_ext == '.docx' else 'application/msword'
            return Response(
                content=file_content,
                media_type=media_type,
                headers={"Content-Disposition": f'attachment; filename="{candidate.name}_resume{file_ext}"'}
            )
        else:
            # Other file types
            return Response(
                content=file_content,
                media_type='application/octet-stream',
                headers={"Content-Disposition": f'inline; filename="{candidate.name}_resume{file_ext}"'}
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Resume file error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to load resume: {str(e)}")

@router.get("/{candidate_id}/ai-analysis")
def get_ai_analysis(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get AI-powered resume analysis with structured data"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Get job description
    job_data = None
    if candidate.job_id:
        from app.models import JobDescription
        job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        if job:
            job_data = {
                'title': job.title,
                'description': job.description or '',
                'requirements': job.requirements or '',
                'skills': job.skills or []
            }
    
    if not job_data:
        job_data = {
            'title': 'General Position',
            'description': '',
            'requirements': '',
            'skills': []
        }
    
    # Prepare candidate data
    candidate_data = {
        'name': candidate.name,
        'email': candidate.email,
        'phone': candidate.phone,
        'skills': candidate.skills or [],
        'experience_text': '',
        'projects': [],
        'full_text': candidate.resume_text or ''
    }
    
    # Get AI analysis
    analysis = analyze_resume_with_ai(candidate_data, job_data)
    
    return analysis

@router.get("/{candidate_id}/resume-summary")
def get_resume_summary(
    candidate_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Generate AI summary based on candidate data
    summary_parts = []
    
    if candidate.current_role and candidate.current_company:
        summary_parts.append(f"Currently working as {candidate.current_role} at {candidate.current_company}")
    
    if candidate.experience_years:
        summary_parts.append(f"with {candidate.experience_years} years of professional experience")
    
    if candidate.skills and len(candidate.skills) > 0:
        top_skills = candidate.skills[:5]  # Top 5 skills
        summary_parts.append(f"Skilled in {', '.join(top_skills)}")
    
    if candidate.resume_score:
        score_desc = "excellent" if candidate.resume_score >= 80 else "good" if candidate.resume_score >= 60 else "average"
        summary_parts.append(f"Resume shows {score_desc} alignment with job requirements (score: {candidate.resume_score})")
    
    if not summary_parts:
        summary = "Limited information available. Resume parsing may be incomplete."
    else:
        summary = ". ".join(summary_parts) + "."
    
    return {"summary": summary}

@router.get("/pipeline/stages")
def get_pipeline_stages(
    client: Optional[str] = None,
    agency_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates grouped by stage for Kanban board"""
    from app.models import JobDescription, UserRole
    stages = {}
    for stage in CandidateStage:
        query = db.query(Candidate).filter(Candidate.stage == stage)
        if agency_id and current_user.role == UserRole.SUPER_ADMIN:
            query = query.filter(Candidate.agency_id == agency_id)
        else:
            query = _apply_candidate_list_scope(query, current_user)
        if client:
            query = query.join(JobDescription).filter(JobDescription.company_name == client)
        candidates = query.all()
        stages[stage.value] = [
            {
                "id": c.id,
                "name": c.name,
                "current_role": c.current_role,
                "current_company": c.current_company,
                "resume_score": c.resume_score,
                "job_title": c.job.title if c.job else None,
                "company_name": c.job.company_name if c.job else None,
                "stage": c.stage.value if c.stage else None,
                "stage_entered_at": c.stage_entered_at.isoformat() if c.stage_entered_at else None,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None
            }
            for c in candidates
        ]
    return stages

@router.post("/bulk-assign")
def bulk_assign_candidates(
    assignment_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk assign candidates to a user (Admin only)"""
    from app.models import UserRole, ReviewStatus
    
    # Admin only
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate_ids = assignment_data.get('candidate_ids', [])
    user_id = assignment_data.get('user_id')
    
    if not candidate_ids or not user_id:
        raise HTTPException(status_code=400, detail="Missing candidate_ids or user_id")
    
    # Verify user exists
    assigned_user = db.query(User).filter(User.id == user_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update candidates and collect names
    updated_count = 0
    candidate_names = []
    for candidate_id in candidate_ids:
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if candidate:
            candidate.assigned_to_user_id = user_id
            candidate.review_status = ReviewStatus.PENDING
            candidate_names.append(candidate.name)
            updated_count += 1
    
    db.commit()
    
    return {"message": f"Successfully assigned {updated_count} candidates to {assigned_user.full_name}", "updated_count": updated_count}

@router.post("/send-email")
def send_email(
    email_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Send email to candidate with interview details link and slot booking button"""
    from app.config import settings
    from app.mailer import is_email_configured, send_html_email
    from urllib.parse import urlencode
    from app.models import EmailCommunication
    
    try:
        candidate_id = email_data.get('candidate_id')
        subject = email_data.get('subject')
        message = email_data.get('message')
        
        if not all([candidate_id, subject, message]):
            raise HTTPException(status_code=400, detail="Missing required fields: candidate_id, subject, message")
        
        # Get candidate details
        candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Get job details
        job = None
        if candidate.job_id:
            from app.models import JobDescription
            job = db.query(JobDescription).filter(JobDescription.id == candidate.job_id).first()
        
        # Check if email service is configured
        if not is_email_configured():
            error_msg = (
                "Email service is not configured. Set RESEND_API_KEY "
                "(or SENDGRID_API_KEY for fallback), FROM_EMAIL, and FROM_NAME "
                "in Railway environment variables."
            )
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # Build interview details URL with query parameters (including job description and resume text)
        params = {
            'candidateId': candidate.id,
            'name': candidate.name,
            'email': candidate.email,
        }
        if job:
            params['jobId'] = job.id
            params['jobTitle'] = job.title
        
        interview_url = f"{settings.FRONTEND_URL}/interview?{urlencode(params)}"
        
        # Build HTML email with slot booking button
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <p>{message.replace(chr(10), '<br>')}</p>
                
                <div style="margin: 30px 0; text-align: center;">
                    <a href="{settings.SLOT_BOOKING_URL}" 
                       style="display: inline-block; padding: 15px 30px; background-color: #2563eb; color: white; text-decoration: none; border-radius: 5px; font-weight: bold;">
                        Book Your Slot
                    </a>
                </div>
                
                <p style="font-size: 12px; color: #666; margin-top: 30px;">
                    View your interview details: <a href="{interview_url}">{interview_url}</a>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Send email via configured provider
        provider_message_id = send_html_email(
            to_email=candidate.email,
            subject=subject,
            html_content=html_body
        )
        
        # Determine email type based on subject
        email_type = "Slot Selection Email"
        if "reject" in subject.lower() or "decline" in subject.lower():
            email_type = "Rejection Email"
        elif "reschedule" in subject.lower():
            email_type = "Interview Rescheduled"
        
        # Create EmailCommunication record
        email_comm = EmailCommunication(
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            candidate_email=candidate.email,
            email_type=email_type,
            status="sent",
            sent_at=datetime.utcnow(),
            provider_message_id=provider_message_id
        )
        db.add(email_comm)
        db.commit()
        
        print(f"✅ Email sent to {candidate.email} - Message-ID: {provider_message_id}")
        print(f"   Email type: {email_type}")
        print(f"   Interview URL: {interview_url}")
        print(f"   Slot Booking: {settings.SLOT_BOOKING_URL}")
        
        return {
            "success": True,
            "message": f"Email sent to {candidate.email}",
            "interview_url": interview_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")









@router.patch("/{candidate_id}/notes")
def update_candidate_notes(
    candidate_id: UUID,
    notes_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Update internal notes for a candidate"""
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    candidate.internal_notes = notes_data.get('notes', '')
    db.commit()
    db.refresh(candidate)
    
    return {"message": "Notes updated successfully", "notes": candidate.internal_notes}


@router.post("/{candidate_id}/assign")
def assign_candidate_to_user(
    candidate_id: UUID,
    assign_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign candidate to a user for review (Admin only)"""
    from app.models import ReviewStatus
    
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign resumes")
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    assigned_to_user_id = assign_data.get('assigned_to_user_id')
    if not assigned_to_user_id:
        raise HTTPException(status_code=400, detail="assigned_to_user_id is required")
    
    # Verify user exists
    assigned_user = db.query(User).filter(User.id == assigned_to_user_id).first()
    if not assigned_user:
        raise HTTPException(status_code=404, detail="Assigned user not found")
    
    candidate.assigned_to_user_id = assigned_to_user_id
    candidate.review_status = ReviewStatus.PENDING
    candidate.reviewed_at = None
    candidate.reviewed_by_user_id = None
    
    db.commit()
    db.refresh(candidate)
    
    return {"message": f"Candidate assigned to {assigned_user.full_name}", "candidate_id": candidate.id}

@router.post("/{candidate_id}/review")
def review_candidate(
    candidate_id: UUID,
    review_data: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Review candidate - send interview invitation or reject"""
    from app.models import ReviewStatus
    from datetime import datetime
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Check if user is assigned to this candidate
    if candidate.assigned_to_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You are not assigned to review this candidate")
    
    action = review_data.get('action')  # "interview" or "reject"
    
    if action == "interview":
        candidate.review_status = ReviewStatus.INTERVIEW_INVITED
        candidate.stage = CandidateStage.INTERVIEW_SCHEDULED
        message = "Interview invitation sent"
    elif action == "reject":
        candidate.review_status = ReviewStatus.REJECTED
        candidate.stage = CandidateStage.REJECTED
        message = "Candidate rejected"
    else:
        raise HTTPException(status_code=400, detail="Invalid action. Use 'interview' or 'reject'")
    
    candidate.reviewed_at = datetime.utcnow()
    candidate.reviewed_by_user_id = current_user.id
    
    db.commit()
    db.refresh(candidate)
    enqueue_stage_notification(background_tasks, db, candidate, candidate.stage.value, user_id=current_user.id)
    
    return {"message": message, "candidate_id": candidate.id, "review_status": candidate.review_status.value}

@router.get("/assigned/me")
def get_my_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates assigned to current user"""
    from app.models import ReviewStatus
    
    candidates = db.query(Candidate).filter(
        Candidate.assigned_to_user_id == current_user.id
    ).all()
    
    result = []
    for c in candidates:
        result.append({
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "resume_score": c.resume_score,
            "job_title": c.job.title if c.job else None,
            "review_status": c.review_status.value if c.review_status else "unassigned",
            "assigned_at": c.created_at.isoformat() if c.created_at else None,
            "reviewed_at": c.reviewed_at.isoformat() if c.reviewed_at else None
        })
    
    return result


@router.post("/{candidate_id}/assign-legacy")
def assign_candidate(
    candidate_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Assign candidate to a user for review (Admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    candidate.assigned_to_user_id = user_id
    candidate.review_status = "PENDING"
    db.commit()
    
    return {"message": f"Candidate assigned to {user.full_name}", "assigned_to": user.full_name}

@router.get("/assigned-to-me")
def get_my_assigned_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates assigned to current user"""
    candidates = db.query(Candidate).filter(
        Candidate.assigned_to_user_id == current_user.id
    ).all()
    
    return [{
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "resume_score": c.resume_score,
        "job_title": c.job.title if c.job else None,
        "review_status": c.review_status.value if c.review_status else "UNASSIGNED",
        "assigned_at": c.updated_at
    } for c in candidates]


@router.post("/bulk-assign")
def bulk_assign_candidates(
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bulk assign multiple candidates to a user (Admin only)"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can assign candidates")
    
    candidate_ids = data.get('candidate_ids', [])
    user_id = data.get('user_id')
    
    if not candidate_ids or not user_id:
        raise HTTPException(status_code=400, detail="candidate_ids and user_id are required")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    assigned_count = 0
    for cid in candidate_ids:
        candidate = db.query(Candidate).filter(Candidate.id == cid).first()
        if candidate:
            candidate.assigned_to_user_id = user_id
            candidate.review_status = "PENDING"
            assigned_count += 1
    
    db.commit()
    
    return {
        "message": f"{assigned_count} candidates assigned to {user.full_name}",
        "assigned_count": assigned_count,
        "assigned_to": user.full_name
    }



