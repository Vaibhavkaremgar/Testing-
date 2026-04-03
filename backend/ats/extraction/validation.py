from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from ats.datasets.parser_config_loader import ParserConfigLoader

BULLET_PREFIX_PATTERN = re.compile(r"^\s*[â€¢â–ªâ—¦â—Â·\-\*]+\s*")
FALLBACK_COMPANY_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9&.,' -]+(?:\s+[A-Z][A-Za-z0-9&.,' -]+)+$")
SENTENCE_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:act as|partnering|support a workforce|recognized for|responsible for|worked on|served as)\b"
)
LOCATION_CANDIDATE_PATTERN = re.compile(
    r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*(?:,\s*[A-Za-z]+(?:[\s-][A-Za-z]+)*){0,2}$"
)

_parser_config_loader = ParserConfigLoader()
_parser_vocabulary = _parser_config_loader.load_parser_vocabulary()

_company_terms = [
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("company_hint_terms") or [])
    if str(value).strip()
]
_role_terms = [
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("role_hint_terms") or [])
    if str(value).strip()
]
_location_noise_terms = [
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("location_noise_terms") or [])
    if str(value).strip()
]

if not _company_terms:
    _company_terms = ["pvt", "ltd", "inc", "technologies", "solutions", "corp", "systems", "software", "labs", "works"]
if not _role_terms:
    _role_terms = [
        "engineer", "developer", "manager", "lead", "head", "analyst", "consultant",
        "architect", "specialist", "administrator", "designer", "executive", "director",
        "officer", "associate", "scientist", "recruiter", "sales", "product", "qa",
        "tester", "intern", "partner", "generalist", "coordinator", "hrbp",
        "human resources", "founder", "owner",
    ]
if not _location_noise_terms:
    _location_noise_terms = [
        "engineer", "developer", "manager", "analyst", "scientist", "director", "lead",
        "consultant", "architect", "summary", "profile", "experience", "skills",
        "education", "projects", "languages", "email", "phone", "resume",
    ]

COMPANY_PATTERN = re.compile(rf"(?i)\b(?:{'|'.join(re.escape(term) for term in _company_terms)})\b")
ROLE_HINT_PATTERN = re.compile(rf"(?i)\b(?:{'|'.join(re.escape(term) for term in _role_terms)})\b")
LOCATION_NOISE_PATTERN = re.compile(rf"(?i)\b(?:{'|'.join(re.escape(term) for term in _location_noise_terms)})\b")


def _normalize(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def validate_current_role(value: Optional[str], skills: Iterable[str]) -> Optional[str]:
    candidate = _normalize(value)
    skill_set = {str(skill).strip().lower() for skill in skills if str(skill).strip()}
    if not candidate:
        return None
    if BULLET_PREFIX_PATTERN.match(candidate):
        return None
    if len(candidate.split()) < 2:
        return None
    if len(candidate.split()) > 12:
        return None
    if SENTENCE_NOISE_PATTERN.search(candidate):
        return None
    if not ROLE_HINT_PATTERN.search(candidate):
        return None
    if candidate.lower() in skill_set:
        return None
    return candidate


def validate_current_company(value: Optional[str], experience_section: str) -> Optional[str]:
    candidate = _normalize(value)
    if not candidate:
        return None
    if candidate not in (experience_section or ""):
        return None
    if len(candidate.split()) > 8:
        return None
    if SENTENCE_NOISE_PATTERN.search(candidate):
        return None
    if not COMPANY_PATTERN.search(candidate) and not FALLBACK_COMPANY_PATTERN.match(candidate):
        return None
    return candidate


def validate_location(value: Optional[str]) -> str:
    candidate = _normalize(value)
    if not candidate:
        return ""
    if len(candidate) > 80:
        return ""
    if LOCATION_NOISE_PATTERN.search(candidate):
        return ""
    if any(char.isdigit() for char in candidate):
        return ""
    if len(candidate.split()) > 5:
        return ""
    if not LOCATION_CANDIDATE_PATTERN.match(candidate):
        return ""
    return candidate


def validate_experience_years(value: Any) -> Optional[float]:
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= years <= 40.0:
        return round(years, 1)
    return None


def _score_role_confidence(value: Optional[str]) -> float:
    candidate = _normalize(value)
    if not candidate:
        return 0.0
    score = 0.35
    if ROLE_HINT_PATTERN.search(candidate):
        score += 0.4
    if 2 <= len(candidate.split()) <= 6:
        score += 0.15
    if not SENTENCE_NOISE_PATTERN.search(candidate):
        score += 0.1
    return round(min(score, 1.0), 2)


def _score_company_confidence(value: Optional[str], experience_section: str) -> float:
    candidate = _normalize(value)
    if not candidate:
        return 0.0
    score = 0.25
    if candidate in (experience_section or ""):
        score += 0.35
    if COMPANY_PATTERN.search(candidate):
        score += 0.25
    elif FALLBACK_COMPANY_PATTERN.match(candidate):
        score += 0.15
    if len(candidate.split()) <= 6:
        score += 0.1
    return round(min(score, 1.0), 2)


def _score_location_confidence(value: Optional[str]) -> float:
    candidate = _normalize(value)
    if not candidate:
        return 0.0
    score = 0.3
    if "," in candidate:
        score += 0.3
    if LOCATION_CANDIDATE_PATTERN.match(candidate):
        score += 0.3
    if not LOCATION_NOISE_PATTERN.search(candidate):
        score += 0.1
    return round(min(score, 1.0), 2)


def _score_experience_confidence(value: Any) -> float:
    years = validate_experience_years(value)
    if years is None:
        return 0.0
    score = 0.5
    if years > 0:
        score += 0.2
    if years <= 40:
        score += 0.3
    return round(min(score, 1.0), 2)


def validate_parsed_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    skills = data.get("skills") or []
    experience_section = data.get("sections", {}).get("experience", "")
    data["current_role"] = validate_current_role(data.get("current_role"), skills)
    data["designation"] = data["current_role"]
    data["current_company"] = validate_current_company(data.get("current_company"), experience_section)
    data["location"] = validate_location(data.get("location"))
    normalized_years = validate_experience_years(data.get("experience_years"))
    data["experience_years"] = normalized_years
    data["total_experience_years"] = validate_experience_years(data.get("total_experience_years"))
    if data["total_experience_years"] is None:
        data["total_experience_years"] = normalized_years
    field_confidence = dict(data.get("field_confidence") or {})
    field_confidence.update(
        {
            "current_role": _score_role_confidence(data.get("current_role")),
            "current_company": _score_company_confidence(data.get("current_company"), experience_section),
            "location": _score_location_confidence(data.get("location")),
            "experience_years": _score_experience_confidence(data.get("total_experience_years")),
        }
    )
    data["field_confidence"] = field_confidence
    return data
