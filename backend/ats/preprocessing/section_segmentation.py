from __future__ import annotations

import re
from typing import Dict, List

SECTION_ALIASES = {
    "header": [
        "contact",
        "contact information",
        "personal details",
        "profile summary",
    ],
    "summary": [
        "summary",
        "professional summary",
        "executive summary",
        "profile",
        "career summary",
        "objective",
        "career objective",
        "professional profile",
        "about me",
    ],
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "key skills",
        "competencies",
        "tech stack",
        "tools",
        "technologies",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "career history",
        "relevant experience",
        "career experience",
    ],
    "education": [
        "education",
        "academic background",
        "academic qualification",
        "academic qualifications",
        "qualification",
        "qualifications",
    ],
    "projects": [
        "projects",
        "project",
        "personal projects",
        "work projects",
        "professional projects",
        "academic projects",
        "side projects",
        "open source projects",
    ],
    "languages": [
        "languages",
        "language",
        "language proficiency",
    ],
}

BOUNDARY_ONLY_ALIASES = {
    "certifications",
    "certification",
    "licenses",
    "licenses and certifications",
    "achievements",
    "awards",
    "honors",
    "publications",
    "languages",
    "interests",
    "hobbies",
    "references",
    "contact",
    "volunteering",
    "volunteer experience",
    "activities",
}

HEADER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s/&,\-()]{0,50}:?$")
INLINE_HEADER_PATTERN = re.compile(
    r"^(?P<header>[A-Za-z][A-Za-z\s/&,\-()]{1,50}?):\s*(?P<content>.+)$"
)
WHITESPACE_PATTERN = re.compile(r"\s+")


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


def _normalize_header(value: str) -> str:
    value = _normalize_text(value).strip().lower().rstrip(":")
    value = re.sub(r"[^a-z\s/&,\-()]", " ", value)
    return WHITESPACE_PATTERN.sub(" ", value).strip()


def _alias_to_section(line: str) -> str | None:
    normalized = _normalize_header(line)
    if not normalized:
        return None

    for section, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return section

    return None


def _is_boundary_header(line: str) -> bool:
    normalized = _normalize_header(line)
    if not normalized:
        return False
    if normalized in BOUNDARY_ONLY_ALIASES:
        return True
    return _alias_to_section(line) is not None


def _looks_like_header(line: str) -> bool:
    stripped = _normalize_text(line).strip()
    if not stripped:
        return False
    if not HEADER_PATTERN.match(stripped):
        return False
    if len(stripped.split()) > 6:
        return False
    if any(char.isdigit() for char in stripped):
        return False
    return True


def _clean_section_content(lines: List[str]) -> str:
    cleaned_lines: List[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if cleaned_lines and cleaned_lines[-1] != "":
                cleaned_lines.append("")
            continue
        cleaned_lines.append(stripped)

    while cleaned_lines and cleaned_lines[-1] == "":
        cleaned_lines.pop()

    return "\n".join(cleaned_lines).strip()


def segment_resume_sections(text: str) -> Dict[str, str]:
    """
    Detect major resume sections using header aliases and conservative boundary heuristics.
    """
    sections = {name: "" for name in SECTION_ALIASES}
    if not text or not text.strip():
        return sections

    normalized_text = _normalize_text(text)
    lines = normalized_text.split("\n")
    current_section: str | None = None
    buffers = {name: [] for name in SECTION_ALIASES}
    header_lines: List[str] = []

    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            if current_section:
                buffers[current_section].append("")
            continue

        if index < 12 and not current_section:
            header_lines.append(line)

        inline_match = INLINE_HEADER_PATTERN.match(line)
        if inline_match:
            header = inline_match.group("header")
            content = inline_match.group("content").strip()
            next_section = _alias_to_section(header)
            if next_section:
                current_section = next_section
                if content:
                    buffers[current_section].append(content)
                continue

        if _looks_like_header(line):
            next_section = _alias_to_section(line)
            if next_section:
                current_section = next_section
                continue
            if _is_boundary_header(line):
                current_section = None
                continue

        if current_section:
            buffers[current_section].append(line)

    for section, collected_lines in buffers.items():
        sections[section] = _clean_section_content(collected_lines)

    sections["header"] = _clean_section_content(header_lines[:10])
    return sections


def get_section_content(text: str, section: str) -> str:
    return segment_resume_sections(text).get(section, "")
