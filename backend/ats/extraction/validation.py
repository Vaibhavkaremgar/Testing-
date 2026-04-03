from __future__ import annotations

import re
from typing import Any, Dict, Iterable, Optional

BULLET_PREFIX_PATTERN = re.compile(r"^\s*[•▪◦●·\-\*]+\s*")
COMPANY_PATTERN = re.compile(r"(?i)\b(?:pvt|ltd|inc|technologies|solutions|corp)\b")
FALLBACK_COMPANY_PATTERN = re.compile(r"^[A-Z][A-Za-z0-9&.,' -]+(?:\s+[A-Z][A-Za-z0-9&.,' -]+)+$")
ROLE_HINT_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|lead|head|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|sales|product|qa|tester|intern|partner|generalist|coordinator|hrbp|human resources|founder|owner)\b"
)
SENTENCE_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:act as|partnering|support a workforce|recognized for|responsible for|worked on|served as)\b"
)


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


def validate_experience_years(value: Any) -> Optional[float]:
    try:
        years = float(value)
    except (TypeError, ValueError):
        return None
    if 0.0 <= years <= 40.0:
        return round(years, 1)
    return None


def validate_parsed_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    skills = data.get("skills") or []
    experience_section = data.get("sections", {}).get("experience", "")
    data["current_role"] = validate_current_role(data.get("current_role"), skills)
    data["designation"] = data["current_role"]
    data["current_company"] = validate_current_company(data.get("current_company"), experience_section)
    normalized_years = validate_experience_years(data.get("experience_years"))
    data["experience_years"] = normalized_years
    data["total_experience_years"] = validate_experience_years(data.get("total_experience_years"))
    if data["total_experience_years"] is None:
        data["total_experience_years"] = normalized_years
    return data
