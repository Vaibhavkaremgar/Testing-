# Skill normalization mapping
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
    'c++': 'cpp',
    'c#': 'csharp',
    'postgresql': 'postgres',
    'mongo': 'mongodb',
    'aws': 'amazon web services',
    'gcp': 'google cloud platform',
    'k8s': 'kubernetes',
    'ml': 'machine learning',
    'ai': 'artificial intelligence',
    'dl': 'deep learning',
    'tf': 'tensorflow',
    'sql server': 'microsoft sql server',
    'mssql': 'microsoft sql server',
    'git & github': 'git',
    'github': 'git',
    'responsive web design': 'responsive',
    'responsive design': 'responsive',
}

def normalize_skill(skill: str) -> str:
    """Normalize skill name to standard form"""
    if not skill:
        return skill
    
    skill_lower = skill.lower().strip()
    
    # Handle complex skills like "React.js (or Angular / Vue)"
    # Extract main skill before parentheses
    if '(' in skill_lower:
        skill_lower = skill_lower.split('(')[0].strip()
    
    return SKILL_ALIASES.get(skill_lower, skill_lower)

def normalize_skills_list(skills: list) -> list:
    """Normalize a list of skills"""
    if not skills:
        return []
    
    normalized = []
    seen = set()
    
    for skill in skills:
        normalized_skill = normalize_skill(skill)
        if normalized_skill and normalized_skill not in seen:
            normalized.append(normalized_skill)
            seen.add(normalized_skill)
    
    return normalized

def skills_match(candidate_skills: list, required_skills: list) -> dict:
    """Check if candidate skills match required skills with normalization"""
    if not candidate_skills or not required_skills:
        return {'matched': [], 'missing': required_skills or [], 'match_percentage': 0}
    
    # Normalize both lists
    norm_candidate = set(normalize_skill(s) for s in candidate_skills)
    norm_required = [normalize_skill(s) for s in required_skills]
    
    matched = []
    missing = []
    
    for req_skill in norm_required:
        if req_skill in norm_candidate:
            matched.append(req_skill)
        else:
            missing.append(req_skill)
    
    match_percentage = (len(matched) / len(norm_required) * 100) if norm_required else 0
    
    return {
        'matched': matched,
        'missing': missing,
        'match_percentage': round(match_percentage, 1)
    }
