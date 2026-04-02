from __future__ import annotations

import re
from typing import Dict, List
from datetime import datetime

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
}

SKILL_KEYWORDS = [
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

DEGREE_PATTERNS = [
    r"\bB\.?\s?Tech\b",
    r"\bM\.?\s?Tech\b",
    r"\bB\.?\s?E\b",
    r"\bM\.?\s?E\b",
    r"\bBCA\b",
    r"\bMCA\b",
    r"\bBSc\b",
    r"\bMSc\b",
    r"\bBachelor(?:'s)?(?:\s+of|\s+in)?\b",
    r"\bMaster(?:'s)?(?:\s+of|\s+in)?\b",
    r"\bDiploma\b",
    r"\bPh\.?\s?D\b",
]

DATE_RANGE_PATTERN = re.compile(
    r"(?P<start>(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)?\.?\s*\d{4}|\d{4})"
    r"\s*(?:-|to|–|—)\s*"
    r"(?P<end>(?:present|current|now|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)?\.?\s*\d{4}|\d{4}))",
    re.IGNORECASE,
)
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
INSTITUTE_HINTS = ("university", "college", "institute", "school", "academy")
LOCATION_HINTS = ("india", "bangalore", "bengaluru", "hyderabad", "chennai", "mumbai", "pune", "delhi", "noida", "gurgaon")
EXPERIENCE_HEADLINE_SPLIT_PATTERN = re.compile(r"\s+[|\-–—]\s+")
WHITESPACE_PATTERN = re.compile(r"\s+")
LOCATION_LINE_PATTERN = re.compile(
    r"(?i)\b(?:location|based in|address|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,.-]{1,80})$"
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
NON_LOCATION_PATTERN = re.compile(r"[@:/\\]|(?:\b(?:java|python|html|css|sql|fastapi|react|angular|git)\b)", re.IGNORECASE)
LANGUAGE_TERMS = [
    "english", "hindi", "telugu", "tamil", "kannada", "malayalam", "marathi",
    "gujarati", "punjabi", "bengali", "urdu", "french", "german", "spanish",
    "arabic", "japanese", "mandarin", "chinese",
]
LANGUAGE_LINE_PATTERN = re.compile(r"(?i)^\s*languages?\s*[:\-]?\s*(?P<value>.+)$")
SOFT_SKILL_PHRASES = {
    "communication": ["communication", "communicate", "client interaction", "stakeholder communication"],
    "teamwork": ["team player", "worked with teams", "collaborated", "cross-functional", "team collaboration"],
    "leadership": ["led", "leadership", "managed team", "mentored", "supervised", "ownership"],
    "problem solving": ["problem solving", "resolved issues", "debugged", "troubleshooting", "root cause analysis"],
    "time management": ["time management", "met deadlines", "prioritized tasks"],
    "adaptability": ["adapt", "adaptability", "flexible", "fast-paced"],
}
RESPONSIBILITY_SKILL_PHRASES = {
    "cold calling": ["cold calling"],
    "lead generation": ["lead generation", "generated leads"],
    "sales": ["sales", "sales target", "revenue growth"],
    "negotiation": ["negotiation", "negotiated"],
    "crm": ["crm", "salesforce", "hubspot", "zoho crm"],
    "customer relationship management": ["customer relationship", "client relationship", "account management"],
    "presentation": ["presentation", "presented", "demoed"],
    "rest api": ["rest api", "restful api", "api development"],
    "sql": ["sql", "mysql", "postgresql", "database queries"],
    "fastapi": ["fastapi"],
    "python": ["python"],
    "java": ["java"],
    "html": ["html"],
    "css": ["css"],
}

_skill_keyword_processor = KeywordProcessor(case_sensitive=False)
for canonical_skill in SKILL_KEYWORDS:
    _skill_keyword_processor.add_keyword(canonical_skill, canonical_skill)
for alias, canonical_skill in SKILL_ALIASES.items():
    _skill_keyword_processor.add_keyword(alias, canonical_skill)

_skill_intelligence = SkillIntelligence()


def normalize_skill_name(skill: str) -> str:
    normalized = skill.strip().lower()
    normalized = SKILL_ALIASES.get(normalized, normalized)
    return normalized


def _unique_in_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def extract_skill_keywords(text: str, section_text: str = "") -> List[str]:
    """Extract normalized skills using conservative matching to avoid generic false positives."""
    matches: List[str] = []
    intelligence_matches: List[str] = []

    if section_text:
        matches.extend(_skill_keyword_processor.extract_keywords(section_text))
        intelligence_matches.extend(_skill_intelligence.extract_skills(section_text))
    elif text:
        # Fallback to direct technical keyword matching only on full text.
        matches.extend(_skill_keyword_processor.extract_keywords(text))

    if section_text:
        for chunk in re.split(r"[\n,;|/]", section_text):
            chunk = chunk.strip(" -*:\t")
            if not chunk:
                continue
            normalized = normalize_skill_name(chunk)
            if normalized in SKILL_KEYWORDS:
                matches.append(normalized)

    combined = [normalize_skill_name(skill) for skill in matches]
    combined.extend(_skill_intelligence.map_skills(intelligence_matches))
    filtered = [skill for skill in _unique_in_order(combined) if skill in SKILL_KEYWORDS]
    return filtered[:40]


def _looks_like_location(value: str) -> bool:
    cleaned = WHITESPACE_PATTERN.sub(" ", value.strip(" ,.-")) if value else ""
    if not cleaned or len(cleaned) > 80:
        return False
    if NON_LOCATION_PATTERN.search(cleaned):
        return False
    if any(char.isdigit() for char in cleaned):
        return False
    words = cleaned.split()
    if len(words) > 5:
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z\s,.-]*", cleaned))


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

    return {"title": title[:120], "company": company[:120]}


def _parse_date_token(token: str) -> tuple[int, int] | None:
    if not token:
        return None

    token = token.strip().lower()
    month_map = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    if token in {"present", "current", "now"}:
        now = datetime.utcnow()
        return (now.year, now.month)

    match = re.match(
        r"(?:(jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+)?(\d{4})",
        token,
    )
    if not match:
        return None

    month_token, year_token = match.groups()
    return (int(year_token), month_map.get(month_token, 1) if month_token else 1)


def estimate_total_experience_years(entries: List[Dict]) -> float | None:
    intervals: List[tuple[tuple[int, int], tuple[int, int]]] = []
    for entry in entries:
        start = _parse_date_token(entry.get("start_date", ""))
        end = _parse_date_token(entry.get("end_date", ""))
        if not start or not end:
            continue
        if end < start:
            continue
        intervals.append((start, end))

    if not intervals:
        return None

    intervals.sort(key=lambda item: item[0])
    merged: List[list[tuple[int, int]]] = [[intervals[0][0], intervals[0][1]]]
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

    for skill, phrases in SOFT_SKILL_PHRASES.items():
        if any(phrase in lowered_text for phrase in phrases):
            matches.append(skill)

    return _unique_in_order(matches)


def extract_experience_entries(text: str, experience_section: str = "") -> List[Dict]:
    """Extract structured work-experience entries from the segmented experience section."""
    section_text = experience_section or segment_resume_sections(text).get("experience", "")
    if not section_text:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        fallback_blocks: List[str] = []
        current_block: List[str] = []
        for line in lines:
            if DATE_RANGE_PATTERN.search(line):
                if current_block:
                    fallback_blocks.append("\n".join(current_block))
                    current_block = []
                current_block.append(line)
                continue
            if current_block:
                if len(current_block) < 5:
                    current_block.append(line)
                else:
                    fallback_blocks.append("\n".join(current_block))
                    current_block = []
        if current_block:
            fallback_blocks.append("\n".join(current_block))
        if not fallback_blocks:
            return []
        section_text = "\n\n".join(fallback_blocks[:8])

    blocks = [block.strip() for block in re.split(r"\n\s*\n", section_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in section_text.splitlines() if line.strip()]

    entries: List[Dict] = []
    for block in blocks[:12]:
        lines = [line.strip(" -\t") for line in block.splitlines() if line.strip()]
        headline = lines[0] if lines else block
        date_match = DATE_RANGE_PATTERN.search(block)
        years = sorted(set(match.group(0) for match in YEAR_PATTERN.finditer(block)))

        headline_fields = _extract_experience_headline_fields(headline)
        title = headline_fields["title"]
        company = headline_fields["company"]
        if not company and SPACY_AVAILABLE and nlp is not None:
            doc = nlp(headline)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                company = org_entities[0]

        if date_match and company:
            company = company.replace(date_match.group(0), "").strip(" ,|-")

        description_lines = [line for line in lines[1:] if not DATE_RANGE_PATTERN.search(line)]
        entries.append(
            {
                "title": title[:120],
                "company": company[:120],
                "start_date": date_match.group("start").strip() if date_match else (years[0] if years else ""),
                "end_date": date_match.group("end").strip() if date_match else (years[-1] if len(years) > 1 else ""),
                "description": " ".join(description_lines)[:500],
                "raw_text": block[:700],
            }
        )

    return entries


def extract_education_entries(text: str, education_section: str = "") -> List[Dict]:
    """Extract degree, institution, and year from the segmented education section."""
    section_text = education_section or segment_resume_sections(text).get("education", "")
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
        preferred_institution = ""
        for line in lines:
            line_lower = line.lower()
            if any(hint in line_lower for hint in INSTITUTE_HINTS):
                preferred_institution = line
                break

        if SPACY_AVAILABLE and nlp is not None:
            doc = nlp(combined)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                institution = org_entities[0]

        if preferred_institution:
            institution = preferred_institution

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
    """Extract a likely candidate location from explicit location clues only."""
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:30]:
        explicit_match = LOCATION_LINE_PATTERN.search(line)
        if explicit_match:
            candidate = explicit_match.group("value").strip(" ,.-")
            if _looks_like_location(candidate):
                return candidate

    for line in lines[:20]:
        normalized = line.lower()
        if any(hint in normalized for hint in LOCATION_HINTS) and _looks_like_location(line):
            return line[:80].strip(" ,.-")

    if SPACY_AVAILABLE and nlp is not None:
        doc = nlp(text[:3000])
        for ent in doc.ents:
            if ent.label_ in {"GPE", "LOC"}:
                candidate = ent.text.strip()
                if _looks_like_location(candidate):
                    return candidate

    return ""


def extract_resume_information(text: str) -> Dict:
    """
    Core ATS information extraction layer powered by:
    - spaCy for entity-aware parsing
    - Flashtext for fast skill lookup
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
    education_entries = extract_education_entries(text, sections.get("education", ""))
    languages = extract_languages(text, sections.get("languages", ""))
    experience_years = estimate_total_experience_years(experience_entries)
    current_company = experience_entries[0].get("company") if experience_entries else None
    designation = experience_entries[0].get("title") if experience_entries else None

    return {
        "sections": sections,
        "skills": skills,
        "experience": experience_entries,
        "education": education_entries,
        "location": extract_location(text),
        "current_company": current_company,
        "designation": designation,
        "experience_years": experience_years,
        "languages": languages,
        "experience_text": clean_text_pipeline(sections.get("experience", "")),
        "education_text": clean_text_pipeline(sections.get("education", "")),
        "projects_text": clean_text_pipeline(sections.get("projects", "")),
    }
