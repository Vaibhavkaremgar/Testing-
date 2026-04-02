from __future__ import annotations

import re
from typing import Dict, List

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
    """Extract normalized skills using Flashtext over both section and full text."""
    matches: List[str] = []
    intelligence_matches: List[str] = []

    for source in (section_text, text):
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

    combined = [normalize_skill_name(skill) for skill in matches]
    combined.extend(_skill_intelligence.map_skills(intelligence_matches))
    return _unique_in_order(combined)[:40]


def extract_experience_entries(text: str, experience_section: str = "") -> List[Dict]:
    """Extract structured work-experience entries from the segmented experience section."""
    section_text = experience_section or segment_resume_sections(text).get("experience", "")
    if not section_text:
        return []

    blocks = [block.strip() for block in re.split(r"\n\s*\n", section_text) if block.strip()]
    if not blocks:
        blocks = [line.strip() for line in section_text.splitlines() if line.strip()]

    entries: List[Dict] = []
    for block in blocks[:12]:
        lines = [line.strip(" -\t") for line in block.splitlines() if line.strip()]
        headline = lines[0] if lines else block
        date_match = DATE_RANGE_PATTERN.search(block)
        years = sorted(set(match.group(0) for match in YEAR_PATTERN.finditer(block)))

        title = ""
        company = ""
        if " at " in headline.lower():
            parts = re.split(r"\bat\b", headline, maxsplit=1, flags=re.IGNORECASE)
            title = parts[0].strip(" ,|-")
            company = parts[1].strip(" ,|-")
        else:
            title = headline.strip(" ,|-")
            if SPACY_AVAILABLE and nlp is not None:
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
    """Extract a likely candidate location from resume text."""
    if not text:
        return ""

    if SPACY_AVAILABLE and nlp is not None:
        doc = nlp(text[:3000])
        for ent in doc.ents:
            if ent.label_ in {"GPE", "LOC"}:
                candidate = ent.text.strip()
                if candidate and len(candidate) <= 80:
                    return candidate

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:20]:
        normalized = line.lower()
        if any(hint in normalized for hint in LOCATION_HINTS):
            return line[:80]

    return ""


def extract_resume_information(text: str) -> Dict:
    """
    Core ATS information extraction layer powered by:
    - spaCy for entity-aware parsing
    - Flashtext for fast skill lookup
    """
    sections = segment_resume_sections(text)
    skills = extract_skill_keywords(text, sections.get("skills", ""))
    experience_entries = extract_experience_entries(text, sections.get("experience", ""))
    education_entries = extract_education_entries(text, sections.get("education", ""))

    return {
        "sections": sections,
        "skills": skills,
        "experience": experience_entries,
        "education": education_entries,
        "location": extract_location(text),
        "experience_text": clean_text_pipeline(sections.get("experience", "")),
        "education_text": clean_text_pipeline(sections.get("education", "")),
        "projects_text": clean_text_pipeline(sections.get("projects", "")),
    }
