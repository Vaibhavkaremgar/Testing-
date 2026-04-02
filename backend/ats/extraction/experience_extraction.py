from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ats.preprocessing.section_segmentation import segment_resume_sections
from app.spacy_nlp import SPACY_AVAILABLE, nlp

MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
PRESENT_PATTERN = r"(?:present|current|now|today|till date|till now)"
DATE_SEPARATOR_PATTERN = r"(?:\-|–|—|―|to|until|through|thru)"

EXPERIENCE_SECTION_ALIASES = {
    "experience",
    "work experience",
    "professional experience",
    "employment history",
    "work history",
    "career history",
    "professional background",
}

IGNORE_SECTION_KEYWORDS = {
    "education",
    "academic background",
    "academic qualifications",
    "qualification",
    "qualifications",
    "projects",
    "project",
    "certifications",
    "certification",
    "awards",
    "publications",
    "internships",
    "internship",
}

INTERNSHIP_PATTERN = re.compile(r"(?i)\b(?:intern|internship|trainee|apprentice|apprenticeship)\b")
COMPANY_HINT_PATTERN = re.compile(
    r"(?i)\b(?:inc|llc|ltd|limited|corp|corporation|company|technologies|systems|solutions|software|labs|global|services|consulting)\b"
)
ROLE_HINT_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|intern)\b"
)
HEADER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s/&,-]{0,60}:?$")
DATE_CONTEXT_BLACKLIST = re.compile(
    r"(?i)\b(?:education|bachelor|master|b\.?tech|m\.?tech|bca|mca|degree|diploma|certification|certificate|project|projects|thesis|coursework|cgpa|gpa)\b"
)
MONTH_MAP = {
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

DATE_RANGE_REGEX = re.compile(
    rf"""
    (?P<start>
        {MONTH_PATTERN}\.?\s+\d{{4}}
        |
        \d{{1,2}}[/-]\d{{4}}
        |
        \d{{4}}
    )
    \s*
    {DATE_SEPARATOR_PATTERN}
    \s*
    (?P<end>
        {PRESENT_PATTERN}
        |
        {MONTH_PATTERN}\.?\s+\d{{4}}
        |
        \d{{1,2}}[/-]\d{{4}}
        |
        \d{{4}}
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass(frozen=True)
class ParsedDate:
    value: datetime
    precision: str
    is_present: bool = False


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _normalize_text(value: str) -> str:
    normalized = (value or "").replace("\r", "\n")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "â€“": "-",
        "â€”": "-",
        "\u00a0": " ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    return normalized


def _normalize_header(line: str) -> str:
    normalized = _normalize_text(line).strip().lower().rstrip(":")
    normalized = re.sub(r"[^a-z\s/&,-]", " ", normalized)
    return _normalize_whitespace(normalized)


def _is_probable_section_header(line: str) -> bool:
    return bool(HEADER_PATTERN.match((_normalize_text(line) or "").strip()))


def _is_ignored_header(line: str) -> bool:
    return _normalize_header(line) in IGNORE_SECTION_KEYWORDS


def _last_day_of_month(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


def _month_from_token(token: str) -> Optional[int]:
    if not token:
        return None
    return MONTH_MAP.get(token.strip().lower().replace(".", ""))


def _normalize_company_name(company: str) -> str:
    company = _normalize_whitespace((company or "").strip(" ,-|\t"))
    company = re.sub(r"\s*\([^)]*\)\s*$", "", company).strip(" ,-|\t")
    return company[:160]


def _line_looks_like_date_range(line: str) -> bool:
    return bool(DATE_RANGE_REGEX.search(_normalize_text(line)))


def _contains_blacklisted_context(value: str) -> bool:
    return bool(DATE_CONTEXT_BLACKLIST.search(value or ""))


def _looks_like_employment_context(line: str) -> bool:
    normalized = _normalize_text(line)
    lowered = normalized.lower()
    return bool(COMPANY_HINT_PATTERN.search(normalized) or ROLE_HINT_PATTERN.search(normalized) or " at " in lowered)


def _extract_neighbor_window(lines: Sequence[str], index: int, radius: int = 2) -> List[str]:
    start = max(0, index - radius)
    end = min(len(lines), index + radius + 1)
    return [lines[position] for position in range(start, end) if lines[position].strip()]


def _parse_year_token(year: int, is_end: bool) -> datetime:
    month = 12 if is_end else 1
    day = _last_day_of_month(year, month) if is_end else 1
    return datetime(year, month, day)


def parse_date(date_string: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    parsed = _parse_date_parts(date_string, is_end=is_end, today=today)
    return parsed.value if parsed else None


def _parse_date_parts(date_string: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[ParsedDate]:
    raw = _normalize_whitespace(_normalize_text(date_string)).lower().replace(".", "")
    if not raw:
        return None

    current = today or datetime.utcnow()
    if re.fullmatch(PRESENT_PATTERN, raw, flags=re.IGNORECASE):
        return ParsedDate(current, precision="present", is_present=True)

    month_year_match = re.fullmatch(rf"(?P<month>{MONTH_PATTERN})\s+(?P<year>\d{{4}})", raw, flags=re.IGNORECASE)
    if month_year_match:
        year = int(month_year_match.group("year"))
        month = _month_from_token(month_year_match.group("month"))
        if not month or year < 1950 or year > current.year + 2:
            return None
        day = _last_day_of_month(year, month) if is_end else 1
        return ParsedDate(datetime(year, month, day), precision="month")

    slash_match = re.fullmatch(r"(?P<month>\d{1,2})[/-](?P<year>\d{4})", raw)
    if slash_match:
        year = int(slash_match.group("year"))
        month = int(slash_match.group("month"))
        if month < 1 or month > 12 or year < 1950 or year > current.year + 2:
            return None
        day = _last_day_of_month(year, month) if is_end else 1
        return ParsedDate(datetime(year, month, day), precision="month")

    iso_month_match = re.fullmatch(r"(?P<year>\d{4})-(?P<month>\d{1,2})", raw)
    if iso_month_match:
        year = int(iso_month_match.group("year"))
        month = int(iso_month_match.group("month"))
        if month < 1 or month > 12 or year < 1950 or year > current.year + 2:
            return None
        day = _last_day_of_month(year, month) if is_end else 1
        return ParsedDate(datetime(year, month, day), precision="month")

    year_match = re.fullmatch(r"(?P<year>\d{4})", raw)
    if year_match:
        year = int(year_match.group("year"))
        if year < 1950 or year > current.year + 2:
            return None
        return ParsedDate(_parse_year_token(year, is_end=is_end), precision="year")

    return None


def calculate_duration(start: datetime, end: datetime) -> float:
    if not start or not end or end < start:
        return 0.0
    total_days = (end - start).days + 1
    return round(total_days / 365.25, 1)


def merge_overlapping_ranges(
    ranges: Sequence[Tuple[datetime, datetime]],
) -> List[Tuple[datetime, datetime]]:
    normalized = sorted(
        [(start, end) for start, end in ranges if start and end and end >= start],
        key=lambda item: item[0],
    )
    if not normalized:
        return []

    merged: List[List[datetime]] = [[normalized[0][0], normalized[0][1]]]
    for start, end in normalized[1:]:
        last_start, last_end = merged[-1]
        if start <= (last_end + timedelta(days=1)):
            if end > last_end:
                merged[-1][1] = end
            continue
        merged.append([start, end])
    return [(start, end) for start, end in merged]


def compute_total_experience(ranges: Sequence[Tuple[datetime, datetime]]) -> float:
    merged = merge_overlapping_ranges(ranges)
    total_days = sum((end - start).days + 1 for start, end in merged)
    return round(total_days / 365.25, 1) if total_days > 0 else 0.0


def extract_experience_section(text: str) -> str:
    if not text or not text.strip():
        return ""

    normalized_text = _normalize_text(text)
    sections = segment_resume_sections(normalized_text)
    experience_section = sections.get("experience", "").strip()
    if experience_section:
        return experience_section

    lines = [line.rstrip() for line in normalized_text.split("\n")]
    collected: List[str] = []
    capture = False
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if capture:
                collected.append("")
            continue

        normalized = _normalize_header(line)
        if normalized in EXPERIENCE_SECTION_ALIASES:
            capture = True
            continue

        if capture and (_is_ignored_header(line) or (_is_probable_section_header(line) and normalized not in EXPERIENCE_SECTION_ALIASES)):
            break

        if capture:
            collected.append(line)

    return "\n".join(collected).strip()


def extract_date_ranges(text: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    if not text:
        return matches

    normalized_text = _normalize_text(text)
    for match in DATE_RANGE_REGEX.finditer(normalized_text):
        start_text = match.group("start")
        end_text = match.group("end")
        start = parse_date(start_text, is_end=False)
        end = parse_date(end_text, is_end=True)
        if not start or not end or end < start:
            continue
        matches.append(
            {
                "start": start_text.strip(),
                "end": end_text.strip(),
                "start_date": start,
                "end_date": end,
                "span": match.span(),
                "matched_text": match.group(0).strip(),
            }
        )

    return matches


def _line_has_experience_signal(line: str) -> bool:
    lowered = line.lower()
    return any(
        token in lowered
        for token in ("experience", "employment", "worked", "developer", "engineer", "manager", "analyst", "consultant")
    )


def _split_experience_blocks(section_text: str) -> List[List[str]]:
    lines = [line.strip() for line in _normalize_text(section_text).split("\n")]
    blocks: List[List[str]] = []
    current: List[str] = []

    def flush() -> None:
        nonlocal current
        cleaned = [line for line in current if line]
        if cleaned:
            blocks.append(cleaned)
        current = []

    for line in lines:
        if not line:
            flush()
            continue

        if _is_ignored_header(line):
            flush()
            break

        if _is_probable_section_header(line) and current and not _line_looks_like_date_range(line):
            flush()

        current.append(line)

    flush()
    return blocks


def _find_best_date_range(block_lines: Sequence[str]) -> Optional[Dict[str, Any]]:
    candidate_lines = list(block_lines[:6])
    for line in candidate_lines:
        if _contains_blacklisted_context(line):
            continue
        ranges = extract_date_ranges(line)
        if ranges:
            return ranges[0]

    joined = " | ".join(candidate_lines)
    ranges = extract_date_ranges(joined)
    return ranges[0] if ranges else None


def _extract_company_from_lines(block_lines: Sequence[str], date_text: str) -> str:
    candidates: List[str] = []
    prioritized_lines = list(block_lines[:4])
    for line in prioritized_lines:
        cleaned = _normalize_whitespace(_normalize_text(line).replace(date_text, "").strip(" ,-|\t"))
        if not cleaned:
            continue

        if " at " in cleaned.lower():
            parts = re.split(r"\bat\b", cleaned, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                return _normalize_company_name(parts[1])

        split_parts = [part.strip(" ,-|\t") for part in re.split(r"\s+\|\s+|\s+-\s+", cleaned) if part.strip(" ,-|\t")]
        if len(split_parts) >= 2:
            for part in split_parts[1:]:
                normalized = _normalize_company_name(part)
                if normalized:
                    return normalized

        candidates.append(cleaned)

    if SPACY_AVAILABLE and nlp is not None:
        joined = "\n".join(prioritized_lines)[:400]
        try:
            doc = nlp(joined)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                return _normalize_company_name(org_entities[0])
        except Exception:
            pass

    for candidate in candidates:
        if COMPANY_HINT_PATTERN.search(candidate):
            return _normalize_company_name(candidate)

    if len(candidates) >= 2:
        return _normalize_company_name(candidates[1])
    return ""


def _extract_title_from_lines(block_lines: Sequence[str], date_text: str, company: str) -> str:
    for line in block_lines[:4]:
        cleaned = _normalize_whitespace(_normalize_text(line).replace(date_text, "").strip(" ,-|\t"))
        if not cleaned:
            continue

        if " at " in cleaned.lower():
            parts = re.split(r"\bat\b", cleaned, maxsplit=1, flags=re.IGNORECASE)
            return _normalize_whitespace(parts[0])[:120]

        split_parts = [part.strip(" ,-|\t") for part in re.split(r"\s+\|\s+|\s+-\s+", cleaned) if part.strip(" ,-|\t")]
        if split_parts:
            if company and len(split_parts) >= 2:
                return _normalize_whitespace(split_parts[0])[:120]
            if not COMPANY_HINT_PATTERN.search(split_parts[0]):
                return _normalize_whitespace(split_parts[0])[:120]

    return ""


def _infer_company_from_context(block_lines: Sequence[str], company: str) -> str:
    if company:
        return company
    for line in block_lines[1:4]:
        cleaned = _normalize_company_name(line)
        if COMPANY_HINT_PATTERN.search(cleaned):
            return cleaned
    return company


def _block_should_be_ignored(block_lines: Sequence[str], ignore_internships: bool) -> bool:
    joined = " ".join(block_lines[:4])
    if _contains_blacklisted_context(joined):
        return True
    if ignore_internships and INTERNSHIP_PATTERN.search(joined):
        return True
    if not any(_line_looks_like_date_range(line) for line in block_lines):
        return True
    return False


def _serialize_year_month(date_value: datetime) -> str:
    return date_value.strftime("%Y-%m")


def _experience_entry_from_block(block_lines: Sequence[str], ignore_internships: bool) -> Optional[Dict[str, Any]]:
    if not block_lines or _block_should_be_ignored(block_lines, ignore_internships=ignore_internships):
        return None

    best_range = _find_best_date_range(block_lines)
    if not best_range:
        return None

    company = _extract_company_from_lines(block_lines, best_range["matched_text"])
    company = _infer_company_from_context(block_lines, company)
    title = _extract_title_from_lines(block_lines, best_range["matched_text"], company)

    start_date = best_range["start_date"]
    end_date = best_range["end_date"]
    duration_years = calculate_duration(start_date, end_date)

    return {
        "title": title or None,
        "company": company or None,
        "start_date": _serialize_year_month(start_date),
        "end_date": _serialize_year_month(end_date),
        "duration_years": duration_years,
        "raw_text": "\n".join(block_lines)[:1000],
    }


def _fallback_experience_candidates(text: str) -> Iterable[List[str]]:
    lines = [line.strip() for line in _normalize_text(text).split("\n") if line.strip()]
    for index, line in enumerate(lines):
        if _is_ignored_header(line) or _contains_blacklisted_context(line):
            continue
        if not _line_looks_like_date_range(line):
            continue

        candidate_block = _extract_neighbor_window(lines, index, radius=2)
        joined = " ".join(candidate_block[:4])
        if _contains_blacklisted_context(joined):
            continue
        if not any(_looks_like_employment_context(candidate) for candidate in candidate_block if candidate != line):
            continue
        yield candidate_block


def extract_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    experience_section = extract_experience_section(text)
    blocks = _split_experience_blocks(experience_section) if experience_section else []

    entries: List[Dict[str, Any]] = []
    for block in blocks:
        entry = _experience_entry_from_block(block, ignore_internships=ignore_internships)
        if entry:
            entries.append(entry)

    if not entries and text:
        for block in _fallback_experience_candidates(text):
            entry = _experience_entry_from_block(block, ignore_internships=ignore_internships)
            if entry:
                entries.append(entry)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        key = (
            (entry.get("title") or "").lower(),
            (entry.get("company") or "").lower(),
            entry["start_date"],
            entry["end_date"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    deduped.sort(key=lambda item: item["end_date"], reverse=True)
    return deduped


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
        "total_experience_years": compute_total_experience(ranges),
        "experiences": normalized_entries,
    }
