from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dateutil import parser as date_parser

from ats.datasets.parser_config_loader import ParserConfigLoader
from ats.preprocessing.section_segmentation import get_section_content, segment_resume_sections
from app.spacy_nlp import SPACY_AVAILABLE, get_experience_doc

logger = logging.getLogger(__name__)

MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
PRESENT_PATTERN = r"(?:present|current|now|today|ongoing|till date|till now|till-date|tilldate)"
DATE_TOKEN_PATTERN = (
    rf"(?:{MONTH_PATTERN}[.\-/\s,']+\d{{2,4}}"
    rf"|\d{{1,2}}[.\-/\s](?:{MONTH_PATTERN})[.\-/\s,']+\d{{2,4}}"
    rf"|(?:{MONTH_PATTERN})[.\-/\s,']+\d{{1,2}}(?:st|nd|rd|th)?[,\s.\-/]+\d{{2,4}}"
    rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}[/-]\d{{1,2}}"
    rf"|\d{{1,2}}\.\d{{2,4}}"
    rf"|\d{{4}})"
)
DATE_RANGE_REGEX = re.compile(
    rf"(?:\bfrom\s+)?(?P<start>{DATE_TOKEN_PATTERN})\s*"
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
_parser_config_loader = ParserConfigLoader()
_parser_vocabulary = _parser_config_loader.load_parser_vocabulary()
_company_hint_terms = [
    str(value).strip().lower()
    for value in (_parser_vocabulary.get("company_hint_terms") or [])
    if str(value).strip()
]
if not _company_hint_terms:
    _company_hint_terms = [
        "pvt", "ltd", "inc", "llc", "llp", "technologies", "solutions", "corp", "corporation",
        "organisation", "organization", "systems", "labs", "works", "school", "college",
        "university", "academy", "institute", "services",
    ]
COMPANY_PATTERN = re.compile(
    rf"(?i)\b(?:{'|'.join(re.escape(term) for term in _company_hint_terms)})\b"
)
SKILL_LIKE_PATTERN = re.compile(
    r"(?i)\b(?:python|java|javascript|typescript|react|angular|vue|node(?:\.js)?|fastapi|django|flask|sql|aws|azure|gcp|docker|kubernetes|seo|crm|machine learning)\b"
)
COMPANY_STOPWORD_PATTERN = re.compile(r"(?i)\b(?:strategy|analytics|marketing|platform|pipeline|roadmap|adoption|enterprise)\b")
BULLET_PREFIX_PATTERN = re.compile(r"^\s*[\u2022\u25aa\u25e6\u25cf\u00b7\-\*]+\s*")
SECTION_BREAK_PATTERN = re.compile(r"(?i)^(?:education|projects?|skills|technical skills|certifications?|summary|profile|languages?)$")
EXPERIENCE_HEADER_PATTERN = re.compile(r"(?i)^(?:work experience|professional experience|employment history|employment|career history|experience|period)$")
NON_EXPERIENCE_HEADER_PATTERN = re.compile(
    r"(?i)^(?:certifications?|soft skills?|technical skills|skills|education|projects?|languages?|profile summary|summary|job objective|objective|contact details|areas of expertise)$"
)
EXPERIENCE_CONTINUATION_HEADER_PATTERN = re.compile(r"(?i)^(?:previous experience|prior experience|internship|internships?)$")
CERTIFICATION_ROLE_PATTERN = re.compile(r"(?i)\b(?:certified|certification|certificate|ccna|azure fundamentals|associate - back-end)\b")
ORGANIZATION_LINE_PATTERN = re.compile(r"(?i)^organization\s*:\s*(?P<value>.+)$")
DESIGNATION_LINE_PATTERN = re.compile(r"(?i)^designation\s*:\s*(?P<value>.+)$")
PERIOD_LINE_PATTERN = re.compile(r"(?i)^(?:period\s*:?\s*)?(?P<value>.+)$")
INLINE_ROLE_PATTERN_TEXT = (
    r"(?:[A-Z][A-Za-z0-9()\/&.-]*\s+){0,6}"
    r"(?:Engineer|Analyst|Manager|Consultant|Developer|Specialist|Architect|Administrator|Intern|Partner|Teacher|Officer)"
    r"(?:\s+[A-Z0-9][A-Za-z0-9()\/&.-]*){0,3}"
)
INLINE_ROLE_DATE_PATTERN = re.compile(
    rf"(?P<role>{INLINE_ROLE_PATTERN_TEXT})\s+\|\s+"
    rf"(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|â€“|â€”|to|until|through)\s*"
    rf"(?P<end>{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})\s+"
    rf"(?P<rest>.+?)"
    rf"(?=(?P<next>{INLINE_ROLE_PATTERN_TEXT})\s+\|\s+{DATE_TOKEN_PATTERN}\s*(?:-|â€“|â€”|to|until|through)\s*(?:{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})|KEY PROJECTS|PROJECTS|AWARDS|COMMUNITY|$)",
    re.IGNORECASE,
)
INLINE_ACTION_SPLIT_PATTERN = re.compile(
    r"(?i)\b(?:Own|Owned|Monitor(?:ed)?|Led|Developed|Authored|Achieved|Assisted|Completed|Executed|Validated|Troubleshot|Maintained|Mentored|Ensured|Built|Designed|Conducted|Spearheaded|Performed)\b"
)
ACTION_SENTENCE_PATTERN = re.compile(
    r"(?i)\b(?:designed|built|led|owned|managed|partnered|created|developed|delivered|reduced|defined|ran|spearheaded|implemented|launched|using)\b"
)
DATE_RANGE_REGEX = re.compile(
    rf"(?P<start>{DATE_TOKEN_PATTERN})\s*"
    rf"(?:-|–|—|\?|to|until|through)\s*"
    rf"(?P<end>{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})",
    re.IGNORECASE,
)
INLINE_ROLE_DATE_PATTERN = re.compile(
    rf"(?P<role>{INLINE_ROLE_PATTERN_TEXT})\s+\|\s+"
    rf"(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|–|—|\?|to|until|through)\s*"
    rf"(?P<end>{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})\s+"
    rf"(?P<rest>.+?)"
    rf"(?=(?P<next>{INLINE_ROLE_PATTERN_TEXT})\s+\|\s+{DATE_TOKEN_PATTERN}\s*(?:-|–|—|\?|to|until|through)\s*(?:{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})|KEY PROJECTS|PROJECTS|AWARDS|COMMUNITY|$)",
    re.IGNORECASE,
)
LEADING_ROLE_PATTERN = re.compile(
    r"(?i)^(?P<role>(?:(?:senior|sr|junior|jr|lead|principal|staff|associate|assistant|graphic|brand|visual|creative|content|product|frontend|front-end|backend|back-end|full[- ]stack|data|software|web|mobile|qa|devops|machine learning|ml|human resources|hr|engineering|business|intelligence|sales|marketing|customer|growth)\s+){0,5}(?:engineer|developer|manager|lead|analyst|consultant|architect|specialist|administrator|designer|executive|director|officer|associate|scientist|recruiter|tester|teacher|partner|generalist|coordinator))\b"
)


def _normalize_text(value: str) -> str:
    normalized = (value or "").replace("\r\n", "\n").replace("\r", "\n")
    replacements = {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
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
    normalized = re.sub(r"(?i)\bfrom\s+", "", normalized)
    normalized = re.sub(r"(?i)\btill\b", "to", normalized)
    normalized = re.sub(
        rf"(?i)(?P<start>{DATE_TOKEN_PATTERN}|{PRESENT_PATTERN})\s+\?\s+(?P<end>{DATE_TOKEN_PATTERN}|{PRESENT_PATTERN})",
        r"\g<start> - \g<end>",
        normalized,
    )
    normalized = re.sub(r"\s+\?\s+", " | ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _normalize_line(line: str) -> str:
    normalized = re.sub(r"\s+", " ", _normalize_text(line)).strip(" |-")
    normalized = re.sub(r"^\s*(?:\d+\)|\d+\.\s*)", "", normalized).strip()
    return normalized


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
    if ACTION_SENTENCE_PATTERN.search(candidate):
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
    compact_numeric_date = re.fullmatch(r"(?P<day>\d{1,2})[\s/-](?P<month>\d{1,2})[\s/-](?P<year>\d{4})", raw)
    if compact_numeric_date:
        day_int = int(compact_numeric_date.group("day"))
        month_int = int(compact_numeric_date.group("month"))
        year_int = int(compact_numeric_date.group("year"))
        if 1 <= month_int <= 12 and 1 <= day_int <= 31:
            try:
                return datetime(year_int, month_int, day_int)
            except ValueError:
                return None
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
        if current and seen_date and ORGANIZATION_LINE_PATTERN.match(line):
            flush()

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
        r"(?i)^(?:work experience|professional experience|employment history|employment|career history|experience|period)\s+",
        "",
        candidate,
    ).strip(" |-,:")

    if role and candidate.lower().startswith(role.lower()):
        candidate = candidate[len(role):].strip(" |-,:")

    candidate = re.sub(r"(?i)^previously worked at\s+", "", candidate).strip()
    candidate = re.sub(r"(?i)^at\s+", "", candidate).strip()
    if " in " in candidate.lower():
        parts = re.split(r"\bin\b", candidate, maxsplit=1, flags=re.IGNORECASE)
        if len(parts) == 2:
            candidate = parts[1].strip(" |-,:")
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
    for line in block_lines[:4]:
        organization_match = ORGANIZATION_LINE_PATTERN.match(_normalize_line(line))
        if organization_match:
            company = _clean_company_name(organization_match.group("value"))
            if company:
                return company

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
        normalized_line = _normalize_line(line.replace("?", "|"))
        if re.search(r"(?i)\broles?\s*and\s*responsibilit", normalized_line):
            continue
        if " - " in normalized_line:
            left_part, right_part = [part.strip() for part in normalized_line.split(" - ", 1)]
            if "," in right_part and _looks_like_company(left_part):
                return _clean_company_name(left_part)
        if " at " in normalized_line.lower():
            parts = re.split(r"\bat\b", normalized_line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and _looks_like_company(parts[1]):
                return _clean_company_name(parts[1])
        if " in " in normalized_line.lower():
            parts = re.split(r"\bin\b", normalized_line, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and _looks_like_company(parts[1]):
                return _clean_company_name(parts[1])
        if "|" in normalized_line:
            parts = [part.strip() for part in normalized_line.split("|") if part.strip()]
            for part in reversed(parts):
                if _looks_like_company(part):
                    return _clean_company_name(part)
        extracted = _extract_company_from_heading_line(normalized_line, role_hint)
        if extracted and _looks_like_company(extracted):
            return extracted
        if _looks_like_company(normalized_line):
            return _clean_company_name(normalized_line)
    if SPACY_AVAILABLE:
        doc = get_experience_doc("\n".join(context_lines))
        if doc is not None:
            for ent in doc.ents:
                candidate = _normalize_line(ent.text)
                if ent.label_ == "ORG" and _looks_like_company(candidate):
                    return _clean_company_name(candidate)
    return None


def _extract_role_candidate(block_lines: Sequence[str], company: Optional[str]) -> Optional[str]:
    for line in block_lines[:4]:
        designation_match = DESIGNATION_LINE_PATTERN.match(_normalize_line(line))
        if designation_match:
            candidate = _normalize_line(designation_match.group("value"))
            if candidate and not _is_skill_like(candidate):
                return candidate

    context_lines = _candidate_lines_near_date(block_lines)
    for line in context_lines:
        normalized = _normalize_line(line.replace("?", "|"))
        if not normalized or _is_bullet_line(line):
            continue
        if company and normalized == company:
            continue
        leading_match = LEADING_ROLE_PATTERN.search(normalized)
        if leading_match:
            candidate = _normalize_line(leading_match.group("role"))
            if candidate and not _is_skill_like(candidate):
                return candidate
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
    if role and CERTIFICATION_ROLE_PATTERN.search(role):
        return None
    if company and CERTIFICATION_ROLE_PATTERN.search(company):
        return None
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


def _extract_structured_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    lines = [_normalize_line(line) for line in _normalize_text(text).split("\n") if _normalize_line(line)]
    entries: List[Dict[str, Any]] = []
    current_block: Dict[str, Any] = {}

    def flush() -> None:
        nonlocal current_block
        if not current_block:
            return
        period_value = str(current_block.get("period") or "").strip()
        if not period_value:
            current_block = {}
            return
        range_match = DATE_RANGE_REGEX.search(period_value)
        if not range_match:
            current_block = {}
            return
        start_date = parse_date(range_match.group("start"), is_end=False)
        end_date = parse_date(range_match.group("end"), is_end=True)
        if not start_date or not end_date or end_date < start_date:
            current_block = {}
            return
        role = _normalize_line(str(current_block.get("designation") or ""))
        company = _clean_company_name(str(current_block.get("organization") or ""))
        internship_source = " ".join(filter(None, [role, company]))
        if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", internship_source):
            current_block = {}
            return
        if not role and not company:
            current_block = {}
            return
        details = " ".join(str(item) for item in current_block.get("details") or [])
        entries.append(
            {
                "role": role or None,
                "title": role or None,
                "company": company,
                "start_date": _serialize_year_month(start_date),
                "end_date": _serialize_year_month(end_date),
                "duration_years": round(max(0.0, (end_date - start_date).days + 1) / 365.25, 1),
                "raw_text": "\n".join(str(item) for item in current_block.get("raw_lines") or [])[:1000],
                "is_current": bool(re.search(PRESENT_PATTERN, range_match.group("end"), re.IGNORECASE)),
                "description": details[:600],
            }
        )
        current_block = {}

    for line in lines:
        organization_match = ORGANIZATION_LINE_PATTERN.match(line)
        if organization_match:
            flush()
            current_block = {
                "organization": organization_match.group("value"),
                "details": [],
                "raw_lines": [line],
            }
            continue
        if not current_block:
            continue
        current_block.setdefault("raw_lines", []).append(line)
        designation_match = DESIGNATION_LINE_PATTERN.match(line)
        if designation_match:
            current_block["designation"] = designation_match.group("value")
            continue
        normalized_line = line
        if normalized_line.lower() == "period":
            continue
        period_match = PERIOD_LINE_PATTERN.match(normalized_line.lstrip(": ").strip())
        if period_match and DATE_RANGE_REGEX.search(period_match.group("value")) and not current_block.get("period"):
            current_block["period"] = period_match.group("value")
            continue
        if NON_EXPERIENCE_HEADER_PATTERN.match(normalized_line) or EXPERIENCE_CONTINUATION_HEADER_PATTERN.match(normalized_line):
            flush()
            continue
        current_block.setdefault("details", []).append(normalized_line)
    flush()
    return entries


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
    deduped: List[Dict[str, Any]] = []
    primary_index: Dict[Tuple[str, str, str], int] = {}
    role_date_index: Dict[Tuple[str, str, str], int] = {}

    def conflict_score(item: Dict[str, Any]) -> Tuple[int, int, int, int]:
        raw_text = (item.get("raw_text") or "").lower()
        company = (item.get("company") or "").lower()
        company_pos = raw_text.find(company) if company else 99999
        if company_pos < 0:
            company_pos = 99999
        return (
            1 if item.get("description") else 0,
            1 if item.get("is_current") else 0,
            -company_pos,
            len(company),
        )

    for entry in entries:
        company = (entry.get("company") or "").lower()
        start_date = entry.get("start_date")
        end_date = entry.get("end_date")
        primary_key = (
            company,
            start_date,
            end_date,
        )
        role_key = (
            (entry.get("role") or "").lower(),
            company,
            entry.get("start_date"),
            entry.get("end_date"),
        )
        if any(
            (
                (existing.get("role") or "").lower(),
                (existing.get("company") or "").lower(),
                existing.get("start_date"),
                existing.get("end_date"),
            ) == role_key
            for existing in deduped
        ):
            continue
        role_date_key = (
            (entry.get("role") or "").lower(),
            start_date,
            end_date,
        )
        if role_date_key in role_date_index:
            existing = deduped[role_date_index[role_date_key]]
            if conflict_score(entry) > conflict_score(existing):
                deduped[role_date_index[role_date_key]] = entry
                primary_index[(
                    (existing.get("company") or "").lower(),
                    existing.get("start_date"),
                    existing.get("end_date"),
                )] = role_date_index[role_date_key]
                primary_index[primary_key] = role_date_index[role_date_key]
            continue
        if primary_key in primary_index:
            existing = deduped[primary_index[primary_key]]
            if existing.get("role") and not entry.get("role"):
                continue
            if entry.get("role") and not existing.get("role"):
                deduped[primary_index[primary_key]] = entry
                continue
            existing_role = (existing.get("role") or "").strip()
            new_role = (entry.get("role") or "").strip()
            if existing_role and new_role:
                if len(new_role.split()) > len(existing_role.split()):
                    deduped[primary_index[primary_key]] = entry
                continue
        deduped.append(entry)
        primary_index[primary_key] = len(deduped) - 1
        role_date_index[role_date_key] = len(deduped) - 1
    deduped.sort(key=_sort_key, reverse=True)
    return deduped


def _fallback_blocks_from_full_text(text: str) -> List[List[str]]:
    sections = segment_resume_sections(text)
    if sections.get("experience"):
        return _split_experience_blocks(sections["experience"])
    return _split_experience_blocks(_normalize_text(text))


def _looks_like_global_job_start(line: str, next_line: str = "") -> bool:
    normalized = _normalize_line(line)
    following = _normalize_line(next_line)
    if not normalized or _is_bullet_line(normalized):
        return False
    if NON_EXPERIENCE_HEADER_PATTERN.match(normalized) or EXPERIENCE_CONTINUATION_HEADER_PATTERN.match(normalized):
        return False
    if CERTIFICATION_ROLE_PATTERN.search(normalized):
        return False
    line_has_date = bool(extract_date_ranges(normalized))
    next_has_date = bool(following and extract_date_ranges(following))
    role_or_company_hint = bool(
        ROLE_HINT_PATTERN.search(normalized)
        or COMPANY_PATTERN.search(normalized)
        or "|" in normalized
        or "?" in normalized
        or " at " in normalized.lower()
    )
    if line_has_date and role_or_company_hint:
        return True
    if next_has_date and role_or_company_hint:
        return True
    return False


def _global_experience_blocks(text: str) -> List[List[str]]:
    lines = [_normalize_line(line) for line in _normalize_text(text).split("\n")]
    blocks: List[List[str]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if not _looks_like_global_job_start(line, next_line):
            index += 1
            continue
        block = [line]
        cursor = index + 1
        while cursor < len(lines):
            candidate = lines[cursor]
            future = lines[cursor + 1] if cursor + 1 < len(lines) else ""
            if not candidate:
                cursor += 1
                continue
            if cursor != index and _looks_like_global_job_start(candidate, future):
                break
            if NON_EXPERIENCE_HEADER_PATTERN.match(candidate):
                break
            if EXPERIENCE_CONTINUATION_HEADER_PATTERN.match(candidate):
                break
            block.append(candidate)
            cursor += 1
        if len(block) >= 2:
            blocks.append(block)
        index = max(cursor, index + 1)
    return blocks


def _extract_inline_company_and_description(rest: str) -> Tuple[Optional[str], str]:
    normalized = _normalize_line(rest)
    if not normalized:
        return None, ""
    action_match = INLINE_ACTION_SPLIT_PATTERN.search(normalized)
    company_part = normalized[: action_match.start()].strip(" |-,:") if action_match else normalized
    description = normalized[action_match.start():].strip() if action_match else ""
    company_part = re.sub(r"\s+-\s+[A-Z][A-Za-z.\s]+(?:,\s*[A-Z][A-Za-z.\s]+)?(?:\s*/\s*Remote)?$", "", company_part).strip(" |-,:")
    company_part = re.sub(r"\s+/+\s*Remote$", "", company_part).strip(" |-,:")
    company = _clean_company_name(company_part)
    return company, description


def _extract_inline_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    normalized = _normalize_text(text)
    entries: List[Dict[str, Any]] = []
    for match in INLINE_ROLE_DATE_PATTERN.finditer(normalized):
        role = _normalize_line(match.group("role"))
        start_text = match.group("start")
        end_text = match.group("end")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not start_date or not end_date or end_date < start_date:
            continue
        if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", role):
            continue
        company, description = _extract_inline_company_and_description(match.group("rest"))
        if not company:
            continue
        entries.append(
            {
                "role": role,
                "title": role,
                "company": company,
                "start_date": _serialize_year_month(start_date),
                "end_date": _serialize_year_month(end_date),
                "duration_years": round(max(0.0, (end_date - start_date).days + 1) / 365.25, 1),
                "raw_text": _normalize_line(match.group(0))[:1000],
                "is_current": bool(re.search(PRESENT_PATTERN, end_text, re.IGNORECASE)),
                "description": description[:600],
            }
        )
    return entries


def extract_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    experience_section = extract_experience_section(text)
    structured_entries = _extract_structured_experience_entries(text, ignore_internships=ignore_internships)
    blocks = _split_experience_blocks(experience_section) if experience_section else _fallback_blocks_from_full_text(text)
    blocks.extend(_global_experience_blocks(text))
    entries = list(structured_entries)
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
    if not entries:
        entries.extend(_extract_inline_experience_entries(experience_section or text, ignore_internships=ignore_internships))
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
