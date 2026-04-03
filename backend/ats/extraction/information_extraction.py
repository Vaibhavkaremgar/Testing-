from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from flashtext import KeywordProcessor

from ats.datasets.parser_config_loader import ParserConfigLoader
from ats.extraction.experience_extraction import extract_total_experience
from ats.extraction.skill_intelligence import LANGUAGE_TERMS, NOISE_ALIASES, NOISE_TERMS, SkillIntelligence
from ats.extraction.validation import validate_parsed_fields
from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import (
    clean_text_pipeline,
    merge_broken_lines,
    normalize_common_artifacts,
    normalize_document_structure,
    normalize_text,
    repair_date_ranges,
    split_inline_section_headers,
)
from app.spacy_nlp import SPACY_AVAILABLE, get_section_doc
from ats.extraction.experience_extraction import DATE_RANGE_REGEX

def extract_name(text: str) -> str:
    if not text:
        return ""

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    # 1. Try spaCy
    if SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(lines[:10]))
        if doc:
            for ent in doc.ents:
                if ent.label_ == "PERSON" and 1 < len(ent.text.split()) <= 4:
                    return ent.text

    # 2. Fallback
    for line in lines[:5]:
        if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3}$", line):
            return line

    return ""

SKILL_ALIASES = {
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "b2g": "b2g sales",
    "node": "nodejs",
    "node.js": "nodejs",
    "react.js": "react",
    "reactjs": "react",
    "django": "django",
    "flask": "flask",
    "fastapi": "fastapi",
    "aws": "aws",
    "docker-compose": "docker",
    "pipeline mgmt": "pipeline management",
    "territory mgmt": "territory management",
    "account mgmt": "account management",
    "cross sell": "cross-selling",
    "closing deals": "deal closing",
    "product demo": "product demos",
    "product demonstrations": "product demos",
    "zoho": "zoho crm",
    "sap extended wareho use management": "sap extended warehouse management",
    "sap extended warehouse management module": "sap extended warehouse management",
    "extended warehouse management": "sap extended warehouse management",
    "extended warehouse management module": "sap extended warehouse management",
    "sap ewm consultant": "sap ewm",
    "sap ewm con su ltant": "sap ewm",
    "sap ecc integrations with extended warehouse management module": "sap ecc",
    "logistics execution system": "logistics execution",
}

SKILL_TOKEN_SPLIT_PATTERN = re.compile(r"[\n,;|]+")
SKILL_SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?]\s+")
SKILL_YEAR_RANGE_PATTERN = re.compile(r"^\s*(?:19|20)\d{2}\s*[-/to]+\s*(?:19|20)\d{2}\s*$", re.IGNORECASE)
SKILL_YEAR_ONLY_PATTERN = re.compile(r"^\s*(?:19|20)\d{2}\s*$")
SKILL_COMMUNICATION_PATTERN = re.compile(r"(?i)^\s*communication\s*[:\-]")
SKILL_ROLE_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:senior|sr|junior|jr|lead)\s+(?:sales|business development|account)\s+"
    r"(?:executive|manager|associate|representative)\b|"
    r"\b(?:sales|business development|account)\s+(?:executive|manager|associate|representative)\b"
)
SKILL_COMPANY_LIKE_PATTERN = re.compile(
    r"(?i)\b(?:services|solutions|technologies|systems|enterprises|marketing|corporation|corp|ltd|pvt)\b"
)
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
LOCATION_PATTERN = re.compile(
    r"(?i)\b(?:location|based in|address|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,.-]{1,80})$"
)
HEADER_LOCATION_PATTERN = re.compile(
    r"^(?P<value>[A-Za-z][A-Za-z\s.-]{1,40},\s*[A-Za-z][A-Za-z\s.-]{1,40})(?:\s+(?:\+?\d|[A-Za-z0-9._%+-]+@|linkedin|github).*)?$",
    re.IGNORECASE,
)
PIPE_HEADER_LOCATION_PATTERN = re.compile(
    r"(?i)(?:^|\|)\s*(?P<value>[A-Za-z][A-Za-z\s.-]{1,40}(?:,\s*[A-Za-z][A-Za-z\s.-]{1,40})?)\s*(?=\||$)"
)
LOCATION_CANDIDATE_PATTERN = re.compile(
    r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*(?:,\s*[A-Za-z]+(?:[\s-][A-Za-z]+)*){0,2}$"
)
_parser_config_loader = ParserConfigLoader()
_parser_vocabulary = _parser_config_loader.load_parser_vocabulary()
INSTITUTE_HINTS = tuple(
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("institution_hint_terms") or ["university", "college", "institute", "school", "academy"])
    if str(value).strip()
)
_degree_terms = [
    str(value).strip()
    for value in (_parser_vocabulary.get("education_degree_terms") or [])
    if str(value).strip()
]
if _degree_terms:
    DEGREE_PATTERNS = []
    for term in _degree_terms:
        escaped_term = re.escape(term).replace(r"\.", r"\.?")
        DEGREE_PATTERNS.append(rf"\b{escaped_term}\b")
LOCATION_NOISE_PATTERN = re.compile(
    rf"(?i)\b(?:{'|'.join(re.escape(str(value).strip().lower()) for value in (_parser_vocabulary.get('location_noise_terms') or []) if str(value).strip())})\b"
)
LANGUAGE_LINE_PATTERN = re.compile(r"(?i)^\s*languages?\s*[:\-]?\s*(?P<value>.+)$")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
SKILL_LABEL_TERMS = {
    "and tools",
    "tools",
    "languages",
    "frameworks",
    "databases",
    "devops",
    "messaging",
    "testing",
}
SKILL_CHUNK_NOISE_TERMS = {
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("skill_chunk_noise_terms") or [])
    if str(value).strip()
}
SKILL_CHUNK_LEADIN_PATTERN = re.compile(
    r"(?i)^(?:technical skills?|core skills?|key skills?|primary skills?|professional skills?|skills?|"
    r"technical competencies|competencies|areas of expertise|expertise|technologies|technology stack|"
    r"tools(?: and technologies)?|frameworks|databases|platforms|languages)\s*[:\-]?\s*"
)
LOCATION_LEADING_DESCRIPTORS = {
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("location_leading_descriptors") or [])
    if str(value).strip()
}
CERTIFICATION_NOISE_TERMS = {
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("certification_noise_terms") or [])
    if str(value).strip()
}
CERTIFICATION_SPLIT_PATTERN = re.compile(r"[\n|,;]+")
CERTIFICATION_HINT_PATTERN = re.compile(
    r"(?i)\b(?:certified|certification|certificate|license|licence|aws certified|azure certified|google cloud certified|scrum master|pmp)\b"
)
NAME_LIKE_SKILL_PATTERN = re.compile(r"^[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}$")
ROLE_LIKE_SKILL_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|tester|analyst|consultant|manager|lead|architect|specialist)\b"
)
SOFT_SKILL_LINE_PATTERN = re.compile(r"(?i)^\s*(?:communication|analytical|problem-solving|critical thinking)\s*$")
ROLE_TITLE_LINE_PATTERN = re.compile(
    r"(?i)^(?:senior|sr\.?|junior|jr\.?|lead|principal|staff|associate|assistant)?\s*"
    r"(?:python\s+automation\s+test\s+)?"
    r"(?:software|qa|quality assurance|automation|test|backend|frontend|data|machine learning|network|devops)?\s*"
    r"(?:engineer|developer|tester|analyst|consultant|manager|intern)(?:\s+[A-Za-z]+){0,3}$"
)
SKILL_SECTION_BREAK_PATTERN = re.compile(
    r"(?i)^(?:profile(?: summary)?|professional summary|summary|work experience|experience|employment|"
    r"projects?|education|certifications?|achievements?|awards?|languages?|references?|internship|job objective|objective)$"
)
SOFT_SKILLS_HEADER_PATTERN = re.compile(r"(?i)^soft skills?$")
PERSON_NAME_BLOCKLIST = {
    "management", "planning", "development", "assessment", "communication", "pedagogy",
    "teaching", "analysis", "analytics", "framework", "testing", "learning", "vision",
    "engineering", "science", "automation", "protocols", "tools", "skills",
}


def _language_label_lines(*sections: str) -> str:
    extracted_lines: List[str] = []
    for section in sections:
        for line in (section or "").splitlines():
            stripped = line.strip()
            header_match = LANGUAGE_LINE_PATTERN.match(stripped)
            if not header_match:
                continue
            value = header_match.group("value")
            if any(re.search(rf"\b{re.escape(language)}\b", value, re.IGNORECASE) for language in LANGUAGE_TERMS):
                extracted_lines.append(stripped)
    return "\n".join(extracted_lines)


def _sanitize_skill_section(section_text: str) -> str:
    if not section_text:
        return ""

    sanitized_lines: List[str] = []
    lines = [line.strip() for line in (section_text or "").splitlines()]
    previous_kept = ""
    for raw_line in lines:
        line = raw_line.strip(" -*\t")
        if not line:
            continue
        if SKILL_SECTION_BREAK_PATTERN.match(line):
            break
        if SOFT_SKILLS_HEADER_PATTERN.match(line):
            break
        if _looks_like_person_name_line(line):
            continue
        if ROLE_TITLE_LINE_PATTERN.match(line):
            continue
        if SOFT_SKILL_LINE_PATTERN.match(line):
            continue
        if previous_kept and _looks_like_person_name_line(previous_kept) and ROLE_TITLE_LINE_PATTERN.match(line):
            if sanitized_lines:
                sanitized_lines.pop()
            previous_kept = ""
            continue
        sanitized_lines.append(line)
        previous_kept = line
    return "\n".join(sanitized_lines)


def _looks_like_person_name_line(value: str) -> bool:
    compact = re.sub(r"\s+", " ", (value or "").strip())
    if not NAME_LIKE_SKILL_PATTERN.match(compact):
        return False
    lowered_tokens = [token.strip(".,").lower() for token in compact.split()]
    if any(token in PERSON_NAME_BLOCKLIST for token in lowered_tokens):
        return False
    return True

_skill_intelligence = SkillIntelligence()
_skill_keyword_processor = KeywordProcessor(case_sensitive=False)


def _is_valid_skill_candidate(skill: str) -> bool:
    normalized = (skill or "").strip().lower()
    return bool(normalized and normalized not in LANGUAGE_TERMS and normalized not in NOISE_TERMS and normalized not in NOISE_ALIASES)


def _looks_like_skill_chunk(chunk: str) -> bool:
    normalized = clean_text_pipeline(chunk or "").strip().lower()
    if not normalized:
        return False
    raw_compact = re.sub(r"\s+", " ", (chunk or "").strip())
    if _looks_like_person_name_line(raw_compact):
        return False
    if ROLE_LIKE_SKILL_PATTERN.search(raw_compact) and len(raw_compact.split()) >= 3:
        return False
    if SOFT_SKILL_LINE_PATTERN.match(raw_compact):
        return False
    normalized = SKILL_CHUNK_LEADIN_PATTERN.sub("", normalized).strip()
    if not normalized or normalized in SKILL_CHUNK_NOISE_TERMS:
        return False
    if DATE_RANGE_REGEX.search(normalized) or SKILL_YEAR_RANGE_PATTERN.match(normalized) or SKILL_YEAR_ONLY_PATTERN.match(normalized):
        return False
    if SKILL_COMMUNICATION_PATTERN.match(normalized):
        return False
    if SKILL_ROLE_NOISE_PATTERN.search(normalized):
        return False
    if SKILL_COMPANY_LIKE_PATTERN.search(normalized):
        return False

    tokens = normalized.split()
    if len(tokens) > 8:
        return False

    if re.search(r"\b(responsible for|worked on|involved in|experience with|project|team|client)\b", normalized):
        return False
    if re.search(r"\b(worked in|worked as|door to door|walk-in)\b", normalized):
        return False

    return True


def _fallback_skill_from_chunk(chunk: str) -> str:
    normalized = clean_text_pipeline(chunk or "").strip().lower()
    raw_compact = re.sub(r"\s+", " ", (chunk or "").strip())
    if _looks_like_person_name_line(raw_compact):
        return ""
    if ROLE_LIKE_SKILL_PATTERN.search(raw_compact) and len(raw_compact.split()) >= 3:
        return ""
    if SOFT_SKILL_LINE_PATTERN.match(raw_compact):
        return ""
    normalized = SKILL_CHUNK_LEADIN_PATTERN.sub("", normalized).strip()
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip(" -,:/")
    if not normalized:
        return ""
    if normalized in SKILL_CHUNK_NOISE_TERMS:
        return ""
    if DATE_RANGE_REGEX.search(normalized) or SKILL_YEAR_RANGE_PATTERN.match(normalized) or SKILL_YEAR_ONLY_PATTERN.match(normalized):
        return ""
    if SKILL_COMMUNICATION_PATTERN.match(normalized):
        return ""
    if SKILL_ROLE_NOISE_PATTERN.search(normalized):
        return ""
    if SKILL_COMPANY_LIKE_PATTERN.search(normalized):
        return ""
    if normalized in {"robot", "framework"}:
        return ""
    if re.search(r"\b(worked in|worked as|door to door|walk-in)\b", normalized):
        return ""
    normalized_tokens = normalized.split()
    canonical_skill = _skill_intelligence.get_synonym_dictionary().get(normalized, normalized)
    if len(normalized_tokens) > 2 and canonical_skill not in _skill_intelligence.get_skill_dictionary():
        return ""
    if len(normalized_tokens) > 4:
        return ""
    if re.search(r"\b(intermediate|advanced|beginner|native|fluent|professional)\b", normalized):
        normalized = re.sub(r"\b(intermediate|advanced|beginner|native|fluent|professional)\b", "", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip(" -,:/")
    return normalize_skill_name(normalized)


def _is_supported_extracted_skill(skill: str, chunk: str) -> bool:
    normalized_skill = normalize_skill_name(skill)
    normalized_chunk = clean_text_pipeline(chunk or "").strip().lower()
    aliased_chunk = SKILL_ALIASES.get(normalized_chunk, normalized_chunk)
    canonical_chunk = _skill_intelligence.get_synonym_dictionary().get(aliased_chunk, aliased_chunk)
    if not normalized_skill or not normalized_chunk:
        return False
    if _skill_intelligence._is_noise(normalized_skill):
        return False
    if re.search(r"\b[a-z]\b", normalized_skill) and normalized_skill not in {"c", "r"}:
        return False
    if normalized_skill == aliased_chunk:
        return True
    if normalized_skill == canonical_chunk:
        return True
    if normalized_skill == normalized_chunk:
        return True
    if re.search(rf"(?<!\w){re.escape(normalized_skill)}(?!\w)", normalized_chunk):
        return True
    return normalized_skill.replace(" ", "") in normalized_chunk.replace(" ", "")


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
    normalized = clean_text_pipeline(skill or "").lower().strip(" -,:;/()[]{}")
    normalized = SKILL_CHUNK_LEADIN_PATTERN.sub("", normalized).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if (
        not _is_valid_skill_candidate(normalized)
        or normalized in SKILL_LABEL_TERMS
        or normalized in SKILL_CHUNK_NOISE_TERMS
    ):
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


def _filter_section_level_matches(matches: List[str], source_text: str) -> List[str]:
    filtered: List[str] = []
    source_lower = clean_text_pipeline(source_text or "").lower()
    for match in matches:
        normalized = normalize_skill_name(match)
        if not normalized:
            continue
        category = _skill_intelligence.category_map.get(normalized)
        if category == "industry":
            continue
        if normalized not in filtered and re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", source_lower):
            filtered.append(normalized)
    return filtered


def _suppress_generic_overlaps(skills: List[str]) -> List[str]:
    skill_set = set(skills)
    suppressed: List[str] = []
    for skill in skills:
        if skill == "robot" and "robot framework" in skill_set:
            continue
        if skill == "selenium" and "selenium webdriver" in skill_set:
            continue
        suppressed.append(skill)
    return suppressed


def extract_skill_keywords(text: str, section_text: str = "") -> List[str]:
    source = _sanitize_skill_section(section_text or text)
    if not source:
        return []

    normalized_section = source.replace("•", ",").replace("▪", ",").replace("|", ",")
    raw_chunks: List[str] = []
    for sentence in SKILL_SENTENCE_SPLIT_PATTERN.split(normalized_section):
        raw_chunks.extend(
            chunk.strip(" -*:\t")
            for chunk in SKILL_TOKEN_SPLIT_PATTERN.split(sentence)
            if chunk.strip(" -*:\t")
        )
    matches: List[str] = []

    for chunk in raw_chunks:
        if len(chunk) < 2 or not _looks_like_skill_chunk(chunk):
            continue
        chunk_matches = []
        chunk_matches.extend(_skill_keyword_processor.extract_keywords(chunk))
        chunk_matches.extend(_skill_intelligence.extract_skills(chunk))
        if not chunk_matches:
            fallback_skill = _fallback_skill_from_chunk(chunk)
            if fallback_skill:
                chunk_matches.append(fallback_skill)
        matches.extend(
            match for match in chunk_matches
            if _is_supported_extracted_skill(match, chunk)
        )

    section_matches = []
    section_matches.extend(_skill_keyword_processor.extract_keywords(normalized_section))
    section_matches.extend(_skill_intelligence.extract_skills(normalized_section))
    matches.extend(_filter_section_level_matches(section_matches, normalized_section))

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

    normalized_matches = _skill_intelligence.map_skills(matches)
    return _unique_in_order(_suppress_generic_overlaps(normalized_matches))[:50]


def extract_email(text: str) -> str:
    if not text:
        return ""

    text = re.sub(r'(\w+)\s*@\s*\n\s*(\w+\.\w+)', r'\1@\2', text)
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
        for line in lines:
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in DEGREE_PATTERNS):
                degree = line[:120]
                break
        if not degree:
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
    embedded_location_pattern = re.compile(
        r"(?P<value>[A-Za-z][A-Za-z\s.-]{1,40},\s*[A-Za-z][A-Za-z\s.-]{1,40})",
        re.IGNORECASE,
    )

    def normalize_location_candidate(candidate: str) -> str:
        compact = re.sub(r"\s+", " ", candidate.strip(" ,.-"))
        if "," not in compact:
            return compact
        left, right = [part.strip() for part in compact.split(",", 1)]
        left_words = left.split()
        if len(left_words) > 2:
            left = " ".join(left_words[-2:]).strip()
            left_words = left.split()
        if len(left_words) == 2 and left_words[0].lower() in LOCATION_LEADING_DESCRIPTORS:
            left = left_words[-1]
        right_tokens: List[str] = []
        for token in right.split():
            lowered = token.lower()
            if (
                "@" in token
                or "." in token
                or any(ch.isdigit() for ch in token)
                or lowered.startswith(("linkedin", "github", "kaggle", "medium"))
            ):
                break
            right_tokens.append(token)
            if len(right_tokens) >= 3:
                break
        cleaned_right = " ".join(right_tokens).strip()
        if not cleaned_right:
            return left.strip(" ,")
        return f"{left}, {cleaned_right}".strip(" ,")

    for line in lines[:8]:
        match = LOCATION_PATTERN.search(line)
        if match:
            compact = normalize_location_candidate(match.group("value"))
            if compact and not LOCATION_NOISE_PATTERN.search(compact):
                return compact[:80]
    for line in lines[:8]:
        matches = [m.group("value") for m in embedded_location_pattern.finditer(line)]
        for candidate in reversed(matches):
            compact = normalize_location_candidate(candidate)
            if compact and not LOCATION_NOISE_PATTERN.search(compact):
                return compact[:80]
    for line in lines[:12]:
        match = HEADER_LOCATION_PATTERN.match(line)
        if match:
            compact = re.sub(r"\s+", " ", match.group("value").strip(" ,.-"))
            if compact and not LOCATION_NOISE_PATTERN.search(compact):
                return compact[:80]
    for line in lines[:12]:
        if "@" not in line and "|" not in line:
            continue
        candidates = [m.group("value") for m in PIPE_HEADER_LOCATION_PATTERN.finditer(line)]
        ranked_candidates = sorted(candidates, key=lambda value: ("," not in value, len(value)))
        for candidate in ranked_candidates:
            compact = re.sub(r"\s+", " ", candidate.strip(" ,.-"))
            if not compact or LOCATION_NOISE_PATTERN.search(compact):
                continue
            if any(char.isdigit() for char in compact):
                continue
            if len(compact.split()) > 4:
                continue
            if compact.lower().startswith(("linkedin", "github", "medium", "kaggle")):
                continue
            return compact[:80]
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


def extract_certification_entries(text: str, certifications_section: str = "") -> List[Dict[str, str]]:
    section_text = certifications_section or segment_resume_sections(text).get("certifications", "")
    if not section_text:
        return []

    entries: List[Dict[str, str]] = []
    seen = set()
    for chunk in CERTIFICATION_SPLIT_PATTERN.split(section_text):
        normalized = clean_text_pipeline(chunk or "").strip(" -,:")
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in CERTIFICATION_NOISE_TERMS:
            continue
        if len(normalized.split()) > 10:
            continue
        if not CERTIFICATION_HINT_PATTERN.search(normalized):
            continue
        key = lowered
        if key in seen:
            continue
        seen.add(key)
        entries.append({"name": normalized[:160]})
    return entries


def extract_languages(text: str, languages_section: str = "", header_text: str = "") -> List[str]:
    if not languages_section and not header_text:
        return []
    matches: List[str] = []
    section_source = languages_section or ""
    if section_source:
        for chunk in re.split(r"[\n|,;/]+", section_source):
            normalized = clean_text_pipeline(chunk or "").strip().lower()
            normalized = re.sub(r"\b(?:fluent|native|conversational|working|professional|advanced|beginner|intermediate)\b", "", normalized)
            normalized = re.sub(r"[()\-]", " ", normalized)
            normalized = re.sub(r"\s+", " ", normalized).strip()
            if normalized in LANGUAGE_TERMS:
                matches.append(normalized.title())
    search_lines = [line.strip() for line in (languages_section or "").splitlines() if line.strip()]
    search_lines.extend(line.strip() for line in (header_text or "").splitlines() if line.strip())
    for line in search_lines[:20]:
        header_match = LANGUAGE_LINE_PATTERN.match(line)
        if header_match:
            for chunk in re.split(r"[,;|/]", header_match.group("value")):
                normalized = chunk.strip().lower()
                if normalized in LANGUAGE_TERMS:
                    matches.append(normalized.title())
    combined_search_text = "\n".join(search_lines)
    for match in re.finditer(r"(?is)\blanguages?\s*[:\-]?\s*(?P<value>.{0,160})", combined_search_text or ""):
        value = match.group("value")
        for language in LANGUAGE_TERMS:
            if re.search(rf"\b{re.escape(language)}\b", value, re.IGNORECASE):
                matches.append(language.title())
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
    structural_text = normalize_text(
        merge_broken_lines(
            normalize_document_structure(text or "")
        )
    )
    cleaned_text = clean_text_pipeline(text)
    sections = segment_resume_sections(cleaned_text)
    
    structural_source = normalize_document_structure(text or "")
    raw_sections = segment_resume_sections(structural_source)
    
    skills_section = _sanitize_skill_section(raw_sections.get("skills", "") or sections.get("skills", ""))
    
    skills = extract_skill_keywords(skills_section, skills_section)
    
    if not skills:
        skills = extract_skill_keywords(cleaned_text, cleaned_text)
    
    experience_result = extract_total_experience(structural_text)
    
    if not experience_result.get("experiences"):
        experience_result = extract_total_experience(cleaned_text)
    
    experience_entries = experience_result.get("experiences", [])
    total_experience_years = experience_result.get("total_experience_years")

    current_entry = {}
    if experience_entries:
        experience_entries_sorted = sorted(
            experience_entries,
            key=lambda x: x.get("end_date") or "Present",
            reverse=True,
        )
        current_entry = experience_entries_sorted[0]

    # Fallback current_role from header when no experience entries parsed.
    header_role = ""
    if not experience_entries and not current_entry.get("role"):
        from ats.extraction.experience_extraction import ROLE_TITLE_PATTERN

        for line in (sections.get("header", "") or "").splitlines():
            m = ROLE_TITLE_PATTERN.search(line.strip())
            if m:
                header_role = m.group("role").strip()
                break

    location = extract_location(sections.get("header", ""))
    if not location and SPACY_AVAILABLE:
        doc = get_section_doc(text[:500])
        if doc:
            for ent in doc.ents:
                if ent.label_ == "GPE":
                    location = ent.text
                    break

    result = {
        "sections": sections,
        "skills": skills,
        "name": extract_name(text),
        "experience": experience_entries,
        "projects": extract_project_entries(cleaned_text, sections.get("projects", "")),
        "education": extract_education_entries(cleaned_text, sections.get("education", "")),
        "certifications": extract_certification_entries(cleaned_text, sections.get("certifications", "")),
        "location": location,
        "current_company": current_entry.get("company"),
        "current_role": current_entry.get("role") or (header_role if not experience_entries else None),
        "designation": current_entry.get("role") or (header_role if not experience_entries else None) or None,
        "experience_years": total_experience_years,
        "total_experience_years": total_experience_years,
        "experience_level": derive_experience_level(total_experience_years),
        "languages": extract_languages(
            cleaned_text,
            "\n".join(
                filter(
                    None,
                    [
                        sections.get("languages", ""),
                        _language_label_lines(sections.get("header", ""), sections.get("skills", "")),
                    ],
                )
            ),
            sections.get("header", ""),
        ),
        "experience_text": clean_text_pipeline(sections.get("experience", "")),
        "education_text": clean_text_pipeline(sections.get("education", "")),
        "projects_text": clean_text_pipeline(sections.get("projects", "")),
        "certifications_text": clean_text_pipeline(sections.get("certifications", "")),
    }
    return validate_parsed_fields(result)
