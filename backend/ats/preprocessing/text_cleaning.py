from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
EMAIL_IN_URL_PATTERN = re.compile(r"(?i)[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BULLET_PREFIX_PATTERN = re.compile(r"(?m)^\s*[\-\*\u2022\u25aa\u25e6\u2043\u2219]+\s*")
SPECIAL_CHARACTER_PATTERN = re.compile(r"[^\w\s@.,;:/+#&()'\-|\n]")
CID_ARTIFACT_PATTERN = re.compile(r"\(cid:\d+\)")
ZERO_WIDTH_PATTERN = re.compile(r"[\u200b-\u200d\ufeff]")
INVISIBLE_CONTROL_PATTERN = re.compile(r"[\u2060\u00ad]")
DECORATIVE_SYMBOL_PATTERN = re.compile(r"(?:(?<!\w)[@#&=~*_]{2,}|[@#&=~*_]{2,}(?!\w))")
REPEATED_PUNCTUATION_PATTERN = re.compile(r"([.,;:|/()\-])\1+")
PIPE_SEPARATOR_PATTERN = re.compile(r"\s*\|\s*")
DATE_TOKEN_PATTERN = (
    r"(?:"
    r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)(?:[\s/-]+)\d{4}"
    r"|\d{1,2}[/-]\d{4}"
    r"|\d{4}"
    r")"
)
DATE_RANGE_REPAIR_PATTERN = re.compile(
    rf"(?i)\b(?P<start>{DATE_TOKEN_PATTERN})\b\s*(?:\?{{2,}}|\s+)\s*(?P<end>present|current|now|{DATE_TOKEN_PATTERN})\b"
)
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
HEADER_LOCATION_PATTERN = re.compile(
    r"\b(?P<location>[A-Z][A-Za-z.\-]{1,30}(?:\s+[A-Z][A-Za-z.\-]{1,30}){0,2},\s*"
    r"[A-Z][A-Za-z.\-]{1,30}(?:\s+[A-Z][A-Za-z.\-]{1,30}){0,2})\b"
)
NAME_LIKE_PATTERN = re.compile(r"^[A-Z][A-Za-z'`.-]+(?:\s+[A-Z][A-Za-z'`.-]+){1,3}$")
HEADER_NAME_EXCLUDE_TOKENS = {
    "contact",
    "analyst",
    "architect",
    "assistant",
    "associate",
    "backend",
    "business",
    "consultant",
    "coordinator",
    "data",
    "designer",
    "developer",
    "director",
    "education",
    "engineer",
    "executive",
    "experience",
    "faculty",
    "frontend",
    "fullstack",
    "human",
    "intern",
    "lead",
    "manager",
    "mathematics",
    "officer",
    "principal",
    "product",
    "profile",
    "project",
    "projects",
    "qa",
    "resources",
    "sales",
    "scientist",
    "skills",
    "software",
    "special",
    "student",
    "summary",
    "teacher",
    "technical",
    "trainer",
    "tutor",
}
HEADER_PATTERN = re.compile(
    r"(?i)^(?:work experience|professional experience|employment history|employment|experience|period|skills|technical skills|education|projects?|summary|profile|languages?)$"
)
WHITESPACE_PATTERN = re.compile(r"[ \t]+")
SAFE_HORIZONTAL_SPACE_PATTERN = re.compile(r"[ \u00a0]{2,}")
INLINE_SECTION_HEADER_PATTERN = re.compile(
    r"(?i)(?<!\n)(?:\s{2,}|\s)(?P<header>"
    r"career profile|professional summary|profile summary|profile|summary|objective|"
    r"work experience|professional experience|employment history|period|"
    r"technical skills|core skills|skills|education|"
    r"achievements?\s*&\s*recognition|awards?\s*&\s*recognition)\b"
)
LINE_PREFIX_SECTION_HEADER_PATTERN = re.compile(
    r"(?im)^\s*(?P<header>"
    r"career profile|professional summary|profile summary|profile|summary|objective|"
    r"work experience|professional experience|employment history|employment|career history|experience|period|"
    r"technical skills|core skills|key skills|skills|"
    r"education|academic qualifications|qualifications|"
    r"languages?|language proficiency|"
    r"certifications?|professional certifications?"
    r")\s+(?P<content>\S.+)$"
)
GLUED_SECTION_HEADER_PATTERN = re.compile(
    r"(?im)^(?P<header>"
    r"TECHNICAL SKILLS|CORE SKILLS|KEY SKILLS|SKILLS|"
    r"WORK EXPERIENCE|PROFESSIONAL EXPERIENCE|EMPLOYMENT HISTORY|EXPERIENCE|PERIOD|"
    r"EDUCATION|ACADEMIC QUALIFICATIONS|QUALIFICATIONS|"
    r"LANGUAGES|LANGUAGE PROFICIENCY|"
    r"CERTIFICATIONS|PROFESSIONAL CERTIFICATIONS"
    r")(?P<content>[A-Z0-9].+)$"
)
ATTACHED_SECTION_HEADER_PATTERN = re.compile(
    r"(?i)\|\s*(?P<header>"
    r"summary|profile|objective|"
    r"work experience|professional experience|employment history|career history|period|"
    r"technical skills|core skills|key skills|skills|"
    r"education|academic qualifications|qualifications|"
    r"languages?|language proficiency|"
    r"certifications?|professional certifications?"
    r")\b"
)
SPLIT_MONTH_PATTERN = re.compile(
    r"(?i)\b(?P<prefix>j|f|m|a|s|o|n|d)[ \t]+(?P<suffix>anuary|ebruary|arch|pril|ay|une|uly|eptember|ctober|ovember|ecember)\b"
)
FRAGMENTED_EMAIL_PATTERN = re.compile(
    r"(?i)\b(?P<local>[A-Za-z0-9._%+-]+)[ \t]*@[ \t]*(?P<domain>[A-Za-z0-9.-]+(?:[ \t]+[A-Za-z0-9.-]+)*)[ \t]*\.[ \t]*(?P<tld>[A-Za-z]{2,})\b"
)
FRAGMENTED_UPPERCASE_TRIPLE_PATTERN = re.compile(r"\b([A-Z]{3,})[ \t]+([A-Z]{1,2})[ \t]+([A-Z]{3,})\b")
FRAGMENTED_UPPERCASE_DOUBLE_PATTERN = re.compile(r"\b([A-Z]{4,})[ \t]+([A-Z]{2,3})\b")
SPLIT_SECTION_WORD_PATTERNS = (
    (re.compile(r"(?i)\bexpe\s+rience\b"), "Experience"),
    (re.compile(r"(?i)\bexperi\s+ence\b"), "Experience"),
    (re.compile(r"(?i)\bprofessi\s+onal\b"), "Professional"),
    (re.compile(r"(?i)\bsum\s+mary\b"), "Summary"),
    (re.compile(r"(?i)\beduca\s+tion\b"), "Education"),
    (re.compile(r"(?i)\bcertifi\s+cations?\b"), "Certifications"),
    (re.compile(r"(?i)\bpro\s+jects?\b"), "Projects"),
    (re.compile(r"(?i)\bskill\s+s\b"), "Skills"),
)


def normalize_line_breaks(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _looks_like_name(value: str) -> bool:
    candidate = WHITESPACE_PATTERN.sub(" ", (value or "").strip(" ,|-"))
    if not candidate or not NAME_LIKE_PATTERN.match(candidate):
        return False
    lowered_tokens = {token.strip(".,").lower() for token in candidate.split()}
    return not any(token in HEADER_NAME_EXCLUDE_TOKENS for token in lowered_tokens)


def normalize_common_artifacts(text: str) -> str:
    normalized = normalize_line_breaks(text)
    normalized = CID_ARTIFACT_PATTERN.sub(" ", normalized)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2022": " ",
        "\u25aa": " ",
        "\u25e6": " ",
        "\u2043": " ",
        "\u2219": " ",
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
    normalized = FRAGMENTED_EMAIL_PATTERN.sub(
        lambda match: "{}@{}.{}".format(
            match.group("local"),
            re.sub(r"\s+", "", match.group("domain")),
            match.group("tld"),
        ),
        normalized,
    )
    normalized = SPLIT_MONTH_PATTERN.sub(lambda match: f"{match.group('prefix')}{match.group('suffix')}", normalized)
    normalized = FRAGMENTED_UPPERCASE_TRIPLE_PATTERN.sub(lambda match: "".join(match.groups()), normalized)
    normalized = FRAGMENTED_UPPERCASE_DOUBLE_PATTERN.sub(lambda match: "".join(match.groups()), normalized)
    for pattern, replacement in SPLIT_SECTION_WORD_PATTERNS:
        normalized = pattern.sub(replacement, normalized)
    return ZERO_WIDTH_PATTERN.sub("", normalized)


def remove_urls(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        value = match.group(0)
        email_match = EMAIL_IN_URL_PATTERN.search(value)
        if email_match:
            return f" {email_match.group(0)} "
        return " "

    return URL_PATTERN.sub(replacer, text or "")


def remove_bullets(text: str) -> str:
    return BULLET_PREFIX_PATTERN.sub("", text or "")


def remove_special_characters(text: str) -> str:
    cleaned = SPECIAL_CHARACTER_PATTERN.sub(" ", text or "")
    cleaned = DECORATIVE_SYMBOL_PATTERN.sub(" ", cleaned)
    cleaned = REPEATED_PUNCTUATION_PATTERN.sub(r"\1", cleaned)
    return cleaned


def _is_section_header(line: str) -> bool:
    cleaned = WHITESPACE_PATTERN.sub(" ", line.strip(" :")).strip()
    return bool(cleaned and HEADER_PATTERN.match(cleaned))


def repair_date_ranges(text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        start = match.group("start").strip()
        end = match.group("end").strip()
        return f"{start} - {end}"

    return DATE_RANGE_REPAIR_PATTERN.sub(replacer, text or "")


def _is_contact_line(line: str) -> bool:
    return bool(EMAIL_PATTERN.search(line or "") or PHONE_PATTERN.search(line or ""))


def _find_contact_start(line: str) -> int | None:
    starts = []
    email_match = EMAIL_PATTERN.search(line or "")
    phone_match = PHONE_PATTERN.search(line or "")
    if email_match:
        starts.append(email_match.start())
    if phone_match:
        starts.append(phone_match.start())
    if not starts:
        return None
    return min(starts)


def restore_header_line_breaks(text: str) -> str:
    if not text:
        return ""

    repaired_lines = []
    for index, raw_line in enumerate(normalize_line_breaks(text).split("\n")):
        line = WHITESPACE_PATTERN.sub(" ", raw_line).strip()
        if (
            not line
            or index > 5
            or "\n" in line
            or not (_is_contact_line(line) or "|" in line)
        ):
            repaired_lines.append(raw_line)
            continue

        contact_start = _find_contact_start(line)
        if contact_start is not None:
            prefix = line[:contact_start].strip(" ,|-")
            prefix = re.sub(r"(?i)^contact\s+", "", prefix).strip()
            suffix = line[contact_start:].strip()
            prefix_tokens = [token for token in prefix.split() if token]
            for token_count in range(2, min(5, len(prefix_tokens)) + 1):
                candidate_name = " ".join(prefix_tokens[:token_count]).strip()
                remainder = prefix[len(candidate_name):].strip(" ,|-")
                if _looks_like_name(candidate_name) and remainder:
                    rebuilt_suffix = f"{remainder} {suffix}".strip()
                    repaired_lines.append(f"{candidate_name}\n{rebuilt_suffix}")
                    break
            else:
                location_match = HEADER_LOCATION_PATTERN.search(line)
                if not location_match:
                    repaired_lines.append(raw_line)
                    continue

                prefix = line[:location_match.start()].strip(" ,|-")
                if not _looks_like_name(prefix):
                    repaired_lines.append(raw_line)
                    continue

                rebuilt = f"{prefix}\n{line[location_match.start():].strip()}"
                repaired_lines.append(rebuilt)
            continue

        location_match = HEADER_LOCATION_PATTERN.search(line)
        if not location_match:
            repaired_lines.append(raw_line)
            continue

        prefix = line[:location_match.start()].strip(" ,|-")
        if not _looks_like_name(prefix):
            repaired_lines.append(raw_line)
            continue

        rebuilt = f"{prefix}\n{line[location_match.start():].strip()}"
        repaired_lines.append(rebuilt)

    return "\n".join(repaired_lines)


def normalize_document_structure(text: str) -> str:
    normalized = normalize_common_artifacts(text)
    normalized = restore_header_line_breaks(normalized)
    normalized = split_inline_section_headers(normalized)
    normalized = repair_date_ranges(normalized)
    return normalized


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

        if _is_contact_line(pending) or _is_contact_line(line):
            merged_lines.append(pending.strip())
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
    normalized = normalize_common_artifacts(text)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    normalized = PIPE_SEPARATOR_PATTERN.sub(" | ", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    return normalized.strip()


def split_inline_section_headers(text: str) -> str:
    if not text:
        return ""

    def replacer(match: re.Match[str]) -> str:
        header = match.group("header")
        return f"\n{header.upper()}\n"

    normalized = LINE_PREFIX_SECTION_HEADER_PATTERN.sub(
        lambda match: f"{match.group('header').upper()}\n{match.group('content')}",
        text,
    )
    normalized = INLINE_SECTION_HEADER_PATTERN.sub(replacer, normalized)
    normalized = ATTACHED_SECTION_HEADER_PATTERN.sub(replacer, normalized)
    normalized = GLUED_SECTION_HEADER_PATTERN.sub(
        lambda match: f"{match.group('header')}\n{match.group('content')}",
        normalized,
    )
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def clean_text_pipeline(text: str) -> str:
    cleaned_text = normalize_document_structure(text)
    cleaned_text = remove_urls(cleaned_text)
    cleaned_text = split_inline_section_headers(cleaned_text)
    cleaned_text = remove_bullets(cleaned_text)
    cleaned_text = remove_special_characters(cleaned_text)
    cleaned_text = merge_broken_lines(cleaned_text)
    cleaned_text = normalize_text(cleaned_text)
    return cleaned_text


def clean_text(text: str) -> str:
    if not text:
        return ""

    cleaned_text = normalize_line_breaks(text)
    cleaned_text = cleaned_text.replace("\u00a0", " ")
    cleaned_text = cleaned_text.replace("\t", "    ")
    cleaned_text = ZERO_WIDTH_PATTERN.sub("", cleaned_text)
    cleaned_text = INVISIBLE_CONTROL_PATTERN.sub("", cleaned_text)
    cleaned_text = cleaned_text.replace("\f", "\n")
    cleaned_text = cleaned_text.replace("\v", "\n")

    normalized_lines = []
    for line in cleaned_text.split("\n"):
        line = re.sub(r"[ ]+\t", "    ", line)
        line = SAFE_HORIZONTAL_SPACE_PATTERN.sub(lambda match: " " if len(match.group(0)) <= 2 else "  ", line)
        normalized_lines.append(line.rstrip())

    cleaned_text = "\n".join(normalized_lines)
    cleaned_text = re.sub(r"\n{4,}", "\n\n\n", cleaned_text)
    logger.info("Safe text cleaning applied")
    return cleaned_text.strip()
