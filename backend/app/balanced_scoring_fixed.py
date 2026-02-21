"""
FIXED Resume Scoring System - Addresses Backend Resume Under-scoring
Total: 100 points (Experience:35, Skills:30, Projects:20, Education:10, Soft Skills:5)

FIXES APPLIED:
1. Declared skills get baseline credit (+1 per match)
2. Evidence-based skills get higher weight (+2.5 per action sentence)
3. Backend work experience counts as project evidence
4. Title match bonus for relevant roles
5. Education capped, doesn't mask skill failure
"""

import re
from typing import Dict, List, Tuple
from difflib import SequenceMatcher

from app.spacy_nlp import get_nlp_signals, SPACY_AVAILABLE

if not SPACY_AVAILABLE:
    raise ImportError("spaCy required")


# FIX 1 & 2: DECLARED + EVIDENCE-BASED SKILLS (30 points)
def calculate_skills_score(resume_text: str, required_skills: List[str], 
                          projects_score: float = 0, max_points: int = 30) -> Dict:
    """
    FIX: Declared skills (+1) + Evidence-based skills (+2.5)
    """
    if not required_skills or not resume_text:
        return {'score': 0.0, 'max': max_points, 'matched_skills': [], 'match_percentage': 0.0}
    
    resume_lower = resume_text.lower()
    nlp_signals = get_nlp_signals(resume_text)
    
    # Extract declared skills section
    declared_skills = extract_declared_skills(resume_text)
    
    matched_skills = []
    declared_score = 0.0
    evidence_score = 0.0
    
    for skill in required_skills:
        skill_lower = skill.lower()
        
        # FIX 1: Declared skill match (+1 point)
        if any(skill_lower in ds.lower() for ds in declared_skills):
            matched_skills.append(skill)
            declared_score += 1.0
        
        # FIX 2: Evidence-based skill (+2.5 points if in action sentence)
        if is_skill_in_action_context(skill_lower, resume_text, nlp_signals):
            evidence_score += 2.5
            if skill not in matched_skills:
                matched_skills.append(skill)
    
    total_score = declared_score + evidence_score
    
    # Bonus: +5 if strong projects
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
    """Extract skills from Skills/Technical Skills section ONLY"""
    skills = []
    lines = resume_text.split('\n')
    in_skills_section = False
    
    for i, line in enumerate(lines):
        line_lower = line.lower().strip()
        
        # Detect skills section start
        if re.match(r'^(technical\s+)?skills?\s*:?$', line_lower):
            in_skills_section = True
            continue
        
        # Detect section end
        if in_skills_section and re.match(r'^(experience|education|projects|work|certifications)', line_lower):
            break
        
        # Extract skills from section
        if in_skills_section and line.strip():
            # Remove bullets and split by common delimiters
            cleaned = re.sub(r'^[-•*]\s*', '', line)
            skill_items = re.split(r'[,;|]', cleaned)
            skills.extend([s.strip() for s in skill_items if s.strip()])
    
    return skills


def is_skill_in_action_context(skill: str, resume_text: str, nlp_signals: Dict) -> bool:
    """Check if skill appears in action-oriented sentence (not just listed)"""
    action_verbs = {'developed', 'built', 'implemented', 'designed', 'optimized', 
                   'integrated', 'created', 'deployed', 'maintained', 'architected'}
    
    # Split into sentences
    sentences = re.split(r'[.!?\n]', resume_text.lower())
    
    for sentence in sentences:
        if skill in sentence:
            # Check if sentence has action verb
            if any(verb in sentence for verb in action_verbs):
                return True
    
    return False


# FIX 4: EXPERIENCE WITH TITLE MATCH BONUS (35 points)
def calculate_experience_score(resume_text: str, years_of_experience: float, 
                               required_skills: List[str], required_min: float, 
                               required_max: float, job_title: str = "",
                               max_points: int = 35) -> Dict:
    """
    FIX: Added title match bonus (+3 max)
    """
    if years_of_experience is None:
        years_of_experience = 0
    
    # Base years score (10-12 pts)
    if years_of_experience >= required_max:
        base_score = 12
    elif years_of_experience >= required_min:
        base_score = 10 + (years_of_experience - required_min) / (required_max - required_min) * 2
    else:
        base_score = (years_of_experience / required_min) * 10 if required_min > 0 else 0
    
    if not resume_text:
        return {'score': round(base_score, 2), 'max': max_points, 'years': years_of_experience}
    
    nlp_signals = get_nlp_signals(resume_text)
    resume_lower = resume_text.lower()
    
    # JD relevant actions bonus (up to 15 pts)
    action_count = nlp_signals.get('action_verb_count', 0)
    skill_mentions = sum(1 for skill in required_skills if skill.lower() in resume_lower)
    jd_relevant_bonus = min(15, (action_count * 0.5) + (skill_mentions * 1.5))
    
    # Seniority adjustment
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
        'title_bonus': round(title_bonus, 2)
    }


def calculate_title_match_bonus(resume_text: str, job_title: str) -> float:
    """FIX 4: Fuzzy match resume titles with JD title"""
    if not job_title:
        return 0.0
    
    job_title_lower = job_title.lower()
    lines = resume_text.split('\n')
    
    # Extract potential job titles (lines near "experience" or standalone)
    resume_titles = []
    for i, line in enumerate(lines[:30]):  # Check first 30 lines
        line_clean = line.strip()
        if 3 < len(line_clean) < 60 and not line_clean.endswith(':'):
            # Likely a job title
            resume_titles.append(line_clean.lower())
    
    # Fuzzy match
    best_match = 0.0
    for resume_title in resume_titles:
        similarity = SequenceMatcher(None, job_title_lower, resume_title).ratio()
        best_match = max(best_match, similarity)
    
    # Award bonus based on similarity
    if best_match >= 0.8:
        return 3.0
    elif best_match >= 0.6:
        return 2.0
    elif best_match >= 0.4:
        return 1.0
    
    return 0.0


# FIX 3: PROJECTS WITH BACKEND EXPERIENCE MERGE (20 points)
def calculate_projects_score(resume_text: str, job_description: str, 
                            experience_years: float, job_title: str = "",
                            max_points: int = 20) -> Dict:
    """
    FIX 3: Backend work experience counts as project evidence
    """
    if not resume_text:
        return {'score': 0.0, 'max': max_points, 'relevance_score': 0.0, 'complexity_score': 0.0}
    
    resume_lower = resume_text.lower()
    nlp_signals = get_nlp_signals(resume_text)
    
    # FIX 3: Check if backend role
    is_backend_role = any(keyword in job_title.lower() for keyword in 
                         ['backend', 'software engineer', 'api', 'server', 'full stack'])
    
    # Part A: Work Relevance (0-10 points)
    relevance_score = 0.0
    
    # Action verbs
    action_count = nlp_signals['action_verb_count']
    verb_density = nlp_signals['verb_density']
    relevance_score += min(3, action_count * 0.3)
    
    if verb_density > 3.0:
        relevance_score += 2
    elif verb_density > 2.0:
        relevance_score += 1
    
    # Collaboration
    if nlp_signals['collaboration_count'] >= 2:
        relevance_score += 2
    elif nlp_signals['collaboration_count'] >= 1:
        relevance_score += 1
    
    # Production work (not academic)
    academic_keywords = ['college', 'academic', 'university project', 'course project']
    if not any(keyword in resume_lower for keyword in academic_keywords):
        relevance_score += 3
    
    # FIX 3: Backend experience as project evidence
    if is_backend_role:
        backend_evidence = count_backend_work_evidence(resume_text)
        relevance_score += min(3, backend_evidence)  # Up to +3 bonus
    
    # Part B: Technical Complexity (0-10 points)
    complexity_score = 0.0
    
    if experience_years <= 3:
        junior_keywords = {'web': 2, 'backend': 2, 'frontend': 2, 'database': 2,
                          'api': 2, 'responsive': 1, 'crud': 1, 'rest': 2}
        for keyword, points in junior_keywords.items():
            if keyword in resume_lower:
                complexity_score += points
    else:
        senior_keywords = {'microservices': 3, 'architecture': 3, 'cloud': 3, 'aws': 2,
                          'kubernetes': 2, 'docker': 2, 'scalable': 2, 'distributed': 2,
                          'ci/cd': 2, 'devops': 2}
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
    
    return min(evidence_count, 5)  # Cap at 5


# FIX 5: EDUCATION CAPPED (10 points max)
def calculate_education_score(resume_text: str, max_points: int = 10) -> Dict:
    """FIX 5: Education capped, cannot compensate for missing skills"""
    if not resume_text:
        return {'score': 0.0, 'max': max_points, 'degree_found': 'None'}
    
    resume_lower = resume_text.lower()
    score = 0.0
    degree_found = 'None'
    
    # Highly relevant (10 pts)
    highly_relevant = ['computer science', 'software engineering', 'information technology',
                      'computer engineering', r'\bcs\b', 'b.tech cs', 'mca', 'm.tech cs']
    
    for degree in highly_relevant:
        if re.search(degree, resume_lower):
            score = 10
            degree_found = degree.upper()
            break
    
    # Moderately relevant (6 pts)
    if score == 0:
        moderately_relevant = ['engineering', 'b.tech', 'b.e', 'bca', 'electronics']
        for degree in moderately_relevant:
            if re.search(degree, resume_lower):
                score = 6
                degree_found = degree.upper()
                break
    
    # Pursuing penalty (-20%)
    if score > 0:
        if any(kw in resume_lower for kw in ['pursuing', 'expected', 'in progress']):
            score *= 0.8
    
    return {'score': round(score, 2), 'max': max_points, 'degree_found': degree_found}


# Soft Skills (unchanged)
def calculate_soft_skills_score(resume_text: str, experience_years: float, max_points: int = 5) -> Dict:
    if not resume_text:
        return {'score': 0.0, 'max': max_points}
    
    nlp_signals = get_nlp_signals(resume_text)
    score = 0.0
    
    if nlp_signals['leadership_count'] >= 3:
        score += 2
    elif nlp_signals['leadership_count'] >= 1:
        score += 1
    
    if nlp_signals['collaboration_count'] >= 2:
        score += 2
    elif nlp_signals['collaboration_count'] >= 1:
        score += 1
    
    if nlp_signals['impact_count'] >= 2:
        score += 1
    
    return {'score': round(min(score, max_points), 2), 'max': max_points}


def extract_years_experience(resume_text: str) -> float:
    if not resume_text:
        return 0.0
    
    resume_lower = resume_text.lower()
    
    # Pattern: "X years"
    year_patterns = [r'(\d+)\s*\+?\s*years?\s+of\s+experience', r'(\d+)\s*\+?\s*years?\s+experience']
    for pattern in year_patterns:
        match = re.search(pattern, resume_lower)
        if match:
            return float(match.group(1))
    
    # Date ranges
    current_year = 2024
    date_pattern = r'(\d{4})\s*[-–]\s*(?:(\d{4})|present|current)'
    matches = re.findall(date_pattern, resume_lower, re.IGNORECASE)
    
    if matches:
        total_years = sum(max(0, (int(m[1]) if m[1] else current_year) - int(m[0])) for m in matches)
        return float(total_years)
    
    return 0.0


# MAIN EVALUATION FUNCTION
def evaluate_resume_balanced(resume_data: Dict, job_requirements: Dict) -> Dict:
    """
    FIXED evaluation with all 5 fixes applied
    """
    resume_text = resume_data.get('full_text', '')
    years_exp = resume_data.get('years_of_experience')
    
    if years_exp is None or years_exp == 0:
        years_exp = extract_years_experience(resume_text)
    
    required_skills = job_requirements.get('required_skills', [])
    exp_min = job_requirements.get('experience_min', 0)
    exp_max = job_requirements.get('experience_max', 10)
    job_desc = job_requirements.get('description', '')
    job_title = job_requirements.get('title', '')
    
    # Calculate components (projects first for skills bonus)
    projects_result = calculate_projects_score(resume_text, job_desc, years_exp, job_title)
    skills_result = calculate_skills_score(resume_text, required_skills, projects_result['score'])
    experience_result = calculate_experience_score(resume_text, years_exp, required_skills, exp_min, exp_max, job_title)
    education_result = calculate_education_score(resume_text)
    soft_skills_result = calculate_soft_skills_score(resume_text, years_exp)
    
    total_score = (experience_result['score'] + skills_result['score'] + 
                  projects_result['score'] + education_result['score'] + 
                  soft_skills_result['score'])
    
    # Assign label
    if total_score >= 75:
        label, status = "Strong Fit", "shortlisted"
    elif total_score >= 55:
        label, status = "Potential Fit", "shortlisted"
    elif total_score >= 45:
        label, status = "Borderline Fit", "review"
    else:
        label, status = "Weak Fit", "rejected"
    
    return {
        'total_score': round(total_score, 2),
        'label': label,
        'status': status,
        'components': {
            'experience': experience_result,
            'skills': skills_result,
            'projects': projects_result,
            'education': education_result,
            'soft_skills': soft_skills_result
        }
    }
