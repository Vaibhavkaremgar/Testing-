from __future__ import annotations

import re
from typing import Dict, List

from ats.datasets.parser_config_loader import ParserConfigLoader

CORE_SECTIONS = ("experience", "skills", "education", "projects")
OPTIONAL_SECTIONS = ("header", "contact", "summary", "languages", "achievements", "certifications", "awards", "publications", "interests", "references")
ALL_SECTIONS = CORE_SECTIONS + OPTIONAL_SECTIONS

DEFAULT_SECTION_HEADER_TERMS = {
    "summary": [
        "summary",
        "professional summary",
        "profile summary",
        "career summary",
        "professional overview",
        "executive summary",
    ],
    "contact": [
        "contact",
        "contact details",
        "contact information",
        "personal details",
        "personal information",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core skills",
        "key skills",
        "primary skills",
        "tools",
        "technologies",
        "technical expertise",
        "expertise",
        "tool stack",
        "tech stack",
        "tools and technologies",
        "tools & technologies",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment",
        "employment history",
        "career history",
        "work history",
        "internships",
        "internship experience",
        "previous experience",
        "prior experience",
        "period",
    ],
    "education": [
        "education",
        "academic background",
        "academic profile",
        "qualification",
        "qualifications",
        "education details",
    ],
    "projects": [
        "projects",
        "project",
        "work projects",
        "professional projects",
        "project profile",
    ],
    "certifications": [
        "certifications",
        "certification",
        "certificates",
        "certificate",
        "licenses and certifications",
        "licenses & certifications",
    ],
    "languages": [
        "languages",
        "language skills",
        "spoken languages",
    ],
}

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


_configured_section_header_terms = {
    str(key).strip().lower(): [str(value).strip().lower() for value in values if str(value).strip()]
    for key, values in (_parser_vocabulary.get("section_header_terms") or {}).items()
}
_section_header_terms = {key: list(values) for key, values in DEFAULT_SECTION_HEADER_TERMS.items()}
for key, values in _configured_section_header_terms.items():
    existing = _section_header_terms.setdefault(key, [])
    for value in values:
        if value not in existing:
            existing.append(value)
HEADER_NORMALIZATION_MAP = {
    "career profile": "summary",
    "career summary": "summary",
    "profile summary": "summary",
    "professional profile": "summary",
    "professional overview": "summary",
    "executive summary": "summary",
    "work history": "experience",
    "experience summary": "experience",
    "employment details": "experience",
    "professional background": "experience",
    "internships": "experience",
    "internship experience": "experience",
    "career journey": "experience",
    "period": "experience",
    "contact details": "contact",
    "contact information": "contact",
    "personal details": "contact",
    "personal information": "contact",
    "technical expertise": "skills",
    "skill set": "skills",
    "tools and technologies": "skills",
    "tools & technologies": "skills",
    "technology tools": "skills",
    "tech stack": "skills",
    "tool stack": "skills",
    "academic profile": "education",
    "education details": "education",
    "professional projects": "projects",
    "project profile": "projects",
    "spoken languages": "languages",
    "language skills": "languages",
    "certificates": "certifications",
    "licenses and certifications": "certifications",
    "licenses & certifications": "certifications",
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
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)[.\-/\s]+\d{2,4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}[/-]\d{2,4}"
    r"|\d{4}[/-]\d{1,2}"
    r"|\d{1,2}\.\d{2,4}"
    r"|\d{4}"
    r")\s*(?:-|to|until)\s*(?:present|current|now|"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)[.\-/\s]+\d{2,4}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}[/-]\d{2,4}"
    r"|\d{4}[/-]\d{1,2}"
    r"|\d{1,2}\.\d{2,4}"
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
    normalized_candidate = HEADER_NORMALIZATION_MAP.get(candidate.lower())
    if normalized_candidate:
        return normalized_candidate
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



_SECTION_ANCHOR_TEXT = {
    "experience": "employment job worked responsibilities managed led company role position",
    "skills": "tools technologies proficient languages frameworks software abilities",
    "education": "university college degree studied graduated diploma academic",
    "certifications": "certified awarded license accredited credential certification",
    "achievements": "achieved won recognition award performance impact result",
    "summary": "objective profile about myself overview professional background",
    "projects": "built developed created designed implemented project solution",
}

_section_anchor_docs = None


def _get_section_anchors():
    global _section_anchor_docs
    if _section_anchor_docs is not None:
        return _section_anchor_docs
    try:
        from app.spacy_nlp import get_nlp
        nlp = get_nlp()
        if nlp is None:
            _section_anchor_docs = {}
            return _section_anchor_docs
        _section_anchor_docs = {k: nlp(v) for k, v in _SECTION_ANCHOR_TEXT.items()}
    except Exception:
        _section_anchor_docs = {}
    return _section_anchor_docs


def semantic_section_fallback(text: str) -> dict:
    try:
        from app.spacy_nlp import get_nlp, get_section_doc
        nlp = get_nlp()
        if nlp is None:
            return {}
        anchors = _get_section_anchors()
        if not anchors:
            return {}
        doc = get_section_doc(text[:3000])
        if doc is None:
            return {}
        result = {k: [] for k in anchors}
        for sent in doc.sents:
            clean = sent.text.strip()
            if len(clean) < 10:
                continue
            best, best_score = None, 0.38
            for section, anchor_doc in anchors.items():
                try:
                    score = sent.similarity(anchor_doc)
                    if score > best_score:
                        best_score = score
                        best = section
                except Exception:
                    continue
            if best:
                result[best].append(clean)
        return result
    except Exception:
        return {}


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

        if current_section == "contact" and index < 20 and CONTACT_HEADER_PATTERN.match(line):
            buffers["contact"].append(line)
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

    populated = [k for k, v in sections.items() if v and k != "header"]
    if len(populated) < 2:
        sem = semantic_section_fallback(text)
        for k, v in sem.items():
            if not sections.get(k) and v:
                sections[k] = "\n".join(v)
    return sections


def get_section_content(text: str, section: str) -> str:
    return segment_resume_sections(text).get(section, "")
