from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
BULLET_PREFIX_PATTERN = re.compile(r"(?m)^\s*[▪•\-\*\u2022\u25aa\u25e6\u2043\u2219]+\s*")
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^\w\s@.,;:/+#&()\-|\n]")
HEADER_PATTERN = re.compile(
    r"(?i)^(?:work experience|professional experience|employment history|employment|experience|skills|technical skills|education|projects?|summary|profile|languages?)$"
)
WHITESPACE_PATTERN = re.compile(r"[ \t]+")


def normalize_line_breaks(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def remove_urls(text: str) -> str:
    return URL_PATTERN.sub(" ", text or "")


def remove_bullets(text: str) -> str:
    return BULLET_PREFIX_PATTERN.sub("", text or "")


def remove_special_characters(text: str) -> str:
    return SPECIAL_CHARACTER_PATTERN.sub(" ", text or "")


def _is_section_header(line: str) -> bool:
    cleaned = WHITESPACE_PATTERN.sub(" ", line.strip(" :")).strip()
    return bool(cleaned and HEADER_PATTERN.match(cleaned))


def merge_broken_lines(text: str) -> str:
    if not text:
        return ""

    merged_lines = []
    pending = ""
    lines = normalize_line_breaks(text).split("\n")

    for raw_line in lines:
        line = WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if not line:
            if pending:
                merged_lines.append(pending.strip())
                pending = ""
            merged_lines.append("")
            continue

        if _is_section_header(line):
            if pending:
                merged_lines.append(pending.strip())
                pending = ""
            merged_lines.append(line)
            continue

        if not pending:
            pending = line
            continue

        if pending.endswith((",", ";", "|", "/", "-", "(")) or line[:1].islower():
            pending = f"{pending} {line}".strip()
        else:
            merged_lines.append(pending.strip())
            pending = line

    if pending:
        merged_lines.append(pending.strip())

    cleaned_lines = []
    previous_blank = False
    for line in merged_lines:
        if not line:
            if not previous_blank:
                cleaned_lines.append("")
            previous_blank = True
            continue
        cleaned_lines.append(line)
        previous_blank = False
    return "\n".join(cleaned_lines).strip()


def normalize_text(text: str) -> str:
    if not text:
        return ""
    normalized = normalize_line_breaks(text)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "â€“": "-",
        "â€”": "-",
        "Â·": "|",
        "â€¢": " ",
    }
    for source, target in replacements.items():
        normalized = normalized.replace(source, target)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    return normalized.strip()


def clean_text_pipeline(text: str) -> str:
    cleaned_text = normalize_line_breaks(text)
    cleaned_text = remove_urls(cleaned_text)
    cleaned_text = remove_bullets(cleaned_text)
    cleaned_text = remove_special_characters(cleaned_text)
    cleaned_text = merge_broken_lines(cleaned_text)
    cleaned_text = normalize_text(cleaned_text)
    return cleaned_text


def clean_text(text: str) -> str:
    cleaned_text = clean_text_pipeline(text)
    logger.info("Text Cleaning Applied")
    return cleaned_text
