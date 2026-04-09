"""
Balanced Resume Scoring System - spaCy Only
Total: 100 points (Experience:35, Skills:30, Projects:20, Education:10, Soft Skills:5)
"""

import re
from datetime import datetime
from typing import Dict, List, Tuple

from ats.preprocessing.section_segmentation import get_section_content

# Import spaCy NLP helpers (REQUIRED - no fallback)
from app.spacy_nlp import get_nlp_signals, SPACY_AVAILABLE

if not SPACY_AVAILABLE:
    raise ImportError("spaCy is required for resume scoring. Please install: pip install spacy && python -m spacy download en_core_web_sm")

print("[OK] spaCy NLP scoring system loaded successfully")


# FIX 1 & 2: DECLARED + EVIDENCE-BASED SKILLS (30 points)
def calculate_skills_score(resume_text: str, required_skills: List[str], projects_score: float = 0, max_points: int = 30, nlp_cache: Dict = None) -> Dict:
    """
    FIX: Declared skills (+1) + Evidence-based skills (+2.5) + Skill normalization (js→javascript)
    """
    if not required_skills or not resume_text:
        return {'score': 0.0, 'max': max_points, 'matched_skills': [], 'match_percentage': 0.0}
    
    from app.skill_normalizer import normalize_skill
    
    resume_lower = resume_text.lower()

    if re.search(r'\b(fresher|fresh graduate|recent graduate|entry level|no experience|0\s*\+?\s*years?)\b', resume_lower):
        return 0.0
    nlp_signals = nlp_cache if nlp_cache else get_nlp_signals(resume_text)
    declared_skills = extract_declared_skills(resume_text)
    
    matched_skills = []
    declared_score = 0.0
    evidence_score = 0.0
    
    for skill in required_skills:
        skill_lower = skill.lower()
        skill_normalized = normalize_skill(skill_lower)
        
        # FIX 1: Declared skill match (+1 point) with normalization
        skill_found = False
        for ds in declared_skills:
            ds_normalized = normalize_skill(ds.lower())
            if skill_normalized == ds_normalized or skill_lower in ds.lower() or ds.lower() in skill_lower:
                matched_skills.append(skill)
                declared_score += 1.0
                skill_found = True
                break
        
        # FIX 2: Evidence-based skill (+2.5 points if in action sentence)
        if is_skill_in_action_context(skill_lower, resume_text, nlp_signals) or \
           is_skill_in_action_context(skill_normalized, resume_text, nlp_signals):
            evidence_score += 2.5
            if skill not in matched_skills:
                matched_skills.append(skill)
    
    total_score = declared_score + evidence_score
    if projects_score > 12:
        total_score += 5
    
    total_score = min(total_score, max_points)
    match_percentage = (len(matched_skills) / len(required_skills)) * 100 if required_skills else 0
    
    return {
        'score': round(total_score, 2),
        'max': max_points,
        'matched_skills': matched_skills,
        'match_percentage': round(match_percentage, 2),
        'declared_score': round(declared_score, 2),
        'evidence_score': round(evidence_score, 2)
    }


def extract_declared_skills(resume_text: str) -> List[str]:
    """Extract skills from Skills section ONLY"""
    skills = []
    lines = resume_text.split('\n')
    in_skills_section = False
    
    for line in lines:
        line_lower = line.lower().strip()
        if re.match(r'^(technical\s+)?skills?\s*:?$', line_lower):
            in_skills_section = True
            continue
        if in_skills_section and re.match(r'^(experience|education|projects|work|certifications)', line_lower):
            break
        if in_skills_section and line.strip():
            cleaned = re.sub(r'^[-•*]\s*', '', line)
            skill_items = re.split(r'[,;|]', cleaned)
            skills.extend([s.strip() for s in skill_items if s.strip()])
    return skills


def is_skill_in_action_context(skill: str, resume_text: str, nlp_signals: Dict) -> bool:
    """Check if skill appears in action-oriented sentence"""
    action_verbs = {'developed', 'built', 'implemented', 'designed', 'optimized', 
                   'integrated', 'created', 'deployed', 'maintained', 'architected'}
    sentences = re.split(r'[.!?\n]', resume_text.lower())
    for sentence in sentences:
        if skill in sentence and any(verb in sentence for verb in action_verbs):
            return True
    return False


# FIX 4: EXPERIENCE WITH TITLE MATCH BONUS (35 points)
def calculate_experience_score(resume_text: str, years_of_experience: float, 
                               required_skills: List[str], required_min: float, 
                               required_max: float, job_title: str = "", max_points: int = 35, nlp_cache: Dict = None) -> Dict:
    """
    Formula: base_years_score (10-12) + jd_relevant_actions_bonus (up to 15) + seniority_adjustment
    """
    if years_of_experience is None:
        years_of_experience = 0
    
    # Part A: Base years score (10-12 pts)
    if years_of_experience >= required_max:
        base_score = 12
    elif years_of_experience >= required_min:
        base_score = 10 + (years_of_experience - required_min) / (required_max - required_min) * 2
    else:
        base_score = (years_of_experience / required_min) * 10 if required_min > 0 else 0
    
    # Part B: JD relevant actions bonus (up to 15 pts)
    jd_relevant_bonus = 0.0
    seniority_adjustment = 0.0
    
    if not resume_text:
        return {
            'score': round(base_score, 2),
            'max': max_points,
            'years': years_of_experience,
            'assessment': 'Base years only'
        }
    
    nlp_signals = nlp_cache if nlp_cache else get_nlp_signals(resume_text)
    resume_lower = resume_text.lower()
    
    # JD relevant actions (action verbs + skill mentions)
    action_count = nlp_signals.get('action_verb_count', 0)
    skill_mentions = sum(1 for skill in required_skills if skill.lower() in resume_lower)
    
    jd_relevant_bonus = min(15, (action_count * 0.5) + (skill_mentions * 1.5))
    
    # Part C: Seniority adjustment
    leadership_count = nlp_signals.get('leadership_count', 0)
    if years_of_experience >= 5 and leadership_count >= 2:
        seniority_adjustment = 8
    elif years_of_experience >= 3 and leadership_count >= 1:
        seniority_adjustment = 5
    elif years_of_experience >= 2:
        seniority_adjustment = 3
    else:
        seniority_adjustment = 0
    
    # FIX 4: Title match bonus (+3 max)
    title_bonus = calculate_title_match_bonus(resume_text, job_title)
    
    total_score = base_score + jd_relevant_bonus + seniority_adjustment + title_bonus
    total_score = min(total_score, max_points)
    
    return {
        'score': round(total_score, 2),
        'max': max_points,
        'years': years_of_experience,
        'base_score': round(base_score, 2),
        'jd_bonus': round(jd_relevant_bonus, 2),
        'seniority': round(seniority_adjustment, 2),
        'title_bonus': round(title_bonus, 2),
        'assessment': f"Base:{base_score:.1f} + JD:{jd_relevant_bonus:.1f} + Senior:{seniority_adjustment:.1f} + Title:{title_bonus:.1f}"
    }


def calculate_title_match_bonus(resume_text: str, job_title: str) -> float:
    """FIX 4: Fuzzy match resume titles with JD title"""
    if not job_title:
        return 0.0
    from difflib import SequenceMatcher
    job_title_lower = job_title.lower()
    lines = resume_text.split('\n')
    resume_titles = [line.strip().lower() for line in lines[:30] if 3 < len(line.strip()) < 60 and not line.strip().endswith(':')]
    best_match = max([SequenceMatcher(None, job_title_lower, rt).ratio() for rt in resume_titles], default=0.0)
    if best_match >= 0.8:
        return 3.0
    elif best_match >= 0.6:
        return 2.0
    elif best_match >= 0.4:
        return 1.0
    return 0.0


# FIX 3: PROJECTS WITH BACKEND EXPERIENCE MERGE (20 points)
def calculate_projects_score(resume_text: str, job_description: str, 
                            experience_years: float, job_title: str = "", max_points: int = 20, nlp_cache: Dict = None) -> Dict:
    """
    FIX 3: Backend work experience counts as project evidence
    """
    if not resume_text:
        return {
            'score': 0.0,
            'max': max_points,
            'relevance_score': 0.0,
            'complexity_score': 0.0
        }
    
    resume_lower = resume_text.lower()
    
    nlp_signals = nlp_cache if nlp_cache else get_nlp_signals(resume_text)
    
    # FIX 3: Check if backend role
    is_backend_role = any(keyword in job_title.lower() for keyword in 
                         ['backend', 'software engineer', 'api', 'server', 'full stack'])
    
    # Part A: Work Relevance (0-10 points)
    relevance_score = 0.0
    action_count = nlp_signals['action_verb_count']
    verb_density = nlp_signals['verb_density']
    relevance_score += min(3, action_count * 0.3)
    
    if verb_density > 3.0:
        relevance_score += 2
    elif verb_density > 2.0:
        relevance_score += 1
    
    if nlp_signals['collaboration_count'] >= 2:
        relevance_score += 2
    elif nlp_signals['collaboration_count'] >= 1:
        relevance_score += 1
    
    academic_keywords = ['college', 'academic', 'university project', 'course project']
    if not any(keyword in resume_lower for keyword in academic_keywords):
        relevance_score += 3
    
    # FIX 3: Backend experience as project evidence
    if is_backend_role:
        backend_evidence = count_backend_work_evidence(resume_text)
        relevance_score += min(3, backend_evidence)
    
    # Part B: Technical Complexity (0-10 points) - SENIORITY-ADJUSTED
    complexity_score = 0.0
    
    if experience_years <= 3:
        # Junior keywords
        junior_keywords = {
            'web': 2, 'backend': 2, 'frontend': 2, 'database': 2,
            'api': 2, 'responsive': 1, 'crud': 1, 'rest': 2
        }
        for keyword, points in junior_keywords.items():
            if keyword in resume_lower:
                complexity_score += points
    else:
        # Senior keywords
        senior_keywords = {
            'microservices': 3, 'architecture': 3, 'cloud': 3, 'aws': 2,
            'kubernetes': 2, 'docker': 2, 'scalable': 2, 'distributed': 2,
            'ci/cd': 2, 'devops': 2
        }
        for keyword, points in senior_keywords.items():
            if keyword in resume_lower:
                complexity_score += points
    
    complexity_score = min(10, complexity_score)
    total_score = min(relevance_score + complexity_score, max_points)
    
    return {
        'score': round(total_score, 2),
        'max': max_points,
        'relevance_score': round(relevance_score, 2),
        'complexity_score': round(complexity_score, 2)
    }


def count_backend_work_evidence(resume_text: str) -> int:
    """FIX 3: Count backend responsibilities in work experience"""
    backend_indicators = [
        'api development', 'rest api', 'restful', 'database', 'sql', 'nosql',
        'authentication', 'authorization', 'backend', 'server', 'microservice',
        'integration', 'endpoint', 'middleware', 'orm', 'query optimization'
    ]
    resume_lower = resume_text.lower()
    evidence_count = sum(1 for indicator in backend_indicators if indicator in resume_lower)
    return min(evidence_count, 5)


# Component 4: Education (10 points)
def calculate_education_score(resume_text: str, max_points: int = 10) -> Dict:
    """
    Evaluate if candidate has relevant educational background.
    
    Highly relevant: 10 points (100%)
    Moderately relevant: 6 points (60%)
    Pursuing: -20% penalty
    """
    if not resume_text:
        return {
            'score': 0.0,
            'max': max_points,
            'degree_found': 'None',
            'relevance': 'Not Found'
        }
    
    resume_lower = resume_text.lower()
    score = 0.0
    degree_found = 'None'
    relevance = 'Not Found'
    
    # Highly relevant degrees (10 pts)
    highly_relevant = [
        'computer science', 'software engineering', 'information technology',
        'computer engineering', r'\bcs\b', 'b.tech cs', 'b.e cs', 'b.tech cse',
        'mca', 'm.tech cs', 'bsc cs', 'msc cs'
    ]
    
    for degree in highly_relevant:
        if re.search(degree, resume_lower):
            score = 10
            degree_found = degree.upper()
            relevance = 'Highly Relevant'
            break
    
    # Moderately relevant (6 pts)
    if score == 0:
        moderately_relevant = [
            'engineering', 'b.tech', 'b.e', 'bca', 'electronics', 'electrical', 'bsc it'
        ]
        for degree in moderately_relevant:
            if re.search(degree, resume_lower):
                score = 6
                degree_found = degree.upper()
                relevance = 'Moderately Relevant'
                break
    
    # Check for pursuing/incomplete (-20% penalty)
    if score > 0:
        pursuing_keywords = ['pursuing', 'expected', 'current', 'in progress']
        if any(keyword in resume_lower for keyword in pursuing_keywords):
            score *= 0.8
            relevance += ' (Pursuing)'
    
    return {
        'score': round(score, 2),
        'max': max_points,
        'degree_found': degree_found,
        'relevance': relevance
    }


# Component 5: Soft Skills & Leadership (5 points) - SPACY VERB ANALYSIS
def calculate_soft_skills_score(resume_text: str, experience_years: float, max_points: int = 5, nlp_cache: Dict = None) -> Dict:
    """
    spaCy-based soft skill detection using verb analysis.
    """
    if not resume_text:
        return {'score': 0.0, 'max': max_points, 'leadership': 0, 'collaboration': 0, 'metrics': 0}
    
    # Get NLP signals from spaCy
    nlp_signals = nlp_cache if nlp_cache else get_nlp_signals(resume_text)
    
    leadership_count = nlp_signals['leadership_count']
    collaboration_count = nlp_signals['collaboration_count']
    impact_count = nlp_signals['impact_count']
    
    score = 0.0
    
    # Leadership (0-2 pts)
    if leadership_count >= 3:
        score += 2
    elif leadership_count >= 1:
        score += 1
    
    # Collaboration (0-2 pts)
    if collaboration_count >= 2:
        score += 2
    elif collaboration_count >= 1:
        score += 1
    
    # Impact metrics (0-1 pt)
    if impact_count >= 2:
        score += 1
    
    return {
        'score': round(min(score, max_points), 2),
        'max': max_points,
        'leadership': leadership_count,
        'collaboration': collaboration_count,
        'metrics': impact_count
    }


# Helper function
def _extract_experience_section(resume_text: str) -> str:
    patterns = [
        r'(?:work\s+)?experience\s*:?\s*(.*?)(?=\n\s*(?:education|skills|projects?|certifications?|achievements|summary)\b|\Z)',
        r'(?:professional|employment)\s+(?:experience|history)\s*:?\s*(.*?)(?=\n\s*(?:education|skills|projects?|certifications?|achievements|summary)\b|\Z)',
        r'internships?\s*:?\s*(.*?)(?=\n\s*(?:education|skills|projects?|certifications?|achievements|summary)\b|\Z)',
    ]

    for pattern in patterns:
        match = re.search(pattern, resume_text, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip()

    return ""


def _parse_month_year(token: str, current_year: int) -> Tuple[int, int] | None:
    if not token:
        return None

    token = token.strip().lower()
    month_map = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    if token in {'present', 'current', 'now'}:
        now = datetime.utcnow()
        return (now.year, now.month)

    match = re.match(r'(?:(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+)?(\d{4})', token)
    if not match:
        return None

    month_token, year_token = match.groups()
    year = int(year_token)
    if year < 1990 or year > current_year:
        return None

    return (year, month_map.get(month_token, 1) if month_token else 1)


def extract_declared_skills(resume_text: str) -> List[str]:
    """Extract skills from the segmented skills section only."""
    skills_section = get_section_content(resume_text, "skills")
    if not skills_section:
        return []

    skills: List[str] = []
    for line in skills_section.split('\n'):
        if line.strip():
            cleaned = re.sub(r'^[-•*]\s*', '', line)
            skill_items = re.split(r'[,;|]', cleaned)
            skills.extend([item.strip() for item in skill_items if item.strip()])
    return skills


def _extract_experience_section(resume_text: str) -> str:
    return get_section_content(resume_text, "experience").strip()


def _merge_intervals(intervals: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not intervals:
        return []

    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end + 1:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def extract_years_experience(resume_text: str) -> float:
    """
    Extract years of experience from resume text.
    
    Look for patterns:
    1. "X years of experience"
    2. "X+ years"
    3. Date ranges: "2020-2024", "2023-Present"
    """
    if not resume_text:
        return 0.0
    
    resume_lower = resume_text.lower()

    if re.search(r'\b(fresher|fresh graduate|recent graduate|entry level|no experience|0\s*\+?\s*years?)\b', resume_lower):
        return 0.0

    experience_text = _extract_experience_section(resume_text)
    if not experience_text:
        return 0.0

    # ATS scoring should ignore summary/header claims like "10+ years experience"
    # and rely only on dated roles from the Experience section.
    current_year = datetime.utcnow().year
    date_pattern = r'(\d{4})\s*[-–]\s*(?:(\d{4})|present|current)'
    matches = re.findall(date_pattern, experience_text, re.IGNORECASE)
    
    if matches:
        intervals: List[Tuple[int, int]] = []
        for match in matches:
            start_year = int(match[0])
            end_year = int(match[1]) if match[1] else current_year
            if end_year < start_year:
                continue
            intervals.append((start_year, end_year))

        merged_intervals = _merge_intervals(sorted(intervals))
        total_years = sum(end - start for start, end in merged_intervals)
        if total_years <= 40:
            return float(total_years)
    
    return 0.0


# Main evaluation function
def evaluate_resume_balanced(resume_data: Dict, job_requirements: Dict) -> Dict:
    """
    Main function to evaluate resume using balanced scoring system.
    
    Args:
        resume_data: {
            'full_text': str,
            'years_of_experience': float
        }
        
        job_requirements: {
            'required_skills': list,
            'experience_min': float,
            'experience_max': float,
            'description': str
        }
    
    Returns:
        Complete evaluation with scores and components
    """
    # Extract data
    resume_text = resume_data.get('full_text', '')
    years_exp = resume_data.get('years_of_experience')
    
    # If years not provided, try to extract
    if years_exp is None or years_exp == 0:
        years_exp = extract_years_experience(resume_text)
    
    required_skills = job_requirements.get('required_skills', [])
    exp_min = job_requirements.get('experience_min', 0)
    exp_max = job_requirements.get('experience_max', 10)
    job_desc = job_requirements.get('description', '')
    job_title = job_requirements.get('title', '')
    
    # FIX: Cache NLP signals ONCE to ensure deterministic scoring
    nlp_cache = get_nlp_signals(resume_text) if resume_text else {}
    print(f"   NLP Cache created with {nlp_cache.get('action_verb_count', 0)} action verbs (DETERMINISTIC MODE)")
    
    # Calculate all components (projects first for skills bonus) - pass nlp_cache
    projects_result = calculate_projects_score(resume_text, job_desc, years_exp, job_title, nlp_cache=nlp_cache)
    skills_result = calculate_skills_score(resume_text, required_skills, projects_result['score'], nlp_cache=nlp_cache)
    print(f"   Skills result: {skills_result.get('matched_skills', [])} ({skills_result.get('score', 0)}/30)")
    experience_result = calculate_experience_score(resume_text, years_exp, required_skills, exp_min, exp_max, job_title, nlp_cache=nlp_cache)
    education_result = calculate_education_score(resume_text)
    soft_skills_result = calculate_soft_skills_score(resume_text, years_exp, nlp_cache=nlp_cache)
    
    # Calculate total score
    total_score = (
        experience_result['score'] +
        skills_result['score'] +
        projects_result['score'] +
        education_result['score'] +
        soft_skills_result['score']
    )
    
    # Assign label and status (threshold = 55)
    if total_score >= 75:
        label = "Strong Fit"
        status = "shortlisted"
    elif total_score >= 55:
        label = "Potential Fit"
        status = "shortlisted"
    elif total_score >= 45:
        label = "Borderline Fit"
        status = "review"
    else:
        label = "Weak Fit"
        status = "rejected"
    
    # Build components dict
    components = {
        'experience': experience_result,
        'skills': skills_result,
        'projects': projects_result,
        'education': education_result,
        'soft_skills': soft_skills_result
    }
    
    return {
        'total_score': round(total_score, 2),
        'label': label,
        'status': status,
        'components': components,
    }


# Test/Example usage
if __name__ == "__main__":
    # Test with Rahul Sharma's resume
    resume_data = {
        'full_text': """
        Rahul Sharma
        Software Engineer
        Hyderabad
        Email: rahul.sharma@email.com
        
        Professional Summary
        Software Engineer with 2 years of experience in the IT industry, 
        specializing in web application development using HTML, CSS, 
        JavaScript, Java, and SQL.
        
        Skills
        HTML, CSS, JavaScript, Java, SQL
        
        Work Experience
        Software Engineer – ABC Tech Pvt Ltd (2023–Present)
        - Developed responsive web interfaces using HTML, CSS, and JavaScript
        - Built backend modules using Java
        - Worked with SQL databases for data storage and retrieval
        - Collaborated with cross-functional IT teams
        
        Education
        B.Tech in Computer Science – JNTU Hyderabad (2022)
        """,
        'years_of_experience': 2
    }
    
    job_requirements = {
        'required_skills': ['HTML', 'CSS', 'JavaScript', 'Java', 'SQL'],
        'experience_min': 1,
        'experience_max': 3,
        'description': 'Software engineer with 1-3 years of experience in IT industry'
    }
    
    result = evaluate_resume_balanced(resume_data, job_requirements)
    
    print("="*80)
    print("BALANCED RESUME SCORING SYSTEM - TEST RESULT")
    print("="*80)
    print(f"\nTotal Score: {result['total_score']}/100")
    print(f"Label: {result['label']}")
    print(f"Status: {result['status']}")
    print(f"\nComponent Breakdown:")
    print(f"  Experience: {result['components']['experience']['score']}/35")
    print(f"  Skills: {result['components']['skills']['score']}/30")
    print(f"  Projects: {result['components']['projects']['score']}/20")
    print(f"  Education: {result['components']['education']['score']}/10")
    print(f"  Soft Skills: {result['components']['soft_skills']['score']}/5")
    print("="*80)
