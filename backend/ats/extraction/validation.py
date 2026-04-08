from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

from ats.datasets.parser_config_loader import ParserConfigLoader

BULLET_PREFIX_PATTERN = re.compile(r"^\s*[â€¢â–ªâ—¦â—Â·\-\*]+\s*")
FALLBACK_COMPANY_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9&.,' -]+(?:\s+[A-Z][A-Za-z0-9&.,' -]+)+$")
SINGLE_TOKEN_COMPANY_PATTERN = re.compile(r"^[A-Z][A-Z0-9&.'-]{2,}$")
SENTENCE_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:act as|partnering|support a workforce|recognized for|responsible for|worked on|served as|designed|built|led|owned|managed|created|developed|implemented|using)\b"
)
LOCATION_CANDIDATE_PATTERN = re.compile(
    r"^[A-Za-z]+(?:[\s-][A-Za-z]+)*(?:,\s*[A-Za-z]+(?:[\s-][A-Za-z]+)*){0,2}$"
)
EMAIL_PATTERN = re.compile(r"(?i)^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
NAME_PATTERN = re.compile(r"^[A-Z][A-Za-z'`.-]*(?:\s+[A-Z][A-Za-z'`.-]*){1,3}$")
INVALID_LOCATION_TOKENS = {"contact", "profile", "summary", "skills", "experience", "education", "certifications"}
INVALID_LOCATION_WORDS = {
    "job",
    "objective",
    "contact",
    "details",
    "summary",
    "profile",
    "linkedin",
    "github",
    "portfolio",
    "career",
    "passing",
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
}
LOCATION_FALSE_POSITIVE_TECH_PATTERN = re.compile(
    r"(?i)\b(?:python|java|selenium|playwright|robot framework|robot|sql|typescript|react|docker|jenkins|postman|restassured|pytest|fastapi|power bi|tableau|jira|maven|ui)\b"
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
LEADING_ROLE_PATTERN = re.compile(
    r"(?i)^(?P<role>(?:(?:senior|sr|junior|jr|lead|principal|staff|associate|assistant|graphic|brand|visual|creative|content|product|frontend|front-end|backend|back-end|full[- ]stack|data|software|web|mobile|qa|devops|machine learning|ml|human resources|hr|engineering|business|intelligence|sales|marketing|customer|growth)\s+){0,5}(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|tester|teacher|partner|generalist|coordinator))\b"
)


def _normalize(value: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _strip_trailing_company_punctuation(value: str) -> str:
    candidate = _normalize(value)
    while candidate.endswith((".", ",", ";", ":")):
        candidate = candidate[:-1].rstrip()
    return candidate


def validate_current_role(value: Optional[str], skills: Iterable[str]) -> Optional[str]:
    candidate = _normalize(value)
    skill_set = {str(skill).strip().lower() for skill in skills if str(skill).strip()}
    if not candidate:
        return None
    candidate = re.sub(r"^\s*(?:\d+\)|\d+\.\s*|[-*•]+\s*)", "", candidate).strip()
    leading_match = LEADING_ROLE_PATTERN.search(candidate)
    if leading_match:
        candidate = _normalize(leading_match.group("role"))
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
    candidate = _strip_trailing_company_punctuation(value or "")
    if not candidate:
        return None
    if candidate not in (experience_section or ""):
        return None
    if len(candidate.split()) > 8:
        return None
    if SENTENCE_NOISE_PATTERN.search(candidate):
        return None
    if not COMPANY_PATTERN.search(candidate) and not FALLBACK_COMPANY_PATTERN.match(candidate) and not SINGLE_TOKEN_COMPANY_PATTERN.match(candidate):
        return None
    return candidate


def validate_location(value: Optional[str]) -> str:
    candidate = _normalize(value)
    if not candidate:
        return ""
    if len(candidate) > 80:
        return ""
    lowered = candidate.lower()
    if lowered in INVALID_LOCATION_TOKENS or lowered in INVALID_LOCATION_WORDS:
        return ""
    tokens = {
        token.strip(".,:-").lower()
        for token in re.split(r"[\s,/|()]+", candidate)
        if token.strip(".,:-")
    }
    if tokens & NON_LOCATION_CONTEXT_TERMS:
        return ""
    if tokens & INVALID_LOCATION_WORDS:
        return ""
    if LOCATION_NOISE_PATTERN.search(candidate):
        return ""
    if LOCATION_FALSE_POSITIVE_TECH_PATTERN.search(candidate):
        return ""
    if any(char.isdigit() for char in candidate):
        return ""
    if len(candidate.split()) > 5:
        return ""
    if len(candidate.split()) == 1 and len(candidate) < 3:
        return ""
    if len(candidate.split()) == 1 and candidate.isupper():
        return ""
    if "," not in candidate and NAME_PATTERN.match(candidate):
        return ""
    geo_parts = [part.strip() for part in candidate.split(",") if part.strip()]
    if "," in candidate and len(geo_parts) < 2:
        return ""
    if not LOCATION_CANDIDATE_PATTERN.match(candidate):
        return ""
    return candidate


def validate_name(
    value: Optional[str],
    skills: Iterable[str],
    *,
    organizations: Iterable[str] = (),
    locations: Iterable[str] = (),
    experience_companies: Iterable[str] = (),
    current_role: Optional[str] = None,
) -> str:
    candidate = _normalize(value)
    if not candidate or not NAME_PATTERN.match(candidate):
        return ""
    lowered = candidate.lower()
    invalid_tokens = {
        "contact", "profile", "summary", "skills", "experience", "education", "certifications",
    }
    if any(token in invalid_tokens for token in lowered.split()):
        return ""
    if ROLE_HINT_PATTERN.search(candidate):
        return ""
    if COMPANY_PATTERN.search(candidate):
        return ""
    skill_set = {str(skill).strip().lower() for skill in skills if str(skill).strip()}
    if lowered in skill_set:
        return ""
    blocked_values = {
        _normalize(item).lower()
        for item in [*organizations, *locations, *experience_companies, current_role or ""]
        if _normalize(item)
    }
    if lowered in blocked_values:
        return ""
    if validate_location(candidate):
        return ""
    return candidate


def validate_email(value: Optional[str]) -> str:
    candidate = _normalize(value).strip(".,;:")
    if not candidate or not EMAIL_PATTERN.match(candidate):
        return ""
    lowered = candidate.lower()
    if any(marker in lowered for marker in (".linkedin.", ".github.", ".portfolio.")):
        return ""
    return candidate


def validate_skills(values: Iterable[str], location: Optional[str]) -> list[str]:
    blocked_terms = {part.strip().lower() for part in (location or "").split(",") if part.strip()}
    cleaned: list[str] = []
    seen = set()
    for value in values or []:
        candidate = _normalize(str(value)).lower()
        if not candidate or candidate in seen:
            continue
        if candidate in blocked_terms:
            continue
        if LOCATION_NOISE_PATTERN.search(candidate):
            continue
        seen.add(candidate)
        cleaned.append(candidate)
    return cleaned


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
    elif SINGLE_TOKEN_COMPANY_PATTERN.match(candidate):
        score += 0.2
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


def _score_name_confidence(value: Optional[str]) -> float:
    candidate = _normalize(value)
    if not candidate:
        return 0.0
    score = 0.45
    if 2 <= len(candidate.split()) <= 4:
        score += 0.2
    if NAME_PATTERN.match(candidate):
        score += 0.2
    if not COMPANY_PATTERN.search(candidate) and not ROLE_HINT_PATTERN.search(candidate):
        score += 0.15
    return round(min(score, 1.0), 2)


def validate_parsed_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    skills = data.get("skills") or []
    experience_section = data.get("sections", {}).get("experience", "")
    experience_entries = data.get("experience_entries") or data.get("experience") or []
    entities = data.get("entities") or {}
    experience_entry_text = "\n".join(
        str(entry.get("raw_text") or "")
        for entry in experience_entries
        if isinstance(entry, dict)
    )
    experience_source = "\n".join(part for part in [experience_section, experience_entry_text] if part)
    experience_companies = [
        str(entry.get("company") or "")
        for entry in experience_entries
        if isinstance(entry, dict)
    ]
    entity_locations = [*entities.get("locations", [])]
    if data.get("location"):
        entity_locations.append(data.get("location"))
    data["name"] = validate_name(
        data.get("name"),
        skills,
        organizations=entities.get("organizations", []),
        locations=entity_locations,
        experience_companies=experience_companies,
        current_role=data.get("current_role"),
    )
    data["email"] = validate_email(data.get("email"))
    data["current_role"] = validate_current_role(data.get("current_role"), skills)
    data["designation"] = data["current_role"]
    data["current_company"] = validate_current_company(data.get("current_company"), experience_source)
    data["location"] = validate_location(data.get("location"))
    data["skills"] = validate_skills(skills, data.get("location"))
    normalized_years = validate_experience_years(data.get("experience_years"))
    data["experience_years"] = normalized_years
    data["total_experience_years"] = validate_experience_years(data.get("total_experience_years"))
    if data["total_experience_years"] is None:
        data["total_experience_years"] = normalized_years
    field_confidence = dict(data.get("field_confidence") or {})
    field_confidence.update(
        {
            "current_role": _score_role_confidence(data.get("current_role")),
            "current_company": _score_company_confidence(data.get("current_company"), experience_source),
            "location": _score_location_confidence(data.get("location")),
            "experience_years": _score_experience_confidence(data.get("total_experience_years")),
            "name": _score_name_confidence(data.get("name")),
            "email": 1.0 if data.get("email") else 0.0,
            "skills": 1.0 if data.get("skills") else 0.0,
        }
    )
    data["field_confidence"] = field_confidence
    data["validation_summary"] = {
        "name_valid": bool(data.get("name")),
        "email_valid": bool(data.get("email")),
        "location_valid": bool(data.get("location")),
        "skills_valid": bool(data.get("skills")),
        "experience_valid": bool(data.get("experience_entries") or data.get("experience") or data.get("total_experience_years")),
    }
    return data
