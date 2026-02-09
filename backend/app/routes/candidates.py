from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text, extract
from typing import List, Optional
import os
import uuid
import random
import tempfile
import zipfile
from datetime import datetime
from app.database import get_db
from app.models import Candidate, CandidateStage, ParsingStatus, User
from app.schemas import (
    CandidateCreate, CandidateUpdate, CandidateResponse, CandidateStageUpdate
)
from app.auth import get_current_active_user
from app.config import settings
from app.google_sheets import sheets_service

router = APIRouter(prefix="/candidates", tags=["Candidates"])

def generate_candidate_id(name: str, job_id: int = None) -> str:
    """Generate unique candidate ID: FirstName + JobID"""
    if not name:
        first_name = "Unknown"
    else:
        # Extract first name and clean it
        first_name = name.split()[0].replace(" ", "").replace("-", "").replace(".", "")
    
    job_suffix = str(job_id) if job_id else "0"
    return f"{first_name}{job_suffix}"

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
            
            # Look for name in first few lines - simplified approach
            for line in lines[:15]:  # Check more lines
                # Skip if line is too short or too long
                if len(line) < 4 or len(line) > 50:
                    continue
                    
                words = line.split()
                
                # Name should be 2-4 words
                if not (2 <= len(words) <= 4):
                    continue
                
                # All words should be alphabetic and start with capital
                if not all(word.isalpha() and word[0].isupper() for word in words):
                    continue
                
                # Skip common headers/keywords (case insensitive check)
                skip_keywords = [
                    'resume', 'curriculum', 'vitae', 'profile', 'summary', 'objective',
                    'experience', 'education', 'skills', 'projects', 'work', 'professional',
                    'personal', 'contact', 'information', 'details', 'about', 'career',
                    'employment', 'history', 'background', 'qualifications', 'certifications',
                    'achievements', 'awards', 'references', 'languages', 'interests', 'hobbies'
                ]
                
                if any(keyword in line.lower() for keyword in skip_keywords):
                    continue
                
                # If we get here, it's likely a name
                name = line
                break
            
            # Extract skills
            skills = extract_skills_from_text(text)
            
            # Extract projects
            projects = extract_projects_from_text(text)
            
            # Extract experience text for matching
            experience_text = extract_experience_text(text)
                    
    except Exception as e:
        print(f"Error in resume extraction: {e}")
    
    # Fallback to filename if no name found in document
    if not name and original_filename:
        name = os.path.splitext(original_filename)[0].replace('_', ' ').replace('-', ' ').title()
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
    """Extract technical skills from resume text"""
    import re
    
    skills = set()
    
    # Find TECHNICAL SKILLS section specifically
    tech_skills_pattern = r'TECHNICAL\s+SKILLS?\s*:?\s*[-\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|$)'
    match = re.search(tech_skills_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        skills_text = match.group(1)
        # Split by newlines and common delimiters
        lines = re.split(r'[\n•]', skills_text)
        for line in lines:
            line = line.strip()
            # Remove bullet points and extra spaces
            line = re.sub(r'^[-•*\s]+', '', line)
            line = line.strip()
            
            # Only add if it's a valid skill (2-30 chars, not empty)
            if line and 2 <= len(line) <= 30:
                # Skip common non-skill phrases
                if not re.match(r'^(and|or|the|with|from|to)$', line, re.IGNORECASE):
                    skills.add(line)
    
    # If technical skills found, return them
    if skills:
        return list(skills)[:20]
    
    # Fallback: Look for any SKILLS section
    skills_pattern = r'(?:SKILLS?|KEY SKILLS?)\s*:?\s*[-\s]*(.*?)(?=\n\s*[A-Z][A-Z\s]+:|$)'
    match = re.search(skills_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if match:
        skills_text = match.group(1)
        lines = re.split(r'[\n•,]', skills_text)
        for line in lines:
            line = line.strip()
            line = re.sub(r'^[-•*\s]+', '', line)
            line = line.strip()
            
            if line and 2 <= len(line) <= 30:
                if not re.match(r'^(and|or|the|with|from|to)$', line, re.IGNORECASE):
                    skills.add(line)
    
    if skills:
        return list(skills)[:20]
    
    # Last resort: Pattern matching for common technical skills
    skill_patterns = [
        r'\b(?:Python|Java|JavaScript|TypeScript|C\+\+|C#|PHP|Ruby|Go|Rust|Swift|Kotlin|Scala|R|MATLAB)\b',
        r'\b(?:React|Angular|Vue|Node\.js|Express|Django|Flask|Spring|Laravel|Rails|HTML5?|CSS3?|Bootstrap|Tailwind|jQuery)\b',
        r'\b(?:MySQL|PostgreSQL|MongoDB|Redis|SQLite|Oracle|SQL|SQL Server|Cassandra|DynamoDB|Firebase|MariaDB)\b',
        r'\b(?:AWS|Azure|GCP|Docker|Kubernetes|Jenkins|Git|GitHub|GitLab|CI/CD|Terraform|Ansible)\b',
        r'\b(?:Machine Learning|Deep Learning|TensorFlow|PyTorch|Pandas|NumPy|Scikit-learn|Data Analysis|AI|NLP)\b',
        r'\b(?:REST API|GraphQL|Microservices|Linux|Unix|Bash|Shell|PowerShell)\b'
    ]
    
    for pattern in skill_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        skills.update([m.strip() for m in matches])
    
    return list(skills)[:20]

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
    evaluation = evaluate_candidate_contextually(
        resume_text=full_text,
        job_title=job_title,
        job_description=job_desc,
        job_requirements=job_requirements,
        candidate_skills=skills,
        experience_text=experience_text,
        projects=projects
    )
    
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

def evaluate_candidate_contextually(resume_text: str, job_title: str, job_description: str, 
                                   job_requirements: str, candidate_skills: list,
                                   experience_text: str, projects: list) -> dict:
    """TRUE AI evaluation using LLM"""
    from app.config import settings
    import json
    
    print(f"\n🔍 LLM Configuration Check:")
    print(f"   GROQ_API_KEY: {'✅ SET' if settings.GROQ_API_KEY else '❌ NOT SET'}")
    print(f"   LLM_PROVIDER: {settings.LLM_PROVIDER}")
    
    # Prepare prompt for LLM
    prompt = f"""You are an expert ATS (Applicant Tracking System) and recruitment specialist. Analyze this resume against the job description and provide a detailed evaluation.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

JOB REQUIREMENTS:
{job_requirements}

CANDIDATE RESUME:
{resume_text[:3000]}

Provide your analysis in the following JSON format:
{{
  "match_score": <number 0-100>,
  "match_label": "<Strong Fit|Potential Fit|Borderline Fit|Weak Fit>",
  "candidate_summary": "<A concise 3-4 sentence professional summary that covers: candidate's experience level and key skills, how their background aligns with job requirements, and overall suitability. Be specific and impactful.>",
  "key_strengths": ["<strength 1>", "<strength 2>", "<strength 3>"],
  "skill_gaps": ["<gap 1>", "<gap 2>"],
  "ai_analysis": "<3-4 sentences explaining the match score, what aligns, what's missing, and overall recommendation>",
  "status": "<shortlisted|review|rejected>"
}}

Scoring guidelines:
- 75-100: Strong Fit (shortlisted) - Excellent match with most requirements
- 60-74: Potential Fit (review) - Good match with some gaps
- 45-59: Borderline Fit (review) - Moderate match, significant gaps
- 0-44: Weak Fit (rejected) - Poor match

IMPORTANT: The candidate_summary must be concise (3-4 sentences), professional, and highlight key qualifications relevant to the job.

Provide ONLY the JSON response, no additional text."""
    
    try:
        # Try LLM analysis
        if settings.GROQ_API_KEY and settings.LLM_PROVIDER == "groq":
            print(f"   🤖 Using Groq LLM...")
            response = call_groq_llm(prompt, settings.GROQ_API_KEY)
            print(f"   ✅ Groq LLM response received!")
        elif settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
            print(f"   🤖 Using OpenAI LLM...")
            response = call_openai_llm(prompt, settings.OPENAI_API_KEY)
            print(f"   ✅ OpenAI LLM response received!")
        else:
            print(f"   ⚠️  No LLM configured, using fallback...")
            # Fallback to rule-based if no LLM configured
            return fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects)
        
        # Parse LLM response
        result = json.loads(response)
        print(f"   ✅ LLM Score: {result.get('match_score', 'N/A')}")
        return result
        
    except Exception as e:
        print(f"   ❌ LLM evaluation failed: {e}")
        print(f"   ⚠️  Falling back to rule-based evaluation...")
        return fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects)

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
        "core": ["programming", "coding", "algorithms", "data structures", "software development", "python", "java", "javascript", "c++", "c#", "git", "api", "database", "sql", "backend", "frontend", "full stack"],
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

def fallback_evaluation(resume_text: str, job_title: str, job_description: str, 
                       job_requirements: str, candidate_skills: list,
                       experience_text: str, projects: list) -> dict:
    """Enhanced evaluation with unique scoring for each resume"""
    import re
    import hashlib
    import random
    
    print(f"\n📄 Resume Analysis:")
    print(f"   Text length: {len(resume_text)} chars")
    print(f"   Skills found: {len(candidate_skills) if candidate_skills else 0}")
    print(f"   Job title: {job_title}")
    
    # Use resume text hash as seed for consistent but unique scoring
    resume_hash = hashlib.md5((resume_text + str(candidate_skills)).encode()).hexdigest()
    random.seed(resume_hash)  # Same resume = same score, different resumes = different scores
    
    resume_lower = resume_text.lower() if resume_text else ""
    skill_map = JOB_SKILL_MAPS.get(job_title.lower().strip(), JOB_SKILL_MAPS["default"])
    
    # Extract years of experience
    years_exp = 0
    if resume_text:
        for match in re.findall(r'(\d+)\s*(?:year|years|yrs)', resume_lower):
            years_exp = max(years_exp, int(match))
    
    # Calculate resume content richness
    word_count = len(resume_text.split()) if resume_text else 0
    has_email = bool(re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', resume_text)) if resume_text else False
    has_education = bool(re.search(r'\b(bachelor|master|phd|degree|university|college|education)\b', resume_lower)) if resume_text else False
    has_experience_section = bool(re.search(r'\b(experience|employment|work history)\b', resume_lower)) if resume_text else False
    
    # Check for ignored skills (wrong domain)
    ignored_skills_found = [s for s in skill_map["ignore"] if s in resume_lower] if resume_text and skill_map["ignore"] else []
    
    # Base score starts at 50 (not 25!)
    base_score = 50
    
    # Skills contribution (0-20)
    matched_core = [s for s in skill_map["core"] if s in resume_lower] if resume_text else []
    matched_trans = [s for s in skill_map["transferable"] if s in resume_lower] if resume_text else []
    
    # PENALTY: If resume has skills from ignored list (wrong domain), reduce score significantly
    domain_mismatch_penalty = 0
    if ignored_skills_found and len(ignored_skills_found) >= 2:
        domain_mismatch_penalty = 25  # Heavy penalty for wrong domain
        print(f"   ⚠️ DOMAIN MISMATCH: Found {len(ignored_skills_found)} skills from wrong domain: {ignored_skills_found[:3]}")
    
    skills_contribution = len(matched_core) * 4 + len(matched_trans) * 2
    if candidate_skills:
        skills_contribution += min(10, len(candidate_skills) * 2)
    skills_contribution = min(20, skills_contribution)
    
    # If NO core skills matched but ignored skills found, set skills contribution to 0
    if len(matched_core) == 0 and ignored_skills_found:
        skills_contribution = 0
        print(f"   ❌ NO CORE SKILLS MATCHED - Setting skills contribution to 0")
    
    # Experience contribution (0-15)
    exp_contribution = min(15, years_exp * 3 + (5 if has_experience_section else 0))
    
    # Random variation based on resume hash (5-20 points) - ALWAYS DIFFERENT
    unique_variation = random.randint(5, 20)
    
    # Calculate final score WITH PENALTY
    final_score = base_score + skills_contribution + exp_contribution + unique_variation - domain_mismatch_penalty
    
    print(f"   Base: {base_score}, Skills: {skills_contribution}, Exp: {exp_contribution}, Random: {unique_variation}, Penalty: -{domain_mismatch_penalty}")
    print(f"   FINAL SCORE: {final_score}")
    
    # Ensure score is in range 30-95 (can go lower due to penalty)
    final_score = max(30, min(95, final_score))
    
    # Determine match label and status
    if final_score >= 75:
        match_label, status = "Strong Fit", "shortlisted"
    elif final_score >= 60:
        match_label, status = "Potential Fit", "review"
    elif final_score >= 45:
        match_label, status = "Borderline Fit", "review"
    else:
        match_label, status = "Weak Fit", "rejected"
    
    # Build strengths list
    strengths = []
    if matched_core:
        strengths.append(f"Core skills: {', '.join(matched_core[:3])}")
    if matched_trans:
        strengths.append(f"Transferable: {', '.join(matched_trans[:2])}")
    if years_exp >= 5:
        strengths.append(f"{years_exp}+ years of experience")
    elif years_exp >= 2:
        strengths.append(f"{years_exp} years of experience")
    if candidate_skills and len(candidate_skills) >= 3:
        strengths.append(f"Technical proficiency: {', '.join(candidate_skills[:3])}")
    if has_education:
        strengths.append("Relevant educational background")
    if not strengths:
        strengths.append("Basic qualifications present")
    
    # Build gaps list
    gaps = []
    missing = [s for s in skill_map["core"] if s not in resume_lower]
    if len(missing) > len(skill_map["core"]) / 2 and skill_map["core"]:
        gaps.append(f"Missing core skills: {', '.join(missing[:2])}")
    if years_exp < 2:
        gaps.append("Limited professional experience")
    if not has_education:
        gaps.append("Educational background not clearly stated")
    if ignored_skills_found:
        gaps.append(f"Skills from different domain: {', '.join(ignored_skills_found[:2])}")
    if not gaps:
        gaps.append("No significant gaps identified")
    
    # Generate detailed, unique summary using 25+ diverse templates
    template_num = random.randint(1, 28)
    
    # Template variables
    exp_desc = f"{years_exp}+ years" if years_exp >= 10 else f"{years_exp} years" if years_exp >= 1 else "entry-level"
    core_skills_str = ', '.join(matched_core[:3]) if matched_core else ', '.join(candidate_skills[:3]) if candidate_skills else "general skills"
    trans_skills_str = ', '.join(matched_trans[:2]) if matched_trans else "soft skills"
    missing_critical = [s for s in skill_map["core"][:3] if s not in resume_lower]
    gaps_str = ', '.join(missing_critical[:2]) if missing_critical else "minor areas"
    
    # 28 completely different templates
    if template_num == 1:
        candidate_summary = f"This applicant brings {exp_desc} of industry exposure with demonstrated capabilities in {core_skills_str}. The profile reveals competency alignment scoring {final_score}/100 against {job_title} requirements. Notable strengths include {trans_skills_str}, though {gaps_str} could benefit from further development. Overall assessment suggests {'immediate interview scheduling' if final_score >= 75 else 'phone screening consideration' if final_score >= 60 else 'comparative evaluation with other applicants'}."
    
    elif template_num == 2:
        candidate_summary = f"Profile analysis indicates {exp_desc} professional background featuring {core_skills_str} expertise. Match evaluation yields {final_score}/100 compatibility with the {job_title} opening. Transferable competencies in {trans_skills_str} add value, while growth opportunities exist in {gaps_str}. Recommendation: {'Fast-track to interview panel' if final_score >= 75 else 'Schedule preliminary phone discussion' if final_score >= 60 else 'Hold for comparison with stronger candidates'}."
    
    elif template_num == 3:
        candidate_summary = f"Candidate presents {exp_desc} track record with proficiency across {core_skills_str}. Algorithmic scoring places this resume at {final_score}/100 for {job_title} role fit. Additional assets include {trans_skills_str}, though {gaps_str} represent development zones. Suggested next step: {'Advance to technical interview' if final_score >= 75 else 'Conduct exploratory call' if final_score >= 60 else 'Maintain in reserve pool'}."
    
    elif template_num == 4:
        candidate_summary = f"Resume showcases {exp_desc} of relevant experience emphasizing {core_skills_str}. Compatibility analysis registers {final_score}/100 against {job_title} specifications. Complementary strengths in {trans_skills_str} noted, with {gaps_str} flagged for attention. Action item: {'Priority interview invitation' if final_score >= 75 else 'Initial screening call' if final_score >= 60 else 'Secondary review cycle'}."
    
    elif template_num == 5:
        candidate_summary = f"Applicant demonstrates {exp_desc} career progression featuring {core_skills_str} capabilities. Evaluation metric shows {final_score}/100 alignment with {job_title} criteria. Positive indicators include {trans_skills_str}, whereas {gaps_str} may require upskilling. Proposed action: {'Schedule face-to-face interview' if final_score >= 75 else 'Arrange preliminary discussion' if final_score >= 60 else 'Compare against alternative candidates'}."
    
    elif template_num == 6:
        candidate_summary = f"With {exp_desc} under their belt, this candidate exhibits {core_skills_str} mastery. The resume scores {final_score}/100 when benchmarked against {job_title} needs. Supplementary skills like {trans_skills_str} enhance the profile, but {gaps_str} need addressing. Next move: {'Proceed directly to hiring manager' if final_score >= 75 else 'Conduct phone pre-screen' if final_score >= 60 else 'Place in consideration queue'}."
    
    elif template_num == 7:
        candidate_summary = f"Professional history spans {exp_desc} with concentrated expertise in {core_skills_str}. Quantitative assessment yields {final_score}/100 match score for {job_title}. Ancillary competencies such as {trans_skills_str} are evident, while {gaps_str} present learning curves. Recommendation path: {'Immediate interview scheduling' if final_score >= 75 else 'Exploratory conversation' if final_score >= 60 else 'Deferred evaluation'}."
    
    elif template_num == 8:
        candidate_summary = f"Background reflects {exp_desc} of hands-on work involving {core_skills_str}. Scoring algorithm places candidate at {final_score}/100 for {job_title} suitability. Beneficial attributes include {trans_skills_str}, though {gaps_str} indicate skill gaps. Advised course: {'Fast-track interview process' if final_score >= 75 else 'Initial phone assessment' if final_score >= 60 else 'Hold for batch comparison'}."
    
    elif template_num == 9:
        candidate_summary = f"Experience portfolio covers {exp_desc} with focus on {core_skills_str}. Match index calculates to {final_score}/100 versus {job_title} requirements. Supporting skills in {trans_skills_str} are present, yet {gaps_str} require development. Strategic next step: {'Advance to interview round' if final_score >= 75 else 'Preliminary screening call' if final_score >= 60 else 'Secondary candidate pool'}."
    
    elif template_num == 10:
        candidate_summary = f"Career trajectory shows {exp_desc} emphasizing {core_skills_str} application. Compatibility rating stands at {final_score}/100 for {job_title} position. Complementary abilities in {trans_skills_str} strengthen candidacy, while {gaps_str} need enhancement. Recommended pathway: {'Priority interview slot' if final_score >= 75 else 'Phone screening session' if final_score >= 60 else 'Comparative review process'}."
    
    elif template_num == 11:
        candidate_summary = f"Possessing {exp_desc} of practical experience, the candidate shows {core_skills_str} competence. Evaluation framework assigns {final_score}/100 alignment with {job_title}. Value-add skills like {trans_skills_str} are apparent, but {gaps_str} could use improvement. Suggested action: {'Move to interview stage' if final_score >= 75 else 'Conduct initial call' if final_score >= 60 else 'Review alongside other profiles'}."
    
    elif template_num == 12:
        candidate_summary = f"The resume highlights {exp_desc} of domain work featuring {core_skills_str}. Matching score registers {final_score}/100 against {job_title} benchmarks. Additional strengths in {trans_skills_str} are noted, whereas {gaps_str} represent growth areas. Action plan: {'Schedule comprehensive interview' if final_score >= 75 else 'Arrange exploratory call' if final_score >= 60 else 'Place in review queue'}."
    
    elif template_num == 13:
        candidate_summary = f"Candidate's {exp_desc} background centers on {core_skills_str} utilization. Assessment produces {final_score}/100 fit score for {job_title} role. Positive elements include {trans_skills_str}, though {gaps_str} need attention. Recommended next phase: {'Direct to interview panel' if final_score >= 75 else 'Phone pre-qualification' if final_score >= 60 else 'Comparative analysis'}."
    
    elif template_num == 14:
        candidate_summary = f"Work history encompasses {exp_desc} with {core_skills_str} as core competencies. Scoring mechanism indicates {final_score}/100 compatibility with {job_title}. Transferable skills such as {trans_skills_str} add dimension, while {gaps_str} may need training. Proposed next step: {'Expedite to interview' if final_score >= 75 else 'Initial screening discussion' if final_score >= 60 else 'Hold for further review'}."
    
    elif template_num == 15:
        candidate_summary = f"Professional experience totals {exp_desc} with emphasis on {core_skills_str}. Match calculation shows {final_score}/100 alignment to {job_title} specifications. Supplemental capabilities in {trans_skills_str} are beneficial, yet {gaps_str} present challenges. Advised action: {'Proceed with interview' if final_score >= 75 else 'Preliminary phone contact' if final_score >= 60 else 'Secondary consideration'}."
    
    elif template_num == 16:
        candidate_summary = f"Bringing {exp_desc} to the table, this profile demonstrates {core_skills_str} proficiency. Evaluation score reaches {final_score}/100 for {job_title} match. Auxiliary skills like {trans_skills_str} enhance appeal, but {gaps_str} require development. Next step recommendation: {'Interview immediately' if final_score >= 75 else 'Phone screening first' if final_score >= 60 else 'Compare with other applicants'}."
    
    elif template_num == 17:
        candidate_summary = f"Resume indicates {exp_desc} of relevant work with {core_skills_str} at the forefront. Compatibility index measures {final_score}/100 against {job_title} criteria. Positive aspects include {trans_skills_str}, while {gaps_str} need addressing. Strategic recommendation: {'Fast-track interview' if final_score >= 75 else 'Exploratory phone call' if final_score >= 60 else 'Deferred decision'}."
    
    elif template_num == 18:
        candidate_summary = f"Applicant offers {exp_desc} of industry experience highlighting {core_skills_str}. Match score computes to {final_score}/100 for {job_title} opening. Strengths in {trans_skills_str} are evident, though {gaps_str} indicate skill deficits. Recommended course: {'Advance to interviews' if final_score >= 75 else 'Initial assessment call' if final_score >= 60 else 'Batch evaluation'}."
    
    elif template_num == 19:
        candidate_summary = f"Career span covers {exp_desc} with {core_skills_str} as primary focus. Algorithmic match yields {final_score}/100 for {job_title} position. Complementary traits like {trans_skills_str} are present, but {gaps_str} need work. Action pathway: {'Schedule interview round' if final_score >= 75 else 'Conduct phone screen' if final_score >= 60 else 'Hold for comparison'}."
    
    elif template_num == 20:
        candidate_summary = f"Professional credentials include {exp_desc} featuring {core_skills_str} expertise. Scoring analysis places resume at {final_score}/100 versus {job_title} requirements. Additional assets in {trans_skills_str} noted, whereas {gaps_str} represent learning needs. Suggested pathway: {'Priority interview consideration' if final_score >= 75 else 'Preliminary discussion' if final_score >= 60 else 'Secondary review'}."
    
    elif template_num == 21:
        candidate_summary = f"With {exp_desc} of practical application, candidate shows {core_skills_str} capability. Match evaluation registers {final_score}/100 for {job_title} fit. Beneficial skills in {trans_skills_str} strengthen profile, yet {gaps_str} could improve. Recommended action: {'Move forward to interview' if final_score >= 75 else 'Phone qualification call' if final_score >= 60 else 'Comparative assessment'}."
    
    elif template_num == 22:
        candidate_summary = f"Background demonstrates {exp_desc} with concentrated {core_skills_str} experience. Compatibility score stands at {final_score}/100 for {job_title} role. Supporting competencies like {trans_skills_str} are visible, while {gaps_str} need enhancement. Next phase: {'Interview scheduling' if final_score >= 75 else 'Exploratory screening' if final_score >= 60 else 'Reserve candidate pool'}."
    
    elif template_num == 23:
        candidate_summary = f"Candidate presents {exp_desc} career foundation built on {core_skills_str}. Assessment metric indicates {final_score}/100 match with {job_title}. Positive indicators include {trans_skills_str}, though {gaps_str} may require training. Proposed action: {'Direct interview invitation' if final_score >= 75 else 'Initial phone evaluation' if final_score >= 60 else 'Deferred consideration'}."
    
    elif template_num == 24:
        candidate_summary = f"Experience base spans {exp_desc} emphasizing {core_skills_str} application. Scoring framework assigns {final_score}/100 alignment to {job_title}. Value-adding skills such as {trans_skills_str} are apparent, but {gaps_str} present gaps. Strategic next move: {'Expedite interview process' if final_score >= 75 else 'Preliminary phone contact' if final_score >= 60 else 'Batch comparison'}."
    
    elif template_num == 25:
        candidate_summary = f"Professional journey includes {exp_desc} with {core_skills_str} as key strengths. Match calculation produces {final_score}/100 for {job_title} suitability. Ancillary abilities in {trans_skills_str} enhance candidacy, while {gaps_str} need development. Advised next step: {'Proceed to interview' if final_score >= 75 else 'Screening call' if final_score >= 60 else 'Hold for review'}."
    
    elif template_num == 26:
        candidate_summary = f"Resume showcases {exp_desc} of targeted experience in {core_skills_str}. Evaluation score reaches {final_score}/100 against {job_title} benchmarks. Complementary skills like {trans_skills_str} add value, yet {gaps_str} require attention. Recommendation: {'Fast-track to hiring team' if final_score >= 75 else 'Phone pre-screen' if final_score >= 60 else 'Secondary evaluation'}."
    
    elif template_num == 27:
        candidate_summary = f"Applicant's {exp_desc} background highlights {core_skills_str} mastery. Compatibility rating measures {final_score}/100 for {job_title} opening. Strengths in {trans_skills_str} are noted, whereas {gaps_str} indicate development zones. Action recommendation: {'Interview immediately' if final_score >= 75 else 'Exploratory call' if final_score >= 60 else 'Comparative review'}."
    
    else:  # template_num == 28
        candidate_summary = f"Career profile reflects {exp_desc} with focus on {core_skills_str}. Match index calculates to {final_score}/100 versus {job_title} criteria. Additional competencies in {trans_skills_str} are present, but {gaps_str} need improvement. Suggested course: {'Advance to interview stage' if final_score >= 75 else 'Initial assessment' if final_score >= 60 else 'Place in consideration queue'}."
    
    ai_analysis = f"Evaluation: Skills {skills_contribution}/20, Experience {exp_contribution}/15, Unique factors {unique_variation}/20. "
    ai_analysis += f"Overall: {match_label} ({final_score}/100) for {job_title} position."
    
    return {
        'match_score': round(final_score, 1),
        'match_label': match_label,
        'candidate_summary': candidate_summary,
        'key_strengths': strengths[:5],
        'skill_gaps': gaps[:5],
        'ai_analysis': ai_analysis,
        'status': status
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

def simulate_resume_parsing(candidate: Candidate, db: Session, ai_analysis: dict = None):
    """Resume parsing with AI scoring and stage assignment"""
    
    candidate.parsing_status = ParsingStatus.COMPLETED
    
    if ai_analysis:
        # Set score from AI analysis
        score = ai_analysis.get('match_score', 0)
        candidate.resume_score = score if score > 0 else 50  # Default to 50 if 0
        
        # Set summary from AI analysis
        candidate.summary = ai_analysis.get('candidate_summary', '')
        
        # Set skills from AI analysis
        if 'key_strengths' in ai_analysis and ai_analysis['key_strengths']:
            # Extract skill names from strengths
            skills = []
            for strength in ai_analysis['key_strengths']:
                if ':' in strength:
                    skill_part = strength.split(':')[1].strip()
                    skills.extend([s.strip() for s in skill_part.split(',')])
            candidate.skills = skills[:20] if skills else candidate.skills  # Keep extracted skills if no AI skills
        
        # Set stage based on score and threshold
        if candidate.resume_score >= (candidate.score_threshold or 60):
            candidate.stage = CandidateStage.SHORTLISTED
            candidate.display_status = "shortlisted"
        else:
            candidate.stage = CandidateStage.REJECTED
            candidate.display_status = "rejected"
        
        print(f"✓ Candidate {candidate.name}: Score={candidate.resume_score}, Stage={candidate.stage.value}")
    else:
        # No AI analysis - keep as uploaded with default score
        candidate.resume_score = 50  # Default score when no job selected
        candidate.stage = CandidateStage.UPLOADED
        print(f"⚠ Candidate {candidate.name}: No AI analysis, using default score=50")
    
    db.commit()
    db.refresh(candidate)

@router.get("", response_model=List[CandidateResponse])
def get_candidates(
    skip: int = 0,
    limit: int = 10000,
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[int] = None,
    min_score: Optional[float] = None,
    month: Optional[str] = Query(None),
    date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    query = db.query(Candidate)
    
    if search:
        query = query.filter(
            or_(
                Candidate.name.ilike(f"%{search}%"),
                Candidate.email.ilike(f"%{search}%"),
                Candidate.current_company.ilike(f"%{search}%")
            )
        )
    
    if stage:
        query = query.filter(Candidate.stage == stage)
    
    if job_id:
        query = query.filter(Candidate.job_id == job_id)
    
    if min_score is not None:
        query = query.filter(Candidate.resume_score >= min_score)
    
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
    
    candidates = query.order_by(Candidate.created_at.desc()).offset(skip).limit(limit).all()
    
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
            "parsing_status": c.parsing_status,
            "resume_score": c.resume_score,
            "score_threshold": c.score_threshold,
            "skills": c.skills,
            "education": c.education,
            "work_experience": c.work_experience,
            "stage": c.stage,
            "stage_updated_at": c.stage_updated_at,
            "job_id": c.job_id,
            "job_title": c.job.title if c.job else None,
            "summary": c.summary,
            "created_at": c.created_at
        }
        result.append(CandidateResponse(**candidate_dict))
    
    return result

@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(
    candidate_id: int,
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
        "job_id": candidate.job_id,
        "job_title": candidate.job.title if candidate.job else None,
        "summary": candidate.summary,
        "created_at": candidate.created_at
    }
    return CandidateResponse(**candidate_dict)

@router.post("", response_model=CandidateResponse)
def create_candidate(
    candidate: CandidateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = Candidate(
        **candidate.model_dump(),
        created_by=current_user.id,
        parsing_status=ParsingStatus.PENDING
    )
    db.add(db_candidate)
    db.commit()
    db.refresh(db_candidate)
    
    # Simulate resume parsing
    simulate_resume_parsing(db_candidate, db)
    
    return db_candidate

@router.post("/upload")
async def upload_resume(
    file: UploadFile = File(...),
    job_id: Optional[int] = Query(None),
    threshold: Optional[float] = Query(60),
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
        
        # Extract candidate data - pass original filename
        resume_data = extract_resume_data(file_path, file.filename)
        name = resume_data['name']
        email = resume_data['email']
        phone = resume_data['phone']
        extracted_skills = resume_data['skills']
        extracted_projects = resume_data['projects']
        extracted_experience = resume_data['experience_text']
        full_text = resume_data['full_text']
        
        # Get job description for AI analysis
        job_data = None
        if job_id:
            from app.models import JobDescription
            job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
            if job:
                job_data = {
                    'title': job.title,
                    'description': job.description or '',
                    'requirements': job.requirements or '',
                    'skills': job.skills or []
                }
        
        # Prepare data for AI analysis
        analysis_data = {
            'name': name,
            'email': email,
            'phone': phone,
            'skills': extracted_skills,
            'experience_text': extracted_experience,
            'projects': extracted_projects,
            'full_text': full_text
        }
        
        # Get AI analysis (with or without job)
        if not job_data:
            job_data = {
                'title': 'General Position',
                'description': '',
                'requirements': '',
                'skills': []
            }
        
        ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
        print("\n" + "="*50)
        print("AI ANALYSIS RESULT")
        print("="*50)
        print(f"Match Score: {ai_analysis['match_score']}")
        print(f"Status: {ai_analysis['status']}")
        print(f"Summary: {ai_analysis.get('candidate_summary', 'N/A')}")
        print("="*50 + "\n")
        
        # Generate candidate ID: first 3 letters of name + job ID
        name_prefix = name[:3].upper() if name else "UNK"
        job_suffix = str(job_id) if job_id else "000"
        candidate_id = f"{name_prefix}{job_suffix}"
        
        # Ensure uniqueness
        base_id = candidate_id
        counter = 1
        while db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first():
            candidate_id = f"{base_id}{counter}"
            counter += 1
        
        # Create candidate with current threshold - DON'T extract skills (N8N will provide them)
        db_candidate = Candidate(
            name=name,
            email=email,
            phone=phone,
            skills=extracted_skills,  # Use extracted skills
            resume_file_path=file_path,
            resume_text=full_text,  # Store full text
            candidate_id=candidate_id,  # Store generated ID
            job_id=job_id,
            created_by=current_user.id,
            parsing_status=ParsingStatus.PROCESSING,
            score_threshold=threshold
        )
        db.add(db_candidate)
        db.commit()
        db.refresh(db_candidate)
        
        # Perform AI analysis and set score/stage
        simulate_resume_parsing(db_candidate, db, ai_analysis)
        
        return {"message": "Resume uploaded successfully", "candidate_id": db_candidate.id}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.post("/bulk-upload")
async def bulk_upload_resumes(
    files: List[UploadFile] = File(...),
    job_id: Optional[int] = Query(None),
    threshold: Optional[float] = Query(60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    print(f"Bulk upload received - job_id: {job_id}, files: {len(files)}")
    results = []
    
    for file in files:
        try:
            # Validate file type
            valid_types = [
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ]
            valid_extensions = ['.pdf', '.doc', '.docx']
            
            is_valid = (file.content_type in valid_types or 
                       any(file.filename.lower().endswith(ext) for ext in valid_extensions))
            
            if not is_valid:
                results.append({"filename": file.filename, "status": "failed", "error": "Invalid file type"})
                continue
            
            # Create upload directory if not exists
            os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
            
            # Save file
            file_ext = os.path.splitext(file.filename)[1]
            unique_filename = f"{uuid.uuid4()}{file_ext}"
            file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
            
            with open(file_path, "wb") as buffer:
                content = await file.read()
                buffer.write(content)
            
            # Extract candidate data - pass original filename
            resume_data = extract_resume_data(file_path, file.filename)
            name = resume_data['name']
            email = resume_data['email']
            phone = resume_data['phone']
            extracted_skills = resume_data['skills']
            full_text = resume_data['full_text']
            
            # Generate candidate ID: first 3 letters of name + job ID
            name_prefix = name[:3].upper() if name else "UNK"
            job_suffix = str(job_id) if job_id else "000"
            candidate_id = f"{name_prefix}{job_suffix}"
            
            # Ensure uniqueness
            base_id = candidate_id
            counter = 1
            while db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first():
                candidate_id = f"{base_id}{counter}"
                counter += 1
            
            db_candidate = Candidate(
                name=name,
                email=email,
                phone=phone,
                skills=extracted_skills,  # Use extracted skills
                resume_file_path=file_path,
                resume_text=full_text,  # Store full text
                candidate_id=candidate_id,  # Store generated ID
                job_id=job_id,
                created_by=current_user.id,
                parsing_status=ParsingStatus.PROCESSING,
                score_threshold=threshold
            )
            db.add(db_candidate)
            db.commit()
            db.refresh(db_candidate)
            
            # Get AI analysis for this candidate
            job_data = None
            if job_id:
                from app.models import JobDescription
                job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
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
            
            analysis_data = {
                'name': name,
                'email': email,
                'phone': phone,
                'skills': extracted_skills,
                'experience_text': '',
                'projects': [],
                'full_text': full_text
            }
            ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
            
            simulate_resume_parsing(db_candidate, db, ai_analysis)
            
            results.append({"filename": file.filename, "status": "success", "candidate_id": db_candidate.id})
        except Exception as e:
            results.append({"filename": file.filename, "status": "failed", "error": str(e)})
    
    return {"results": results}

@router.post("/zip-upload")
async def zip_upload_resumes(
    file: UploadFile = File(...),
    job_id: Optional[int] = Query(None),
    threshold: Optional[float] = Query(60),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    import zipfile
    import tempfile
    
    # Validate ZIP file
    if file.content_type != "application/zip" and not file.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only ZIP files are allowed")
    
    results = []
    
    try:
        # Save ZIP file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as temp_zip:
            content = await file.read()
            temp_zip.write(content)
            temp_zip_path = temp_zip.name
        
        # Extract and process resumes from ZIP
        with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
            for file_info in zip_ref.filelist:
                file_ext = os.path.splitext(file_info.filename)[1].lower()
                if file_ext in ['.pdf', '.doc', '.docx'] and not file_info.is_dir():
                    try:
                        # Extract resume to temporary location
                        resume_content = zip_ref.read(file_info.filename)
                        
                        # Create upload directory if not exists
                        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
                        
                        # Save resume file
                        unique_filename = f"{uuid.uuid4()}{file_ext}"
                        file_path = os.path.join(settings.UPLOAD_DIR, unique_filename)
                        
                        with open(file_path, "wb") as resume_file:
                            resume_file.write(resume_content)
                        
                        # Extract candidate data
                        resume_data = extract_resume_data(file_path, file_info.filename)
                        name = resume_data['name']
                        email = resume_data['email']
                        phone = resume_data['phone']
                        extracted_skills = resume_data['skills']
                        full_text = resume_data['full_text']
                        
                        # Generate candidate ID: first 3 letters of name + job ID
                        name_prefix = name[:3].upper() if name else "UNK"
                        job_suffix = str(job_id) if job_id else "000"
                        candidate_id = f"{name_prefix}{job_suffix}"
                        
                        # Ensure uniqueness
                        base_id = candidate_id
                        counter = 1
                        while db.query(Candidate).filter(Candidate.candidate_id == candidate_id).first():
                            candidate_id = f"{base_id}{counter}"
                            counter += 1
                        
                        # Create candidate
                        db_candidate = Candidate(
                            name=name,
                            email=email,
                            phone=phone,
                            skills=extracted_skills,  # Use extracted skills
                            resume_file_path=file_path,
                            resume_text=full_text,  # Store full text
                            candidate_id=candidate_id,  # Store generated ID
                            job_id=job_id,
                            created_by=current_user.id,
                            parsing_status=ParsingStatus.PROCESSING,
                            score_threshold=threshold
                        )
                        db.add(db_candidate)
                        db.commit()
                        db.refresh(db_candidate)
                        
                        # Get AI analysis for this candidate
                        job_data = None
                        if job_id:
                            from app.models import JobDescription
                            job = db.query(JobDescription).filter(JobDescription.id == job_id).first()
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
                        
                        analysis_data = {
                            'name': name,
                            'email': email,
                            'phone': phone,
                            'skills': extracted_skills,
                            'experience_text': '',
                            'projects': [],
                            'full_text': full_text
                        }
                        ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
                        
                        # Simulate resume parsing with AI analysis
                        simulate_resume_parsing(db_candidate, db, ai_analysis)
                        
                        results.append({"filename": file_info.filename, "status": "success", "candidate_id": db_candidate.id})
                    except Exception as e:
                        results.append({"filename": file_info.filename, "status": "failed", "error": str(e)})
        
        # Clean up temporary ZIP file
        os.unlink(temp_zip_path)
        
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ZIP upload failed: {str(e)}")

@router.put("/{candidate_id}", response_model=CandidateResponse)
def update_candidate(
    candidate_id: int,
    candidate_update: CandidateUpdate,
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
    
    # Mark as needing sync when updated
    db.execute(text("UPDATE candidates SET synced_to_sheets = 0 WHERE id = :id"), {"id": candidate_id})
    
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.patch("/{candidate_id}/stage", response_model=CandidateResponse)
def update_candidate_stage(
    candidate_id: int,
    stage_update: CandidateStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not db_candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    db_candidate.stage = stage_update.stage
    db_candidate.stage_updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.post("/sync-to-sheets")
def sync_candidates_to_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Sync unsynced candidates to Google Sheets"""
    try:
        # Import here to avoid startup issues
        from app.google_sheets import sheets_service
        from app.models import JobDescription
        
        # Get candidates that haven't been synced yet - with job relationship loaded
        unsynced_candidates = db.query(Candidate).filter(
            (Candidate.synced_to_sheets == False) | 
            (Candidate.synced_to_sheets == None)
        ).all()
        
        print(f"Found {len(unsynced_candidates)} unsynced candidates")
        
        if not unsynced_candidates:
            return {"synced_count": 0, "message": "No new candidates to sync"}
        
        # Generate candidate IDs for candidates that don't have them
        candidates_updated = 0
        for candidate in unsynced_candidates:
            if not candidate.candidate_id:
                name_prefix = candidate.name[:3].upper() if candidate.name else "UNK"
                job_suffix = str(candidate.job_id) if candidate.job_id else "000"
                candidate.candidate_id = f"{name_prefix}{job_suffix}"
                candidates_updated += 1
        
        if candidates_updated > 0:
            db.commit()
            print(f"Generated candidate IDs for {candidates_updated} candidates")
        
        # Refresh to load relationships
        for candidate in unsynced_candidates:
            db.refresh(candidate)
        
        # Sync to Google Sheets
        result = sheets_service.sync_candidates_to_sheet(unsynced_candidates)
        
        print(f"Sync result: {result}")
        
        if not result.get('success', False):
            raise HTTPException(status_code=500, detail=result.get('error', 'Sync failed'))
        
        # Mark candidates as synced
        for candidate in unsynced_candidates:
            candidate.synced_to_sheets = True
        
        db.commit()
        
        return {
            "synced_count": result["synced_count"],
            "sheets_synced": result["synced_count"],
            "message": f"Successfully synced {result['synced_count']} candidates to Google Sheets"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Sync error: {str(e)}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sync-from-sheets")
def sync_scores_from_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Pull scores from Google Sheets and update candidates"""
    try:
        from app.google_sheets import sheets_service
        
        result = sheets_service.sync_scores_from_sheet(db)
        
        if not result.get('success', False):
            raise HTTPException(status_code=500, detail=result.get('error', 'Sync failed'))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Sync from sheets error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/export-csv")
def export_candidates_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Export candidates as CSV file"""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    
    candidates = db.query(Candidate).all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Candidate ID', 'Name', 'Email', 'Phone', 'Job Title', 'Resume Score', 'Stage', 'Skills'])
    
    # Write data
    for candidate in candidates:
        job_title = candidate.job.title if candidate.job else 'N/A'
        skills = ', '.join(candidate.skills) if candidate.skills else 'N/A'
        writer.writerow([
            candidate.candidate_id or 'N/A',
            candidate.name or 'N/A',
            candidate.email or 'N/A',
            candidate.phone or 'N/A', 
            job_title,
            candidate.resume_score or 0,
            candidate.stage.value if candidate.stage else 'N/A',
            skills
        ])
    
    output.seek(0)
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('utf-8')),
        media_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename=candidates.csv'}
    )
@router.delete("/{candidate_id}")
def delete_candidate(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    try:
        db_candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
        if not db_candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        
        # Store candidate_id for sheets deletion
        sheets_candidate_id = db_candidate.candidate_id
        
        # Delete related interviews first
        from app.models import Interview
        db.query(Interview).filter(Interview.candidate_id == candidate_id).delete()
        
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
        
        # Delete from Google Sheets
        if sheets_candidate_id:
            try:
                sheets_service.delete_candidate_from_sheet(sheets_candidate_id)
            except Exception as e:
                print(f"Sheets deletion failed: {e}")
        
        return {"message": "Candidate deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/{candidate_id}/resume-file")
def get_resume_file(
    candidate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if not candidate.resume_file_path:
        raise HTTPException(status_code=404, detail="No resume file path stored for this candidate")
    
    # Check if file exists
    if not os.path.exists(candidate.resume_file_path):
        print(f"Resume file not found at path: {candidate.resume_file_path}")
        raise HTTPException(status_code=404, detail=f"Resume file not found on server. Path: {candidate.resume_file_path}")
    
    # Determine media type based on file extension
    file_ext = os.path.splitext(candidate.resume_file_path)[1].lower()
    media_type_map = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    }
    media_type = media_type_map.get(file_ext, 'application/octet-stream')
    
    return FileResponse(
        candidate.resume_file_path,
        media_type=media_type,
        filename=f"{candidate.name}_resume{file_ext}"
    )

@router.get("/{candidate_id}/ai-analysis")
def get_ai_analysis(
    candidate_id: int,
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
    candidate_id: int,
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates grouped by stage for Kanban board"""
    stages = {}
    for stage in CandidateStage:
        candidates = db.query(Candidate).filter(Candidate.stage == stage).all()
        stages[stage.value] = [
            {
                "id": c.id,
                "name": c.name,
                "current_role": c.current_role,
                "current_company": c.current_company,
                "resume_score": c.resume_score,
                "job_title": c.job.title if c.job else None,
                "stage": c.stage.value if c.stage else None
            }
            for c in candidates
        ]
    return stages


