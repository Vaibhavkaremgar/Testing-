from __future__ import annotations

import re
from typing import Dict, List

from ats.datasets.parser_config_loader import ParserConfigLoader

CORE_SECTIONS = ("experience", "skills", "education", "projects")
OPTIONAL_SECTIONS = ("header", "summary", "languages", "achievements", "certifications", "awards", "publications", "interests", "references")
ALL_SECTIONS = CORE_SECTIONS + OPTIONAL_SECTIONS

_parser_config_loader = ParserConfigLoader()
_parser_vocabulary = _parser_config_loader.load_parser_vocabulary()


def _compile_exact_terms(terms: List[str]) -> re.Pattern:
    escaped_terms = [re.escape(term) for term in terms if term]
    return re.compile(rf"(?i)^(?:{'|'.join(escaped_terms)})$") if escaped_terms else re.compile(r"$^")


def _compile_prefix_terms(terms: List[str]) -> re.Pattern:
    escaped_terms = [re.escape(term) for term in terms if term]
    return re.compile(rf"(?i)^(?:{'|'.join(escaped_terms)})\b") if escaped_terms else re.compile(r"$^")


def _compile_contains_terms(terms: List[str]) -> re.Pattern:
    escaped_terms = [re.escape(term) for term in terms if term]
    return re.compile(rf"(?i)\b(?:{'|'.join(escaped_terms)})\b") if escaped_terms else re.compile(r"$^")


_section_header_terms = {
    str(key).strip().lower(): [str(value).strip().lower() for value in values if str(value).strip()]
    for key, values in (_parser_vocabulary.get("section_header_terms") or {}).items()
}
SECTION_HEADER_PATTERNS = {
    section: _compile_exact_terms(terms)
    for section, terms in _section_header_terms.items()
}
SECTION_PREFIX_PATTERNS = {
    section: _compile_prefix_terms(terms)
    for section, terms in _section_header_terms.items()
}
BOUNDARY_HEADER_PATTERNS = [
    _compile_exact_terms([str(value).strip().lower() for value in (_parser_vocabulary.get("boundary_headers") or []) if str(value).strip()])
]

INLINE_HEADER_PATTERN = re.compile(r"^(?P<header>[^:]{1,60}?):\s*(?P<content>.+)$")
DATE_RANGE_PATTERN = re.compile(
    r"(?i)\b(?:"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4}"
    r")\s*(?:-|to|until)\s*(?:present|current|now|"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)\s+\d{4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4})\b"
)
ROLE_HINT_PATTERN = _compile_contains_terms([str(value).strip().lower() for value in (_parser_vocabulary.get("role_hint_terms") or []) if str(value).strip()])
COMPANY_HINT_PATTERN = _compile_contains_terms([str(value).strip().lower() for value in (_parser_vocabulary.get("company_hint_terms") or []) if str(value).strip()])
DECORATION_PATTERN = re.compile(r"^[\s|_\-=~*#.:]+|[\s|_\-=~*#.:]+$")
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
BULLET_PREFIX_PATTERN = re.compile(r"^\s*[\-\*\u2022\u25aa\u25e6\u00b7]+\s*")
CONTACT_HEADER_PATTERN = _compile_prefix_terms([str(value).strip().lower() for value in (_parser_vocabulary.get("contact_header_terms") or []) if str(value).strip()])


def _normalize_line(line: str) -> str:
    normalized = (line or "").replace("\r", "")
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2022": " ",
        "\u25aa": " ",
        "\u25e6": " ",
        "\u00b7": " ",
        "\u00a0": " ",
        "â€“": "-",
        "â€”": "-",
        "â€¢": " ",
        "â–ª": " ",
        "â—¦": " ",
        "â—": " ",
        "Ã¢â‚¬â€œ": "-",
        "Ã¢â‚¬â€": "-",
        "Ã‚Â·": " ",
        "Ã¢â‚¬Â¢": " ",
        "Ã¢â€“Âª": " ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def _clean_header_candidate(line: str) -> str:
    cleaned = _normalize_line(line).strip(":")
    cleaned = DECORATION_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"[^A-Za-z\s-]", " ", cleaned)
    cleaned = WHITESPACE_PATTERN.sub(" ", cleaned)
    return cleaned.strip(" -")


def _match_section_name(header_text: str) -> str | None:
    candidate = _clean_header_candidate(header_text)
    if not candidate:
        return None
    for section, pattern in SECTION_HEADER_PATTERNS.items():
        if pattern.match(candidate):
            return section
    for section, pattern in SECTION_PREFIX_PATTERNS.items():
        if pattern.match(candidate):
            return section
    return None


def _extract_prefixed_header_content(line: str, section: str | None) -> str:
    if not section:
        return ""
    normalized = _normalize_line(line)
    prefix_pattern = SECTION_PREFIX_PATTERNS.get(section)
    if prefix_pattern is None:
        return ""
    match = prefix_pattern.match(_clean_header_candidate(line))
    if not match:
        return ""

    raw_match = re.match(prefix_pattern.pattern, normalized, re.IGNORECASE)
    if not raw_match:
        return ""

    remainder = normalized[raw_match.end():].strip(" :-|")
    if not remainder or _match_section_name(remainder):
        return ""
    return remainder


def _is_boundary_header(header_text: str) -> bool:
    candidate = _clean_header_candidate(header_text)
    if not candidate:
        return False
    return any(pattern.match(candidate) for pattern in BOUNDARY_HEADER_PATTERNS)


def _looks_like_header(line: str) -> bool:
    candidate = _clean_header_candidate(line)
    if not candidate:
        return False
    if len(candidate.split()) > 6:
        return False
    return candidate.isalpha() or " " in candidate or "-" in candidate


def _clean_section_content(lines: List[str]) -> str:
    cleaned: List[str] = []
    for line in lines:
        normalized = _normalize_line(line)
        normalized = BULLET_PREFIX_PATTERN.sub("", normalized)
        if not normalized:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue
        cleaned.append(normalized)
    while cleaned and cleaned[-1] == "":
        cleaned.pop()
    return "\n".join(cleaned).strip()


def _collect_inferred_experience(lines: List[str]) -> str:
    blocks: List[List[str]] = []
    current: List[str] = []
    seen_date = False

    def looks_like_employment(block: List[str]) -> bool:
        joined = " ".join(block[:4])
        return bool(
            DATE_RANGE_PATTERN.search(joined)
            and (ROLE_HINT_PATTERN.search(joined) or COMPANY_HINT_PATTERN.search(joined) or " at " in joined.lower() or "|" in joined)
        )

    def flush() -> None:
        nonlocal current, seen_date
        cleaned = [item for item in current if item.strip()]
        if cleaned and seen_date and looks_like_employment(cleaned):
            blocks.append(cleaned)
        current = []
        seen_date = False

    for raw_line in lines:
        line = _normalize_line(raw_line)
        if not line:
            flush()
            continue
        if _is_boundary_header(line) or _match_section_name(line) in {"education", "projects", "skills"}:
            flush()
            continue
        has_date = bool(DATE_RANGE_PATTERN.search(line))
        if current and seen_date and has_date:
            flush()
        current.append(line)
        seen_date = seen_date or has_date
    flush()
    return "\n\n".join("\n".join(block) for block in blocks[:12]).strip()


def segment_resume_sections(text: str) -> Dict[str, str]:
    sections = {name: "" for name in ALL_SECTIONS}
    if not text or not text.strip():
        return sections

    normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
    raw_lines = normalized_text.split("\n")
    current_section: str | None = None
    buffers = {name: [] for name in ALL_SECTIONS}
    header_buffer: List[str] = []
    collecting_header = True

    for index, raw_line in enumerate(raw_lines):
        line = _normalize_line(raw_line)
        if not line:
            if current_section:
                buffers[current_section].append("")
            continue

        inline_match = INLINE_HEADER_PATTERN.match(line)
        if inline_match:
            next_section = _match_section_name(inline_match.group("header"))
            if next_section:
                if current_section == "skills" and next_section == "languages":
                    buffers[current_section].append(line)
                    continue
                collecting_header = False
                current_section = next_section
                content = _normalize_line(inline_match.group("content"))
                if content:
                    buffers[current_section].append(content)
                continue

        if _looks_like_header(line):
            next_section = _match_section_name(line)
            if next_section:
                collecting_header = False
                current_section = next_section
                content = _extract_prefixed_header_content(line, next_section)
                if content:
                    buffers[current_section].append(content)
                continue
            if _is_boundary_header(line):
                collecting_header = False
                current_section = None
                continue

        if index < 12 and collecting_header and not current_section:
            header_buffer.append(line)
            continue

        if current_section == "summary" and index < 12 and CONTACT_HEADER_PATTERN.match(line):
            header_buffer.append(line)
            continue

        if current_section:
            buffers[current_section].append(line)

    for section in ALL_SECTIONS:
        if section == "header":
            sections[section] = _clean_section_content(header_buffer[:10])
        else:
            sections[section] = _clean_section_content(buffers[section])

    if not sections["experience"]:
        sections["experience"] = _collect_inferred_experience(raw_lines)

    return sections


def get_section_content(text: str, section: str) -> str:
    return segment_resume_sections(text).get(section, "")
