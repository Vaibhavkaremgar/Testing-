from __future__ import annotations

import calendar
import logging
import re
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from dateutil import parser as date_parser

from ats.datasets.parser_config_loader import ParserConfigLoader
from ats.preprocessing.section_segmentation import get_section_content
from app.spacy_nlp import SPACY_AVAILABLE, get_experience_doc

logger = logging.getLogger(__name__)

MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
PRESENT_PATTERN = r"(?:present|current|currently|now|today|ongoing|till date|till now|till-date|tilldate)"
EXTENDED_PRESENT_PATTERN = r"(?:present|current|currently|now|today|ongoing|continuing|till date|till now|till-date|tilldate|to date|date)"
DATE_TOKEN_PATTERN = (
    rf"(?:{MONTH_PATTERN}[.\-/\s,'’]+\d{{2,4}}"
    rf"|\d{{1,2}}[.\-/\s](?:{MONTH_PATTERN})[.\-/\s,'’]+\d{{2,4}}"
    rf"|(?:{MONTH_PATTERN})[.\-/\s,'’]+\d{{1,2}}(?:st|nd|rd|th)?[,\s.\-/]+\d{{2,4}}"
    rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}\.\d{{1,2}}"
    rf"|\d{{4}}[/-]\d{{1,2}}"
    rf"|\d{{1,2}}\.\d{{2,4}}"
    rf"|\d{{4}})"
)
DATE_RANGE_REGEX = re.compile(
    rf"(?:\bfrom\s+)?(?P<start>{DATE_TOKEN_PATTERN})\s*"
    rf"(?:-|–|—|to|till|until|through)\s*"
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
PROSE_COMPANY_PATTERN = re.compile(
    rf"(?i)\b(?:worked at|working at|employed at|joined|with|at)\s+"
    rf"(?P<company>[A-Z][A-Za-z0-9&.'-]*(?:\s+[A-Z][A-Za-z0-9&.'-]*){{0,6}}?)\s+"
    rf"(?:from\s+)?(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|to|till|until|through)\s*(?P<end>{PRESENT_PATTERN}|{DATE_TOKEN_PATTERN})"
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
OPEN_ENDED_DATE_RANGE_REGEX = re.compile(
    rf"(?:\bfrom\s+)?(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|â€“|â€”)\s*$",
    re.IGNORECASE,
)
YEAR_SPAN_PATTERN = re.compile(r"^(?P<start>\d{4})\s*[-/]\s*(?P<end>\d{2,4})$")
FISCAL_YEAR_TOKEN_PATTERN = re.compile(r"(?i)^(?P<prefix>FY|AY)\s*[- ]?(?P<start>\d{4})(?:\s*[-/]\s*(?P<end>\d{2,4}))?$")
OPEN_RANGE_PREFIX_PATTERN = re.compile(
    rf"(?i)\b(?:since|from|starting)\s+(?P<start>{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)\b"
)
SENTENCE_RANGE_PATTERN = re.compile(
    rf"(?i)\b(?:worked\s+from|from|joined|starting|started)\s+(?P<start>{DATE_TOKEN_PATTERN})\b"
    rf"(?:.*?\b(?:to|till|until|through)\b\s+(?P<end>{EXTENDED_PRESENT_PATTERN}|{DATE_TOKEN_PATTERN}))?"
)
BRACKETED_DATE_PATTERN = re.compile(
    rf"[\[\(]\s*(?P<value>{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)\s*[\]\)]",
    re.IGNORECASE,
)
OPEN_ENDED_SENTENCE_PATTERN = re.compile(
    rf"(?i)\b(?P<start>{DATE_TOKEN_PATTERN})\s*(?:-|–|—|~)\s*$"
)
DATE_LIKE_PATTERN = re.compile(
    rf"(?i)\b(?:{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?|{EXTENDED_PRESENT_PATTERN})\b"
)
LAYER2_RANGE_REGEX = re.compile(
    rf"(?P<start>{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)\s*"
    rf"(?:-|–|—|to|till|until|through|~)\s*"
    rf"(?P<end>{EXTENDED_PRESENT_PATTERN}|{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)",
    re.IGNORECASE,
)
MERGE_ADJACENT_INTERVAL_DAYS = 31
MAX_REASONABLE_EXPERIENCE_MONTHS = 45 * 12
TEXT_DURATION_PATTERN = re.compile(
    r"(?i)\b(?:(?P<years>\d+(?:\.\d+)?)\s+years?)?(?:\s*(?P<months>\d+)\s+months?)?\b"
)
KNOWN_LOCATION_TOKENS = {
    "bangalore", "bengaluru", "chennai", "hyderabad", "pune", "mumbai", "delhi",
    "gurugram", "noida", "karnataka", "tamil nadu", "maharashtra", "haryana",
    "india", "remote",
}


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
    normalized = BRACKETED_DATE_PATTERN.sub(lambda match: match.group("value"), normalized)
    normalized = re.sub(r"(?i)\bfrom\s+", "", normalized)
    normalized = re.sub(r"(?i)\btill date\b", "Present", normalized)
    normalized = re.sub(r"(?i)\btill now\b", "Present", normalized)
    normalized = re.sub(r"(?i)\btill-date\b", "Present", normalized)
    normalized = re.sub(r"(?i)\btilldate\b", "Present", normalized)
    normalized = re.sub(r"(?i)\bto date\b", "Present", normalized)
    normalized = re.sub(r"(?i)\bcontinuing\b", "Present", normalized)
    normalized = re.sub(
        rf"(?P<start>{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)\s+/\s+(?P<end>{DATE_TOKEN_PATTERN}|{EXTENDED_PRESENT_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)",
        r"\g<start> - \g<end>",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        rf"(?i)\bjoined\s+(?P<start>{DATE_TOKEN_PATTERN})\s+and\s+worked\s+until\s+(?P<end>{DATE_TOKEN_PATTERN}|{EXTENDED_PRESENT_PATTERN})",
        r"\g<start> - \g<end>",
        normalized,
    )
    normalized = re.sub(
        rf"(?i)\bworked\s+from\s+(?P<start>{DATE_TOKEN_PATTERN})\s+to\s+(?P<end>{DATE_TOKEN_PATTERN}|{EXTENDED_PRESENT_PATTERN})",
        r"\g<start> - \g<end>",
        normalized,
    )
    normalized = OPEN_RANGE_PREFIX_PATTERN.sub(lambda match: f"{match.group('start')} - Present", normalized)
    normalized = re.sub(
        rf"(?im)\b(?P<start>{DATE_TOKEN_PATTERN}|FY\s*\d{{4}}(?:[-/]\d{{2,4}})?|AY\s*\d{{4}}(?:[-/]\d{{2,4}})?)\s*(?:-|–|—|~)\s*$",
        r"\g<start> - Present",
        normalized,
    )
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
    normalized = re.sub(r"^\s*(?:\d{1,2}\)|\d{1,2}\.\s+)", "", normalized).strip()
    return normalized


def _is_present_token(token: str) -> bool:
    compact = re.sub(r"\s+", " ", str(token or "").strip(" -|,.:")).lower()
    return bool(compact and re.fullmatch(EXTENDED_PRESENT_PATTERN, compact, flags=re.IGNORECASE))


def _safe_build_datetime(year: int, month: int, *, is_end: bool) -> Optional[datetime]:
    try:
        day = calendar.monthrange(year, month)[1] if is_end else 1
        return datetime(year, month, day)
    except ValueError:
        return None


def _parse_month_name_year(token: str, *, is_end: bool) -> Optional[datetime]:
    match = re.fullmatch(rf"(?i)(?P<month>{MONTH_PATTERN})[\s'\-/,]*(?P<year>\d{{2}}|\d{{4}})", token.strip())
    if not match:
        return None
    month_value = date_parser.parse(match.group("month"), fuzzy=True, default=datetime(2000, 1, 1)).month
    year_fragment = match.group("year")
    year_value = int(year_fragment)
    if len(year_fragment) == 2:
        year_value = 2000 + year_value if year_value <= 49 else 1900 + year_value
    return _safe_build_datetime(year_value, month_value, is_end=is_end)


def _parse_numeric_month_year(token: str, *, is_end: bool) -> Optional[datetime]:
    match = re.fullmatch(r"(?P<month>\d{1,2})[/.](?P<year>\d{2,4})", token.strip())
    if not match:
        return None
    month_value = int(match.group("month"))
    year_fragment = match.group("year")
    year_value = int(year_fragment)
    if len(year_fragment) == 2:
        year_value = 2000 + year_value if year_value <= 49 else 1900 + year_value
    return _safe_build_datetime(year_value, month_value, is_end=is_end)


def _parse_year_month_numeric(token: str, *, is_end: bool) -> Optional[datetime]:
    match = re.fullmatch(r"(?P<year>\d{4})[./-](?P<month>\d{1,2})", token.strip())
    if not match:
        return None
    return _safe_build_datetime(int(match.group("year")), int(match.group("month")), is_end=is_end)


def _parse_year_only(token: str, *, is_end: bool) -> Optional[datetime]:
    if not re.fullmatch(r"\d{4}", token.strip()):
        return None
    return _safe_build_datetime(int(token.strip()), 12 if is_end else 1, is_end=is_end)


def _parse_year_span(token: str, *, is_end: bool) -> Optional[datetime]:
    match = YEAR_SPAN_PATTERN.fullmatch(token.strip())
    if not match:
        return None
    start_year = int(match.group("start"))
    end_fragment = match.group("end")
    end_year = int(end_fragment)
    if len(end_fragment) == 2:
        end_year = (start_year // 100) * 100 + end_year
        if end_year < start_year:
            end_year += 100
    return _safe_build_datetime(end_year if is_end else start_year, 12 if is_end else 1, is_end=is_end)


def _parse_fiscal_year_token(token: str, *, is_end: bool) -> Optional[datetime]:
    match = FISCAL_YEAR_TOKEN_PATTERN.fullmatch(token.strip())
    if not match:
        return None
    start_year = int(match.group("start"))
    end_fragment = match.group("end")
    end_year = start_year
    if end_fragment:
        end_year = int(end_fragment)
        if len(end_fragment) == 2:
            end_year = (start_year // 100) * 100 + end_year
            if end_year < start_year:
                end_year += 100
    return _safe_build_datetime(end_year if is_end else start_year, 12 if is_end else 1, is_end=is_end)


def _parse_text_duration_months(token: str) -> int:
    match = TEXT_DURATION_PATTERN.search(token or "")
    if not match:
        return 0
    years_value = float(match.group("years") or 0)
    months_value = int(match.group("months") or 0)
    return max(int(round(years_value * 12)) + months_value, 0)


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
    if ROLE_HINT_PATTERN.search(candidate):
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
    # Remove role fragments and connector words before validating the company.
    candidate = re.sub(r"(?i)^(?:worked|working|joined|serving)\s+", "", candidate)
    candidate = re.sub(r"(?i)\b(?:at|with|for)\b\s+", "", candidate)
    role_match = ROLE_TITLE_PATTERN.search(candidate)
    if role_match:
        candidate = candidate.replace(role_match.group("role"), " ")
    candidate = re.sub(r"\(\s*(?:\d{4}\s*(?:-|to)\s*(?:\d{4}|now|present)|digital agency)\s*\)", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\(\s*\)", "", candidate)
    candidate = re.sub(r"\s*-\s*[A-Z][A-Za-z.\s]+,\s*[A-Z][A-Za-z.\s]+$", "", candidate)
    for location_token in sorted(KNOWN_LOCATION_TOKENS, key=len, reverse=True):
        candidate = re.sub(rf"(?i)\b{re.escape(location_token)}\b", "", candidate)
    candidate = re.sub(r"\s+", " ", candidate).strip(" |-,:")
    return candidate or None


def _parse_date_token(token: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    if _is_present_token(token):
        return today or datetime.utcnow()
    normalized_token = _normalize_line(token)
    year_month_dot_match = re.fullmatch(r"(?P<year>\d{4})\.(?P<month>\d{1,2})", normalized_token)
    if year_month_dot_match:
        return _safe_build_datetime(
            int(year_month_dot_match.group("year")),
            int(year_month_dot_match.group("month")),
            is_end=is_end,
        )
    for parser_fn in (
        _parse_month_name_year,
        _parse_numeric_month_year,
        _parse_year_month_numeric,
        _parse_fiscal_year_token,
        _parse_year_span,
        _parse_year_only,
    ):
        try:
            parsed = parser_fn(normalized_token, is_end=is_end)
        except Exception as exc:
            logger.warning("Experience date parser %s failed for token=%s error=%s", parser_fn.__name__, token, exc)
            parsed = None
        if parsed is not None:
            return parsed

    raw = normalized_token.lower()
    if not raw:
        return None
    raw = re.sub(rf"(?i)\b({MONTH_PATTERN})'(\d{{2}})\b", r"\1 \2", raw)
    raw = re.sub(r"(?<=\d)'(?=\d{2}\b)", "", raw)
    raw = re.sub(r"\b(?P<year>\d{4})\.(?P<month>\d{1,2})\b", r"\g<month>/\g<year>", raw)
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
    compact_month_name_year = re.fullmatch(rf"(?i)(?P<month>{MONTH_PATTERN})\s+(?P<year>\d{{2}}|\d{{4}})", raw)
    if compact_month_name_year:
        month_label = compact_month_name_year.group("month")
        year_fragment = compact_month_name_year.group("year")
        year_value = int(year_fragment)
        if len(year_fragment) == 2:
            year_value = 2000 + year_value if year_value <= 49 else 1900 + year_value
        month_value = date_parser.parse(month_label, fuzzy=True, default=datetime(2000, 1, 1)).month
        if is_end:
            if month_value == 12:
                return datetime(year_value, 12, 31)
            return datetime(year_value, month_value + 1, 1) - timedelta(days=1)
        return datetime(year_value, month_value, 1)
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
        logger.warning("Experience date parse failed for token=%s normalized=%s", token, raw)
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


@lru_cache(maxsize=4096)
def _parse_date_token_cached(token: str, is_end: bool) -> Optional[datetime]:
    return _parse_date_token(token, is_end=is_end)


def parse_date(date_string: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    if today is None:
        return _parse_date_token_cached(str(date_string or ""), is_end)
    return _parse_date_token(date_string, is_end=is_end, today=today)


def normalize_date(date_string: str, is_end: bool = False, today: Optional[datetime] = None) -> Optional[datetime]:
    return parse_date(date_string, is_end=is_end, today=today)


def extract_experience_section(text: str) -> str:
    cleaned = _normalize_text(text)
    if not cleaned:
        return ""
    explicit_section = get_section_content(cleaned, "experience")
    if explicit_section and len(explicit_section.splitlines()) >= 2:
        return explicit_section
    fallback_section = _infer_experience_section_from_full_text(cleaned)
    return explicit_section or fallback_section


def _infer_experience_section_from_full_text(text: str) -> str:
    lines = [_normalize_line(line) for line in _normalize_text(text).split("\n") if _normalize_line(line)]
    if not lines:
        return ""

    collected: List[str] = []
    active = False
    for index, line in enumerate(lines[:240]):
        if NON_EXPERIENCE_HEADER_PATTERN.match(line):
            if active:
                break
            continue
        if EXPERIENCE_HEADER_PATTERN.match(line) or EXPERIENCE_CONTINUATION_HEADER_PATTERN.match(line):
            active = True
            collected.append(line)
            continue
        if DATE_RANGE_REGEX.search(line) or OPEN_ENDED_DATE_RANGE_REGEX.search(line):
            if not active and index > 0:
                previous = lines[index - 1]
                if previous and not NON_EXPERIENCE_HEADER_PATTERN.match(previous):
                    collected.append(previous)
            active = True
            collected.append(line)
            continue
        if active:
            if SECTION_BREAK_PATTERN.match(line):
                break
            collected.append(line)

    inferred = "\n".join(collected).strip()
    return inferred if (DATE_RANGE_REGEX.search(inferred) or OPEN_ENDED_DATE_RANGE_REGEX.search(inferred)) else ""


def extract_date_ranges(text: str) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    normalized_text = _normalize_text(text)
    for match in DATE_RANGE_REGEX.finditer(normalized_text):
        start_text = match.group("start")
        end_text = match.group("end")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not _is_valid_experience_window(start_date, end_date):
            logger.warning("Experience range rejected start=%s end=%s matched=%s", start_text, end_text, match.group(0))
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
    for match in OPEN_ENDED_DATE_RANGE_REGEX.finditer(normalized_text):
        start_text = match.group("start")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date("Present", is_end=True)
        if not _is_valid_experience_window(start_date, end_date):
            logger.warning("Open-ended experience range rejected start=%s matched=%s", start_text, match.group(0))
            continue
        matches.append(
            {
                "start": start_text,
                "end": "Present",
                "start_date": start_date,
                "end_date": end_date,
                "matched_text": match.group(0),
                "span": match.span(),
            }
        )
    return matches


def _extract_layer2_date_ranges(text: str) -> List[Dict[str, Any]]:
    normalized_text = _normalize_text(text)
    ranges: List[Dict[str, Any]] = []
    for match in LAYER2_RANGE_REGEX.finditer(normalized_text):
        start_text = match.group("start")
        end_text = match.group("end")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not _is_valid_experience_window(start_date, end_date):
            logger.warning("Layer2 experience range parse failed start=%s end=%s matched=%s", start_text, end_text, match.group(0))
            continue
        ranges.append(
            {
                "start": start_text,
                "end": end_text,
                "start_date": start_date,
                "end_date": end_date,
                "matched_text": match.group(0),
                "span": match.span(),
            }
        )

    for match in SENTENCE_RANGE_PATTERN.finditer(normalized_text):
        start_text = match.group("start")
        end_text = match.group("end") or "Present"
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not _is_valid_experience_window(start_date, end_date):
            logger.warning("Sentence experience range parse failed start=%s end=%s matched=%s", start_text, end_text, match.group(0))
            continue
        ranges.append(
            {
                "start": start_text,
                "end": end_text,
                "start_date": start_date,
                "end_date": end_date,
                "matched_text": match.group(0),
                "span": match.span(),
            }
        )

    standalone_token = _normalize_line(normalized_text)
    if YEAR_SPAN_PATTERN.fullmatch(standalone_token) or FISCAL_YEAR_TOKEN_PATTERN.fullmatch(standalone_token):
        start_date = parse_date(standalone_token, is_end=False)
        end_date = parse_date(standalone_token, is_end=True)
        if _is_valid_experience_window(start_date, end_date):
            ranges.append(
                {
                    "start": standalone_token,
                    "end": standalone_token,
                    "start_date": start_date,
                    "end_date": end_date,
                    "matched_text": standalone_token,
                    "span": (0, len(standalone_token)),
                }
            )
        else:
            logger.warning("Standalone experience token parse failed token=%s", standalone_token)

    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in ranges:
        key = (item["start_date"], item["end_date"], item["matched_text"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


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

    if "|" in candidate:
        pipe_parts = [part.strip() for part in candidate.split("|") if part.strip()]
        for part in pipe_parts:
            part = re.sub(
                r"\s+-\s+[A-Z][A-Za-z.\s]+(?:,\s*[A-Z][A-Za-z.\s]+)?(?:\s*/\s*Remote)?$",
                "",
                part,
            ).strip(" |-,:")
            if part and _looks_like_company(part):
                return _clean_company_name(part)
            if re.match(r"^[A-Z][A-Za-z0-9&.'-]{2,}$", part) and not ROLE_HINT_PATTERN.search(part):
                return _clean_company_name(part)
        if role is None and ROLE_HINT_PATTERN.search(candidate):
            return None

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
                part = re.sub(
                    r"\s+-\s+[A-Z][A-Za-z.\s]+(?:,\s*[A-Z][A-Za-z.\s]+)?(?:\s*/\s*Remote)?$",
                    "",
                    part,
                ).strip(" |-,:")
                if _looks_like_company(part):
                    return _clean_company_name(part)
                if re.match(r"^[A-Z][A-Za-z0-9&.'-]{2,}$", part) and not ROLE_HINT_PATTERN.search(part):
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


def _months_between(start_date: datetime, end_date: datetime) -> int:
    if not start_date or not end_date or end_date < start_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day >= start_date.day:
        months += 1
    return max(months, 1)


def _duration_parts(total_months: int) -> Tuple[int, int]:
    years = max(total_months, 0) // 12
    months = max(total_months, 0) % 12
    return years, months


def _format_duration(total_months: int) -> str:
    years, months = _duration_parts(total_months)
    parts: List[str] = []
    if years:
        parts.append(f"{years} year" + ("s" if years != 1 else ""))
    if months:
        parts.append(f"{months} month" + ("s" if months != 1 else ""))
    return " ".join(parts) if parts else "Less than 1 month"


def _is_valid_experience_window(
    start_date: Optional[datetime],
    end_date: Optional[datetime],
    *,
    today: Optional[datetime] = None,
) -> bool:
    if not start_date or not end_date or end_date < start_date:
        return False
    reference_today = today or datetime.utcnow()
    if start_date > reference_today:
        return False
    if end_date > reference_today and (end_date.year != reference_today.year or end_date.month != reference_today.month):
        return False
    return _months_between(start_date, end_date) > 0


def _experience_confidence(entry: Dict[str, Any]) -> float:
    score = 0.2
    if entry.get("company"):
        score += 0.25
    if entry.get("role"):
        score += 0.25
    if entry.get("start_date") and entry.get("end_date"):
        score += 0.2
    if entry.get("duration_months", 0) > 0:
        score += 0.1
    return round(min(score, 1.0), 2)


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
    if not company and role and block_lines:
        first_line = _normalize_line(block_lines[0])
        if first_line.lower().startswith(role.lower()):
            remainder = first_line[len(role):].strip(" |-,:")
            remainder = re.sub(r"\s+[A-Z][A-Za-z.\s]+,\s*[A-Z][A-Za-z.\s]+$", "", remainder).strip(" |-,:")
            remainder = re.sub(
                r"\b(?:Bengaluru|Bangalore|Chennai|Hyderabad|Pune|Mumbai|Delhi|Gurugram|Noida|Karnataka|Tamil Nadu|Maharashtra|Haryana)\b.*$",
                "",
                remainder,
            ).strip(" |-,:")
            fallback_company = _clean_company_name(remainder)
            if fallback_company and len(fallback_company.split()) >= 1:
                company = fallback_company
    if not company:
        return None
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
    if not _is_valid_experience_window(start_date, end_date):
        return None
    duration_months = _months_between(start_date, end_date)
    duration_months = max(duration_months, 0)
    duration_years = round(duration_months / 12.0, 1)
    description = " ".join(
        line for line in block_lines if not DATE_RANGE_REGEX.search(line) and line not in {role, company}
    )[:600]
    entry = {
        "role": role,
        "title": role,
        "company": company,
        "start": _serialize_year_month(start_date),
        "end": _serialize_year_month(end_date),
        "start_date": _serialize_year_month(start_date),
        "end_date": _serialize_year_month(end_date),
        "duration_years": duration_years,
        "duration_months": duration_months,
        "duration": _format_duration(duration_months),
        "raw_text": "\n".join(block_lines)[:1000],
        "is_current": bool(re.search(PRESENT_PATTERN, date_range["end"], re.IGNORECASE)),
        "description": description,
    }
    entry["confidence"] = _experience_confidence(entry)
    _internship_src = (entry.get("role") or "") + " " + (entry.get("company") or "")
    entry["is_internship"] = bool(re.search(r"(?i)\b(intern|internship|trainee|apprentice)\b", _internship_src))
    return entry


def _extract_structured_experience_entries(section_text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    lines = [_normalize_line(line) for line in _normalize_text(section_text).split("\n") if _normalize_line(line)]
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
        if not _is_valid_experience_window(start_date, end_date):
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
                "start": _serialize_year_month(start_date),
                "end": _serialize_year_month(end_date),
                "start_date": _serialize_year_month(start_date),
                "end_date": _serialize_year_month(end_date),
                "duration_years": round(_months_between(start_date, end_date) / 12.0, 1),
                "duration_months": _months_between(start_date, end_date),
                "duration": _format_duration(_months_between(start_date, end_date)),
                "raw_text": "\n".join(str(item) for item in current_block.get("raw_lines") or [])[:1000],
                "is_current": bool(re.search(PRESENT_PATTERN, range_match.group("end"), re.IGNORECASE)),
                "description": details[:600],
            }
        )
        entries[-1]["confidence"] = _experience_confidence(entries[-1])
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
        if start <= (merged[-1][1] + timedelta(days=MERGE_ADJACENT_INTERVAL_DAYS)):
            if end > merged[-1][1]:
                logger.info(
                    "Merging experience intervals existing_end=%s next_start=%s next_end=%s",
                    merged[-1][1].date(),
                    start.date(),
                    end.date(),
                )
                merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def compute_total_experience(ranges: Sequence[Tuple[datetime, datetime]]) -> float:
    merged = merge_overlapping_ranges(ranges)
    total_days = sum((end - start).days + 1 for start, end in merged)
    return round(total_days / 365.25, 1) if total_days > 0 else 0.0


def _sort_key(entry: Dict[str, Any]) -> Tuple[int, datetime, datetime]:
    start_date = parse_date(entry.get("start_date", ""), is_end=False) or datetime(1900, 1, 1)
    end_date = (datetime.utcnow() if entry.get("is_current") else parse_date(entry.get("end_date", ""), is_end=True)) or datetime(1900, 1, 1)
    return (1 if entry.get("is_current") else 0, end_date, start_date)


_COMPANY_NOISE = re.compile(
    r"\b(?:pvt|ltd|inc|llc|limited|technologies|technology|solutions|services|group|consulting|india|global)\b",
    re.IGNORECASE
)


def _normalize_company_key(name: str) -> str:
    if not name:
        return ""
    return _COMPANY_NOISE.sub("", name).strip().lower()


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
            _normalize_company_key(entry.get("company", "")),
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
    entries: List[Dict[str, Any]] = []
    for raw_line in _normalize_text(text).splitlines():
        normalized_line = _normalize_line(raw_line)
        if not normalized_line:
            continue
        match = INLINE_ROLE_DATE_PATTERN.search(normalized_line)
        if not match:
            continue
        role = _normalize_line(match.group("role"))
        start_text = match.group("start")
        end_text = match.group("end")
        start_date = parse_date(start_text, is_end=False)
        end_date = parse_date(end_text, is_end=True)
        if not _is_valid_experience_window(start_date, end_date):
            continue
        if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", role):
            continue
        company, description = _extract_inline_company_and_description(match.group("rest"))
        if not company:
            continue
        if "," in company and not COMPANY_PATTERN.search(company):
            continue
        entries.append(
            {
                "role": role,
                "title": role,
                "company": company,
                "start": _serialize_year_month(start_date),
                "end": _serialize_year_month(end_date),
                "start_date": _serialize_year_month(start_date),
                "end_date": _serialize_year_month(end_date),
                "duration_years": round(_months_between(start_date, end_date) / 12.0, 1),
                "duration_months": _months_between(start_date, end_date),
                "duration": _format_duration(_months_between(start_date, end_date)),
                "raw_text": normalized_line[:1000],
                "is_current": bool(re.search(PRESENT_PATTERN, end_text, re.IGNORECASE)),
                "description": description[:600],
            }
        )
        entries[-1]["confidence"] = _experience_confidence(entries[-1])
    return entries


def _extract_prose_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    normalized = _normalize_text(text)
    entries: List[Dict[str, Any]] = []
    for match in PROSE_COMPANY_PATTERN.finditer(normalized):
        company = _clean_company_name(match.group("company"))
        start_date = parse_date(match.group("start"), is_end=False)
        end_date = parse_date(match.group("end"), is_end=True)
        if not company or not _is_valid_experience_window(start_date, end_date):
            continue
        surrounding_text = normalized[max(0, match.start() - 120): min(len(normalized), match.end() + 120)]
        role_match = PROSE_ROLE_PATTERN.search(surrounding_text) or ROLE_TITLE_PATTERN.search(surrounding_text)
        role = _normalize_line(role_match.group("role")) if role_match and role_match.groupdict().get("role") else None
        internship_source = " ".join(filter(None, [role or "", company]))
        if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", internship_source):
            continue
        duration_months = _months_between(start_date, end_date)
        entry = {
            "role": role,
            "title": role,
            "company": company,
            "start": _serialize_year_month(start_date),
            "end": _serialize_year_month(end_date),
            "start_date": _serialize_year_month(start_date),
            "end_date": _serialize_year_month(end_date),
            "duration_years": round(duration_months / 12.0, 1),
            "duration_months": duration_months,
            "duration": _format_duration(duration_months),
            "raw_text": _normalize_line(match.group(0))[:1000],
            "is_current": bool(re.search(PRESENT_PATTERN, match.group("end"), re.IGNORECASE)),
            "description": "",
        }
        entry["confidence"] = _experience_confidence(entry)
        entries.append(entry)
    return entries


def _select_current_experience(entries: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not entries:
        return None
    valid_entries = [
        entry
        for entry in entries
        if _is_valid_experience_window(
            parse_date(entry.get("start_date", ""), is_end=False),
            parse_date(entry.get("end_date", ""), is_end=True),
        )
    ]
    ordered = sorted(valid_entries, key=_sort_key, reverse=True)
    return ordered[0] if ordered else None


def _infer_role_company_from_context(block_lines: Sequence[str]) -> tuple[Optional[str], Optional[str]]:
    for raw_line in block_lines[:3]:
        line = _remove_date_range_text(raw_line)
        if not line:
            continue
        for separator in (" - ", " | ", " @ "):
            if separator not in line:
                continue
            left, right = [part.strip(" |-,:") for part in line.split(separator, 1)]
            left_is_role = bool(ROLE_HINT_PATTERN.search(left))
            right_is_role = bool(ROLE_HINT_PATTERN.search(right))
            left_company = _clean_company_name(left)
            right_company = _clean_company_name(right)
            if left_is_role and right and not right_is_role:
                return left, right_company or right
            if right_is_role and left and not left_is_role:
                return right, left_company or left
        at_match = re.search(r"(?i)^(?P<role>.+?)\s+at\s+(?P<company>.+)$", line)
        if at_match:
            role = _normalize_line(at_match.group("role"))
            company = _clean_company_name(at_match.group("company"))
            if role or company:
                return role or None, company or None
    return None, None


def _build_layer2_entry(block_lines: Sequence[str], date_range: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not block_lines:
        return None
    company = _extract_company_candidate(block_lines)
    role = _extract_role_candidate(block_lines, company)
    inferred_role, inferred_company = _infer_role_company_from_context(block_lines)
    if not role and inferred_role:
        role = inferred_role
    if not company and inferred_company:
        company = inferred_company
    if role and not company:
        for separator in (" - ", " | ", " @ "):
            if separator in role:
                role_part, company_part = [part.strip(" |-,:") for part in role.split(separator, 1)]
                if ROLE_HINT_PATTERN.search(role_part):
                    role = _normalize_line(role_part)
                    company = _clean_company_name(company_part)
                break
        split_role, split_company = _infer_role_company_from_context([role])
        if split_role and split_company:
            role = split_role
            company = split_company
    if company and DATE_LIKE_PATTERN.search(str(company)):
        company = None
    start_date = date_range.get("start_date")
    end_date = date_range.get("end_date")
    if not _is_valid_experience_window(start_date, end_date):
        logger.warning("Layer2 entry rejected due to invalid window block=%s", " | ".join(block_lines[:3]))
        return None
    duration_months = _months_between(start_date, end_date)
    entry = {
        "role": role,
        "title": role,
        "company": company,
        "start": _serialize_year_month(start_date),
        "end": _serialize_year_month(end_date),
        "start_date": _serialize_year_month(start_date),
        "end_date": _serialize_year_month(end_date),
        "duration_years": round(duration_months / 12.0, 1),
        "duration_months": duration_months,
        "duration": _format_duration(duration_months),
        "raw_text": "\n".join(block_lines)[:1000],
        "is_current": bool(_is_present_token(str(date_range.get("end") or ""))),
        "description": " ".join(line for line in block_lines if not DATE_LIKE_PATTERN.search(line))[:600],
        "confidence": 0.55,
        "is_fallback_layer2": True,
    }
    if entry["company"] or entry["role"]:
        entry["confidence"] = _experience_confidence(entry)
    return entry


def _extract_layer2_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    experience_section = extract_experience_section(text)
    if not experience_section:
        logger.warning("Layer2 experience parser could not find an experience section")
        return []

    normalized_lines = [_normalize_line(line) for line in _normalize_text(experience_section).split("\n") if _normalize_line(line)]
    entries: List[Dict[str, Any]] = []
    for index, line in enumerate(normalized_lines):
        line_ranges = _extract_layer2_date_ranges(line)
        if not line_ranges and index + 1 < len(normalized_lines):
            paired_text = f"{line}\n{normalized_lines[index + 1]}"
            line_ranges = _extract_layer2_date_ranges(paired_text)
        if not line_ranges:
            continue
        context_block = [
            candidate for candidate in normalized_lines[max(0, index - 1): min(len(normalized_lines), index + 3)]
            if candidate and not NON_EXPERIENCE_HEADER_PATTERN.match(candidate)
        ]
        for date_range in line_ranges:
            entry = _build_layer2_entry(context_block, date_range)
            if not entry:
                continue
            internship_source = " ".join(filter(None, [entry.get("role") or "", entry.get("company") or "", entry.get("raw_text") or ""]))
            if ignore_internships and re.search(r"(?i)\b(?:intern|internship|trainee|apprentice)\b", internship_source):
                logger.info("Layer2 experience parser skipped internship entry=%s", internship_source[:120])
                continue
            entries.append(entry)
    if not entries:
        logger.warning("Layer2 experience parser found no entries in section")
    return _dedupe_entries(entries)


def _summarize_experience_result(entries: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    ranges: List[Tuple[datetime, datetime]] = []
    for entry in entries:
        start = parse_date(entry.get("start_date", ""), is_end=False)
        end = parse_date(entry.get("end_date", ""), is_end=True)
        if not _is_valid_experience_window(start, end):
            continue
        ranges.append((start, end))
    merged = merge_overlapping_ranges(ranges)
    total_months = sum(_months_between(start, end) for start, end in merged)
    current_entry = _select_current_experience(entries)
    return {
        "entries": list(entries),
        "merged_ranges": merged,
        "total_months": total_months,
        "current_entry": current_entry,
        "average_confidence": round(
            sum(float(entry.get("confidence") or 0.0) for entry in entries) / len(entries),
            2,
        ) if entries else 0.0,
    }


def _result_needs_review(total_months: int, entries: Sequence[Dict[str, Any]]) -> bool:
    if total_months < 0:
        logger.warning("Experience summary flagged: negative total_months=%s", total_months)
        return True
    if total_months > MAX_REASONABLE_EXPERIENCE_MONTHS:
        logger.warning("Experience summary flagged: unrealistic total_months=%s", total_months)
        return True
    if entries and total_months == 0:
        logger.warning("Experience summary flagged: entries present but total months is zero")
        return True
    return False


def _should_use_layer2(primary_summary: Dict[str, Any], layer2_summary: Dict[str, Any]) -> bool:
    if not layer2_summary["entries"]:
        return False
    layer2_current = layer2_summary.get("current_entry") or {}
    layer2_has_current_signal = bool(layer2_current.get("company") or layer2_current.get("role"))
    if not primary_summary["entries"]:
        logger.info("Layer2 experience summary selected because Layer1 found no entries")
        return True
    if layer2_summary["total_months"] > primary_summary["total_months"]:
        logger.info(
            "Layer2 experience summary selected because it improved total_months old=%s new=%s",
            primary_summary["total_months"],
            layer2_summary["total_months"],
        )
        return True
    if (
        layer2_has_current_signal
        and not primary_summary["current_entry"]
    ):
        logger.info("Layer2 experience summary selected because it resolved a current role/company")
        return True
    if (
        len(layer2_summary["entries"]) > len(primary_summary["entries"])
        and layer2_summary["average_confidence"] >= max(primary_summary["average_confidence"] - 0.05, 0)
    ):
        logger.info("Layer2 experience summary selected because it captured more entries with comparable confidence")
        return True
    return False


def _normalize_current_role_company(entry: Optional[Dict[str, Any]]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    if not entry:
        return None, None, None
    current_role = entry.get("role")
    current_company = entry.get("company")
    if current_role and not current_company:
        for separator in (" - ", " | ", " @ "):
            if separator in str(current_role):
                role_part, company_part = [part.strip(" |-,:") for part in str(current_role).split(separator, 1)]
                if ROLE_HINT_PATTERN.search(role_part):
                    current_role = role_part
                    current_company = _clean_company_name(company_part)
                break
    return current_role, current_company, entry.get("start_date")


def extract_experience_entries(text: str, ignore_internships: bool = False) -> List[Dict[str, Any]]:
    experience_section = extract_experience_section(text)
    if not experience_section:
        return []

    structured_entries = _extract_structured_experience_entries(experience_section, ignore_internships=ignore_internships)
    blocks = _split_experience_blocks(experience_section)
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
    inline_entries = _extract_inline_experience_entries(experience_section, ignore_internships=ignore_internships)
    prose_entries = _extract_prose_experience_entries(experience_section, ignore_internships=ignore_internships)
    if not entries:
        entries.extend(inline_entries)
        entries.extend(prose_entries)
    else:
        entries.extend(inline_entries)
        entries.extend(prose_entries)
    logger.debug("Parsed jobs: %s", entries)
    return _dedupe_entries(entries)


def extract_total_experience(text: str, ignore_internships: bool = False) -> Dict[str, Any]:
    layer1_entries = extract_experience_entries(text, ignore_internships=ignore_internships)
    normalized_layer1_entries: List[Dict[str, Any]] = []
    for entry in layer1_entries:
        start = parse_date(entry.get("start_date", ""), is_end=False)
        end = parse_date(entry.get("end_date", ""), is_end=True)
        if not _is_valid_experience_window(start, end):
            logger.warning("Layer1 experience entry rejected role=%s company=%s", entry.get("role"), entry.get("company"))
            continue
        if not entry.get("duration_months"):
            explicit_duration = _parse_text_duration_months(entry.get("raw_text", ""))
            if explicit_duration:
                entry["duration_months"] = explicit_duration
                entry["duration_years"] = round(explicit_duration / 12.0, 1)
                entry["duration"] = _format_duration(explicit_duration)
        elif start and end:
            computed_duration = _months_between(start, end)
            if abs(int(entry.get("duration_months") or 0) - computed_duration) > 1:
                logger.info(
                    "Experience duration cross-validation mismatch role=%s company=%s stated=%s computed=%s",
                    entry.get("role"),
                    entry.get("company"),
                    entry.get("duration_months"),
                    computed_duration,
                )
        normalized_layer1_entries.append(entry)

    layer1_summary = _summarize_experience_result(normalized_layer1_entries)
    layer2_entries = _extract_layer2_experience_entries(text, ignore_internships=ignore_internships)
    layer2_summary = _summarize_experience_result(layer2_entries)

    selected_summary = layer2_summary if _should_use_layer2(layer1_summary, layer2_summary) else layer1_summary
    normalized_entries = list(selected_summary["entries"])
    total_months = int(selected_summary["total_months"] or 0)
    if total_months > MAX_REASONABLE_EXPERIENCE_MONTHS:
        logger.warning("Selected experience summary exceeded max allowed months=%s", total_months)
        total_months = 0
        normalized_entries = []
        selected_summary = {
            **selected_summary,
            "entries": [],
            "total_months": 0,
            "merged_ranges": [],
            "current_entry": None,
        }

    total_years = round(total_months / 12.0, 1) if total_months > 0 else None
    current_entry = selected_summary["current_entry"]
    average_confidence = selected_summary["average_confidence"]
    years_part, months_part = _duration_parts(total_months)
    total_experience_text = _format_duration(total_months) if total_months else ""
    if normalized_entries and not total_experience_text:
        total_experience_text = "Less than 1 month"
    needs_review = _result_needs_review(total_months, normalized_entries)
    if layer1_summary["total_months"] and layer2_summary["total_months"] and layer1_summary["total_months"] != layer2_summary["total_months"]:
        logger.info(
            "Experience cross validation mismatch layer1_months=%s layer2_months=%s",
            layer1_summary["total_months"],
            layer2_summary["total_months"],
        )

    current_role, current_company, current_role_start = _normalize_current_role_company(current_entry)

    return {
        "total_experience_years": total_years,
        "total_experience_months": total_months,
        "experience_months": total_months,
        "total_experience_years_component": years_part,
        "total_experience_months_component": months_part,
        "total_experience": total_experience_text,
        "experience_duration": total_experience_text,
        "current_company": current_company,
        "current_role": current_role,
        "current_role_start": current_role_start,
        "experience_extraction_confidence": average_confidence,
        "needs_review": needs_review,
        "experience_parser_layer": "layer2" if selected_summary is layer2_summary else "layer1",
        "experience": normalized_entries,
        "experiences": normalized_entries,
    }
