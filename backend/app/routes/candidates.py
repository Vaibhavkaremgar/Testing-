from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
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
            
            # Extract skills (normalized to lowercase)
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

def evaluate_candidate_contextually(resume_text: str, job_title: str, job_description: str, job_requirements: str, candidate_skills: list, experience_text: str, projects: list, job_skills: list = None) -> dict:
    """Evidence-based AI evaluation using LLM with structured scoring"""
    from app.config import settings
    import json
    
    print(f"\n🔍 LLM Configuration Check:")
    print(f"   GROQ_API_KEY: {'✅ SET' if settings.GROQ_API_KEY else '❌ NOT SET'}")
    print(f"   LLM_PROVIDER: {settings.LLM_PROVIDER}")
    
    # Enhanced prompt with weighted evaluation criteria
    prompt = f"""You are a senior technical recruiter with 15+ years of experience. Evaluate this candidate for the {job_title} position using weighted scoring.

JOB TITLE: {job_title}

JOB DESCRIPTION:
{job_description}

JOB REQUIREMENTS:
{job_requirements}

CANDIDATE RESUME:
{resume_text[:3000]}

EVALUATE BASED ON THESE WEIGHTED CRITERIA:

1. SKILLS MATCH (0-45 points) - MOST IMPORTANT
   - Must-have skills from JD (semantic match, not just keywords)
   - Good-to-have skills
   - Skills inferred from experience/projects (e.g., "Built Flask APIs" → Python, REST)
   - Skill relevance and depth

2. EXPERIENCE RELEVANCE & YEARS (0-25 points)
   - Total years of experience
   - Relevant experience (role/domain match)
   - Recent experience (last 3-5 years weighted higher)
   - Penalize irrelevant domains

3. PROJECT RELEVANCE (0-15 points)
   - Real-world projects with tech stack alignment
   - Project complexity and responsibility
   - Backend role → APIs, DBs, scalability
   - ML role → models, datasets, metrics
   - Internship/academic projects get less weight

4. EDUCATION & CERTIFICATIONS (0-10 points)
   - Degree relevance (not institution prestige)
   - Role-aligned certifications
   - Irrelevant degrees are neutral

5. SOFT SKILLS (0-5 points)
   - Communication, leadership, team collaboration
   - Only if backed by experience (not generic fluff)
   - "Led 5-member team" ✅ vs "Hardworking team player" ❌

Provide your analysis in this EXACT JSON format:
{{
  "skills_score": <0-45>,
  "experience_score": <0-25>,
  "projects_score": <0-15>,
  "education_score": <0-10>,
  "soft_skills_score": <0-5>,
  "match_score": <sum of above, 0-100>,
  "match_label": "<Strong Fit|Potential Fit|Borderline Fit|Weak Fit>",
  "candidate_summary": "<3-4 sentence professional summary highlighting experience, key skills, alignment with job, and suitability>",
  "key_strengths": ["<specific strength with evidence>", "<specific strength with evidence>", "<specific strength with evidence>"],
  "skill_gaps": ["<specific gap>", "<specific gap>"],
  "ai_analysis": "<Detailed 4-5 sentence analysis explaining scores, what makes them strong/weak, evidence found, and hire recommendation>",
  "status": "<shortlisted|review|rejected>",
  "evidence_found": {{
    "must_have_skills_matched": <count>,
    "good_to_have_skills_matched": <count>,
    "years_of_experience": <number>,
    "relevant_projects_count": <count>
  }}
}}

SCORING RULES:
- Skills carry 45% weight (most important for shortlisting)
- Use semantic matching (meaning, not just keywords)
- Penalize skill stuffing and buzzwords
- Ignore large unexplained gaps
- 75-100: Strong Fit (immediate interview)
- 60-74: Potential Fit (phone screen)
- 45-59: Borderline Fit (review with team)
- 0-44: Weak Fit (reject)

Provide ONLY the JSON response, no additional text."""
    
    try:
        # Try LLM analysis
        if settings.GROQ_API_KEY and settings.LLM_PROVIDER == "groq":
            print(f"   🤖 Using Groq LLM with enhanced evaluation...")
            response = call_groq_llm(prompt, settings.GROQ_API_KEY)
            print(f"   ✅ Groq LLM response received!")
        elif settings.OPENAI_API_KEY and settings.LLM_PROVIDER == "openai":
            print(f"   🤖 Using OpenAI LLM with enhanced evaluation...")
            response = call_openai_llm(prompt, settings.OPENAI_API_KEY)
            print(f"   ✅ OpenAI LLM response received!")
        else:
            print(f"   ⚠️  No LLM configured, using enhanced fallback...")
            return enhanced_fallback_evaluation(resume_text, job_title, job_description, job_requirements, candidate_skills, experience_text, projects, job_skills)
        
        # Parse LLM response
        result = json.loads(response)
        print(f"   ✅ LLM Score Breakdown:")
        
        # Support both old and new field names for backward compatibility
        if 'skills_score' in result:
            # New weighted scoring format
            print(f"      Skills Match: {result.get('skills_score', 0)}/45")
            print(f"      Experience: {result.get('experience_score', 0)}/25")
            print(f"      Projects: {result.get('projects_score', 0)}/15")
            print(f"      Education: {result.get('education_score', 0)}/10")
            print(f"      Soft Skills: {result.get('soft_skills_score', 0)}/5")
        else:
            # Old format (fallback)
            print(f"      Technical Depth: {result.get('technical_depth_score', 0)}/30")
            print(f"      Project Complexity: {result.get('project_complexity_score', 0)}/20")
            print(f"      Relevance: {result.get('relevance_score', 0)}/20")
            print(f"      Impact: {result.get('impact_score', 0)}/15")
            print(f"      Seniority: {result.get('seniority_score', 0)}/15")
        
        print(f"      TOTAL: {result.get('match_score', 0)}/100")
        return result
        
    except Exception as e:
        print(f"   ❌ LLM evaluation failed: {e}")
        print(f"   ⚠️  Falling back to enhanced rule-based evaluation...")
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

def simulate_resume_parsing(candidate: Candidate, db: Session, ai_analysis: dict = None):
    """Resume parsing with AI scoring and stage assignment"""
    
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
        
        # Set stage based on score thresholds
        threshold = candidate.score_threshold or 60
        if score >= threshold:
            candidate.stage = CandidateStage.SHORTLISTED
        else:
            candidate.stage = CandidateStage.RESUME_REJECTED
        
        print(f"✓ Candidate {candidate.name}: Score={candidate.resume_score}, Threshold={threshold}, Stage={candidate.stage.value}")
    else:
        # No AI analysis - set minimum score
        candidate.resume_score = 40  # Minimum score when no analysis
        candidate.stage = CandidateStage.APPLIED
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

@router.get("", response_model=List[CandidateResponse])
def get_candidates(
    skip: int = 0,
    limit: int = 10000,
    search: Optional[str] = None,
    stage: Optional[CandidateStage] = None,
    job_id: Optional[int] = None,
    min_score: Optional[float] = None,
    client: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    from app.models import JobDescription
    query = db.query(Candidate)
    
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
            # NO JOB SELECTED: Use generic evaluation with common skills
            job_data = {
                'title': 'General Position',
                'description': 'General professional role',
                'requirements': 'Professional experience with relevant skills',
                'skills': ['communication', 'teamwork', 'problem solving']  # Generic skills
            }
            print("⚠️  No job selected - using generic evaluation")
        
        ai_analysis = analyze_resume_with_ai(analysis_data, job_data)
        print("\n" + "="*50)
        print("AI ANALYSIS RESULT")
        print("="*50)
        print(f"Match Score: {ai_analysis.get('match_score', 'NOT FOUND')}")
        print(f"Status: {ai_analysis.get('status', 'NOT FOUND')}")
        print(f"Summary: {ai_analysis.get('candidate_summary', 'N/A')}")
        print(f"Full Analysis Keys: {list(ai_analysis.keys())}")
        print("="*50 + "\n")
        
        # SAFETY CHECK: Ensure score is never 0 for valid resumes
        if ai_analysis.get('match_score', 0) == 0 and full_text.strip():
            print("⚠️  WARNING: Score is 0 but resume has content. Using minimum score of 30.")
            ai_analysis['match_score'] = 30
        
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
        
        return {"message": "Resume analyzed successfully", "candidate_id": db_candidate.id}
        
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
    db_candidate.stage_entered_at = datetime.utcnow()
    
    db.commit()
    db.refresh(db_candidate)
    return db_candidate

@router.post("/sync-to-sheets")
def sync_candidates_to_sheets(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Sync candidates to Google Sheets via webhook"""
    import requests
    
    webhook_url = "https://script.google.com/macros/s/AKfycby23M_BBZw4VBE1p6Y8MrcBF_66mfOzGvuEckR2RHLs98mE9TEb9AMixQMLZ2IqsgLwPA/exec"
    
    # If webhook URL is set, use simple webhook method
    if webhook_url and webhook_url != "PASTE_YOUR_WEBHOOK_URL_HERE":
        try:
            from app.models import JobDescription
            
            candidates = db.query(Candidate).filter(Candidate.stage != CandidateStage.APPLIED).all()
            
            if not candidates:
                return {"success": True, "synced_count": 0, "message": "No candidates to sync"}
            
            candidates_data = []
            for c in candidates:
                if not c.candidate_id:
                    c.candidate_id = f"{c.name[:3].upper() if c.name else 'UNK'}{c.job_id or '000'}"
                    db.commit()
                
                job_id_str, job_title, job_description = '', '', ''
                if c.job_id:
                    job = db.query(JobDescription).filter(JobDescription.id == c.job_id).first()
                    if job:
                        job_id_str = job.job_id or str(c.job_id)
                        job_title = job.title or ''
                        job_description = (job.description[:1000] + '...') if job.description and len(job.description) > 1000 else (job.description or '')
                
                resume_text = (c.resume_text[:2000] + '...') if c.resume_text and len(c.resume_text) > 2000 else (c.resume_text or '')
                skills_str = ', '.join(c.skills) if c.skills else ''
                
                candidates_data.append({
                    'candidate_id': c.candidate_id,
                    'name': c.name or '',
                    'email': c.email or '',
                    'phone': c.phone or '',
                    'job_id': job_id_str,
                    'job_title': job_title,
                    'resume_text': resume_text,
                    'job_description': job_description,
                    'score': str(c.resume_score) if c.resume_score is not None else '',
                    'skills': skills_str,
                    'resume_evaluated': '',  # Leave blank for N8N workflow
                    'summary': c.summary or '',
                    'predefined_questions': c.predefined_questions or ''
                })
            
            print(f"Sending {len(candidates_data)} candidates to webhook...")
            response = requests.post(webhook_url, json={'candidates': candidates_data}, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                synced = result.get('synced_count', 0)
                print(f"✅ Successfully synced {synced} candidates")
                return {
                    'success': True,
                    'synced_count': synced,
                    'sheets_synced': synced,
                    'message': f'Successfully synced {synced} new candidates to Google Sheets'
                }
            else:
                raise HTTPException(status_code=500, detail=f'Webhook failed: {response.text}')
        except Exception as e:
            print(f"❌ Webhook sync failed: {str(e)}")
            raise HTTPException(status_code=500, detail=f'Sync failed: {str(e)}')
    
    # If no webhook URL, show error
    raise HTTPException(
        status_code=400, 
        detail="Google Sheets webhook not configured. Please update webhook_url in candidates.py (line 1850)"
    )

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

@router.post("/clear-sheets")
def clear_sheets_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Clear all data from Google Sheets"""
    import requests
    
    webhook_url = "https://script.google.com/macros/s/AKfycby23M_BBZw4VBE1p6Y8MrcBF_66mfOzGvuEckR2RHLs98mE9TEb9AMixQMLZ2IqsgLwPA/exec"
    
    try:
        response = requests.post(webhook_url, json={'action': 'clear'}, timeout=30)
        
        if response.status_code == 200:
            return {'success': True, 'message': 'Google Sheets cleared successfully'}
        else:
            raise HTTPException(status_code=500, detail=f'Clear failed: {response.text}')
    except Exception as e:
        print(f"❌ Clear sheets failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f'Clear failed: {str(e)}')
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
        
        # Delete from Google Sheets via webhook
        if sheets_candidate_id:
            try:
                import requests
                webhook_url = "https://script.google.com/macros/s/AKfycby23M_BBZw4VBE1p6Y8MrcBF_66mfOzGvuEckR2RHLs98mE9TEb9AMixQMLZ2IqsgLwPA/exec"
                response = requests.post(webhook_url, json={'action': 'delete', 'candidate_id': sheets_candidate_id}, timeout=10)
                if response.status_code == 200:
                    print(f"✅ Deleted {sheets_candidate_id} from Google Sheets")
            except Exception as e:
                print(f"⚠️ Sheets deletion failed: {e}")
        
        return {"message": "Candidate deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"Delete error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")

@router.get("/{candidate_id}/resume-file")
async def get_resume_file(
    candidate_id: int,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
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
        
        if not os.path.exists(candidate.resume_file_path):
            raise HTTPException(status_code=404, detail=f"Resume file not found at path: {candidate.resume_file_path}")
        
        file_ext = os.path.splitext(candidate.resume_file_path)[1].lower()
        
        # Read file content
        with open(candidate.resume_file_path, 'rb') as f:
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
    client: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get candidates grouped by stage for Kanban board"""
    from app.models import JobDescription
    stages = {}
    for stage in CandidateStage:
        query = db.query(Candidate).filter(Candidate.stage == stage)
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
                "stage": c.stage.value if c.stage else None,
                "stage_entered_at": c.stage_entered_at.isoformat() if c.stage_entered_at else None,
                "applied_at": c.applied_at.isoformat() if c.applied_at else None
            }
            for c in candidates
        ]
    return stages

@router.post("/send-email")
def send_email(
    email_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Send email to candidate"""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    try:
        to_email = email_data.get('to')
        subject = email_data.get('subject')
        body = email_data.get('body')
        
        if not all([to_email, subject, body]):
            raise HTTPException(status_code=400, detail="Missing required fields: to, subject, body")
        
        # TODO: Configure SMTP settings in environment variables
        # For now, return success (email functionality needs SMTP configuration)
        print(f"📧 Email would be sent to: {to_email}")
        print(f"   Subject: {subject}")
        print(f"   Body: {body[:100]}...")
        
        return {
            "success": True,
            "message": f"Email sent to {to_email}",
            "note": "SMTP not configured. Email logged to console."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Email send error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")







