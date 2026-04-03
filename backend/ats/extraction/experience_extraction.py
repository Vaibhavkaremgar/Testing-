from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dateutil import parser as date_parser

from ats.preprocessing.section_segmentation import get_section_content, segment_resume_sections
from app.spacy_nlp import SPACY_AVAILABLE, get_experience_doc

logger = logging.getLogger(__name__)

MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
PRESENT_PATTERN = r"(?:present|current|now|today|till date|till now)"
DATE_TOKEN_PATTERN = (
    rf"(?:{MONTH_PATTERN}[.\-/\s,']+\d{{2,4}}"
    rf"|\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}[/-]\d{{1,2}}"
    rf"|\d{{1,2}}\.\d{{2,4}}"
    rf"|\d{{4}})"
)
DATE_RANGE_REGEX = re.compile(
    rf"(?P<start>{DATE_TOKEN_PATTERN})\s*"
    rf"(?:-|–|—|to|until|through)\s*"
    rf"(?P<end>{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})",
    re.IGNORECASE,
)
ROLE_HINT_PATTERN = re.compile(
    r"(?i)\b(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|sales|product|qa|tester|intern|teacher|partner|coordinator)\b"
)
ROLE_TITLE_PATTERN = re.compile(
    r"(?i)\b(?P<role>(?:(?:senior|sr|junior|jr|lead|principal|staff|associate|assistant|frontend|front-end|backend|back-end|full[- ]stack|data|product|software|web|mobile|qa|devops|machine learning|ml|human resources|hr|engineering|business|intelligence|sales|sap|mathematics)\s+){0,4}(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|sales|product|qa|tester|intern|teacher|partner|generalist|coordinator|consultant))\b"
)
PROSE_ROLE_PATTERN = re.compile(
    r"(?i)\b(?:i\s+was|worked\s+as|work(?:ed)?\s+as|joined\s+as|served\s+as|role\s+was|position\s+was)\s+(?:an?\s+)?(?P<role>[A-Za-z][A-Za-z/&\-\s]{1,80}?(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|sales|product|qa|tester|intern|teacher|partner|generalist|coordinator))\b"
)
COMPANY_PATTERN = re.compile(
    r"(?i)\b(?:pvt|ltd|inc|llc|llp|technologies|solutions|corp|corporation|organisation|organization|systems|labs|works|school|college|university|academy|institute|services)\b"
)
SKILL_LIKE_PATTERN = re.compile(
    r"(?i)\b(?:python|java|javascript|typescript|react|angular|vue|node(?:\.js)?|fastapi|django|flask|sql|aws|azure|gcp|docker|kubernetes|seo|crm|machine learning)\b"
)
COMPANY_STOPWORD_PATTERN = re.compile(r"(?i)\b(?:strategy|analytics|marketing|platform|pipeline|roadmap|adoption|enterprise)\b")
BULLET_PREFIX_PATTERN = re.compile(r"^\s*[\u2022\u25aa\u25e6\u25cf\u00b7\-\*]+\s*")
SECTION_BREAK_PATTERN = re.compile(r"(?i)^(?:education|projects?|skills|technical skills|certifications?|summary|profile|languages?)$")
EXPERIENCE_HEADER_PATTERN = re.compile(r"(?i)^(?:work experience|professional experience|employment history|employment|career history|experience)$")


def _normalize_text(value: str) -> str:
    normalized = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u00b7": "|",
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â‚¬â€": "-",
        "Ã‚Â·": "|",
        "Ã¢â‚¬Â¢": " ",
        "Ã¢â€“Âª": " ",
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


def _looks_like_experience_heading(value: str) -> bool:
    candidate = _normalize_line(value)
    if not candidate or len(candidate.split()) > 12:
        return False
    if candidate.endswith("."):
        return False
    return bool(ROLE_HINT_PATTERN.search(candidate))


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


def _clean_company_name(value: Optional[str]) -> Optional[str]:
    candidate = _normalize_line(value or "")
    if not candidate:
        return None
    candidate = re.sub(r"\(\s*(?:\d{4}\s*(?:-|to)\s*(?:\d{4}|now|present)|digital agency)\s*\)", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\(\s*\)", "", candidate)
    candidate = re.sub(r"\s*-\s*[A-Z][A-Za-z.\s]+,\s*[A-Z][A-Za-z.\s]+$", "", candidate)
    candidate = re.sub(r"\b(?:Bengaluru|Bangalore|Chennai|Hyderabad|Pune|Mumbai|Delhi|Gurugram|Noida)\b$", "", candidate).strip(" |-,:")
    candidate = re.sub(r"\s+", " ", candidate).strip(" |-,:")
    return candidate or None


def _parse_date_token(token: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    raw = _normalize_line(token).lower().replace(".", "")
    if not raw:
        return None
    raw = re.sub(r"(?<=\d)'(?=\d{2}\b)", "", raw)
    raw = re.sub(r"\b(?P<year>\d{4})[/-](?P<month>\d{1,2})\b", r"\g<month>/\g<year>", raw)
    raw = re.sub(r"\b(?P<month>\d{1,2})\.(?P<year>\d{2,4})\b", r"\g<month>/\g<year>", raw)
    raw = re.sub(rf"\b({MONTH_PATTERN})[-/](\d{{2,4}})\b", r"\1 \2", raw, flags=re.IGNORECASE)
    raw = re.sub(rf"\b({MONTH_PATTERN})\s*,\s*(\d{{2,4}})\b", r"\1 \2", raw, flags=re.IGNORECASE)
    compact_month_year_match = re.fullmatch(r"(?P<month>\d{1,2})/(?P<year>\d{2,4})", raw)
    if compact_month_year_match and len(compact_month_year_match.group("year")) == 2:
        year_fragment = int(compact_month_year_match.group("year"))
        year_value = 2000 + year_fragment if year_fragment <= 49 else 1900 + year_fragment
        raw = f"{int(compact_month_year_match.group('month'))}/{year_value}"

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
            return datetime(year_int, month_int + 1, 1) - timedelta(days=1)
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

    for index, line in enumerate(lines):
        if not line:
            flush()
            continue
        if SECTION_BREAK_PATTERN.match(line):
            flush()
            break

        line_has_date = bool(extract_date_ranges(line))
        next_nonempty = ""
        for future_line in lines[index + 1:]:
            if future_line:
                next_nonempty = future_line
                break
        next_has_date = bool(next_nonempty and extract_date_ranges(next_nonempty))

        if current and seen_date and line_has_date:
            flush()
        if current and not line_has_date and next_has_date and _looks_like_experience_heading(line):
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


def _split_block_on_multiple_date_ranges(block_lines: Sequence[str]) -> List[List[str]]:
    if not block_lines:
        return []
    split_blocks: List[List[str]] = []
    current: List[str] = []
    seen_date = False
    for line in block_lines:
        has_date = bool(extract_date_ranges(line))
        if current and seen_date and has_date:
            split_blocks.append(current)
            current = [line]
            seen_date = True
            continue
        current.append(line)
        seen_date = seen_date or has_date
    if current:
        split_blocks.append(current)
    return split_blocks


def _remove_date_range_text(line: str) -> str:
    normalized = _normalize_line(line)
    return DATE_RANGE_REGEX.sub("", normalized).strip(" |-,:")


def _extract_company_from_heading_line(line: str, role: Optional[str] = None) -> Optional[str]:
    candidate = _normalize_line(line)
    if not candidate:
        return None
    candidate = re.sub(
        r"(?i)^(?:work experience|professional experience|employment history|employment|career history|experience)\s+",
        "",
        candidate,
    ).strip(" |-,:")

    if role and candidate.lower().startswith(role.lower()):
        candidate = candidate[len(role):].strip(" |-,:")

    candidate = re.sub(r"(?i)^previously worked at\s+", "", candidate).strip()
    candidate = re.sub(r"(?i)^at\s+", "", candidate).strip()
    candidate = re.sub(r"\([^)]*\)", "", candidate).strip(" |-,:")
    if not candidate:
        return None

    company_match = re.search(
        r"(?i)(?P<company>[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*)*\s+(?:Pvt\.?\s+Ltd\.?|Ltd\.?|Inc\.?|Corp\.?|Corporation|Technologies|Solutions|Systems|Labs|Works|LLP|Services|School|College|University|Institute))\b",
        candidate,
    )
    if company_match:
        return _clean_company_name(company_match.group("company"))

    if role and not COMPANY_PATTERN.search(candidate) and not _looks_like_company(candidate):
        return None

    if " in " in candidate.lower():
        parts = re.split(r"\bin\b", candidate, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2 and _looks_like_company(parts[1]):
            return _clean_company_name(parts[1])

    parts = candidate.split()
    if len(parts) >= 3 and parts[-1][:1].isupper():
        inferred = " ".join(parts[:-1]).strip()
        if inferred and len(inferred.split()) >= 2:
            return _clean_company_name(inferred)

    return None


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
    headline_lines = [_remove_date_range_text(line) for line in block_lines[:3]]
    headline_lines = [line for line in headline_lines if line]
    role_hint = None
    for line in headline_lines:
        role_hint_match = ROLE_TITLE_PATTERN.search(line)
        if role_hint_match:
            role_hint = _normalize_line(role_hint_match.group("role"))
            break
    for line in headline_lines:
        extracted = _extract_company_from_heading_line(line, role_hint)
        if extracted and _looks_like_company(extracted):
            return extracted

    context_lines = _candidate_lines_near_date(block_lines)
    for line in context_lines:
        if " - " in line:
            left_part, right_part = [part.strip() for part in line.split(" - ", 1)]
            if "," in right_part and _looks_like_company(left_part):
                return _clean_company_name(left_part)
        if " at " in line.lower():
            parts = re.split(r"\bat\b", line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and _looks_like_company(parts[1]):
                return _clean_company_name(parts[1])
        if " in " in line.lower():
            parts = re.split(r"\bin\b", line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and _looks_like_company(parts[1]):
                return _clean_company_name(parts[1])
        if "|" in line:
            parts = [part.strip() for part in line.split("|") if part.strip()]
            for part in reversed(parts):
                if _looks_like_company(part):
                    return _clean_company_name(part)
        if COMPANY_PATTERN.search(line):
            return _clean_company_name(line)
        if _looks_like_company(line):
            return _clean_company_name(line)
    if SPACY_AVAILABLE:
        doc = get_experience_doc("\n".join(context_lines))
        if doc is not None:
            for ent in doc.ents:
                candidate = _normalize_line(ent.text)
                if ent.label_ == "ORG" and _looks_like_company(candidate):
                    return _clean_company_name(candidate)
    return None


def _extract_role_candidate(block_lines: Sequence[str], company: Optional[str]) -> Optional[str]:
    context_lines = _candidate_lines_near_date(block_lines)
    for line in context_lines:
        normalized = _normalize_line(line)
        if not normalized or _is_bullet_line(line):
            continue
        if company and normalized == company:
            continue
        if " at " in normalized.lower() and len(normalized.split()) <= 12:
            parts = re.split(r"\bat\b", normalized, maxsplit=1, flags=re.IGNORECASE)
            candidate = _normalize_line(parts[0])
            if ROLE_HINT_PATTERN.search(candidate) and not _is_skill_like(candidate):
                return candidate
        if " in " in normalized.lower() and len(normalized.split()) <= 12:
            parts = re.split(r"\bin\b", normalized, maxsplit=1, flags=re.IGNORECASE)
            candidate = _normalize_line(parts[0])
            if ROLE_HINT_PATTERN.search(candidate) and not _is_skill_like(candidate):
                return candidate
        if "|" in normalized:
            parts = [part.strip() for part in normalized.split("|") if part.strip()]
            for part in parts:
                if part == company:
                    continue
                title_match = ROLE_TITLE_PATTERN.search(part)
                if title_match:
                    candidate = _normalize_line(title_match.group("role"))
                    if candidate and not _is_skill_like(candidate):
                        return candidate
                if ROLE_HINT_PATTERN.search(part) and not _is_skill_like(part) and not COMPANY_PATTERN.search(part):
                    return _normalize_line(part)
        prose_match = PROSE_ROLE_PATTERN.search(normalized)
        if prose_match:
            candidate = _normalize_line(prose_match.group("role"))
            if candidate and not _is_skill_like(candidate):
                return candidate
        title_match = ROLE_TITLE_PATTERN.search(normalized)
        if title_match:
            candidate = _normalize_line(title_match.group("role"))
            if candidate and not _is_skill_like(candidate):
                return candidate
        if ROLE_HINT_PATTERN.search(normalized) and not _is_skill_like(normalized) and not COMPANY_PATTERN.search(normalized) and len(normalized.split()) <= 6:
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
    if not any(ROLE_HINT_PATTERN.search(line) or COMPANY_PATTERN.search(line) or " at " in line.lower() or "|" in line or " in " in line.lower() for line in headline_lines):
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


def merge_overlapping_ranges(ranges: Sequence[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
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
        for candidate_block in _split_block_on_multiple_date_ranges(block):
            entry = _entry_from_block(candidate_block)
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


def extract_total_experience(text: str, ignore_internships: bool = False) -> Dict[str, Any]:
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
