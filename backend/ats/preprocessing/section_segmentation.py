from __future__ import annotations

import re
from typing import Dict, List

SECTION_ALIASES = {
    "skills": [
        "skills",
        "technical skills",
        "core competencies",
        "key skills",
        "competencies",
        "tech stack",
    ],
    "experience": [
        "experience",
        "work experience",
        "professional experience",
        "employment history",
        "work history",
        "internship",
        "internships",
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
    "summary",
    "professional summary",
    "profile",
    "objective",
    "certifications",
    "certification",
    "achievements",
    "awards",
    "publications",
    "languages",
    "interests",
    "references",
    "contact",
}

HEADER_PATTERN = re.compile(r"^[A-Za-z][A-Za-z\s/&,-]{0,40}:?$")
INLINE_HEADER_PATTERN = re.compile(
    r"^(?P<header>[A-Za-z][A-Za-z\s/&,-]{1,40}?):\s*(?P<content>.+)$"
)
WHITESPACE_PATTERN = re.compile(r"\s+")


def _normalize_header(value: str) -> str:
    value = value.strip().lower().rstrip(":")
    value = re.sub(r"[^a-z\s/&,-]", " ", value)
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
    Detect major resume sections using lightweight regex and header heuristics.
    """
    sections = {name: "" for name in SECTION_ALIASES}
    if not text or not text.strip():
        return sections

    lines = text.replace("\r", "\n").split("\n")
    current_section: str | None = None
    buffers = {name: [] for name in SECTION_ALIASES}

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if current_section:
                buffers[current_section].append("")
            continue

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

        if HEADER_PATTERN.match(line):
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

    return sections


def get_section_content(text: str, section: str) -> str:
    return segment_resume_sections(text).get(section, "")
