from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dateutil import parser as date_parser

from ats.preprocessing.section_segmentation import get_section_content, segment_resume_sections
from app.spacy_nlp import SPACY_AVAILABLE, get_experience_doc

logger = logging.getLogger(__name__)

MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
PRESENT_PATTERN = r"(?:present|current|now|today|till date|till now)"
DATE_RANGE_REGEX = re.compile(
    rf"(?P<start>{MONTH_PATTERN}\s+\d{{4}}|\d{{1,2}}[/-]\d{{4}}|\d{{4}})\s*"
    rf"(?:-|–|—|to|until|through)\s*"
    rf"(?P<end>{PRESENT_PATTERN}|{MONTH_PATTERN}\s+\d{{4}}|\d{{1,2}}[/-]\d{{4}}|\d{{4}})",
    re.IGNORECASE,
)
ROLE_HINT_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|sales|product|qa|tester|intern)\b"
)
COMPANY_PATTERN = re.compile(r"(?i)\b(?:pvt|ltd|inc|technologies|solutions|corp)\b")
SKILL_LIKE_PATTERN = re.compile(
    r"(?i)\b(?:python|java|javascript|typescript|react|angular|vue|node(?:\.js)?|fastapi|django|flask|sql|aws|azure|gcp|docker|kubernetes|seo|crm|machine learning)\b"
)
COMPANY_STOPWORD_PATTERN = re.compile(r"(?i)\b(?:strategy|analytics|marketing|platform|pipeline|roadmap|adoption|enterprise)\b")
BULLET_PREFIX_PATTERN = re.compile(r"^\s*[•▪◦●·\-\*]+\s*")
SECTION_BREAK_PATTERN = re.compile(r"(?i)^(?:education|projects?|skills|technical skills|certifications?|summary|profile|languages?)$")
EXPERIENCE_HEADER_PATTERN = re.compile(r"(?i)^(?:work experience|professional experience|employment history|employment|career history|experience)$")


def _normalize_text(value: str) -> str:
    normalized = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u00b7": "|",
        "â€“": "-",
        "â€”": "-",
        "Â·": "|",
        "â€¢": " ",
        "â–ª": " ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", _normalize_text(line)).strip(" |-")


def _is_bullet_line(line: str) -> bool:
    return bool(BULLET_PREFIX_PATTERN.match(line or ""))


def _is_skill_like(value: str) -> bool:
    candidate = _normalize_line(value).lower()
    if not candidate:
        return True
    if len(candidate.split()) < 2:
        return True
    return bool(SKILL_LIKE_PATTERN.search(candidate)) and not ROLE_HINT_PATTERN.search(candidate)


def _looks_like_company(value: str) -> bool:
    candidate = _normalize_line(value)
    if not candidate:
        return False
    if "," in candidate:
        return False
    if COMPANY_STOPWORD_PATTERN.search(candidate):
        return False
    if COMPANY_PATTERN.search(candidate):
        return True
    words = candidate.split()
    if len(words) < 2:
        return False
    return all(word[:1].isupper() for word in words if word[:1].isalpha()) and not ROLE_HINT_PATTERN.search(candidate)


def _parse_date_token(token: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    raw = _normalize_line(token).lower().replace(".", "")
    if not raw:
        return None
    current = today or datetime.utcnow()
    if re.fullmatch(PRESENT_PATTERN, raw, flags=re.IGNORECASE):
        return current
    try:
        default = datetime(current.year, 12, 31) if is_end else datetime(current.year, 1, 1)
        parsed = date_parser.parse(raw, fuzzy=True, default=default)
    except (ValueError, OverflowError, TypeError):
        return None
    if parsed.year < 1950 or parsed.year > current.year + 2:
        return None
    if re.fullmatch(r"\d{4}", raw):
        return parsed.replace(month=12 if is_end else 1, day=31 if is_end else 1)
    if re.fullmatch(r"\d{1,2}[/-]\d{4}", raw):
        month, year = re.split(r"[/-]", raw)
        month_int = int(month)
        year_int = int(year)
        if is_end:
            if month_int == 12:
                return datetime(year_int, 12, 31)
            return datetime(year_int, month_int + 1, 1) - datetime.resolution
        return datetime(year_int, month_int, 1)
    return parsed


def parse_date(date_string: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    return _parse_date_token(date_string, is_end=is_end, today=today)


def extract_experience_section(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""
    return get_section_content(cleaned, "experience")


def extract_date_ranges(text: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    for match in DATE_RANGE_REGEX.finditer(_normalize_text(text)):
        start_text = match.group("start")
        end_text = match.group("end")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not start_date or not end_date or end_date < start_date:
            continue
        matches.append(
            {
                "start": start_text,
                "end": end_text,
                "start_date": start_date,
                "end_date": end_date,
                "matched_text": match.group(0),
                "span": match.span(),
            }
        )
    return matches


def _split_experience_blocks(section_text: str) -> List[List[str]]:
    lines = [_normalize_line(line) for line in _normalize_text(section_text).split("\n")]
    blocks: List[List[str]] = []
    current: List[str] = []
    seen_date = False

    def flush() -> None:
        nonlocal current, seen_date
        cleaned = [line for line in current if line]
        if cleaned and seen_date:
            blocks.append(cleaned)
        current = []
        seen_date = False

    for line in lines:
        if not line:
            flush()
            continue
        if SECTION_BREAK_PATTERN.match(line):
            flush()
            break
        line_has_date = bool(DATE_RANGE_REGEX.search(line))
        if current and seen_date and line_has_date:
            flush()
        current.append(line)
        seen_date = seen_date or line_has_date
    flush()
    return blocks


def _find_date_range(block_lines: Sequence[str]) -> Optional[Dict[str, Any]]:
    for line in block_lines:
        matches = extract_date_ranges(line)
        if matches:
            return matches[0]
    joined = " | ".join(block_lines[:4])
    matches = extract_date_ranges(joined)
    return matches[0] if matches else None


def _remove_date_range_text(line: str) -> str:
    normalized = _normalize_line(line)
    return DATE_RANGE_REGEX.sub("", normalized).strip(" |-,:")


def _candidate_lines_near_date(block_lines: Sequence[str]) -> List[str]:
    date_index = 0
    for index, line in enumerate(block_lines):
        if DATE_RANGE_REGEX.search(line):
            date_index = index
            break
    same_line = _remove_date_range_text(block_lines[date_index]) if block_lines else ""
    before = [
        line for line in block_lines[max(0, date_index - 2):date_index]
        if line and not EXPERIENCE_HEADER_PATTERN.match(line)
    ]
    after = [
        line for line in block_lines[date_index + 1:date_index + 3]
        if line and not EXPERIENCE_HEADER_PATTERN.match(line)
    ]
    candidates: List[str] = []
    if same_line:
        candidates.append(same_line)
    candidates.extend(before)
    candidates.extend(after)
    return candidates


def _extract_company_candidate(block_lines: Sequence[str]) -> Optional[str]:
    context_lines = _candidate_lines_near_date(block_lines)
    for line in context_lines:
        if " at " in line.lower():
            parts = re.split(r"\bat\b", line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and _looks_like_company(parts[1]):
                return _normalize_line(parts[1])
        if "|" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            for part in reversed(parts):
                if _looks_like_company(part):
                    return _normalize_line(part)
        if COMPANY_PATTERN.search(line):
            return _normalize_line(line)
        if _looks_like_company(line):
            return _normalize_line(line)
    if SPACY_AVAILABLE:
        doc = get_experience_doc("\n".join(context_lines))
        if doc is not None:
            for ent in doc.ents:
                candidate = _normalize_line(ent.text)
                if ent.label_ == "ORG" and _looks_like_company(candidate):
                    return candidate
    return None


def _extract_role_candidate(block_lines: Sequence[str], company: Optional[str]) -> Optional[str]:
    context_lines = _candidate_lines_near_date(block_lines)
    for line in context_lines:
        normalized = _normalize_line(line)
        if not normalized or _is_bullet_line(line):
            continue
        if company and normalized == company:
            continue
        if " at " in normalized.lower():
            parts = re.split(r"\bat\b", normalized, maxsplit=1, flags=re.IGNORECASE)
            candidate = _normalize_line(parts[0])
            if ROLE_HINT_PATTERN.search(candidate) and not _is_skill_like(candidate):
                return candidate
        if "|" in normalized:
            parts = [part.strip() for part in normalized.split("|") if part.strip()]
            for part in parts:
                if part != company and ROLE_HINT_PATTERN.search(part) and not _is_skill_like(part):
                    return _normalize_line(part)
        if ROLE_HINT_PATTERN.search(normalized) and not _is_skill_like(normalized):
            return normalized
    return None


def _serialize_year_month(date_value: datetime) -> str:
    return date_value.strftime("%Y-%m")


def _entry_from_block(block_lines: Sequence[str]) -> Optional[Dict[str, Any]]:
    if not block_lines:
        return None
    if any(_is_bullet_line(line) for line in block_lines[:2]):
        return None
    date_range = _find_date_range(block_lines)
    if not date_range:
        return None
    headline_lines = [_remove_date_range_text(line) for line in block_lines[:3]]
    headline_lines = [line for line in headline_lines if line]
    if not any(ROLE_HINT_PATTERN.search(line) or COMPANY_PATTERN.search(line) or " at " in line.lower() or "|" in line for line in headline_lines):
        return None
    company = _extract_company_candidate(block_lines)
    role = _extract_role_candidate(block_lines, company)
    if role and len(role.split()) < 2:
        role = None
    if role and _is_skill_like(role):
        role = None
    start_date = date_range["start_date"]
    end_date = date_range["end_date"]
    duration_years = round(max(0.0, (end_date - start_date).days + 1) / 365.25, 1)
    description = " ".join(
        line for line in block_lines if not DATE_RANGE_REGEX.search(line) and line not in {role, company}
    )[:600]
    return {
        "role": role,
        "title": role,
        "company": company,
        "start_date": _serialize_year_month(start_date),
        "end_date": _serialize_year_month(end_date),
        "duration_years": duration_years,
        "raw_text": "\n".join(block_lines)[:1000],
        "is_current": bool(re.search(PRESENT_PATTERN, date_range["end"], re.IGNORECASE)),
        "description": description,
    }


def merge_overlapping_ranges(
    ranges: Sequence[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    valid_ranges = sorted(
        [(start, end) for start, end in ranges if start and end and end >= start],
        key=lambda item: item[0],
    )
    if not valid_ranges:
        return []
    merged: List[List[datetime]] = [[valid_ranges[0][0], valid_ranges[0][1]]]
    for start, end in valid_ranges[1:]:
        if start <= merged[-1][1]:
            if end > merged[-1][1]:
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def compute_total_experience(ranges: Sequence[Tuple[datetime, datetime]]) -> float:
    merged = merge_overlapping_ranges(ranges)
    total_days = sum((end - start).days + 1 for start, end in merged)
    return round(total_days / 365.25, 1) if total_days > 0 else 0.0


def _sort_key(entry: Dict[str, Any]) -> Tuple[int, datetime]:
    end_date = parse_date(entry.get("end_date", ""), is_end=True) or datetime(1900, 1, 1)
    return (1 if entry.get("is_current") else 0, end_date)


def _dedupe_entries(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for entry in entries:
        key = (
            (entry.get("role") or "").lower(),
            (entry.get("company") or "").lower(),
            entry.get("start_date"),
            entry.get("end_date"),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    deduped.sort(key=_sort_key, reverse=True)
    return deduped


def _fallback_blocks_from_full_text(text: str) -> List[List[str]]:
    sections = segment_resume_sections(text)
    if sections.get("experience"):
        return _split_experience_blocks(sections["experience"])
    return _split_experience_blocks(_normalize_text(text))


def extract_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    experience_section = extract_experience_section(text)
    blocks = _split_experience_blocks(experience_section) if experience_section else _fallback_blocks_from_full_text(text)
    entries = []
    for block in blocks:
        entry = _entry_from_block(block)
        if not entry:
            continue
        internship_source = " ".join(
            value for value in [entry.get("role") or "", entry.get("raw_text") or ""] if value
        )
        if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", internship_source):
            continue
        entries.append(entry)
    logger.debug("Parsed jobs: %s", entries)
    return _dedupe_entries(entries)


def extract_total_experience(
    text: str,
    ignore_internships: bool = False,
) -> Dict[str, Any]:
    entries = extract_experience_entries(text, ignore_internships=ignore_internships)
    ranges = []
    normalized_entries = []
    for entry in entries:
        start = parse_date(entry["start_date"], is_end=False)
        end = parse_date(entry["end_date"], is_end=True)
        if not start or not end or end < start:
            continue
        ranges.append((start, end))
        normalized_entries.append(entry)
    return {
        "total_experience_years": compute_total_experience(ranges) if ranges else None,
        "experiences": normalized_entries,
    }
