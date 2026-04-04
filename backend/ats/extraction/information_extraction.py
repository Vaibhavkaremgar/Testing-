from __future__ import annotations

import logging
import re
import importlib.util
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser

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

logger = logging.getLogger(__name__)

STRICT_EMAIL_PATTERN = re.compile(r"(?i)(?P<email>[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})(?=$|[\s,;:|)\]>])")
ROBUST_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
RELAXED_EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9,._-]+\.[a-zA-Z]{2,}")
EMAIL_COMMON_TLDS = (
    ".com", ".org", ".net", ".edu", ".gov", ".co", ".io", ".ai", ".in", ".uk", ".us", ".de", ".fr", ".au",
)
PHONE_PATTERNS = (
    re.compile(r"(?<!\d)(\+91[\s-]?\d{5}[\s-]?\d{5})(?!\d)"),
    re.compile(r"(?<!\d)(\+91[\s-]?\d{10})(?!\d)"),
    re.compile(r"(?<!\d)(\d{10})(?!\d)"),
)
ALLOWED_SOFT_SKILLS = {"problem-solving", "critical thinking", "stakeholder management"}
EXCLUDED_SOFT_SKILLS = {
    "negotiation", "communication", "leadership", "teamwork", "responsible", "motivated",
}
INVALID_LOCATION_WORDS = {"job", "objective", "contact", "details", "summary", "profile", "linkedin", "github", "portfolio", "career", "passing"}
LOCATION_FALSE_POSITIVE_TECH_PATTERN = re.compile(
    r"(?i)\b(?:python|java|selenium|playwright|robot framework|robot|sql|typescript|react|docker|jenkins|postman|restassured|pytest|fastapi|power bi|tableau|jira|maven)\b"
)
KNOWN_LOCATION_SKILLS_BLOCKLIST = {
    "chennai", "hyderabad", "bangalore", "bengaluru", "pune", "mumbai", "delhi", "gurugram", "noida",
    "kolkata", "ahmedabad", "kochi", "coimbatore", "austin", "seattle",
}
PARENT_SKILL_MAP = {
    "fastapi": ["python"],
    "django": ["python"],
    "flask": ["python"],
    "react": ["javascript"],
    "nodejs": ["javascript"],
    "typescript": ["javascript"],
    "power bi": ["sql"],
}
INVALID_NAME_LABELS = {"contact", "profile", "summary", "technical", "skills", "experience", "education", "certifications"}
INVALID_LOCATION_LABELS = {"contact", "profile", "summary", "skills", "experience", "education", "certifications"}
GEOGRAPHIC_PART_PATTERN = re.compile(r"^[A-Za-z]+(?:[\s.-][A-Za-z]+)*$")
NAME_IGNORE_TERMS = {
    "resume", "email", "phone", "mobile", "contact", "profile", "summary", "skills",
    "experience", "education", "curriculum", "vitae",
}
LOCATION_SPLIT_PATTERN = re.compile(r"\s*(?:\||/|,)\s*")
LOCATION_CONNECTOR_TERMS = {
    "india", "remote", "telangana", "karnataka", "maharashtra", "delhi", "pune", "hyderabad",
    "bangalore", "bengaluru", "mumbai", "chennai", "gurugram", "noida",
}
LOCATION_ROLE_BLOCKLIST = {
    "engineer", "analyst", "developer", "tester", "consultant", "manager", "specialist",
    "architect", "soc", "cybersecurity", "penetration", "software", "data", "business",
    "intelligence", "visualization",
}


def _clean_header_lines(text: str, limit: int = 12) -> List[str]:
    normalized = normalize_document_structure(text or "")
    return [line.strip() for line in normalized.splitlines() if line.strip()][:limit]


def _extract_name_from_email(email: str) -> str:
    if not email or "@" not in email:
        return ""
    prefix = email.split("@", 1)[0]
    prefix = re.sub(r"[._\-+]+", " ", prefix)
    tokens = [token for token in prefix.split() if token.isalpha()]
    if not (1 < len(tokens) <= 4):
        return ""
    candidate = " ".join(token.capitalize() for token in tokens)
    logger.debug("Name fallback extracted from email prefix: %s", candidate)
    return candidate

def extract_name(text: str) -> str:
    if not text:
        return ""

    lines = [l.strip() for l in normalize_document_structure(text).splitlines() if l.strip()]
    contact_zone = lines[:12]

    if SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(contact_zone))
        if doc:
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                candidate = re.sub(r"\s+", " ", ent.text).strip(" ,.-")
                lowered = candidate.lower()
                if len(candidate.split()) < 2 or len(candidate.split()) > 4:
                    continue
                if any(token in INVALID_NAME_LABELS for token in lowered.split()):
                    continue
                if normalize_skill_name(candidate):
                    continue
                return candidate.title()

    for line in contact_zone:
        candidate = re.split(r"\s+\|\s+|\s+[·•]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", line, maxsplit=1)[0].strip()
        candidate = re.sub(r"(?i)^(?:name)\s*[:\-]\s*", "", candidate).strip()
        lowered = candidate.lower()
        if len(candidate.split()) < 2 or len(candidate.split()) > 4:
            continue
        if any(label in lowered.split() for label in INVALID_NAME_LABELS):
            continue
        if normalize_skill_name(candidate):
            continue
        if re.match(r"^[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}$", candidate):
            return candidate.title()

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
PLACE_LINE_PATTERN = re.compile(r"(?i)\bplace\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s.-]{1,40})")
LOCATION_CONTEXT_PATTERN = re.compile(
    r"(?i)\b(?:preferably in|based in|located in|from)\s+(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})\b"
)
LOCATION_OR_PATTERN = re.compile(
    r"(?i)\bor\s+(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})\b"
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
_skillner_extractor = None
_skillner_state = {
    "checked": False,
    "installed": False,
    "usable": False,
}


def _skillner_installed() -> bool:
    return importlib.util.find_spec("skillNer") is not None


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


def extract_name(text: str) -> str:
    if not text:
        return ""

    lines = _clean_header_lines(text, limit=12)
    first_five_lines = lines[:5]

    def _is_valid_name_line(candidate: str) -> bool:
        compact = re.sub(r"\s+", " ", candidate.strip(" ,.-"))
        lowered = compact.lower()
        if not compact:
            return False
        if any(term in lowered for term in NAME_IGNORE_TERMS):
            return False
        if any(char.isdigit() for char in compact):
            return False
        if "@" in compact:
            return False
        words = compact.split()
        if not (2 <= len(words) <= 4):
            return False
        normalized_candidate = clean_text_pipeline(compact).lower()
        if (
            normalized_candidate in _skill_intelligence.get_skill_dictionary()
            or normalized_candidate in _skill_intelligence.get_synonym_dictionary()
            or normalized_candidate in _skill_intelligence.get_synonym_dictionary().values()
        ):
            return False
        capitalized_count = sum(1 for word in words if re.match(r"^[A-Z][A-Za-z'`.-]+$", word))
        return capitalized_count >= max(2, len(words) - 1)

    for line in first_five_lines:
        leading_candidate = re.match(r"^(?P<value>[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3})\b", line)
        if leading_candidate:
            candidate = leading_candidate.group("value").strip()
            role_noise = {"engineer", "analyst", "developer", "tester", "consultant", "manager", "specialist", "architect"}
            candidate_tokens = [token.lower() for token in candidate.split()]
            if not any(token in role_noise for token in candidate_tokens) and _is_valid_name_line(candidate):
                resolved = " ".join(part.capitalize() for part in candidate.split())
                logger.debug("Name extracted from leading header tokens: %s", resolved)
                return resolved
        candidate = re.sub(r"(?i)^(?:name)\s*[:\-]\s*", "", line).strip()
        candidate = re.split(r"\s+\|\s+|\s+[·•]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", candidate, maxsplit=1)[0].strip()
        if _is_valid_name_line(candidate):
            resolved = " ".join(part.capitalize() for part in candidate.split())
            logger.debug("Name extracted from header line: %s", resolved)
            return resolved

    if SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(first_five_lines or lines[:8]))
        if doc:
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                candidate = re.sub(r"\s+", " ", ent.text).strip(" ,.-")
                if _is_valid_name_line(candidate):
                    resolved = " ".join(part.capitalize() for part in candidate.split())
                    logger.debug("Name extracted with spaCy PERSON: %s", resolved)
                    return resolved

    return _extract_name_from_email(extract_email(text))


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


def _extract_gpe_entities(text: str) -> List[str]:
    if not SPACY_AVAILABLE or not text:
        return []
    doc = get_section_doc(text[:2000])
    if doc is None:
        return []
    entities: List[str] = []
    for ent in doc.ents:
        if ent.label_ == "GPE":
            normalized = clean_text_pipeline(ent.text).strip().lower()
            if normalized:
                entities.append(normalized)
    return list(dict.fromkeys(entities))


def _extract_skillner_keywords(text: str) -> List[str]:
    if not text:
        return []
    global _skillner_extractor
    global _skillner_state
    if _skillner_extractor is None:
        _skillner_state["checked"] = True
        _skillner_state["installed"] = _skillner_installed()
        if not _skillner_state["installed"]:
            _skillner_extractor = False
            return []
        try:
            from skillNer.skill_extractor_class import SkillExtractor as SkillNERExtractor  # type: ignore
            _skillner_extractor = SkillNERExtractor()
            _skillner_state["usable"] = True
        except Exception:
            _skillner_extractor = False
            _skillner_state["usable"] = False
    if not _skillner_extractor:
        return []
    try:
        annotations = _skillner_extractor.annotate(text) or {}
    except Exception:
        return []
    matches: List[str] = []
    for key in ("results", "skill_matches", "skills"):
        values = annotations.get(key) if isinstance(annotations, dict) else None
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict):
                skill_value = item.get("doc_node_value") or item.get("skill") or item.get("text")
            else:
                skill_value = str(item)
            normalized = normalize_skill_name(str(skill_value or ""))
            if normalized:
                matches.append(normalized)
    return _unique_in_order(matches)


def _skill_confidence(skill: str, source_text: str, from_section: bool) -> str:
    normalized = normalize_skill_name(skill)
    if not normalized:
        return "low"
    if normalized in _skill_intelligence.get_skill_dictionary():
        return "high" if from_section else "medium"
    if normalized in _skill_intelligence.get_synonym_dictionary().values():
        return "medium"
    if normalized in SKILL_ALIASES.values() or normalized in SKILL_ALIASES:
        return "medium"
    if normalized in _extract_skillner_keywords(source_text):
        return "medium"
    lowered_source = clean_text_pipeline(source_text or "").lower()
    if re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", lowered_source):
        return "low"
    return "low"


def _is_validated_skill(skill: str, source_text: str, from_section: bool, blocked_locations: set[str]) -> bool:
    normalized = normalize_skill_name(skill)
    if not normalized:
        return False
    if normalized in EXCLUDED_SOFT_SKILLS and normalized not in ALLOWED_SOFT_SKILLS:
        return False
    if normalized in blocked_locations or normalized in KNOWN_LOCATION_SKILLS_BLOCKLIST:
        return False
    if _skill_intelligence._is_noise(normalized):
        return False
    if _skill_confidence(normalized, source_text, from_section) == "low":
        return False
    in_esco = normalized in _skill_intelligence.get_skill_dictionary()
    in_synonyms = normalized in _skill_intelligence.get_synonym_dictionary().values()
    in_custom = normalized in set(SKILL_ALIASES.values()) or normalized in set(SKILL_ALIASES.keys())
    return in_esco or in_synonyms or in_custom


def _expand_parent_skills(skills: List[str]) -> List[str]:
    expanded = list(skills)
    seen = set(skills)
    for skill in skills:
        for parent in PARENT_SKILL_MAP.get(skill, []):
            normalized_parent = normalize_skill_name(parent)
            if normalized_parent and normalized_parent not in seen:
                seen.add(normalized_parent)
                expanded.append(normalized_parent)
    return expanded


def _finalize_skills(skills: List[str], source_text: str, location_text: str, from_section: bool) -> List[str]:
    blocked_locations = set(_extract_gpe_entities(location_text or source_text))
    normalized_location_text = clean_text_pipeline(location_text or "").lower()
    for candidate in re.split(r"[,|\n/]+", normalized_location_text):
        cleaned_candidate = candidate.strip()
        if cleaned_candidate and cleaned_candidate in KNOWN_LOCATION_SKILLS_BLOCKLIST:
            blocked_locations.add(cleaned_candidate)
    validated = [
        normalize_skill_name(skill)
        for skill in skills
        if _is_validated_skill(skill, source_text, from_section, blocked_locations)
    ]
    validated = [skill for skill in validated if skill]
    validated = _expand_parent_skills(_unique_in_order(_suppress_generic_overlaps(validated)))
    return _unique_in_order(validated)[:50]


def _extract_contextual_skills(*sections: str) -> List[str]:
    matches: List[str] = []
    for section in sections:
        normalized_section = clean_text_pipeline(section or "")
        if not normalized_section:
            continue
        matches.extend(_skill_keyword_processor.extract_keywords(normalized_section))
        matches.extend(_skill_intelligence.extract_skills(normalized_section))
        matches.extend(_extract_skillner_keywords(normalized_section))
        for sentence in SKILL_SENTENCE_SPLIT_PATTERN.split(normalized_section):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not re.search(r"(?i)\b(?:worked on|built|developed|implemented|used|deploy|designed|experience with|services?|apis?)\b", sentence):
                continue
            matches.extend(_skill_keyword_processor.extract_keywords(sentence))
            matches.extend(_skill_intelligence.extract_skills(sentence))
            matches.extend(_extract_skillner_keywords(sentence))
    return _unique_in_order(matches)


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
        chunk_matches.extend(_extract_skillner_keywords(chunk))
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
    section_matches.extend(_extract_skillner_keywords(normalized_section))
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

    def _clean_email_candidate(candidate: str) -> str:
        candidate = candidate.replace("mailto:", "").replace("MAILTO:", "")
        candidate = re.sub(r"\s+", "", candidate)
        candidate = re.sub(r"(?<=\w),(?=\w)", "", candidate)
        candidate = candidate.strip(".,;:")
        com_match = re.search(r"\.com(?=[^a-zA-Z]|$)", candidate, re.IGNORECASE)
        if com_match:
            return candidate[:com_match.end()]
        tld_match = re.search(r"\.[a-zA-Z]{2,6}(?=[^a-zA-Z]|$)", candidate)
        if tld_match:
            return candidate[:tld_match.end()]
        return candidate

    normalized_text = normalize_common_artifacts(text or "")
    normalized_text = re.sub(r"(\w+)\s*@\s*\n\s*(\w+\.\w+)", r"\1@\2", normalized_text)
    normalized_text = normalized_text.replace("mailto:", " ").replace("MAILTO:", " ")
    normalized_text = re.sub(r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9,._-]+\.[A-Za-z]{2,6})", lambda m: f"{m.group(1)}@{m.group(2).replace(',', '')}", normalized_text)
    relaxed_match = RELAXED_EMAIL_PATTERN.search(normalized_text)
    if relaxed_match:
        email = _clean_email_candidate(relaxed_match.group(0))
        if "@" in email:
            logger.debug("Email extracted with relaxed pattern: %s", email)
            return email
    match = ROBUST_EMAIL_PATTERN.search(normalized_text)
    if match:
        email = _clean_email_candidate(match.group(0))
        logger.debug("Email extracted with robust pattern: %s", email)
        return email
    match = STRICT_EMAIL_PATTERN.search(normalized_text)
    if match:
        email = _clean_email_candidate(match.group("email"))
        logger.debug("Email extracted with strict pattern: %s", email)
        return email
    compact_text = normalized_text.replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
    compact_text = compact_text.replace("(dot)", ".").replace("[dot]", ".").replace(" dot ", ".")
    relaxed_match = RELAXED_EMAIL_PATTERN.search(compact_text)
    if relaxed_match:
        email = _clean_email_candidate(relaxed_match.group(0))
        if "@" in email:
            logger.debug("Email extracted after relaxed artifact cleanup: %s", email)
            return email
    match = ROBUST_EMAIL_PATTERN.search(compact_text)
    if match:
        email = _clean_email_candidate(match.group(0))
        logger.debug("Email extracted after artifact cleanup: %s", email)
        return email
    match = STRICT_EMAIL_PATTERN.search(compact_text)
    if match:
        email = _clean_email_candidate(match.group("email"))
        logger.debug("Email extracted after strict artifact cleanup: %s", email)
        return email
    return ""


def extract_phone(text: str) -> str:
    if not text:
        return ""
    normalized_text = normalize_common_artifacts(text or "")
    for pattern in PHONE_PATTERNS:
        match = pattern.search(normalized_text)
        if not match:
            continue
        candidate = re.sub(r"\s+", " ", match.group(1)).strip()
        logger.debug("Phone extracted: %s", candidate)
        return candidate
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
        raw_lines = [line.strip() for line in normalize_document_structure(text).splitlines() if line.strip()]
        inferred_lines: List[str] = []
        for index, line in enumerate(raw_lines):
            if any(re.search(pattern, line, re.IGNORECASE) for pattern in DEGREE_PATTERNS):
                inferred_lines.extend(raw_lines[index:index + 4])
                break
        section_text = "\n".join(inferred_lines)
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
        left_tokens = [
            token for token in left.split()
            if "@" not in token and "." not in token and not any(ch.isdigit() for ch in token)
        ]
        if left_tokens:
            left = " ".join(left_tokens)
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

    def is_valid_location_candidate(candidate: str) -> bool:
        if not candidate or LOCATION_NOISE_PATTERN.search(candidate):
            return False
        lowered = candidate.lower()
        if lowered in INVALID_LOCATION_LABELS:
            return False
        if lowered in INVALID_LOCATION_WORDS:
            return False
        if lowered.endswith(" or"):
            return False
        if lowered.startswith(("linkedin", "github", "portfolio", "medium", "kaggle")):
            return False
        if any(char.isdigit() for char in candidate):
            return False
        geo_parts = [part.strip() for part in candidate.split(",") if part.strip()]
        for part in geo_parts or [candidate]:
            normalized_part = clean_text_pipeline(part).strip().lower()
            if normalized_part.startswith("in "):
                return False
            if LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(normalized_part):
                return False
        if len(geo_parts) < 2:
            return bool(
                LOCATION_CANDIDATE_PATTERN.match(candidate)
                and len(candidate.split()) <= 3
                and bool(re.match(r"^[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*){0,2}$", candidate))
                and not re.match(r"^[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}$", candidate)
            )
        return all(GEOGRAPHIC_PART_PATTERN.match(part) for part in geo_parts)

    for line in lines[:8]:
        place_match = PLACE_LINE_PATTERN.search(line)
        if place_match:
            compact = re.sub(r"\s+", " ", place_match.group("value").strip(" ,.-"))
            compact = compact.split()[0].strip(" ,.-")
            if is_valid_location_candidate(compact):
                return compact[:80]
    for line in lines[:8]:
        match = LOCATION_PATTERN.search(line)
        if match:
            compact = normalize_location_candidate(match.group("value"))
            if is_valid_location_candidate(compact):
                return compact[:80]
    for line in lines[:8]:
        matches = [m.group("value") for m in embedded_location_pattern.finditer(line)]
        for candidate in reversed(matches):
            compact = normalize_location_candidate(candidate)
            if is_valid_location_candidate(compact):
                return compact[:80]
    for line in lines[:12]:
        match = HEADER_LOCATION_PATTERN.match(line)
        if match:
            compact = re.sub(r"\s+", " ", match.group("value").strip(" ,.-"))
            if is_valid_location_candidate(compact):
                return compact[:80]
    for line in lines[:12]:
        if "@" not in line and "|" not in line:
            continue
        candidates = [m.group("value") for m in PIPE_HEADER_LOCATION_PATTERN.finditer(line)]
        ranked_candidates = sorted(candidates, key=lambda value: ("," not in value, len(value)))
        for candidate in ranked_candidates:
            compact = re.sub(r"\s+", " ", candidate.strip(" ,.-"))
            if is_valid_location_candidate(compact):
                return compact[:80]
    for line in lines[:5]:
        if "@" in line or any(char.isdigit() for char in line):
            continue
        compact = re.sub(r"\s+", " ", line).strip(" ,.-")
        if not compact or LOCATION_NOISE_PATTERN.search(compact):
            continue
        if len(compact.split()) > 4:
            continue
        if is_valid_location_candidate(compact) and LOCATION_CANDIDATE_PATTERN.match(compact):
            return compact[:80]
    contextual_candidates: List[str] = []
    for line in lines[:25]:
        for match in LOCATION_CONTEXT_PATTERN.finditer(line):
            candidate = re.sub(r"\s+", " ", match.group("value").strip(" ,.-"))
            if is_valid_location_candidate(candidate):
                contextual_candidates.append(candidate)
        for match in LOCATION_OR_PATTERN.finditer(line):
            candidate = re.sub(r"\s+", " ", match.group("value").strip(" ,.-"))
            if is_valid_location_candidate(candidate):
                contextual_candidates.append(candidate)
    if contextual_candidates:
        return contextual_candidates[-1][:80]
    if SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(lines[:20]))
        if doc is not None:
            gpe_values = [ent.text.strip(" ,.-") for ent in doc.ents if ent.label_ == "GPE"]
            if len(gpe_values) >= 2:
                candidate = ", ".join(dict.fromkeys(gpe_values[:2]))
                candidate = normalize_location_candidate(candidate)
                if is_valid_location_candidate(candidate):
                    return candidate[:80]
    return ""


def _looks_like_location_fragment(value: str) -> bool:
    candidate = re.sub(r"\s+", " ", (value or "").strip(" ,.|/:-"))
    lowered = candidate.lower()
    if not candidate:
        return False
    if any(char.isdigit() for char in candidate):
        return False
    if lowered in INVALID_LOCATION_WORDS or lowered in INVALID_LOCATION_LABELS:
        return False
    if lowered.startswith(("linkedin", "github", "portfolio")):
        return False
    if "@" in candidate:
        return False
    if LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(lowered):
        return False
    parts = [part.strip() for part in LOCATION_SPLIT_PATTERN.split(candidate) if part.strip()]
    if not parts:
        return False
    lowered_parts = [part.lower() for part in parts]
    if any(part in LOCATION_ROLE_BLOCKLIST for part in lowered_parts):
        return False
    if len(parts) == 1:
        return lowered in LOCATION_CONNECTOR_TERMS
    if any(part in LOCATION_CONNECTOR_TERMS for part in lowered_parts):
        return True
    return len(parts) <= 3 and all(re.match(r"^[A-Z][A-Za-z.-]*(?:\s+[A-Z][A-Za-z.-]*)*$", part) for part in parts)


def _normalize_location_value(value: str) -> str:
    original_value = value or ""
    comma_pair = "," in original_value and "|" not in original_value and "/" not in original_value
    parts = [re.sub(r"\s+", " ", part).strip(" ,.|/:-") for part in LOCATION_SPLIT_PATTERN.split(value or "") if part.strip()]
    deduped: List[str] = []
    seen = set()
    for index, part in enumerate(parts):
        words = part.split()
        if len(words) > 2:
            part = " ".join(words[-2:])
            words = part.split()
        if comma_pair:
            pass
        elif index == 0 and len(words) == 2 and words[0].lower() not in LOCATION_CONNECTOR_TERMS and words[1].lower() in LOCATION_CONNECTOR_TERMS:
            part = words[1]
        elif index == 0 and len(words) == 2 and words[0].lower() not in LOCATION_CONNECTOR_TERMS:
            part = words[-1]
        lowered = part.lower()
        if lowered in seen:
            continue
        if lowered in INVALID_LOCATION_WORDS or lowered in INVALID_LOCATION_LABELS:
            continue
        deduped.append(part)
        seen.add(lowered)
    return ", ".join(deduped[:3])


def _trim_location_segment(value: str) -> str:
    words = [word for word in re.sub(r"\s+", " ", (value or "").strip()).split() if word]
    while len(words) > 2 and words[0].lower() not in LOCATION_CONNECTOR_TERMS:
        words = words[1:]
    if len(words) == 2 and words[0].lower() in LOCATION_ROLE_BLOCKLIST:
        words = words[1:]
    return " ".join(words)


def extract_location(text: str) -> str:
    if not text:
        return ""

    cleaned_text = clean_text_pipeline(text)
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    comma_location_pattern = re.compile(
        r"(?P<left>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,3})\s*,\s*"
        r"(?P<right>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})"
    )
    location_patterns = (
        re.compile(r"\b(?:location|address|based in|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,|/-]{2,80})", re.IGNORECASE),
        re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*,\s*[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?)"),
        re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*/\s*[A-Z][A-Za-z.-]+(?:\s*/\s*[A-Z][A-Za-z.-]+)?)"),
        re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*\|\s*[A-Z][A-Za-z.-]+(?:\s*\|\s*[A-Z][A-Za-z.-]+)?)"),
    )

    for line in lines[:12]:
        for match in comma_location_pattern.finditer(line):
            left = _trim_location_segment(match.group("left"))
            right = re.sub(r"\s+", " ", match.group("right").strip())
            candidate = f"{left}, {right}".strip(" ,")
            if _looks_like_location_fragment(candidate):
                logger.debug("Location extracted from comma header pattern: %s", candidate)
                return candidate
        for pattern in location_patterns:
            for match in pattern.finditer(line):
                candidate = _normalize_location_value(match.group("value"))
                if _looks_like_location_fragment(candidate):
                    logger.debug("Location extracted from explicit pattern: %s", candidate)
                    return candidate

    if SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(lines[:15]))
        if doc is not None:
            gpe_entities = [re.sub(r"\s+", " ", ent.text).strip(" ,.-") for ent in doc.ents if ent.label_ == "GPE"]
            if gpe_entities:
                candidate = _normalize_location_value(" | ".join(gpe_entities[:3]))
                if _looks_like_location_fragment(candidate):
                    logger.debug("Location extracted with spaCy GPE: %s", candidate)
                    return candidate

    for line in lines[:8]:
        candidate = _normalize_location_value(line)
        if _looks_like_location_fragment(candidate):
            logger.debug("Location extracted from fallback line scan: %s", candidate)
            return candidate
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


def _extract_explicit_total_experience(text: str) -> float | None:
    if not text:
        return None
    month_match = re.search(
        r"(?i)\b(?P<years>\d+(?:\.\d+)?)\+?\s*(?:years|yrs)(?:\s+and\s+(?P<months>\d+)\s+months?)?(?:\s+of\s+experience|\s+experience)?\b",
        text,
    )
    if month_match:
        years = float(month_match.group("years"))
        months = float(month_match.group("months") or 0)
        logger.debug("Experience extracted from explicit years/months statement: %s years, %s months", years, months)
        return round(years + (months / 12.0), 1)
    phrase_match = re.search(r"(?i)\b(?P<years>\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s+of\s+experience\b", text)
    if phrase_match:
        years = round(float(phrase_match.group("years")), 1)
        logger.debug("Experience extracted from phrase match: %s", years)
        return years
    year_match = re.search(r"(?i)\b(?P<years>\d+(?:\.\d+)?)\+?\s*(?:years|yrs)\s+experience\b", text)
    if year_match:
        years = round(float(year_match.group("years")), 1)
        logger.debug("Experience extracted from years regex: %s", years)
        return years
    return None


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
    has_resume_experience_header = bool(
        re.search(
            r"(?im)^\s*(?:work experience|professional experience|experience|employment history|employment)\s*$",
            structural_source,
        )
    )
    
    skills_section = _sanitize_skill_section(raw_sections.get("skills", "") or sections.get("skills", ""))
    
    skills = extract_skill_keywords(skills_section, skills_section)
    has_explicit_skills_header = bool(
        re.search(r"(?im)^(?:technical skills|skills|core skills|key skills)\s*$", structural_source)
    )
    contextual_skills = _extract_contextual_skills(
        sections.get("experience", ""),
        sections.get("projects", ""),
        sections.get("summary", ""),
        cleaned_text,
    )
    if skills and (has_explicit_skills_header or len(skills) > 3):
        skills = _unique_in_order(skills)
    elif skills:
        skills = _unique_in_order(skills + contextual_skills)
    else:
        skills = contextual_skills
    
    primary_name = extract_name(cleaned_text)
    primary_email = extract_email(cleaned_text)
    primary_phone = extract_phone(cleaned_text)

    experience_result = extract_total_experience(structural_text)
    
    if not experience_result.get("experiences"):
        experience_result = extract_total_experience(cleaned_text)
    
    experience_entries = experience_result.get("experiences", [])
    total_experience_years = experience_result.get("total_experience_years")
    explicit_total_experience = _extract_explicit_total_experience(cleaned_text)
    if total_experience_years is None and explicit_total_experience is not None:
        total_experience_years = explicit_total_experience
    has_explicit_years_phrase = bool(
        re.search(r"(?i)\b\d+(?:\.\d+)?\+?\s*(?:years|yrs)(?:\s+of\s+experience|\s+experience)\b", cleaned_text)
    )
    has_explicit_experience_section = bool(sections.get("experience", "").strip())
    experience_signal_text = " ".join(
        filter(
            None,
            [
                sections.get("experience", ""),
                sections.get("employment", ""),
                sections.get("summary", ""),
            ],
        )
    )
    has_experience_signal = bool(
        re.search(
            r"(?i)\b(?:experience|employment|worked as|working as|present|current company|current role|years of experience|yrs of experience)\b",
            experience_signal_text,
        )
    )
    if not experience_entries and explicit_total_experience is None and not has_explicit_years_phrase:
        total_experience_years = None
    elif not experience_entries and not has_experience_signal:
        total_experience_years = None

    current_entry = {}
    if experience_entries:
        if (
            explicit_total_experience is not None
            and len(experience_entries) >= 2
            and total_experience_years is not None
            and total_experience_years - explicit_total_experience >= 0.75
        ):
            total_experience_years = explicit_total_experience
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
    header_context = sections.get("header", "")
    if not location:
        top_window_lines = [line.strip() for line in normalize_document_structure(text or "").splitlines()[:25] if line.strip()]
        header_only_lines: List[str] = []
        for line in top_window_lines[:8]:
            if re.match(r"(?i)^(?:professional summary|summary|profile summary|skills|technical skills|experience|work experience|education|projects|certifications?)$", line.strip()):
                break
            header_only_lines.append(line)
            location = extract_location(line)
            if location:
                break
        if not location:
            header_context = "\n".join(header_only_lines)
            location = extract_location(header_context)
    if not location and SPACY_AVAILABLE and header_context:
        doc = get_section_doc(header_context[:800])
        if doc:
            gpe_entities = [ent.text.strip(" ,.-") for ent in doc.ents if ent.label_ == "GPE"]
            ranked = list(dict.fromkeys(entity for entity in gpe_entities if entity and entity.lower() not in INVALID_LOCATION_WORDS))
            if ranked:
                location = ranked[-1]
    logger.debug(
        "Primary contact extraction complete: name=%s email=%s phone=%s location=%s experience=%s",
        primary_name,
        primary_email,
        primary_phone,
        location,
        total_experience_years,
    )
    skills = _finalize_skills(
        skills,
        skills_section or sections.get("experience", "") or sections.get("projects", "") or cleaned_text,
        "\n".join(filter(None, [sections.get("header", ""), location])),
        from_section=bool(skills_section.strip()),
    )

    result = {
        "sections": sections,
        "skills": skills,
        "skill_confidence": {
            skill: _skill_confidence(skill, skills_section or cleaned_text, bool(skills_section.strip()))
            for skill in skills
        },
        "name": primary_name or "",
        "email": primary_email or "",
        "phone": primary_phone or "",
        "experience": experience_entries,
        "projects": extract_project_entries(cleaned_text, sections.get("projects", "")),
        "education": extract_education_entries(cleaned_text, sections.get("education", "")),
        "certifications": extract_certification_entries(cleaned_text, sections.get("certifications", "")),
        "location": location or "",
        "current_company": current_entry.get("company"),
        "current_role": current_entry.get("role") or (header_role if not experience_entries else None),
        "designation": current_entry.get("role") or (header_role if not experience_entries else None) or None,
        "experience_years": total_experience_years,
        "total_experience_years": total_experience_years,
        "total_experience": total_experience_years if total_experience_years is not None else 0.0,
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
        "skill_extraction_support": {
            "esco": True,
            "skillner_installed": _skillner_installed(),
            "skillner_usable": bool(_skillner_state.get("usable")),
            "custom_aliases": True,
            "dynamic_context": True,
        },
    }
    validated_result = validate_parsed_fields(result)
    if not has_resume_experience_header and explicit_total_experience is None and not validated_result.get("experience"):
        validated_result["experience_years"] = None
        validated_result["total_experience_years"] = None
        validated_result["total_experience"] = 0.0
    return validated_result
