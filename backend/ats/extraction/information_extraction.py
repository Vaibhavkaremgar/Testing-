from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from flashtext import KeywordProcessor

from ats.extraction.experience_extraction import extract_total_experience
from ats.extraction.skill_intelligence import LANGUAGE_TERMS, NOISE_ALIASES, NOISE_TERMS, SkillIntelligence
from ats.extraction.validation import validate_parsed_fields
from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import clean_text_pipeline
from app.spacy_nlp import SPACY_AVAILABLE, get_section_doc

SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "node": "nodejs",
    "node.js": "nodejs",
    "react.js": "react",
    "reactjs": "react",
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "aws": "aws",
    "docker-compose": "docker",
}

SKILL_TOKEN_SPLIT_PATTERN = re.compile(r"[\n,;|/]+")
DEGREE_PATTERNS = [
    r"\bB\.?\s?Tech\b",
    r"\bM\.?\s?Tech\b",
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
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
INSTITUTE_HINTS = ("university", "college", "institute", "school", "academy")
LOCATION_PATTERN = re.compile(
    r"(?i)\b(?:location|based in|address|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,.-]{1,80})$"
)
LOCATION_CANDIDATE_PATTERN = re.compile(
    r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*(?:,\s*[A-Za-z]+(?:[\s-][A-Za-z]+)*){0,2}$"
)
LOCATION_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|analyst|director|lead|summary|profile|experience|skills|education|projects|languages|email|phone|resume)\b"
)
LANGUAGE_LINE_PATTERN = re.compile(r"(?i)^\s*languages?\s*[:\-]?\s*(?P<value>.+)$")
LANGUAGE_TERMS = [
    "english", "hindi", "telugu", "tamil", "kannada", "malayalam", "marathi",
    "gujarati", "punjabi", "bengali", "urdu", "french", "german", "spanish",
    "arabic", "japanese", "mandarin", "chinese",
]
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")

_skill_intelligence = SkillIntelligence()
_skill_keyword_processor = KeywordProcessor(case_sensitive=False)


def _is_valid_skill_candidate(skill: str) -> bool:
    normalized = (skill or "").strip().lower()
    return bool(normalized and normalized not in LANGUAGE_TERMS and normalized not in NOISE_TERMS and normalized not in NOISE_ALIASES)


for skill in _skill_intelligence.get_skill_dictionary():
    if _is_valid_skill_candidate(skill):
        _skill_keyword_processor.add_keyword(skill, skill)
for synonym, canonical in _skill_intelligence.get_synonym_dictionary().items():
    if _is_valid_skill_candidate(synonym) and _is_valid_skill_candidate(canonical):
        _skill_keyword_processor.add_keyword(synonym, canonical)
for alias, canonical in SKILL_ALIASES.items():
    if _is_valid_skill_candidate(alias) and _is_valid_skill_candidate(canonical):
        _skill_keyword_processor.add_keyword(alias, canonical)


def normalize_skill_name(skill: str) -> str:
    normalized = clean_text_pipeline(skill or "").lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not _is_valid_skill_candidate(normalized):
        return ""
    return SKILL_ALIASES.get(normalized, normalized)


def _unique_in_order(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        normalized = normalize_skill_name(value)
        if not normalized or len(normalized) < 2 or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def extract_skill_keywords(text: str, section_text: str = "") -> List[str]:
    source = section_text or text
    if not source:
        return []

    normalized_section = source.replace("•", ",").replace("▪", ",").replace("|", ",")
    raw_chunks = [chunk.strip(" -*:\t") for chunk in SKILL_TOKEN_SPLIT_PATTERN.split(normalized_section) if chunk.strip(" -*:\t")]
    matches: List[str] = []

    for chunk in raw_chunks:
        if len(chunk) < 2:
            continue
        matches.extend(_skill_keyword_processor.extract_keywords(chunk))

    if not matches and SPACY_AVAILABLE:
        doc = get_section_doc(normalized_section)
        if doc is not None:
            for chunk in doc.noun_chunks:
                candidate = normalize_skill_name(chunk.text)
                if len(candidate.split()) > 4:
                    continue
                if candidate in _skill_intelligence.get_synonym_dictionary():
                    matches.append(_skill_intelligence.get_synonym_dictionary()[candidate])
                elif candidate in _skill_intelligence.get_skill_dictionary():
                    matches.append(candidate)

    matches.extend(_skill_intelligence.extract_skills(normalized_section))
    normalized_matches = _skill_intelligence.map_skills(matches)
    return _unique_in_order(normalized_matches)[:50]


def extract_email(text: str) -> str:
    if not text:
        return ""
    match = EMAIL_PATTERN.search(text)
    if match:
        return re.sub(r"\s+", "", match.group(0)).strip(".,;:")
    compact_text = text.replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
    compact_text = compact_text.replace("(dot)", ".").replace("[dot]", ".").replace(" dot ", ".")
    match = EMAIL_PATTERN.search(compact_text)
    if match:
        return re.sub(r"\s+", "", match.group(0)).strip(".,;:")
    return ""


def extract_experience_entries(text: str, experience_section: str = "") -> List[Dict]:
    source_text = experience_section or text
    result = extract_total_experience(source_text)
    return result.get("experiences", [])


def extract_project_entries(text: str, projects_section: str = "") -> List[Dict[str, Any]]:
    section_text = projects_section or segment_resume_sections(text).get("projects", "")
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
                "technologies": [],
            }
        )
    return projects


def extract_education_entries(text: str, education_section: str = "") -> List[Dict]:
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
        for line in lines:
            if any(hint in line.lower() for hint in INSTITUTE_HINTS):
                institution = line
                break
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
    if not text:
        return ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:30]:
        match = LOCATION_PATTERN.search(line)
        if match:
            return re.sub(r"\s+", " ", match.group("value").strip(" ,.-"))[:80]
    for line in lines[:5]:
        if "@" in line or any(char.isdigit() for char in line):
            continue
        compact = re.sub(r"\s+", " ", line).strip(" ,.-")
        if not compact or LOCATION_NOISE_PATTERN.search(compact):
            continue
        if len(compact.split()) > 4:
            continue
        if "," not in compact:
            continue
        if LOCATION_CANDIDATE_PATTERN.match(compact):
            return compact[:80]
    return ""


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
    for line in [line.strip() for line in text.splitlines() if line.strip()][:30]:
        header_match = LANGUAGE_LINE_PATTERN.match(line)
        if header_match:
            for chunk in re.split(r"[,;|/]", header_match.group("value")):
                normalized = chunk.strip().lower()
                if normalized in LANGUAGE_TERMS:
                    matches.append(normalized.title())
    return list(dict.fromkeys(matches))


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


def extract_resume_information(text: str) -> Dict:
    cleaned_text = clean_text_pipeline(text)
    sections = segment_resume_sections(cleaned_text)
    skills = extract_skill_keywords(sections.get("skills", ""), sections.get("skills", ""))
    experience_result = extract_total_experience(sections.get("experience", ""))
    experience_entries = experience_result.get("experiences", [])
    total_experience_years = experience_result.get("total_experience_years")

    current_entry = experience_entries[0] if experience_entries else {}
    result = {
        "sections": sections,
        "skills": skills,
        "experience": experience_entries,
        "projects": extract_project_entries(cleaned_text, sections.get("projects", "")),
        "education": extract_education_entries(cleaned_text, sections.get("education", "")),
        "location": extract_location("\n".join(part for part in [sections.get("header", ""), cleaned_text] if part)),
        "current_company": current_entry.get("company"),
        "current_role": current_entry.get("role"),
        "designation": current_entry.get("role"),
        "experience_years": total_experience_years,
        "total_experience_years": total_experience_years,
        "experience_level": derive_experience_level(total_experience_years),
        "languages": extract_languages(cleaned_text, sections.get("languages", "")),
        "experience_text": clean_text_pipeline(sections.get("experience", "")),
        "education_text": clean_text_pipeline(sections.get("education", "")),
        "projects_text": clean_text_pipeline(sections.get("projects", "")),
    }
    return validate_parsed_fields(result)
