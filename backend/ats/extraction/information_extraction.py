from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List

from flashtext import KeywordProcessor

from ats.extraction.skill_intelligence import SkillIntelligence
from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import clean_text_pipeline
from app.spacy_nlp import SPACY_AVAILABLE, nlp

SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "node": "node.js",
    "nodejs": "node.js",
    "react.js": "react",
    "reactjs": "react",
    "vue.js": "vue",
    "vuejs": "vue",
    "angular.js": "angular",
    "angularjs": "angular",
    "nextjs": "next.js",
    "express.js": "express",
    "expressjs": "express",
    "mongo": "mongodb",
    "postgres": "postgresql",
    "k8s": "kubernetes",
    "docker-compose": "docker",
    "github": "git",
    "gitlab": "git",
    "crm": "customer relationship management",
    "client relationship management": "customer relationship management",
    "customer relationship mgmt": "customer relationship management",
    "bd": "business development",
    "lead gen": "lead generation",
    "account handling": "account management",
    "salesforce crm": "customer relationship management",
    "hubspot crm": "customer relationship management",
    "zoho crm": "customer relationship management",
}

TECHNICAL_SKILLS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "php", "ruby", "go",
    "rust", "swift", "kotlin", "scala", "r", "matlab", "perl", "dart", "html", "css",
    "react", "angular", "vue", "node.js", "express", "django", "flask", "spring",
    "spring boot", "laravel", "rails", "fastapi", "next.js", "mysql", "postgresql",
    "mongodb", "redis", "sqlite", "oracle", "sql", "sql server", "cassandra",
    "dynamodb", "firebase", "elasticsearch", "aws", "azure", "gcp", "docker",
    "kubernetes", "jenkins", "git", "ci/cd", "terraform", "ansible", "linux",
    "graphql", "rest api", "restful api", "microservices", "machine learning",
    "deep learning", "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn",
    "nlp", "opencv", "power bi", "tableau", "excel", "tailwind css", "bootstrap",
]
DOMAIN_SKILLS = [
    "sales", "customer relationship management", "lead generation", "cold calling",
    "account management", "business development", "pipeline management", "b2b sales",
    "b2c sales", "saas", "fmcg", "retail", "banking", "recruitment", "talent acquisition",
    "financial analysis", "accounting", "budgeting", "bookkeeping", "payroll",
    "digital marketing", "seo", "sem", "google analytics", "figma", "graphic design",
    "patient care", "medical coding", "healthcare administration", "office administration",
    "document management", "data entry",
]
SKILL_KEYWORDS = TECHNICAL_SKILLS + DOMAIN_SKILLS

RESPONSIBILITY_SKILL_PHRASES = {
    "cold calling": ["cold calling", "cold outreach", "outbound calling"],
    "lead generation": ["lead generation", "generated leads", "prospecting"],
    "sales": ["sales", "sales target", "revenue growth", "inside sales", "outside sales"],
    "customer relationship management": ["crm", "salesforce", "hubspot", "zoho crm", "customer relationship", "client relationship"],
    "account management": ["account management", "account handling", "key accounts"],
    "business development": ["business development", "market expansion", "new business"],
    "pipeline management": ["pipeline management", "sales pipeline", "pipeline tracking"],
    "rest api": ["rest api", "restful api", "api development"],
    "sql": ["sql", "mysql", "postgresql", "database queries"],
    "fastapi": ["fastapi"],
    "python": ["python"],
    "java": ["java"],
    "html": ["html"],
    "css": ["css"],
    "saas": ["saas"],
    "fmcg": ["fmcg"],
    "retail": ["retail"],
    "banking": ["banking"],
}

DEGREE_PATTERNS = [
    r"\bB\.?\s?Tech\b",
    r"\bM\.?\s?Tech\b",
    r"\bB\.?\s?E\b",
    r"\bM\.?\s?E\b",
    r"\bBCA\b",
    r"\bMCA\b",
    r"\bBSc\b",
    r"\bMSc\b",
    r"\bMBA\b",
    r"\bBachelor(?:'s)?(?:\s+of|\s+in)?\b",
    r"\bMaster(?:'s)?(?:\s+of|\s+in)?\b",
    r"\bDiploma\b",
    r"\bPh\.?\s?D\b",
]

MONTH_TOKEN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
DATE_RANGE_PATTERNS = [
    re.compile(
        rf"(?P<start>{MONTH_TOKEN}\.?\s*\d{{4}}|\d{{4}})\s*(?:-|to|–|—|â€“|â€”)\s*(?P<end>present|current|now|till date|till now|{MONTH_TOKEN}\.?\s*\d{{4}}|\d{{4}})",
        re.IGNORECASE,
    ),
]
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
INSTITUTE_HINTS = ("university", "college", "institute", "school", "academy")
LOCATION_HINTS = (
    "india", "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai", "pune",
    "delhi", "noida", "gurgaon", "kolkata", "ahmedabad", "mumbai, maharashtra",
)
PROJECT_SECTION_KEYWORDS = ("projects", "personal projects", "work projects", "professional projects")
EXPERIENCE_HEADLINE_SPLIT_PATTERN = re.compile(r"\s+[|\-–—â€“â€”]\s+")
WHITESPACE_PATTERN = re.compile(r"\s+")
LOCATION_LINE_PATTERN = re.compile(
    r"(?i)\b(?:location|based in|address|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,.-]{1,80})$"
)
CITY_STATE_PATTERN = re.compile(r"^[A-Z][a-zA-Z]+(?:[\s-][A-Z][a-zA-Z]+)*(?:,\s*[A-Z][a-zA-Z]+(?:[\s-][A-Z][a-zA-Z]+)*)?$")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
NON_LOCATION_PATTERN = re.compile(r"[@:/\\]|(?:\b(?:java|python|html|css|sql|fastapi|react|angular|git)\b)", re.IGNORECASE)
LOCATION_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:managing|managed|operations|including|across|responsible|experience|years|sales|development|engineer|developer|manager|executive|specialist|lead|worked|work|support|project|projects|regional|south|north|east|west)\b"
)
LANGUAGE_TERMS = [
    "english", "hindi", "telugu", "tamil", "kannada", "malayalam", "marathi",
    "gujarati", "punjabi", "bengali", "urdu", "french", "german", "spanish",
    "arabic", "japanese", "mandarin", "chinese",
]
LANGUAGE_LINE_PATTERN = re.compile(r"(?i)^\s*languages?\s*[:\-]?\s*(?P<value>.+)$")

_skill_keyword_processor = KeywordProcessor(case_sensitive=False)
for canonical_skill in SKILL_KEYWORDS:
    _skill_keyword_processor.add_keyword(canonical_skill, canonical_skill)
for alias, canonical_skill in SKILL_ALIASES.items():
    _skill_keyword_processor.add_keyword(alias, canonical_skill)

_skill_intelligence = SkillIntelligence()


def normalize_skill_name(skill: str) -> str:
    normalized = clean_text_pipeline(skill or "").strip().lower()
    normalized = SKILL_ALIASES.get(normalized, normalized)
    return normalized


def _unique_in_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = normalize_skill_name(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _fuzzy_skill_match(candidate: str, target: str, threshold: float = 0.9) -> bool:
    candidate_norm = normalize_skill_name(candidate)
    target_norm = normalize_skill_name(target)
    if candidate_norm == target_norm or candidate_norm in target_norm or target_norm in candidate_norm:
        return True
    if len(candidate_norm.split()) > 4 or len(target_norm.split()) > 4:
        return False
    return SequenceMatcher(None, candidate_norm, target_norm).ratio() >= threshold


def _find_date_match(text: str):
    for pattern in DATE_RANGE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match
    return None


def extract_skill_keywords(text: str, section_text: str = "") -> List[str]:
    """
    Extract skills with a hybrid approach:
    - explicit keyword dictionary
    - FlashText matching
    - ontology-backed skill intelligence
    - spaCy noun chunk fallback
    - fuzzy normalization for close variations
    """
    matches: List[str] = []
    intelligence_matches: List[str] = []

    for source in [section_text, text]:
        if not source:
            continue
        matches.extend(_skill_keyword_processor.extract_keywords(source))
        intelligence_matches.extend(_skill_intelligence.extract_skills(source))

    if section_text:
        for chunk in re.split(r"[\n,;|/]", section_text):
            chunk = chunk.strip(" -*:\t")
            if not chunk:
                continue
            normalized = normalize_skill_name(chunk)
            if normalized in SKILL_KEYWORDS:
                matches.append(normalized)
            else:
                for known_skill in SKILL_KEYWORDS:
                    if _fuzzy_skill_match(chunk, known_skill):
                        matches.append(known_skill)
                        break

    if text and SPACY_AVAILABLE and nlp is not None:
        try:
            doc = nlp(text[:12000])
            phrase_candidates = set()
            phrase_candidates.update(chunk.text.strip().lower() for chunk in doc.noun_chunks if 1 <= len(chunk.text.split()) <= 4)
            phrase_candidates.update(ent.text.strip().lower() for ent in doc.ents if ent.label_ in {"ORG", "PRODUCT"} and 1 <= len(ent.text.split()) <= 4)
            for candidate in phrase_candidates:
                normalized = normalize_skill_name(candidate)
                if normalized in SKILL_KEYWORDS:
                    matches.append(normalized)
                else:
                    for known_skill in SKILL_KEYWORDS:
                        if _fuzzy_skill_match(candidate, known_skill):
                            matches.append(known_skill)
                            break
        except Exception:
            pass

    combined = [normalize_skill_name(skill) for skill in matches]
    combined.extend(_skill_intelligence.map_skills(intelligence_matches))
    return _unique_in_order(combined)[:50]


def _looks_like_location(value: str) -> bool:
    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip(" ,.-")) if value else ""
    if not cleaned or len(cleaned) > 80:
        return False
    if NON_LOCATION_PATTERN.search(cleaned):
        return False
    if LOCATION_NOISE_PATTERN.search(cleaned):
        return False
    if any(char.isdigit() for char in cleaned):
        return False
    if len(cleaned.split()) > 5:
        return False
    return bool(CITY_STATE_PATTERN.match(cleaned))


def _normalize_location_candidate(value: str) -> str:
    if not value:
        return ""

    candidate = WHITESPACE_PATTERN.sub(" ", value.strip(" ,.-"))[:80]
    if not candidate:
        return ""

    if _looks_like_location(candidate):
        return candidate

    if len(candidate) > 50 or LOCATION_NOISE_PATTERN.search(candidate):
        return ""

    fragments = [fragment.strip(" ,.-") for fragment in candidate.split(",") if fragment.strip(" ,.-")]
    if 1 <= len(fragments) <= 3 and all(_looks_like_location(fragment) for fragment in fragments):
        return ", ".join(fragments)

    return ""


def _normalize_email_match(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip().strip(".,;:")


def extract_email(text: str) -> str:
    if not text:
        return ""

    match = EMAIL_PATTERN.search(text)
    if match:
        return _normalize_email_match(match.group(0))

    compact_text = text.replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
    compact_text = compact_text.replace("(dot)", ".").replace("[dot]", ".").replace(" dot ", ".")
    match = EMAIL_PATTERN.search(compact_text)
    if match:
        return _normalize_email_match(match.group(0))

    return ""


def _extract_experience_headline_fields(headline: str) -> Dict[str, str]:
    title = ""
    company = ""
    normalized_headline = headline.strip(" ,|-")

    if " at " in normalized_headline.lower():
        parts = re.split(r"\bat\b", normalized_headline, maxsplit=1, flags=re.IGNORECASE)
        title = parts[0].strip(" ,|-")
        company = parts[1].strip(" ,|-")
    else:
        parts = [part.strip(" ,|-") for part in EXPERIENCE_HEADLINE_SPLIT_PATTERN.split(normalized_headline) if part.strip(" ,|-")]
        if len(parts) >= 2:
            title, company = parts[0], parts[1]
        else:
            title = normalized_headline

    return {"title": title[:120], "company": company[:160]}


def _parse_date_token(token: str) -> tuple[int, int] | None:
    if not token:
        return None

    token = token.strip().lower().replace(".", "")
    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12,
    }

    if token in {"present", "current", "now", "till date", "till now"}:
        now = datetime.utcnow()
        return (now.year, now.month)

    match = re.match(
        rf"(?:(?P<month>{MONTH_TOKEN})\s+)?(?P<year>\d{{4}})",
        token,
        re.IGNORECASE,
    )
    if not match:
        return None

    month_token = (match.group("month") or "").lower()
    year_token = int(match.group("year"))
    if year_token < 1980 or year_token > datetime.utcnow().year + 1:
        return None
    return (year_token, month_map.get(month_token, 1) if month_token else 1)


def estimate_total_experience_years(entries: List[Dict]) -> float | None:
    intervals: List[tuple[tuple[int, int], tuple[int, int]]] = []
    for entry in entries:
        start = _parse_date_token(entry.get("start_date", ""))
        end = _parse_date_token(entry.get("end_date", ""))
        if not start or not end or end < start:
            continue
        intervals.append((start, end))

    if not intervals:
        return None

    intervals.sort(key=lambda item: item[0])
    merged: List[List[tuple[int, int]]] = [[intervals[0][0], intervals[0][1]]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1][1] = end
        else:
            merged.append([start, end])

    total_months = 0
    for start, end in merged:
        total_months += max(0, (end[0] - start[0]) * 12 + (end[1] - start[1]))
    return round(total_months / 12.0, 1)


def derive_experience_level(experience_years: float | None) -> str:
    if experience_years is None:
        return ""
    if experience_years <= 2:
        return "Junior"
    if experience_years <= 5:
        return "Mid-level"
    if experience_years <= 10:
        return "Senior"
    return "Lead/Expert"


def extract_languages(text: str, languages_section: str = "") -> List[str]:
    if not text and not languages_section:
        return []

    matches: List[str] = []
    section_source = languages_section or ""
    if section_source:
        for chunk in re.split(r"[\n,;|/]", section_source):
            normalized = chunk.strip().lower()
            if normalized in LANGUAGE_TERMS:
                matches.append(normalized.title())

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:30]:
        header_match = LANGUAGE_LINE_PATTERN.match(line)
        if header_match:
            for chunk in re.split(r"[,;|/]", header_match.group("value")):
                normalized = chunk.strip().lower()
                if normalized in LANGUAGE_TERMS:
                    matches.append(normalized.title())

    lowered_text = text.lower()
    for language in LANGUAGE_TERMS:
        if re.search(rf"\b{re.escape(language)}\b", lowered_text):
            matches.append(language.title())

    return _unique_in_order(matches)[:10]


def infer_responsibility_skills(text: str) -> List[str]:
    lowered_text = text.lower()
    matches: List[str] = []
    for skill, phrases in RESPONSIBILITY_SKILL_PHRASES.items():
        if any(phrase in lowered_text for phrase in phrases):
            matches.append(skill)
    return _unique_in_order(matches)


def extract_experience_entries(text: str, experience_section: str = "") -> List[Dict]:
    """Extract structured work-experience entries with robust date parsing."""
    section_text = experience_section or segment_resume_sections(text).get("experience", "")
    if not section_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        fallback_blocks: List[str] = []
        current_block: List[str] = []
        for line in lines:
            if _find_date_match(line):
                if current_block:
                    fallback_blocks.append("\n".join(current_block))
                    current_block = []
                current_block.append(line)
                continue
            if current_block:
                if len(current_block) < 6:
                    current_block.append(line)
                else:
                    fallback_blocks.append("\n".join(current_block))
                    current_block = []
        if current_block:
            fallback_blocks.append("\n".join(current_block))
        section_text = "\n\n".join(fallback_blocks[:10])
        if not section_text:
            return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", section_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in section_text.splitlines() if line.strip()]

    entries: List[Dict] = []
    for block in blocks[:15]:
        lines = [line.strip(" -\t") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        headline = lines[0]
        date_match = _find_date_match(block)
        years = sorted(set(match.group(0) for match in YEAR_PATTERN.finditer(block)))
        if not date_match and not years:
            continue

        headline_fields = _extract_experience_headline_fields(headline)
        title = headline_fields["title"]
        company = headline_fields["company"]

        if not company and SPACY_AVAILABLE and nlp is not None:
            doc = nlp(headline)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                company = org_entities[0]

        description_lines = [line for line in lines[1:] if not _find_date_match(line)]
        entries.append(
            {
                "title": title[:120],
                "company": company[:160],
                "start_date": date_match.group("start").strip() if date_match else (years[0] if years else ""),
                "end_date": date_match.group("end").strip() if date_match else (years[-1] if len(years) > 1 else ""),
                "description": " ".join(description_lines)[:600],
                "raw_text": block[:800],
            }
        )

    entries.sort(key=lambda entry: _parse_date_token(entry.get("end_date", "")) or (0, 0), reverse=True)
    deduped: List[Dict] = []
    seen = set()
    for entry in entries:
        key = (
            normalize_skill_name(entry.get("title", "")),
            normalize_skill_name(entry.get("company", "")),
            entry.get("start_date", ""),
            entry.get("end_date", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def extract_project_entries(text: str, projects_section: str = "") -> List[Dict[str, Any]]:
    """Extract project title, description, and referenced technologies."""
    section_text = projects_section or segment_resume_sections(text).get("projects", "")
    if not section_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        capture = False
        collected: List[str] = []
        for line in lines:
            lower_line = line.lower().rstrip(":")
            if lower_line in PROJECT_SECTION_KEYWORDS:
                capture = True
                continue
            if capture and re.match(r"^(experience|education|skills|certifications|languages)\b", lower_line):
                break
            if capture:
                collected.append(line)
        section_text = "\n".join(collected).strip()
        if not section_text:
            return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", section_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in section_text.splitlines() if line.strip()]

    projects: List[Dict[str, Any]] = []
    for block in blocks[:8]:
        lines = [line.strip(" -*\t") for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        projects.append(
            {
                "title": lines[0][:120],
                "description": " ".join(lines[1:])[:500] if len(lines) > 1 else block[:500],
                "technologies": extract_skill_keywords(block)[:10],
            }
        )
    return projects


def extract_education_entries(text: str, education_section: str = "") -> List[Dict]:
    """Extract degree, institution, and graduation year using section-first fallback logic."""
    section_text = education_section or segment_resume_sections(text).get("education", "")
    if not section_text:
        fallback_lines = [
            line.strip()
            for line in text.splitlines()
            if re.search(r"(b\.?\s?tech|m\.?\s?tech|bca|mca|bsc|msc|mba|bachelor|master|diploma|ph\.?\s?d)", line, re.IGNORECASE)
        ]
        section_text = "\n".join(fallback_lines)
        if not section_text:
            return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", section_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in section_text.splitlines() if line.strip()]

    entries: List[Dict] = []
    for block in blocks[:8]:
        lines = [line.strip(" -\t") for line in block.splitlines() if line.strip()]
        combined = " ".join(lines)

        degree = ""
        for pattern in DEGREE_PATTERNS:
            match = re.search(pattern, combined, re.IGNORECASE)
            if match:
                degree = match.group(0).strip()
                break

        institution = ""
        for line in lines:
            if any(hint in line.lower() for hint in INSTITUTE_HINTS):
                institution = line
                break

        if not institution and SPACY_AVAILABLE and nlp is not None:
            doc = nlp(combined)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                institution = org_entities[0]

        years = sorted(set(match.group(0) for match in YEAR_PATTERN.finditer(combined)))
        entries.append(
            {
                "degree": degree[:120],
                "institution": institution[:160],
                "year": years[-1] if years else "",
                "raw_text": block[:500],
            }
        )
    return entries


def extract_location(text: str) -> str:
    """Extract location using explicit location lines, city/state patterns, and spaCy NER."""
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:30]:
        explicit_match = LOCATION_LINE_PATTERN.search(line)
        if explicit_match:
            candidate = _normalize_location_candidate(explicit_match.group("value"))
            if candidate:
                return candidate

    for line in lines[:20]:
        if not any(hint in line.lower() for hint in LOCATION_HINTS):
            continue
        candidate = _normalize_location_candidate(line)
        if candidate:
            return candidate

    if SPACY_AVAILABLE and nlp is not None:
        for line in lines[:20]:
            if len(line) > 60 or LOCATION_NOISE_PATTERN.search(line):
                continue
            doc = nlp(line[:200])
            location_entities = []
            for ent in doc.ents:
                if ent.label_ in {"GPE", "LOC"}:
                    candidate = _normalize_location_candidate(ent.text)
                    if candidate:
                        location_entities.append(candidate)
            if location_entities:
                return ", ".join(_unique_in_order(location_entities[:2]))
    return ""


def extract_resume_information(text: str) -> Dict:
    """
    Core ATS information extraction layer.

    This keeps the existing module structure but improves extraction quality for:
    skills, experience, projects, education, location, current company, and
    derived experience level.
    """
    sections = segment_resume_sections(text)
    explicit_skills = extract_skill_keywords(text, sections.get("skills", ""))
    inferred_skills = infer_responsibility_skills(
        "\n".join(
            section for section in [
                sections.get("skills", ""),
                sections.get("experience", ""),
                sections.get("projects", ""),
            ] if section
        ) or text
    )
    skills = _unique_in_order(explicit_skills + inferred_skills)
    experience_entries = extract_experience_entries(text, sections.get("experience", ""))
    project_entries = extract_project_entries(text, sections.get("projects", ""))
    education_entries = extract_education_entries(text, sections.get("education", ""))
    languages = extract_languages(text, sections.get("languages", ""))
    total_experience_years = estimate_total_experience_years(experience_entries)
    current_company = experience_entries[0].get("company") if experience_entries else None
    designation = experience_entries[0].get("title") if experience_entries else None

    return {
        "sections": sections,
        "skills": skills,
        "experience": experience_entries,
        "projects": project_entries,
        "education": education_entries,
        "location": extract_location(text),
        "current_company": current_company,
        "designation": designation,
        "experience_years": total_experience_years,
        "total_experience_years": total_experience_years,
        "experience_level": derive_experience_level(total_experience_years),
        "languages": languages,
        "experience_text": clean_text_pipeline(sections.get("experience", "")),
        "education_text": clean_text_pipeline(sections.get("education", "")),
        "projects_text": clean_text_pipeline(sections.get("projects", "")),
    }
