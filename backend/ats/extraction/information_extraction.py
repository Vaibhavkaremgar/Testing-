from __future__ import annotations

import logging
import re
import time
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional
from dateutil import parser as date_parser

from flashtext import KeywordProcessor

from ats.datasets.parser_config_loader import ParserConfigLoader
from ats.extraction.experience_extraction import extract_total_experience
from ats.extraction.skill_intelligence import LANGUAGE_TERMS, get_skill_engine
from ats.extraction.validation import validate_parsed_fields, validate_location
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
STRONG_EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}", re.IGNORECASE)
BRACKETED_EMAIL_PATTERN = re.compile(r"[\(\[\{<]\s*(?P<email>[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9,._-]+\s*\.\s*[A-Za-z]{2,})\s*[\)\]\}>]")
EMAIL_COMMON_TLDS = (
    ".com", ".org", ".net", ".edu", ".gov", ".co", ".io", ".ai", ".in", ".uk", ".us", ".de", ".fr", ".au",
)
PHONE_PATTERNS = (
    re.compile(r"(?<!\d)(\+91[\s-]?\d{5}[\s-]?\d{5})(?!\d)"),
    re.compile(r"(?<!\d)(\+91[\s-]?\d{10})(?!\d)"),
    re.compile(r"(?<!\d)(\d{10})(?!\d)"),
)
PHONE_CANDIDATE_PATTERN = re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")
ROLE_KEYWORD_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|analyst|consultant|architect|lead|intern|tester|qa|software|automation)\b"
)
HEADER_NAME_SEPARATOR_PATTERN = re.compile(r"\s+\|\s+|\s+-\s+|\s+\((?=[A-Za-z])")
NON_NAME_CHARS_PATTERN = re.compile(r"[^A-Za-z'`.\- ]")
ALLOWED_SOFT_SKILLS = {"problem-solving", "critical thinking", "stakeholder management"}
EXCLUDED_SOFT_SKILLS = {
    "negotiation", "communication", "leadership", "teamwork", "responsible", "motivated",
}
INVALID_LOCATION_WORDS = {
    "job", "objective", "contact", "details", "summary", "profile", "linkedin", "github",
    "portfolio", "career", "passing", "resume", "software", "developer", "engineer",
}
LOCATION_FALSE_POSITIVE_TECH_PATTERN = re.compile(
    r"(?i)\b(?:python|java|selenium|playwright|robot framework|robot|sql|typescript|react|docker|jenkins|postman|restassured|pytest|fastapi|power bi|tableau|jira|maven|ui)\b"
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
ADDRESS_CITY_HINT_PATTERN = re.compile(
    r"(?i)\b(?P<city>[A-Za-z][A-Za-z\s.-]{1,40})\s*(?:\(?(?:dist|district|city)\)?\b)"
)
ADDRESS_PIN_CITY_PATTERN = re.compile(
    r"(?i)\b(?P<city>[A-Za-z][A-Za-z\s.-]{1,40})\s*[-,]\s*\d{5,6}\b"
)
ADDRESS_LABEL_PATTERN = re.compile(r"(?i)\baddress\b\s*[:\-]?\s*(?P<value>.+)")
EXPLICIT_TOTAL_EXPERIENCE_PATTERN = re.compile(
    r"(?i)\b(?P<years>\d+(?:\.\d+)?)\s+years?(?:\s+(?:and|&)\s+(?P<months>\d+)\s+months?)?\s+of\s+experience\b"
)
FALLBACK_TOTAL_EXPERIENCE_PATTERN = re.compile(
    r"(?i)\b(?:over|around|more\s+than)?\s*(?P<years>\d+(?:\.\d+)?)\s*\+?\s*(?:years|yrs)\b"
)
NAME_FALLBACK_BLOCKLIST_PATTERN = re.compile(r"(?i)\b(?:email|phone|linkedin|github)\b")
HEADER_ROLE_STOP_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|analyst|consultant|architect|lead|intern|qa|automation|"
    r"tester|specialist|designer|director|officer|executive|associate|scientist|recruiter|"
    r"coordinator|generalist|administrator|founder|owner|head|vp|president|cto|cfo|coo|ceo)\b"
)
UNSTRUCTURED_EXPERIENCE_STOP_PATTERN = re.compile(
    r"(?i)^(?:education|academic background|qualification|qualifications|projects?|certifications?|skills|technical skills|key skills|core skills|summary|profile|publications|achievements|awards|references)$"
)
UNSTRUCTURED_EDUCATION_HINT_PATTERN = re.compile(
    r"(?i)\b(?:b\.?\s?tech|m\.?\s?tech|bachelor|master|mba|bca|mca|bsc|msc|phd|diploma|university|college|institute|school)\b"
)


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


NAME_COMPANY_PATTERN = re.compile(
    r"(?i)\b(?:pvt|ltd|inc|llc|llp|corp|corporation|technologies|technology|solutions|systems|labs|works|school|college|university|academy|institute|services)\b"
)
UPPERCASE_NAME_PATTERN = re.compile(r"^[A-Z][A-Z'`.-]*(?:\s+[A-Z][A-Z'`.-]*){1,3}$")

def extract_name(text: str) -> str:
    if not text:
        return ""

    lines = [l.strip() for l in normalize_document_structure(text).splitlines() if l.strip()]
    contact_zone = lines[:12]

    if use_spacy and SPACY_AVAILABLE:
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
PROFICIENCY_PATTERN = re.compile(
    r"(?i)\s*[\(\[]\s*(beginner|intermediate|advanced|expert|proficient|familiar|basic)\s*[\)\]]"
)
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
PERSONAL_DETAILS_HEADER_PATTERN = re.compile(
    r"(?i)^\s*(?:personal details?|personal information|personal profile|contact details?|contact information|address details?)\s*[:\-]*\s*$"
)
LOCATION_LINE_LABEL_PATTERN = re.compile(
    r"(?i)\b(?:location|current location|present location|address|place|city|residence)\b\s*[:\-]?\s*(?P<value>.+)$"
)
COMMA_LOCATION_PATTERN = re.compile(
    r"(?P<left>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,3})\s*,\s*"
    r"(?P<right>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})"
)
EXPLICIT_LOCATION_PATTERNS = (
    re.compile(r"\b(?:location|address|based in|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,|/-]{2,80})", re.IGNORECASE),
    re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*,\s*[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?)"),
    re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*/\s*[A-Z][A-Za-z.-]+(?:\s*/\s*[A-Z][A-Za-z.-]+)?)"),
    re.compile(r"(?P<value>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+)?\s*\|\s*[A-Z][A-Za-z.-]+(?:\s*\|\s*[A-Z][A-Za-z.-]+)?)"),
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
LOCATION_TAIL_TOKENS = {
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("location_tail_tokens") or [])
    if str(value).strip()
}
LOCATION_CANONICAL_OVERRIDES = {
    "banglore": "bangalore",
}
NON_LOCATION_CONTEXT_TERMS = {
    "university",
    "board",
    "college",
    "school",
    "institute",
    "education",
    "intermediate",
    "secondary",
    "course",
    "gpa",
    "qualification",
    "qualifications",
    "academic",
    "power",
    "apps",
    "automate",
    "dataverse",
    "sharepoint",
    "technology",
    "technologies",
}
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
SECTION_START_PATTERN = re.compile(
    r"(?i)^(?:summary|profile|professional summary|experience|work experience|professional experience|"
    r"employment history|education|projects?|certifications?|skills|technical skills|languages?)$"
)
SKILL_SECTION_BREAK_PATTERN = re.compile(
    r"(?i)^(?:profile(?: summary)?|professional summary|summary|work experience|experience|period|employment|"
    r"projects?|education|certifications?|achievements?|awards?|languages?|references?|internship|job objective|objective)$"
)
SOFT_SKILLS_HEADER_PATTERN = re.compile(r"(?i)^soft skills?$")
SKILL_FALLBACK_LINE_PATTERN = re.compile(
    r"(?i)\b(?:technical skills?|core skills?|key skills?|primary skills?|professional skills?|"
    r"tool stack|technology stack|tools(?: and technologies)?|frameworks|databases|platforms|technologies|"
    r"programming languages?|libraries|cloud|devops|testing tools?)\b"
)
PERSON_NAME_BLOCKLIST = {
    "management", "planning", "development", "assessment", "communication", "pedagogy",
    "teaching", "analysis", "analytics", "framework", "testing", "learning", "vision",
    "engineering", "science", "automation", "protocols", "tools", "skills",
}
NAME_FIELD_LABELS = {"mobile", "phone", "email", "dob", "date", "address", "contact"}
COMMON_WORD_SKILLS = {"office", "word", "go"}
NAME_SECTION_PRIORITY_LABELS = (
    "header",
    "contact",
    "personal",
    "top_lines",
    "emphasis",
)
NAME_SECTION_WEIGHT = {
    "header": 0,
    "contact": 1,
    "personal": 2,
    "top_lines": 3,
    "emphasis": 4,
}
NAME_IGNORE_LINE_PATTERN = re.compile(
    r"(?i)\b(?:resume|curriculum vitae|curriculum|vitae|cv|profile|summary)\b"
)
SKILL_SUBSECTION_HEADER_PATTERN = re.compile(
    r"(?i)^\s*(?:languages?|frameworks?|tools?|databases?|platforms?|libraries|cloud|devops|testing(?: tools?)?|"
    r"technologies|expertise|tech(?:nical)? stack)\s*[:\-]?\s*$"
)
SKILL_INLINE_SUBSECTION_PATTERN = re.compile(
    r"(?i)\b(?:languages?|frameworks?|tools?|databases?|platforms?|libraries|cloud|devops|testing(?: tools?)?|technologies)\s*:\s*"
)
EXPERIENCE_SKILL_SENTENCE_PATTERN = re.compile(
    r"(?i)\b(?:worked with|experience with|hands-on|used|using|built with|developed with|implemented with|technologies?:|stack:)\b"
)
COMMON_NON_TECH_EXPERIENCE_WORDS = {
    "worked", "developed", "responsible", "managed", "manage", "built", "using", "used",
    "experience", "team", "client", "projects", "project", "support", "analysis", "delivery",
}
TECHNICAL_LANGUAGE_HINT_PATTERN = re.compile(
    r"(?i)\b(?:python|java|javascript|typescript|c\+\+|c#|sql|go|golang|rust|scala|php|ruby|react|fastapi|node(?:\.js)?)\b"
)
HTML_MAILTO_PATTERN = re.compile(
    r"(?is)(?:href\s*=\s*[\"']mailto:(?P<href>[^\"'>\s]+)|mailto:(?P<plain>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}))"
)
BROKEN_EMAIL_LINE_PATTERN = re.compile(
    r"(?im)(?P<local>[A-Za-z0-9._%+-]+)\s*@\s*(?P<domain>[A-Za-z0-9.-]+)\s*\n\s*(?P<tld>\.[A-Za-z]{2,10})"
)
BROKEN_EMAIL_DOMAIN_PATTERN = re.compile(
    r"(?im)(?P<local>[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+)\s*\n\s*(?P<tld>\.[A-Za-z]{2,10})"
)
BROKEN_EMAIL_HTML_PATTERN = re.compile(
    r"(?im)(?P<local>[A-Za-z0-9._%+-]+)\s*@\s*(?:</?[^>]+>\s*)*(?P<domain>[A-Za-z0-9.-]+)\s*(?:</?[^>]+>\s*)*(?P<tld>\.[A-Za-z]{2,10})"
)


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


def _extract_skill_fallback_text(text: str) -> str:
    if not text:
        return ""

    normalized_lines = [line.strip() for line in normalize_document_structure(text).splitlines() if line.strip()]
    fallback_lines: List[str] = []
    capture_remaining = 0

    for line in normalized_lines[:120]:
        cleaned_line = line.strip(" -*\t")
        if not cleaned_line:
            capture_remaining = 0
            continue
        if SECTION_START_PATTERN.match(cleaned_line) and not SKILL_FALLBACK_LINE_PATTERN.search(cleaned_line):
            capture_remaining = 0
            continue
        if DATE_RANGE_REGEX.search(cleaned_line):
            capture_remaining = 0
            continue

        explicit_skill_label = SKILL_FALLBACK_LINE_PATTERN.search(cleaned_line) or SKILL_CHUNK_LEADIN_PATTERN.match(cleaned_line)
        if explicit_skill_label:
            fallback_lines.append(cleaned_line)
            capture_remaining = 3
            continue

        if capture_remaining > 0:
            if ROLE_TITLE_LINE_PATTERN.match(cleaned_line) or _looks_like_person_name_line(cleaned_line):
                capture_remaining = 0
                continue
            fallback_lines.append(cleaned_line)
            capture_remaining -= 1
            continue

    return _sanitize_skill_section("\n".join(fallback_lines))


def _looks_like_person_name_line(value: str) -> bool:
    compact = re.sub(r"\s+", " ", (value or "").strip())
    if not NAME_LIKE_SKILL_PATTERN.match(compact):
        return False
    lowered_tokens = [token.strip(".,").lower() for token in compact.split()]
    if any(token in PERSON_NAME_BLOCKLIST for token in lowered_tokens):
        return False
    return True

_skillner_extractor = None
_skillner_state = {
    "checked": False,
    "installed": False,
    "usable": False,
}
_skill_keyword_processor = None
_skill_keyword_processor_lock = Lock()
_skill_validation_lookups = None
_skill_validation_lock = Lock()
_skill_alias_values = set(SKILL_ALIASES.values())
_skill_alias_keys = set(SKILL_ALIASES.keys())


def _get_skill_intelligence():
    return get_skill_engine()


def _get_skill_validation_lookups() -> tuple[set[str], set[str]]:
    global _skill_validation_lookups

    if _skill_validation_lookups is not None:
        return _skill_validation_lookups

    with _skill_validation_lock:
        if _skill_validation_lookups is not None:
            return _skill_validation_lookups

        skill_engine = _get_skill_intelligence()
        _skill_validation_lookups = (
            set(getattr(skill_engine, "skill_dictionary", set())),
            set(getattr(skill_engine, "synonym_dictionary", {}).values()),
        )

    return _skill_validation_lookups


def _get_skill_keyword_processor() -> KeywordProcessor:
    global _skill_keyword_processor

    if _skill_keyword_processor is not None:
        return _skill_keyword_processor

    with _skill_keyword_processor_lock:
        if _skill_keyword_processor is not None:
            return _skill_keyword_processor

        skill_engine = _get_skill_intelligence()
        processor = KeywordProcessor(case_sensitive=False)
        for skills in getattr(skill_engine, "domain_skills", {}).values():
            for skill in skills:
                if _is_valid_skill_candidate(skill):
                    processor.add_keyword(skill, skill)
        for alias, canonical in SKILL_ALIASES.items():
            if _is_valid_skill_candidate(alias) and _is_valid_skill_candidate(canonical):
                processor.add_keyword(alias, canonical)

        _skill_keyword_processor = processor

    return _skill_keyword_processor


def warm_skill_keyword_processor() -> Dict[str, Any]:
    processor = _get_skill_keyword_processor()
    skill_dictionary_lookup, skill_synonym_lookup = _get_skill_validation_lookups()
    sample_matches = processor.extract_keywords("Python FastAPI Docker SQL")
    return {
        "processor_ready": processor is not None,
        "sample_match_count": len(sample_matches),
        "skill_dictionary_lookup_count": len(skill_dictionary_lookup),
        "skill_synonym_lookup_count": len(skill_synonym_lookup),
    }


def _skillner_installed() -> bool:
    return importlib.util.find_spec("skillNer") is not None


def _is_valid_skill_candidate(skill: str) -> bool:
    normalized = (skill or "").strip().lower()
    if not normalized or normalized in LANGUAGE_TERMS:
        return False
    return not _get_skill_intelligence()._is_noise(normalized)


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
    skill_engine = _get_skill_intelligence()
    canonical_skill = skill_engine.get_synonym_dictionary().get(normalized, normalized)
    if len(normalized_tokens) > 2 and canonical_skill not in skill_engine.get_skill_dictionary():
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
    skill_engine = _get_skill_intelligence()
    canonical_chunk = skill_engine.get_synonym_dictionary().get(aliased_chunk, aliased_chunk)
    if not normalized_skill or not normalized_chunk:
        return False
    if skill_engine._is_noise(normalized_skill):
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


def _extract_contact_priority_blocks(text: str, *, include_document_fallback: bool = False) -> List[str]:
    normalized_text = normalize_document_structure(text or "")
    if not normalized_text:
        return []
    sections = segment_resume_sections(normalized_text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    personal_details = "\n".join(_extract_personal_detail_lines(lines))
    summary_like = "\n".join(
        filter(None, [sections.get("summary", ""), sections.get("profile", ""), sections.get("about", "")])
    )
    ordered_parts = [
        "\n".join(lines[:5]),
        sections.get("header", ""),
        sections.get("contact", ""),
        personal_details,
        summary_like,
    ]
    if include_document_fallback:
        ordered_parts.append(normalized_text)

    deduped: List[str] = []
    seen = set()
    for part in ordered_parts:
        compact = normalize_text(part or "")
        if not compact or compact in seen:
            continue
        seen.add(compact)
        deduped.append(compact)
    return deduped


def _collect_name_priority_candidates(text: str) -> List[Dict[str, Any]]:
    normalized_text = normalize_document_structure(text or "")
    if not normalized_text:
        return []

    sections = segment_resume_sections(normalized_text)
    lines = [line.strip() for line in normalized_text.splitlines() if line.strip()]
    personal_lines = _extract_personal_detail_lines(lines)
    priority_sources = [
        ("header", sections.get("header", "") or "\n".join(lines[:4])),
        ("contact", sections.get("contact", "") or "\n".join(lines[:8])),
        ("personal", "\n".join(personal_lines[:10])),
        ("top_lines", "\n".join(lines[:3])),
        ("emphasis", "\n".join(line for line in lines[:8] if len(line.split()) <= 6)),
    ]

    ordered_candidates: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, int]] = set()
    for source_label, source_text in priority_sources:
        for line_index, raw_line in enumerate(str(source_text or "").splitlines()):
            compact_line = re.sub(r"\s+", " ", raw_line.strip())
            if not compact_line:
                continue
            if NAME_IGNORE_LINE_PATTERN.search(compact_line):
                continue
            ordered_candidates.append(
                {
                    "text": compact_line,
                    "source": source_label,
                    "line_index": line_index,
                }
            )
            seen.add((source_label, compact_line.lower(), line_index))

    for line_index, raw_line in enumerate(lines[:12]):
        compact_line = re.sub(r"\s+", " ", raw_line.strip())
        key = ("top_lines", compact_line.lower(), line_index)
        if not compact_line or key in seen or NAME_IGNORE_LINE_PATTERN.search(compact_line):
            continue
        ordered_candidates.append({"text": compact_line, "source": "top_lines", "line_index": line_index})

    return ordered_candidates


def _score_name_candidate_line(candidate: str, *, source: str, line_index: int) -> tuple[int, int, int, int, int]:
    compact = re.sub(r"\s+", " ", candidate.strip())
    words = compact.split()
    proper_case_words = sum(1 for word in words if re.match(r"^[A-Z][A-Za-z'`.-]+$", word))
    uppercase_words = sum(1 for word in words if re.match(r"^[A-Z][A-Z'`.-]+$", word))
    contact_bonus = 1 if any(token in compact.lower() for token in ("@", "+", "linkedin", "github")) else 0
    return (
        -NAME_SECTION_WEIGHT.get(source, 99),
        contact_bonus,
        proper_case_words,
        uppercase_words,
        -line_index,
    )


def _extract_subsection_skill_text(section_text: str) -> str:
    if not section_text:
        return ""

    lines = [line.strip() for line in normalize_document_structure(section_text).splitlines() if line.strip()]
    collected: List[str] = []
    capture_remaining = 0
    for line in lines:
        if SKILL_SECTION_BREAK_PATTERN.match(line):
            break
        if SKILL_SUBSECTION_HEADER_PATTERN.match(line):
            collected.append(line)
            capture_remaining = 4
            continue
        if SKILL_INLINE_SUBSECTION_PATTERN.search(line):
            collected.append(line)
            continue
        if capture_remaining > 0:
            if DATE_RANGE_REGEX.search(line) or ROLE_TITLE_LINE_PATTERN.match(line):
                capture_remaining = 0
                continue
            collected.append(line)
            capture_remaining -= 1
    return "\n".join(collected)


def _extract_experience_skill_fallback_text(experience_text: str) -> str:
    if not experience_text:
        return ""

    normalized_lines = [line.strip() for line in normalize_document_structure(experience_text).splitlines() if line.strip()]
    candidate_lines: List[str] = []
    for line in normalized_lines[:80]:
        if DATE_RANGE_REGEX.search(line):
            continue
        if len(line.split()) > 20:
            continue
        lowered = line.lower()
        if not EXPERIENCE_SKILL_SENTENCE_PATTERN.search(lowered) and not SKILL_INLINE_SUBSECTION_PATTERN.search(line):
            continue
        candidate_lines.append(line)
    return "\n".join(candidate_lines)


def _augment_skills_section_with_related_blocks(
    skills_section: str,
    *,
    languages_section: str = "",
    header_section: str = "",
) -> str:
    augmented_parts = [skills_section] if skills_section else []
    for candidate_section in (languages_section, header_section):
        normalized_section = normalize_document_structure(candidate_section or "")
        if not normalized_section:
            continue
        if SKILL_INLINE_SUBSECTION_PATTERN.search(normalized_section) or SKILL_SUBSECTION_HEADER_PATTERN.search(normalized_section):
            augmented_parts.append(normalized_section)
            continue
        if TECHNICAL_LANGUAGE_HINT_PATTERN.search(normalized_section):
            augmented_parts.append(normalized_section)
    return "\n".join(part for part in augmented_parts if part).strip()


def _select_latest_experience_entry(entries: List[Dict[str, Any]], preferred_company: str = "", preferred_role: str = "") -> Dict[str, Any]:
    if not entries:
        return {}

    preferred_company_key = str(preferred_company or "").strip().lower()
    preferred_role_key = str(preferred_role or "").strip().lower()
    for entry in entries:
        if (
            preferred_company_key
            and preferred_role_key
            and str(entry.get("company") or "").strip().lower() == preferred_company_key
            and str(entry.get("role") or "").strip().lower() == preferred_role_key
        ):
            return entry

    from ats.extraction.experience_extraction import parse_date

    def _entry_sort_key(item: Dict[str, Any]) -> tuple[int, Any, Any]:
        end_value = parse_date(str(item.get("end_date") or ""), is_end=True)
        start_value = parse_date(str(item.get("start_date") or ""), is_end=False)
        return (
            1 if item.get("is_current") else 0,
            end_value or datetime.min,
            start_value or datetime.min,
        )

    ordered = sorted(entries, key=_entry_sort_key, reverse=True)
    return ordered[0] if ordered else {}


def _normalize_phone_candidate(value: str) -> str:
    candidate = re.sub(r"\s+", " ", (value or "").strip(" ,.;:"))
    candidate = re.sub(r"\s*-\s*", "-", candidate)
    if ")" in candidate and not candidate.startswith("("):
        candidate = f"({candidate}"
    return candidate.strip()


def _phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def _looks_like_valid_phone(value: str) -> bool:
    digits = _phone_digits(value)
    if not (10 <= len(digits) <= 15):
        return False
    if len(digits) == 11 and digits.startswith("1800"):
        return False
    if len(digits) == 10 and digits.startswith(("0", "1")):
        return False
    return True


def _phone_priority(value: str) -> tuple[int, int]:
    digits = _phone_digits(value)
    if digits.startswith("91") and len(digits) == 12 and digits[2] in "6789":
        return (0, 0)
    if len(digits) == 10 and digits[:1] in "6789":
        return (1, 0)
    if len(digits) == 11 and digits.startswith("1"):
        return (2, 0)
    if len(digits) == 10:
        return (3, 0)
    return (4, len(digits))


def extract_name(text: str, use_spacy: bool = True) -> str:
    if not text:
        return ""

    strict_name, _ = _extract_name_and_role_from_first_line(text)
    if strict_name:
        return strict_name

    priority_blocks = _extract_contact_priority_blocks(text, include_document_fallback=False)
    lines: List[str] = []
    seen_lines = set()
    for block in priority_blocks:
        for line in block.splitlines():
            compact_line = line.strip()
            if not compact_line or compact_line in seen_lines:
                continue
            seen_lines.add(compact_line)
            lines.append(compact_line)
    if not lines:
        lines = _clean_header_lines(text, limit=12)
    first_five_lines = lines[:5]
    first_three_lines = [line for line in lines[:3] if not SECTION_START_PATTERN.match(line)]
    header_priority_lines = first_three_lines[:2] or first_five_lines[:2]

    def _sanitize_name_candidate(candidate: str) -> str:
        compact = re.sub(r"\s+", " ", candidate.strip(" ,.-"))
        compact = re.sub(r"(?i)^(?:name)\s*[:\-]\s*", "", compact).strip()
        compact = re.split(r"\s+\|\s+|\s+[Â·â€¢]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", compact, maxsplit=1)[0].strip()
        tokens = []
        for token in compact.split():
            cleaned = token.strip(" ,.-")
            lowered = cleaned.lower()
            if lowered in NAME_FIELD_LABELS or any(char.isdigit() for char in cleaned) or "@" in cleaned:
                break
            tokens.append(cleaned)
        return " ".join(tokens).strip()

    def _format_name(candidate: str) -> str:
        return " ".join(part.capitalize() if len(part) > 1 else part.upper() for part in candidate.split())

    def _is_valid_name_line(candidate: str) -> bool:
        compact = _sanitize_name_candidate(candidate)
        lowered = compact.lower()
        if not compact:
            return False
        if any(term in lowered for term in NAME_IGNORE_TERMS):
            return False
        if NAME_FALLBACK_BLOCKLIST_PATTERN.search(compact):
            return False
        if NAME_COMPANY_PATTERN.search(compact):
            return False
        if validate_location(compact):
            return False
        if ROLE_TITLE_LINE_PATTERN.match(compact):
            return False
        if ROLE_KEYWORD_PATTERN.search(compact):
            return False
        if any(char.isdigit() for char in compact):
            return False
        if "@" in compact:
            return False
        if NON_NAME_CHARS_PATTERN.search(compact):
            return False
        words = compact.split()
        if not (2 <= len(words) <= 4):
            return False
        normalized_candidate = clean_text_pipeline(compact).lower()
        skill_engine = _get_skill_intelligence()
        if (
            normalized_candidate in skill_engine.get_skill_dictionary()
            or normalized_candidate in skill_engine.get_synonym_dictionary()
            or normalized_candidate in skill_engine.get_synonym_dictionary().values()
        ):
            return False
        capitalized_count = sum(1 for word in words if re.match(r"^[A-Z][A-Za-z'`.-]+$", word))
        return capitalized_count >= max(2, len(words) - 1)

    for line in header_priority_lines:
        stripped = line.strip()
        if SECTION_START_PATTERN.match(stripped):
            continue
        label_match = _sanitize_name_candidate(stripped)
        inline_candidate = re.split(r"\s+\|\s+|\s+[Â·â€¢]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", label_match, maxsplit=1)[0].strip()
        if _is_valid_name_line(inline_candidate):
            resolved = _format_name(inline_candidate)
            logger.debug("Name extracted from header block: %s", resolved)
            return resolved

    if use_spacy and SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(first_five_lines or lines[:8]))
        if doc:
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                candidate = re.sub(r"\s+", " ", ent.text).strip(" ,.-")
                if _is_valid_name_line(candidate):
                    resolved = _format_name(candidate)
                    logger.debug("Name extracted with spaCy PERSON in header: %s", resolved)
                    return resolved

    for line in first_three_lines:
        candidate = _sanitize_name_candidate(line)
        candidate = re.split(r"\s+\|\s+|\s+[Â·â€¢]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", candidate, maxsplit=1)[0].strip()
        if UPPERCASE_NAME_PATTERN.match(candidate) and _is_valid_name_line(candidate):
            resolved = _format_name(candidate)
            logger.debug("Name extracted from uppercase header line: %s", resolved)
            return resolved

    for line in first_five_lines:
        leading_candidate = re.match(r"^(?P<value>[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3})\b", _sanitize_name_candidate(line))
        if leading_candidate:
            candidate = leading_candidate.group("value").strip()
            role_noise = {"engineer", "analyst", "developer", "tester", "consultant", "manager", "specialist", "architect"}
            candidate_tokens = [token.lower() for token in candidate.split()]
            if not any(token in role_noise for token in candidate_tokens) and _is_valid_name_line(candidate):
                resolved = _format_name(candidate)
                logger.debug("Name extracted from leading header tokens: %s", resolved)
                return resolved
        candidate = _sanitize_name_candidate(line)
        candidate = re.split(r"\s+\|\s+|\s+[·•]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", candidate, maxsplit=1)[0].strip()
        if _is_valid_name_line(candidate):
            resolved = _format_name(candidate)
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
                    resolved = _format_name(candidate)
                    logger.debug("Name extracted with spaCy PERSON: %s", resolved)
                    return resolved

    if use_spacy and SPACY_AVAILABLE:
        doc = get_section_doc("\n".join(lines[:8]))
        if doc:
            for ent in doc.ents:
                if ent.label_ != "PERSON":
                    continue
                candidate = _sanitize_name_candidate(ent.text)
                if _is_valid_name_line(candidate):
                    logger.debug("Fallback used for name extraction")
                    return _format_name(candidate)

    for line in _clean_header_lines(text, limit=40):
        candidate = _sanitize_name_candidate(line)
        if _is_valid_name_line(candidate):
            logger.debug("Fallback used for name extraction")
            return _format_name(candidate)

    for block in _extract_contact_priority_blocks(text, include_document_fallback=True):
        for line in block.splitlines():
            candidate = _sanitize_name_candidate(line)
            if _is_valid_name_line(candidate):
                logger.debug("Fallback used for name extraction")
                return _format_name(candidate)

    scored_candidates: List[tuple[tuple[int, int, int, int, int], str]] = []
    for candidate_meta in _collect_name_priority_candidates(text):
        candidate = _sanitize_name_candidate(candidate_meta["text"])
        if not _is_valid_name_line(candidate):
            continue
        score = _score_name_candidate_line(
            candidate_meta["text"],
            source=str(candidate_meta["source"]),
            line_index=int(candidate_meta["line_index"]),
        )
        scored_candidates.append((score, candidate))
    if scored_candidates:
        scored_candidates.sort(reverse=True)
        resolved = _format_name(scored_candidates[0][1])
        logger.debug("Name extracted from scored fallback candidate: %s", resolved)
        return resolved

    return ""


def _extract_fallback_experience_years(*sources: str) -> Optional[float]:
    candidates: List[float] = []
    for source in sources:
        normalized_source = clean_text_pipeline(source or "")
        if not normalized_source:
            continue
        for match in EXPLICIT_TOTAL_EXPERIENCE_PATTERN.finditer(normalized_source):
            years_value = float(match.group("years"))
            months_value = int(match.group("months") or 0)
            candidates.append(round(years_value + (months_value / 12.0), 1))
        for match in FALLBACK_TOTAL_EXPERIENCE_PATTERN.finditer(normalized_source):
            candidates.append(round(float(match.group("years")), 1))
    if not candidates:
        return None
    return max(candidates)


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
        category = _get_skill_intelligence().category_map.get(normalized)
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
    skill_dictionary_lookup, skill_synonym_lookup = _get_skill_validation_lookups()
    if normalized in skill_dictionary_lookup:
        return "high" if from_section else "medium"
    if normalized in skill_synonym_lookup:
        return "medium"
    if normalized in _skill_alias_values or normalized in _skill_alias_keys:
        return "medium"
    lowered_source = clean_text_pipeline(source_text or "").lower()
    if re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", lowered_source):
        return "medium" if from_section else "low"
    if not from_section and normalized in _extract_skillner_keywords(source_text):
        return "medium"
    return "low"


def _is_validated_skill(skill: str, source_text: str, from_section: bool, blocked_locations: set[str]) -> bool:
    normalized = normalize_skill_name(skill)
    if not normalized:
        return False
    if normalized in EXCLUDED_SOFT_SKILLS and normalized not in ALLOWED_SOFT_SKILLS:
        return False
    if normalized in blocked_locations or normalized in KNOWN_LOCATION_SKILLS_BLOCKLIST:
        return False
    skill_engine = _get_skill_intelligence()
    if skill_engine._is_noise(normalized):
        return False
    if _skill_confidence(normalized, source_text, from_section) == "low":
        return False
    skill_dictionary_lookup, skill_synonym_lookup = _get_skill_validation_lookups()
    in_esco = normalized in skill_dictionary_lookup
    in_synonyms = normalized in skill_synonym_lookup
    in_custom = normalized in _skill_alias_values or normalized in _skill_alias_keys
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


def _finalize_skills(
    skills: List[str],
    source_text: str,
    location_text: str,
    from_section: bool,
    *,
    name_text: str = "",
    education_entries: Optional[List[Dict[str, str]]] = None,
    header_text: str = "",
    experience_text: str = "",
    skills_text: str = "",
) -> List[str]:
    blocked_locations = set(_extract_gpe_entities(location_text)) if location_text else set()
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
    blocked_terms = {part.strip().lower() for part in clean_text_pipeline(name_text).split() if part.strip()}
    blocked_terms.update(part.strip().lower() for part in normalized_location_text.split(",") if part.strip())
    for entry in education_entries or []:
        institution = clean_text_pipeline(entry.get("institution") or "")
        blocked_terms.update(token for token in institution.split() if token)
    header_lower = clean_text_pipeline(header_text or "").lower()
    experience_lower = clean_text_pipeline(experience_text or "").lower()
    skills_lower = clean_text_pipeline(skills_text or source_text or "").lower()
    filtered_skills: List[str] = []
    for skill in validated:
        if len(skill) < 2:
            continue
        if skill in blocked_terms:
            continue
        if skill in COMMON_WORD_SKILLS:
            if not (
                re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", skills_lower)
                or re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", experience_lower)
            ):
                continue
        if re.search(rf"(?<!\w){re.escape(skill)}(?!\w)", header_lower) and not re.search(
            rf"(?<!\w){re.escape(skill)}(?!\w)", skills_lower
        ):
            continue
        filtered_skills.append(skill)
    validated = _expand_parent_skills(_unique_in_order(_suppress_generic_overlaps(filtered_skills)))
    return _unique_in_order(validated)[:50]


def _extract_contextual_skills(*sections: str) -> List[str]:
    skill_engine = _get_skill_intelligence()
    skill_keyword_processor = _get_skill_keyword_processor()
    matches: List[str] = []
    for section in sections:
        normalized_section = clean_text_pipeline(section or "")
        if not normalized_section:
            continue
        matches.extend(skill_keyword_processor.extract_keywords(normalized_section))
        matches.extend(skill_engine.extract_skills(normalized_section))
        matches.extend(_extract_skillner_keywords(normalized_section))
        for sentence in SKILL_SENTENCE_SPLIT_PATTERN.split(normalized_section):
            sentence = sentence.strip()
            if not sentence:
                continue
            if not re.search(r"(?i)\b(?:worked on|built|developed|implemented|used|deploy|designed|experience with|services?|apis?)\b", sentence):
                continue
            matches.extend(skill_keyword_processor.extract_keywords(sentence))
            matches.extend(skill_engine.extract_skills(sentence))
            matches.extend(_extract_skillner_keywords(sentence))
    return _unique_in_order(matches)


def extract_skill_keywords(text: str, section_text: str = "") -> List[str]:
    skill_engine = _get_skill_intelligence()
    skill_keyword_processor = _get_skill_keyword_processor()
    source = _sanitize_skill_section(section_text) if section_text else ""
    if source:
        subsection_text = _extract_subsection_skill_text(source)
        if subsection_text:
            source = "\n".join(filter(None, [source, subsection_text]))
    if not source:
        source = _extract_skill_fallback_text(text)
    experience_skill_context = _extract_experience_skill_fallback_text(
        segment_resume_sections(text or "").get("experience", "")
    )
    if experience_skill_context and experience_skill_context not in source:
        source = "\n".join(filter(None, [source, experience_skill_context]))
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
        chunk_matches.extend(skill_keyword_processor.extract_keywords(chunk))
        chunk_matches.extend(skill_engine.extract_skills(chunk))
        if not chunk_matches and len(chunk.split()) >= 2:
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
    section_matches.extend(skill_keyword_processor.extract_keywords(normalized_section))
    section_matches.extend(skill_engine.extract_skills(normalized_section))
    if not section_matches:
        section_matches.extend(_extract_skillner_keywords(normalized_section))
    matches.extend(_filter_section_level_matches(section_matches, normalized_section))

    if not matches and SPACY_AVAILABLE:
        doc = get_section_doc(normalized_section)
        if doc is not None:
            for chunk in doc.noun_chunks:
                candidate = normalize_skill_name(chunk.text)
                if len(candidate.split()) > 4:
                    continue
                if candidate in skill_engine.get_synonym_dictionary():
                    matches.append(skill_engine.get_synonym_dictionary()[candidate])
                elif candidate in skill_engine.get_skill_dictionary():
                    matches.append(candidate)

    normalized_matches = skill_engine.map_skills(matches)
    contextual_matches = _extract_contextual_skills(experience_skill_context, source)
    contextual_matches = [
        skill for skill in contextual_matches
        if skill and skill.lower() not in COMMON_NON_TECH_EXPERIENCE_WORDS
    ]
    merged_matches = [*normalized_matches, *contextual_matches]
    return _unique_in_order(_suppress_generic_overlaps(merged_matches))[:50]


def extract_email(text: str) -> str:
    if not text:
        return ""

    def _clean_email_candidate(candidate: str) -> str:
        candidate = candidate.replace("mailto:", "").replace("MAILTO:", "")
        candidate = re.sub(r"\s+", "", candidate)
        candidate = re.sub(r"(?<=\w),(?=\w)", "", candidate)
        candidate = candidate.strip("()[]{}<>.,;:")
        at_index = candidate.find("@")
        domain_part = candidate[at_index + 1:] if at_index >= 0 else candidate
        com_match = re.search(r"\.com", domain_part, re.IGNORECASE)
        if com_match:
            return candidate[: at_index + 1 + com_match.end()] if at_index >= 0 else candidate[:com_match.end()]
        tld_match = re.search(r"\.[a-zA-Z]{2,6}(?=[^a-zA-Z]|$)", domain_part)
        if tld_match:
            return candidate[: at_index + 1 + tld_match.end()] if at_index >= 0 else candidate[:tld_match.end()]
        return candidate

    def _email_priority(candidate: str) -> tuple[int, int]:
        lowered = candidate.lower()
        personal_markers = ("gmail.", "yahoo.", "outlook.", "hotmail.", "icloud.", "proton.")
        return (0 if any(marker in lowered for marker in personal_markers) else 1, len(candidate))

    def _prepare_email_text(source_text: str) -> tuple[str, str]:
        normalized_text = normalize_common_artifacts(source_text or "")
        normalized_text = BROKEN_EMAIL_LINE_PATTERN.sub(
            lambda m: f"{m.group('local')}@{m.group('domain')}{m.group('tld')}",
            normalized_text,
        )
        normalized_text = BROKEN_EMAIL_DOMAIN_PATTERN.sub(
            lambda m: f"{m.group('local')}{m.group('tld')}",
            normalized_text,
        )
        normalized_text = BROKEN_EMAIL_HTML_PATTERN.sub(
            lambda m: f"{m.group('local')}@{m.group('domain')}{m.group('tld')}",
            normalized_text,
        )
        normalized_text = re.sub(r"(\w+)\s*@\s*\n\s*(\w+\.\w+)", r"\1@\2", normalized_text)
        normalized_text = re.sub(
            r"(?i)([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]{1,8})\s*\n\s*([A-Za-z0-9.-]{1,12}\.[A-Za-z]{2,6})",
            lambda m: f"{m.group(1)}@{m.group(2)}{m.group(3)}",
            normalized_text,
        )
        normalized_text = re.sub(
            r"(?im)([A-Za-z0-9._%+-]+)\s*@\s*\n(?:[A-Z][A-Z\s.]{3,}\n)+\s*([A-Za-z0-9.-]+\.[A-Za-z]{2,6})",
            lambda m: f"{m.group(1)}@{m.group(2)}",
            normalized_text,
        )
        normalized_text = re.sub(
            r"(?im)([A-Za-z0-9._%+-]+)\s*@\s*\n(?:[A-Z][A-Z\s]{3,}\n)?\s*([A-Za-z0-9.-]+\.[A-Za-z]{2,6})",
            lambda m: f"{m.group(1)}@{m.group(2)}",
            normalized_text,
        )
        normalized_text = normalized_text.replace("mailto:", " ").replace("MAILTO:", " ")
        normalized_text = re.sub(
            r"([A-Za-z0-9._%+-]+)\s*@\s*([A-Za-z0-9,._-]+\.[A-Za-z]{2,6})",
            lambda m: f"{m.group(1)}@{m.group(2).replace(',', '')}",
            normalized_text,
        )
        compact_text = normalized_text.replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
        compact_text = compact_text.replace("(dot)", ".").replace("[dot]", ".").replace(" dot ", ".")
        return normalized_text, compact_text

    candidates: List[str] = []
    seen_candidates: set[str] = set()
    search_blocks = _extract_contact_priority_blocks(text, include_document_fallback=True)
    for block_index, block in enumerate(search_blocks):
        normalized_text, compact_text = _prepare_email_text(block)
        for mailto_match in HTML_MAILTO_PATTERN.finditer(normalized_text):
            raw_value = mailto_match.group("href") or mailto_match.group("plain") or ""
            email = _clean_email_candidate(raw_value)
            lowered = email.lower()
            if not email or "@" not in email or lowered in seen_candidates:
                continue
            seen_candidates.add(lowered)
            candidates.append(email)
            logger.debug("Email href/mailto match (%s): %s", block_index, email)
        for source_text, source_label in (
            (normalized_text, f"normalized_{block_index}"),
            (compact_text, f"compact_{block_index}"),
        ):
            for pattern, label in (
                (BRACKETED_EMAIL_PATTERN, "bracketed"),
                (STRONG_EMAIL_PATTERN, "strong"),
                (RELAXED_EMAIL_PATTERN, "relaxed"),
                (ROBUST_EMAIL_PATTERN, "robust"),
                (STRICT_EMAIL_PATTERN, "strict"),
            ):
                for match in pattern.finditer(source_text):
                    raw_value = match.group("email") if "email" in match.groupdict() else match.group(0)
                    email = _clean_email_candidate(raw_value)
                    if not email or "@" not in email:
                        continue
                    lowered = email.lower()
                    if lowered in seen_candidates:
                        continue
                    seen_candidates.add(lowered)
                    candidates.append(email)
                    logger.debug("Email regex match (%s/%s): %s", source_label, label, email)

    ordered_candidates = sorted(candidates, key=_email_priority)
    for email in ordered_candidates:
        if STRONG_EMAIL_PATTERN.fullmatch(email):
            logger.debug("Email extracted from strong candidate list: %s", email)
            return email
    if ordered_candidates:
        logger.debug("Email extracted from fallback candidate list: %s", ordered_candidates[0])
        return ordered_candidates[0]
    return ""


def extract_phone(text: str) -> str:
    if not text:
        return ""

    candidates: List[str] = []
    seen = set()
    search_blocks = _extract_contact_priority_blocks(text, include_document_fallback=True)
    for block in search_blocks:
        normalized_text = normalize_common_artifacts(block or "")
        for pattern in PHONE_PATTERNS:
            match = pattern.search(normalized_text)
            if not match:
                continue
            candidate = _normalize_phone_candidate(match.group(1))
            digits = _phone_digits(candidate)
            if digits in seen or not _looks_like_valid_phone(candidate):
                continue
            seen.add(digits)
            candidates.append(candidate)
        for match in PHONE_CANDIDATE_PATTERN.finditer(normalized_text):
            candidate = _normalize_phone_candidate(match.group(1))
            digits = _phone_digits(candidate)
            if digits in seen or not _looks_like_valid_phone(candidate):
                continue
            seen.add(digits)
            candidates.append(candidate)

    if candidates:
        selected = sorted(candidates, key=_phone_priority)[0]
        logger.debug("Phone extracted: %s", selected)
        return selected
    return ""


def extract_experience_entries(text: str, experience_section: str = "") -> List[Dict]:
    if not experience_section.strip():
        return []
    source_text = f"Experience\n{experience_section}"
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


def extract_location(text: str, use_spacy: bool = True) -> str:
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
    if _is_location_noise_candidate(candidate):
        return False
    if _contains_non_location_context(candidate):
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
        return lowered in LOCATION_CONNECTOR_TERMS or lowered in LOCATION_TAIL_TOKENS
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
    if len(words) == 2 and words[1].lower() in (LOCATION_TAIL_TOKENS | set(LOCATION_CANONICAL_OVERRIDES.keys())):
        words = words[1:]
    if len(words) == 2 and words[0].lower() in LOCATION_ROLE_BLOCKLIST:
        words = words[1:]
    return " ".join(words)


def _extract_city_from_address_block(lines: List[str]) -> str:
    if not lines:
        return ""
    search_text = "\n".join(lines[:10])
    label_match = ADDRESS_LABEL_PATTERN.search(search_text)
    if label_match:
        search_text = f"{label_match.group('value')}\n" + "\n".join(lines[1:10])

    district_candidates: List[str] = []
    for match in ADDRESS_CITY_HINT_PATTERN.finditer(search_text):
        candidate = re.sub(r"\s+", " ", match.group("city")).strip(" ,.-")
        if candidate and not LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(candidate.lower()):
            district_candidates.append(candidate)
    if district_candidates:
        return district_candidates[-1]

    pin_match = ADDRESS_PIN_CITY_PATTERN.search(search_text)
    if pin_match:
        candidate = re.sub(r"\s+", " ", pin_match.group("city")).strip(" ,.-")
        candidate_words = candidate.split()
        if len(candidate_words) > 2:
            candidate = candidate_words[-1]
        if candidate and candidate.lower() not in INVALID_LOCATION_WORDS:
            return candidate

    comma_parts = [part.strip(" ,.-") for part in re.split(r"[\n,]+", search_text) if part.strip()]
    for part in reversed(comma_parts):
        lowered = part.lower()
        if any(char.isdigit() for char in part):
            continue
        if lowered in INVALID_LOCATION_WORDS or lowered in INVALID_LOCATION_LABELS:
            continue
        if LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(lowered):
            continue
        words = part.split()
        if 1 <= len(words) <= 3 and all(word[:1].isalpha() for word in words):
            return words[-1].strip(" ,.-")
    return ""


def _is_location_noise_candidate(value: str) -> bool:
    compact = re.sub(r"\s+", " ", (value or "").strip(" ,.|/:-"))
    if not compact:
        return True
    lowered = compact.lower()
    if NAME_LIKE_SKILL_PATTERN.match(compact):
        return True
    if ROLE_KEYWORD_PATTERN.search(compact):
        return True
    if lowered in INVALID_LOCATION_WORDS or lowered in INVALID_LOCATION_LABELS:
        return True
    if LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(lowered):
        return True
    return False


def _canonicalize_location_token(value: str) -> str:
    compact = re.sub(r"\s+", " ", (value or "").strip(" ,.|/:-"))
    lowered = LOCATION_CANONICAL_OVERRIDES.get(compact.lower(), compact.lower())
    if not lowered:
        return ""
    if " " in lowered or "-" in lowered:
        return " ".join(part.capitalize() for part in re.split(r"[\s-]+", lowered)).replace(" ", " ").replace("-", "-")
    return lowered.title()


def _canonicalize_location_pair(value: str) -> str:
    compact = re.sub(r"\s+", " ", (value or "").strip(" ,.|/:-"))
    if not compact:
        return ""
    parts = [part.strip(" ,.|/:-") for part in compact.split(",") if part.strip(" ,.|/:-")]
    if len(parts) < 2:
        return ""
    if any(_is_location_noise_candidate(part) for part in parts):
        return ""
    left = _canonicalize_location_token(parts[0])
    right = _canonicalize_location_token(parts[1])
    if not left or not right:
        return ""
    return f"{left}, {right}"


def _pick_primary_location(value: str) -> str:
    raw_value = re.sub(r"\s+", " ", (value or "").strip())
    normalized = _normalize_location_value(value or "")
    if not normalized:
        normalized = raw_value

    if "|" in raw_value:
        pipe_parts = [
            re.sub(r"\s+", " ", part).strip(" ,.|/:-")
            for part in raw_value.split("|")
            if re.sub(r"\s+", " ", part).strip(" ,.|/:-")
        ]
        for part in pipe_parts:
            lowered = part.lower()
            if (
                "@" in part
                or any(char.isdigit() for char in part)
                or lowered in INVALID_LOCATION_WORDS
                or lowered in INVALID_LOCATION_LABELS
                or SECTION_START_PATTERN.match(part)
                or _is_location_noise_candidate(part)
            ):
                continue
            comma_pair_match = re.search(
                r"(?P<left>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,3})\s*,\s*(?P<right>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})",
                part,
            )
            if comma_pair_match:
                left = _trim_location_segment(comma_pair_match.group("left"))
                pair_value = _canonicalize_location_pair(f"{left}, {comma_pair_match.group('right')}")
                if pair_value and not _contains_non_location_context(pair_value):
                    return pair_value
            if _looks_like_location_fragment(part):
                return _canonicalize_location_token(part)
            for token in sorted(LOCATION_TAIL_TOKENS | set(LOCATION_CANONICAL_OVERRIDES.keys()), key=len, reverse=True):
                if re.search(rf"(?i)\b{re.escape(token)}\b", part):
                    canonical = LOCATION_CANONICAL_OVERRIDES.get(token, token)
                    return _canonicalize_location_token(canonical)

    normalized_parts = [part.strip() for part in normalized.split(",") if part.strip()]
    if len(normalized_parts) == 2 and normalized_parts[1].lower() == "india":
        return _canonicalize_location_token(normalized_parts[0])

    comma_pair_match = re.search(
        r"(?P<left>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})\s*,\s*(?P<right>[A-Z][A-Za-z.-]+(?:\s+[A-Z][A-Za-z.-]+){0,2})",
        raw_value,
    )
    if comma_pair_match:
        pair_value = _canonicalize_location_pair(
            f"{_trim_location_segment(comma_pair_match.group('left'))}, {comma_pair_match.group('right')}"
        )
        if pair_value and not _contains_non_location_context(pair_value):
            return pair_value

    if any(char.isdigit() for char in raw_value):
        parts = [
            re.sub(r"\s+", " ", part).strip(" ,.|/:-")
            for part in re.split(r"[\n,]+", raw_value)
            if re.sub(r"\s+", " ", part).strip(" ,.|/:-")
        ]
        for part in reversed(parts):
            if any(char.isdigit() for char in part):
                continue
            if _contains_non_location_context(part):
                continue
            if _looks_like_location_fragment(part):
                return _canonicalize_location_token(part)

    for token in sorted(LOCATION_TAIL_TOKENS | set(LOCATION_CANONICAL_OVERRIDES.keys()), key=len, reverse=True):
        match = re.search(rf"(?i)\b{re.escape(token)}\b", raw_value)
        if not match:
            continue
        canonical = LOCATION_CANONICAL_OVERRIDES.get(token, token)
        return _canonicalize_location_token(canonical)

    city_candidates: List[tuple[int, str]] = []
    for token in sorted(LOCATION_TAIL_TOKENS | set(LOCATION_CANONICAL_OVERRIDES.keys()), key=len, reverse=True):
        match = re.search(rf"(?i)\b{re.escape(token)}\b", normalized)
        if not match:
            continue
        canonical = LOCATION_CANONICAL_OVERRIDES.get(token, token)
        city_candidates.append((match.start(), canonical))
    if city_candidates:
        city_candidates.sort(key=lambda item: item[0])
        return _canonicalize_location_token(city_candidates[0][1])

    for part in [segment.strip() for segment in LOCATION_SPLIT_PATTERN.split(normalized) if segment.strip()]:
        compact = re.sub(r"\s+", " ", part).strip(" ,.|/:-")
        if _looks_like_location_fragment(compact):
            return _canonicalize_location_token(compact)

    return _canonicalize_location_token(normalized) if _looks_like_location_fragment(normalized) else ""


def _extract_personal_detail_lines(lines: List[str], window: int = 20) -> List[str]:
    if not lines:
        return []

    captured: List[str] = []
    for index, line in enumerate(lines[:80]):
        combined_header = f"{line} {lines[index + 1]}" if index + 1 < len(lines) else line
        header_line_count = 1
        if PERSONAL_DETAILS_HEADER_PATTERN.match(combined_header):
            header_line_count = 2
        elif not PERSONAL_DETAILS_HEADER_PATTERN.match(line):
            continue
        for candidate in lines[index + header_line_count:index + header_line_count + window]:
            if PERSONAL_DETAILS_HEADER_PATTERN.match(candidate):
                break
            if re.match(
                r"(?i)^(?:work experience|professional experience|employment|experience|skills|technical skills|education|projects|summary|profile|certifications|awards|achievements|references)$",
                candidate,
            ):
                break
            captured.append(candidate)
    return captured


def _build_contact_context(*parts: str) -> str:
    ordered_lines: List[str] = []
    seen = set()
    for part in parts:
        for raw_line in normalize_document_structure(part or "").splitlines():
            line = raw_line.strip()
            if not line or line in seen:
                continue
            seen.add(line)
            ordered_lines.append(line)
    return "\n".join(ordered_lines)


def _get_header_contact_role_lines(text: str) -> tuple[str, str, str]:
    lines = [line.strip() for line in normalize_document_structure(text or "").splitlines() if line.strip()]
    return (
        lines[0] if len(lines) > 0 else "",
        lines[1] if len(lines) > 1 else "",
        lines[2] if len(lines) > 2 else "",
    )


def _normalize_header_role_line(value: str) -> str:
    candidate = clean_text_pipeline(value or "").strip(" ,|-")
    if not candidate:
        return ""
    candidate = re.sub(r"(?i)^(?:role|designation|title)\s*[:\-]\s*", "", candidate).strip()
    if SECTION_START_PATTERN.match(candidate):
        return ""
    if EMAIL_PATTERN.search(candidate) or any(pattern.search(candidate) for pattern in PHONE_PATTERNS):
        return ""
    if validate_location(candidate):
        return ""
    if ROLE_TITLE_LINE_PATTERN.match(candidate):
        return candidate
    words = candidate.split()
    if 2 <= len(words) <= 6 and HEADER_ROLE_STOP_PATTERN.search(candidate):
        return candidate
    return ""


def _extract_name_and_role_from_first_line(text: str) -> tuple[str, str]:
    name_line, _, role_line = _get_header_contact_role_lines(text)
    if not name_line:
        return "", _normalize_header_role_line(role_line)

    candidate = clean_text_pipeline(name_line).strip()
    candidate = re.sub(r"(?i)^(?:name)\s*[:\-]\s*", "", candidate).strip()
    pipe_segments = re.split(r"\s+\|\s+|\s+[Â·â€¢]\s+|, (?=\+?\d|[A-Za-z0-9._%+-]+@)", candidate)
    candidate = pipe_segments[0].strip()
    # Step 3: extract role from pipe segment (Name | Role | Skills pattern)
    pipe_role = ""
    if len(pipe_segments) > 1:
        for seg in pipe_segments[1:]:
            normalized_seg = _normalize_header_role_line(seg.strip())
            if normalized_seg:
                pipe_role = normalized_seg
                break
    if not candidate:
        return "", pipe_role or _normalize_header_role_line(role_line)

    extracted_role = _normalize_header_role_line(role_line)
    separator_match = HEADER_NAME_SEPARATOR_PATTERN.search(candidate)
    if separator_match:
        separator_tail = candidate[separator_match.end():].strip(" )|-")
        normalized_separator_role = _normalize_header_role_line(separator_tail)
        if normalized_separator_role:
            extracted_role = extracted_role or normalized_separator_role
            candidate = candidate[:separator_match.start()].strip(" ,|-")
    role_match = HEADER_ROLE_STOP_PATTERN.search(candidate)
    if role_match:
        extracted_role = extracted_role or _normalize_header_role_line(candidate[role_match.start():])
        candidate = candidate[:role_match.start()].strip(" ,|-")
        candidate = re.sub(r"(?i)\b(?:senior|sr|junior|jr|lead|principal|staff|associate|assistant)\b\s*$", "", candidate).strip()

    normalized_name = " ".join(part.capitalize() if len(part) > 1 else part.upper() for part in candidate.split())
    lowered_name = normalized_name.lower()
    if (
        not normalized_name
        or any(term in lowered_name for term in NAME_IGNORE_TERMS)
        or NAME_COMPANY_PATTERN.search(normalized_name)
        or validate_location(normalized_name)
        or any(char.isdigit() for char in normalized_name)
    ):
        normalized_name = ""
    else:
        words = normalized_name.split()
        if not (2 <= len(words) <= 4):
            normalized_name = ""
        elif not all(re.match(r"^[A-Z][A-Za-z'`.-]*$", word) for word in words):
            normalized_name = ""
    return normalized_name or "", extracted_role or pipe_role or ""


def _infer_unstructured_experience_section(text: str) -> str:
    lines = [line.strip() for line in normalize_document_structure(text or "").splitlines() if line.strip()]
    if not lines:
        return ""

    body_lines = lines[2:]
    collected: List[str] = []
    started = False
    previous_line = ""
    for line in body_lines:
        if UNSTRUCTURED_EXPERIENCE_STOP_PATTERN.match(line):
            break
        if UNSTRUCTURED_EDUCATION_HINT_PATTERN.search(line) and not DATE_RANGE_REGEX.search(line):
            if started:
                break
            previous_line = ""
            continue
        if DATE_RANGE_REGEX.search(line):
            if not started and previous_line:
                collected.append(previous_line)
            started = True
            collected.append(line)
            previous_line = ""
            continue
        if started:
            collected.append(line)
            previous_line = line
            continue
        if ROLE_TITLE_LINE_PATTERN.match(line) or re.search(r"\|", line):
            previous_line = line
            continue
        previous_line = line
    inferred = "\n".join(collected).strip()
    return inferred if DATE_RANGE_REGEX.search(inferred) else ""


def _contains_non_location_context(value: str) -> bool:
    tokens = {
        token.strip(".,:-").lower()
        for token in re.split(r"[\s,/|()]+", value or "")
        if token.strip(".,:-")
    }
    if not tokens:
        return False
    if tokens & NON_LOCATION_CONTEXT_TERMS and not tokens & LOCATION_TAIL_TOKENS:
        return True
    return False


def extract_location(text: str, use_spacy: bool = True) -> str:
    if not text:
        return ""

    cleaned_text = normalize_document_structure(text or "")
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    personal_detail_lines = _extract_personal_detail_lines(lines)
    header_lines = lines[:8]
    detected_name = extract_name(cleaned_text, use_spacy=False)
    name_index = next((idx for idx, line in enumerate(header_lines) if detected_name and detected_name.lower() in line.lower()), 0)
    name_window = lines[max(0, name_index - 1):min(len(lines), name_index + 4)]
    prioritized_lines = name_window + personal_detail_lines
    labeled_search_lines = name_window + personal_detail_lines

    for line in labeled_search_lines[:20]:
        if re.match(r"(?i)^(?:languages?|known|nationality)\b", line):
            continue
        label_match = LOCATION_LINE_LABEL_PATTERN.search(line)
        if label_match:
            candidate = _pick_primary_location(label_match.group("value"))
            if candidate:
                logger.debug("Location extracted from labeled line: %s", candidate)
                return candidate

    for line in labeled_search_lines[:20]:
        if re.match(r"(?i)^(?:languages?|known|nationality)\b", line):
            continue
        place_match = PLACE_LINE_PATTERN.search(line)
        if place_match:
            candidate = _pick_primary_location(place_match.group("value"))
            if candidate:
                logger.debug("Location extracted from place line: %s", candidate)
                return candidate

    for line in prioritized_lines[:15]:
        if re.match(r"(?i)^(?:languages?|known|nationality)\b", line):
            continue
        if re.search(r"(?i)\b(?:technology|project|responsibilit|power apps|power automate|dataverse|sharepoint)\b", line):
            continue
        direct_candidate = _pick_primary_location(line)
        if direct_candidate:
            logger.debug("Location extracted directly from prioritized line: %s", direct_candidate)
            return direct_candidate
        for match in COMMA_LOCATION_PATTERN.finditer(line):
            left = _trim_location_segment(match.group("left"))
            right = re.sub(r"\s+", " ", match.group("right").strip())
            candidate = _pick_primary_location(f"{left}, {right}")
            if candidate:
                logger.debug("Location extracted from comma header pattern: %s", candidate)
                return candidate
        for pattern in EXPLICIT_LOCATION_PATTERNS:
            for match in pattern.finditer(line):
                candidate = _pick_primary_location(match.group("value"))
                if candidate:
                    logger.debug("Location extracted from explicit pattern: %s", candidate)
                    return candidate

    city_from_address = _pick_primary_location(_extract_city_from_address_block(personal_detail_lines))
    if city_from_address:
        logger.debug("Location extracted from address block: %s", city_from_address)
        return city_from_address

    if use_spacy and SPACY_AVAILABLE:
        doc = get_section_doc("\n".join((personal_detail_lines or name_window or header_lines)[:15]))
        if doc is not None:
            gpe_entities = [re.sub(r"\s+", " ", ent.text).strip(" ,.-") for ent in doc.ents if ent.label_ == "GPE"]
            if gpe_entities:
                candidate = _pick_primary_location(" | ".join(gpe_entities[:3]))
                if candidate:
                    logger.debug("Location extracted with spaCy GPE: %s", candidate)
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


def extract_resume_information(text: str) -> Dict:
    debug_timings: Dict[str, float] = {}
    regex_started_at = time.perf_counter()
    structural_text = normalize_text(
        merge_broken_lines(
            normalize_document_structure(text or "")
        )
    )
    cleaned_text = clean_text_pipeline(text)
    debug_timings["regex_processing_ms"] = round((time.perf_counter() - regex_started_at) * 1000.0, 2)
    section_started_at = time.perf_counter()
    sections = segment_resume_sections(cleaned_text)
    debug_timings["section_detection_ms"] = round((time.perf_counter() - section_started_at) * 1000.0, 2)
    
    structural_source = normalize_document_structure(text or "")
    raw_sections = segment_resume_sections(structural_source)
    explicit_education_header = re.search(
        r"(?im)^\s*(?:education|academic background|academic profile|academic qualifications?|qualification|qualifications|education details)\s*$",
        structural_source,
    )
    if not explicit_education_header:
        raw_sections["education"] = ""
    header_section = raw_sections.get("header", "") or sections.get("header", "")
    contact_section = raw_sections.get("contact", "") or sections.get("contact", "")
    skills_section = _sanitize_skill_section(raw_sections.get("skills", "") or sections.get("skills", ""))
    skills_section = _augment_skills_section_with_related_blocks(
        skills_section,
        languages_section=raw_sections.get("languages", "") or sections.get("languages", ""),
        header_section=header_section,
    )
    skill_fallback_text = ""
    experience_section = raw_sections.get("experience", "") or sections.get("experience", "")
    if not experience_section.strip():
        experience_section = _infer_unstructured_experience_section(structural_text)
    education_section = raw_sections.get("education", "")
    if not education_section.strip() and explicit_education_header:
        education_section = sections.get("education", "")
    projects_section = raw_sections.get("projects", "") or sections.get("projects", "")
    certifications_section = raw_sections.get("certifications", "") or sections.get("certifications", "")
    structural_lines = [line.strip() for line in normalize_document_structure(text or "").splitlines() if line.strip()]
    contact_context = _build_contact_context(header_section, contact_section)
    contact_extraction_context = _build_contact_context(header_section, contact_section, "\n".join(structural_lines[:8]))
    _, header_contact_line, header_role_line = _get_header_contact_role_lines(contact_context or cleaned_text)
    _, header_role_from_name_line = _extract_name_and_role_from_first_line(contact_context or cleaned_text)
    header_role = header_role_from_name_line or _normalize_header_role_line(header_role_line)
    parallel_started_at = time.perf_counter()
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_name = executor.submit(extract_name, contact_context or cleaned_text, False)
        future_email = executor.submit(extract_email, contact_extraction_context or contact_context or cleaned_text)
        future_phone = executor.submit(extract_phone, contact_extraction_context or contact_context or cleaned_text)
        future_experience = executor.submit(
            extract_total_experience,
            f"Experience\n{experience_section}" if experience_section.strip() else "",
        )
        future_skills = executor.submit(extract_skill_keywords, skills_section, skills_section)
        primary_name = future_name.result()
        primary_email = future_email.result()
        primary_phone = future_phone.result()
        experience_result = future_experience.result()
        skills = future_skills.result()
    debug_timings["parallel_extraction_ms"] = round((time.perf_counter() - parallel_started_at) * 1000.0, 2)
    debug_timings["name_extraction_ms"] = debug_timings["parallel_extraction_ms"]
    skills = _unique_in_order(skills)
    if not skills:
        skill_fallback_text = _extract_skill_fallback_text(
            "\n".join(filter(None, [header_section, contact_section, sections.get("summary", ""), experience_section, cleaned_text]))
        )
        if skill_fallback_text and skill_fallback_text != skills_section:
            skills = _unique_in_order(extract_skill_keywords(skill_fallback_text, skill_fallback_text))
    debug_timings["skill_extraction_ms"] = debug_timings["parallel_extraction_ms"]
    
    experience_started_at = time.perf_counter()
    experience_entries = experience_result.get("experiences", [])
    section_entries = extract_experience_entries(f"Experience\n{experience_section}") if experience_section.strip() else []
    if section_entries:
        seen_experience_keys = {
            (
                str(entry.get("role") or "").strip().lower(),
                str(entry.get("company") or "").strip().lower(),
                str(entry.get("start_date") or "").strip().lower(),
                str(entry.get("end_date") or "").strip().lower(),
            )
            for entry in experience_entries
            if isinstance(entry, dict)
        }
        for entry in section_entries:
            identity = (
                str(entry.get("role") or "").strip().lower(),
                str(entry.get("company") or "").strip().lower(),
                str(entry.get("start_date") or "").strip().lower(),
                str(entry.get("end_date") or "").strip().lower(),
            )
            if not any(identity) or identity in seen_experience_keys:
                continue
            seen_experience_keys.add(identity)
            experience_entries.append(entry)
    debug_timings["experience_extraction_ms"] = round((time.perf_counter() - experience_started_at) * 1000.0, 2)
    total_experience_years = experience_result.get("total_experience_years")
    total_experience_months = experience_result.get("total_experience_months")
    # Only recompute total experience if the first pass found no entries.
    # Recomputing after merging section_entries causes double-counting of overlapping ranges.
    if not experience_entries:
        total_experience_years = None
        total_experience_months = None
    elif total_experience_years is None:
        from ats.extraction.experience_extraction import compute_total_experience, parse_date

        date_ranges = []
        for entry in experience_entries:
            start = parse_date(entry.get("start_date", ""), is_end=False)
            end = parse_date(entry.get("end_date", ""), is_end=True)
            if not start or not end or end < start:
                continue
            date_ranges.append((start, end))
        if date_ranges:
            total_experience_years = compute_total_experience(date_ranges)
            total_experience_months = int(round(total_experience_years * 12))

    summary_section = raw_sections.get("summary", "") or sections.get("summary", "")
    profile_section = raw_sections.get("profile", "") or sections.get("profile", "")
    experience_fallback_allowed = bool(experience_section.strip()) or bool(
        re.search(r"(?i)\bexpe\s+rience\b|\bexperi\s+ence\b", text or "")
    )
    if experience_fallback_allowed:
        fallback_experience_years = _extract_fallback_experience_years(
            experience_section,
            summary_section,
            profile_section,
            structural_text,
        )
        if fallback_experience_years is not None and (
            total_experience_years is None or fallback_experience_years > total_experience_years
        ):
            total_experience_years = fallback_experience_years
            total_experience_months = int(round(fallback_experience_years * 12))
            logger.debug("Fallback used for experience extraction")

    current_entry = {}
    if experience_entries:
        current_company = experience_result.get("current_company")
        current_role = experience_result.get("current_role")
        current_entry = _select_latest_experience_entry(
            experience_entries,
            preferred_company=str(current_company or ""),
            preferred_role=str(current_role or ""),
        )

    location = ""
    header_only_lines: List[str] = []
    for line in structural_lines[:8]:
        if re.match(r"(?i)^(?:professional summary|summary|profile summary|skills|technical skills|experience|work experience|period|education|projects|certifications?)$", line):
            break
        header_only_lines.append(line)

    header_context = "\n".join(header_only_lines)
    personal_detail_lines = _extract_personal_detail_lines(structural_lines)
    personal_details_context = _build_contact_context(contact_section, "\n".join(personal_detail_lines))

    header_present = bool(header_context.strip()) or bool(sections.get("header", "").strip())
    for source in (header_context, personal_details_context):
        if not source:
            continue
        location = extract_location(source, use_spacy=False)
        if location:
            break
    if not location:
        for source in (header_context, personal_details_context):
            for line in [line.strip() for line in source.splitlines() if line.strip()][:10]:
                location = validate_location(line)
                if location:
                    break
            if location:
                break

    need_slow_path = (not primary_name) or (not experience_entries and bool(experience_section.strip())) or (not header_present)
    if need_slow_path and not primary_name:
        primary_name = extract_name(contact_context or cleaned_text, use_spacy=True)

    if not location and need_slow_path and SPACY_AVAILABLE:
        for source in (header_context, personal_details_context):
            if not source:
                continue
            location = extract_location(source, use_spacy=True)
            if location:
                break
    logger.debug(
        "Primary contact extraction complete: name=%s email=%s phone=%s location=%s experience=%s",
        primary_name,
        primary_email,
        primary_phone,
        location,
        total_experience_years,
    )
    populated_sections = [name for name, value in sections.items() if str(value or "").strip()]
    logger.info(
        "Resume extraction diagnostics: raw_text_length=%s sections=%s skill_fallback=%s email_found=%s",
        len(text or ""),
        populated_sections,
        bool(skill_fallback_text.strip()),
        bool(primary_email),
    )
    skills_source_text = skills_section if skills_section.strip() else skill_fallback_text
    skills = _finalize_skills(
        skills,
        skills_source_text,
        "\n".join(filter(None, [header_section, contact_section, location])),
        from_section=bool(skills_source_text.strip()),
        name_text=primary_name,
        education_entries=extract_education_entries(cleaned_text, education_section),
        header_text=header_section,
        experience_text=experience_section,
        skills_text=skills_section,
    )

    result = {
        "sections": sections,
        "skills": skills,
        "skill_confidence": {
            skill: _skill_confidence(skill, skills_source_text, bool(skills_section.strip()))
            for skill in skills
        },
        "name": primary_name or "",
        "email": primary_email or "",
        "phone": primary_phone or "",
        "experience": experience_entries,
        "projects": extract_project_entries(cleaned_text, projects_section),
        "education": extract_education_entries(cleaned_text, education_section if education_section.strip() else " "),
        "certifications": extract_certification_entries(cleaned_text, certifications_section),
        "location": location or "",
        "current_company": current_entry.get("company") or experience_result.get("current_company"),
        "current_role": current_entry.get("role") or experience_result.get("current_role") or header_role or None,
        "designation": current_entry.get("role") or experience_result.get("current_role") or header_role or None,
        "header_role": header_role or None,
        "experience_years": total_experience_years,
        "total_experience_years": total_experience_years,
        "total_experience_months": total_experience_months,
        "total_experience": experience_result.get("total_experience", ""),
        "experience_level": derive_experience_level(total_experience_years),
        "experience_extraction_confidence": experience_result.get("experience_extraction_confidence", 0.0),
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
        "experience_text": clean_text_pipeline(experience_section),
        "education_text": clean_text_pipeline(education_section),
        "projects_text": clean_text_pipeline(projects_section),
        "certifications_text": clean_text_pipeline(certifications_section),
        "skill_extraction_support": {
            "esco": True,
            "skillner_installed": _skillner_installed(),
            "skillner_usable": bool(_skillner_state.get("usable")),
            "custom_aliases": True,
            "dynamic_context": True,
        },
        "debug_timings": debug_timings,
    }
    validated_result = validate_parsed_fields(result)
    if (
        not experience_section.strip()
        and not validated_result.get("experience")
        and validated_result.get("total_experience_years") is None
    ):
        validated_result["experience_years"] = None
        validated_result["total_experience_years"] = None
        validated_result["total_experience"] = ""
    if not validated_result.get("name"):
        logger.warning("Resume parsing validation warning: name is empty")
    if validated_result.get("total_experience_years") is None:
        logger.warning("Resume parsing validation warning: experience is empty")
    return validated_result
