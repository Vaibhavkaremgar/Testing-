from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import pdfplumber
from flashtext import KeywordProcessor
from pypdf import PdfReader
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS

from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import clean_text_pipeline
from app.spacy_nlp import SPACY_AVAILABLE, nlp

logger = logging.getLogger(__name__)

PHONE_PATTERNS = [
    r"\+91[-\s]?\d{5}[-\s]?\d{5}",
    r"\+91[-\s]?\d{10}",
    r"\d{5}[-\s]?\d{5}",
    r"\+?1?[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}",
    r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}",
]
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
LOCATION_PATTERN = re.compile(
    r"(?i)\b(?:location|based in|address|city)\b\s*[:\-]?\s*(?P<value>[A-Za-z][A-Za-z\s,.-]{1,80})$"
)
MONTH_PATTERN = r"(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)"
DATE_RANGE_PATTERNS = [
    re.compile(
        rf"(?P<start>{MONTH_PATTERN}\s+\d{{4}}|\d{{4}})\s*(?:-|to|–|—)\s*(?P<end>{MONTH_PATTERN}\s+\d{{4}}|\d{{4}}|present|current|till date|till now|now)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"(?P<start>{MONTH_PATTERN}\.?\s*\d{{4}}|\d{{4}})\s*(?:-|to|–|—)\s*(?P<end>present|current|till date|till now|now|{MONTH_PATTERN}\.?\s*\d{{4}}|\d{{4}})",
        re.IGNORECASE,
    ),
]
YEAR_ONLY_PATTERN = re.compile(r"\b(19|20)\d{2}\b")
LANGUAGE_TERMS = [
    "english", "hindi", "telugu", "tamil", "kannada", "malayalam", "marathi",
    "gujarati", "punjabi", "bengali", "urdu", "french", "german", "spanish",
    "arabic", "japanese", "mandarin", "chinese",
]
LANGUAGE_HEADER_PATTERN = re.compile(r"(?i)^\s*languages?\s*[:\-]?\s*(?P<value>.+)$")
LOCATION_HINTS = (
    "india", "hyderabad", "bangalore", "bengaluru", "mumbai", "pune", "chennai",
    "delhi", "noida", "gurgaon", "kolkata", "ahmedabad", "remote",
)
EXPERIENCE_SECTION_KEYS = ("experience", "professional experience", "employment history", "work history", "internship")
HEADER_SPLIT_PATTERN = re.compile(r"\s+[|\-–—]\s+")
NON_LOCATION_PATTERN = re.compile(r"[@:/\\]|(?:\b(?:java|python|html|css|sql|fastapi|react|angular|git)\b)", re.IGNORECASE)
LOCATION_NOISE_PATTERN = re.compile(
    r"(?i)\b(?:managing|managed|operations|including|across|responsible|experience|years|sales|development|engineer|developer|manager|executive|specialist|lead|worked|work|support|project|projects|regional|south|north|east|west)\b"
)

SKILL_ONTOLOGY: Dict[str, List[str]] = {
    "sales": ["sales", "sales target", "sales strategy", "revenue growth", "inside sales", "b2b sales"],
    "negotiation": ["negotiation", "negotiated", "deal closing", "closing deals"],
    "customer relationship management": ["crm", "customer relationship management", "client relationship management"],
    "lead generation": ["lead generation", "generated leads", "prospecting", "prospect generation"],
    "cold calling": ["cold calling", "outbound calling", "cold outreach"],
    "business development": ["business development", "bd", "market expansion"],
    "account management": ["account management", "client handling", "account handling"],
    "pipeline management": ["pipeline management", "sales pipeline", "pipeline tracking"],
    "customer service": ["customer service", "customer support", "client support"],
    "presentation": ["presentation", "presentations", "product demo", "demoed"],
    "leadership": ["leadership", "led", "team lead", "managed team", "mentored", "supervised"],
    "communication": ["communication", "communicate", "stakeholder communication", "client interaction"],
    "teamwork": ["teamwork", "team player", "collaborated", "cross-functional"],
    "problem solving": ["problem solving", "resolved issues", "troubleshooting", "debugging"],
    "python": ["python"],
    "java": ["java"],
    "html": ["html", "html5"],
    "css": ["css", "css3"],
    "javascript": ["javascript", "js"],
    "typescript": ["typescript", "ts"],
    "fastapi": ["fastapi"],
    "sql": ["sql", "mysql", "postgresql", "sql server", "oracle sql"],
    "rest api": ["rest api", "restful api", "api development"],
    "react": ["react", "react.js", "reactjs"],
    "customer service": ["customer service", "customer support", "client support"],
}

SKILL_ALIASES = {
    "crm": "customer relationship management",
    "customer relationship management": "customer relationship management",
    "customer relationship mgmt": "customer relationship management",
    "client relationship management": "customer relationship management",
    "lead gen": "lead generation",
    "js": "javascript",
    "ts": "typescript",
    "react.js": "react",
    "reactjs": "react",
    "html5": "html",
    "css3": "css",
    "mysql": "sql",
    "postgresql": "sql",
    "sql server": "sql",
}

EXPERIENCE_LEVELS = [
    (0, 2, "Junior"),
    (3, 5, "Mid-level"),
    (6, 10, "Senior"),
]

_skill_keyword_processor = KeywordProcessor(case_sensitive=False)
for canonical_skill, variants in SKILL_ONTOLOGY.items():
    _skill_keyword_processor.add_keyword(canonical_skill, canonical_skill)
    for variant in variants:
        _skill_keyword_processor.add_keyword(variant, canonical_skill)
for alias, canonical in SKILL_ALIASES.items():
    _skill_keyword_processor.add_keyword(alias, canonical)


def normalize_skill(skill: str) -> str:
    normalized = clean_text_pipeline(skill or "").lower().strip()
    normalized = normalized.replace("  ", " ")
    return SKILL_ALIASES.get(normalized, normalized)


def _unique(values: List[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for value in values:
        if not value:
            continue
        normalized = normalize_skill(value)
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def extract_text(file_path: str) -> str:
    """
    Extract raw text from PDF, DOCX, or DOC files with layered fallbacks.
    """
    if not file_path or not os.path.exists(file_path):
        return ""

    file_ext = os.path.splitext(file_path)[1].lower()
    text_parts: List[str] = []

    try:
        if file_ext == ".pdf":
            try:
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text)
            except Exception as exc:
                logger.warning("pdfplumber extraction failed for %s: %s", file_path, exc)

            if not text_parts:
                try:
                    reader = PdfReader(file_path)
                    for page in reader.pages:
                        page_text = page.extract_text() or ""
                        if page_text.strip():
                            text_parts.append(page_text)
                except Exception as exc:
                    logger.warning("pypdf extraction failed for %s: %s", file_path, exc)

        elif file_ext == ".docx":
            try:
                import docx

                document = docx.Document(file_path)
                for paragraph in document.paragraphs:
                    if paragraph.text.strip():
                        text_parts.append(paragraph.text)
            except Exception as exc:
                logger.warning("python-docx extraction failed for %s: %s", file_path, exc)

        elif file_ext == ".doc":
            try:
                import subprocess

                result = subprocess.run(["antiword", file_path], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    text_parts.append(result.stdout)
            except Exception as exc:
                logger.warning("antiword extraction failed for %s: %s", file_path, exc)

        if not text_parts:
            with open(file_path, "rb") as handle:
                binary_text = handle.read().decode("utf-8", errors="ignore")
                if binary_text.strip():
                    text_parts.append(binary_text)
    except Exception as exc:
        logger.exception("Resume text extraction failed for %s: %s", file_path, exc)
        return ""

    return "\n".join(part.strip() for part in text_parts if part and part.strip())


def _preprocess_text(text: str) -> str:
    cleaned = clean_text_pipeline(text or "")
    tokens = [token for token in cleaned.split() if token not in ENGLISH_STOP_WORDS]
    return " ".join(tokens)


def _fuzzy_contains(text: str, phrase: str, threshold: float = 0.92) -> bool:
    if phrase in text:
        return True

    phrase_tokens = phrase.split()
    token_count = len(phrase_tokens)
    if token_count <= 1:
        return False

    words = text.split()
    for index in range(0, max(0, len(words) - token_count + 1)):
        window = " ".join(words[index:index + token_count])
        if SequenceMatcher(None, window, phrase).ratio() >= threshold:
            return True
    return False


def extract_skills(text: str) -> List[str]:
    """
    Extract skills using a hybrid of:
    - FlashText keyword matching
    - spaCy noun chunks / entities
    - fuzzy phrase matching
    """
    if not text:
        return []

    sections = segment_resume_sections(text)
    candidate_sources = [
        sections.get("skills", ""),
        sections.get("experience", ""),
        sections.get("projects", ""),
        text,
    ]
    matches: List[str] = []

    for source in candidate_sources:
        if not source:
            continue
        matches.extend(_skill_keyword_processor.extract_keywords(source))

    normalized_text = _preprocess_text(text)
    for canonical_skill, variants in SKILL_ONTOLOGY.items():
        all_phrases = [canonical_skill] + variants
        if any(_fuzzy_contains(normalized_text, normalize_skill(phrase)) for phrase in all_phrases):
            matches.append(canonical_skill)

    if SPACY_AVAILABLE and nlp is not None:
        doc = nlp(text[:20000])
        candidate_phrases = set()
        candidate_phrases.update(chunk.text.strip().lower() for chunk in doc.noun_chunks if len(chunk.text.split()) <= 4)
        candidate_phrases.update(ent.text.strip().lower() for ent in doc.ents if ent.label_ in {"PRODUCT", "ORG"} and len(ent.text.split()) <= 4)
        for phrase in candidate_phrases:
            normalized_phrase = normalize_skill(phrase)
            if normalized_phrase in SKILL_ONTOLOGY:
                matches.append(normalized_phrase)
            elif normalized_phrase in SKILL_ALIASES:
                matches.append(SKILL_ALIASES[normalized_phrase])

    return _unique(matches)


def _parse_date_token(token: str) -> Optional[datetime]:
    token = (token or "").strip().lower().replace(".", "")
    if not token:
        return None
    if token in {"present", "current", "now", "till date", "till now"}:
        return datetime.utcnow().replace(day=1)

    month_map = {
        "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
        "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
        "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10,
        "nov": 11, "november": 11, "dec": 12, "december": 12,
    }

    match = re.match(rf"(?:(?P<month>{MONTH_PATTERN})\s+)?(?P<year>\d{{4}})", token, re.IGNORECASE)
    if not match:
        return None

    year = int(match.group("year"))
    month_token = (match.group("month") or "").lower()
    month = month_map.get(month_token, 1)
    if year < 1980 or year > datetime.utcnow().year + 1:
        return None
    return datetime(year, month, 1)


def _experience_source_text(text: str) -> str:
    sections = segment_resume_sections(text)
    for key in ("experience", "projects"):
        if sections.get(key):
            return sections[key]
    return text


def extract_experience(text: str) -> List[Dict[str, Any]]:
    """
    Extract experience entries with title, company, and date ranges.
    """
    if not text:
        return []

    source_text = _experience_source_text(text)
    blocks = [block.strip() for block in re.split(r"\n\s*\n", source_text) if block.strip()]
    if not blocks:
        lines = [line.strip() for line in source_text.splitlines() if line.strip()]
        blocks = []
        current_block: List[str] = []
        for line in lines:
            if any(pattern.search(line) for pattern in DATE_RANGE_PATTERNS):
                if current_block:
                    blocks.append("\n".join(current_block))
                    current_block = []
                current_block.append(line)
            elif current_block:
                current_block.append(line)
            elif any(keyword in line.lower() for keyword in EXPERIENCE_SECTION_KEYS):
                continue
        if current_block:
            blocks.append("\n".join(current_block))

    entries: List[Dict[str, Any]] = []
    for block in blocks:
        date_match = None
        for pattern in DATE_RANGE_PATTERNS:
            date_match = pattern.search(block)
            if date_match:
                break
        if not date_match:
            continue

        lines = [line.strip(" -*\t") for line in block.splitlines() if line.strip()]
        headline = lines[0] if lines else block.splitlines()[0].strip()
        title = ""
        company = ""

        if " at " in headline.lower():
            parts = re.split(r"\bat\b", headline, maxsplit=1, flags=re.IGNORECASE)
            title = parts[0].strip(" ,|-")
            company = parts[1].strip(" ,|-")
        else:
            parts = [part.strip(" ,|-") for part in HEADER_SPLIT_PATTERN.split(headline) if part.strip(" ,|-")]
            if len(parts) >= 2:
                title, company = parts[0], parts[1]
            elif parts:
                title = parts[0]

        if SPACY_AVAILABLE and nlp is not None and not company:
            doc = nlp(headline)
            org_entities = [ent.text.strip() for ent in doc.ents if ent.label_ == "ORG"]
            if org_entities:
                company = org_entities[0]

        start_date = _parse_date_token(date_match.group("start"))
        end_date = _parse_date_token(date_match.group("end"))
        if not start_date or not end_date:
            continue

        description = " ".join(lines[1:])[:600]
        entries.append(
            {
                "title": title[:120] or None,
                "company": company[:160] or None,
                "start_date": start_date,
                "end_date": end_date,
                "raw_text": block[:800],
                "description": description,
            }
        )

    entries.sort(key=lambda item: item["end_date"], reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        key = (entry.get("title"), entry.get("company"), entry.get("start_date"), entry.get("end_date"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def calculate_total_experience(experience_entries: List[Dict[str, Any]]) -> float:
    """
    Merge overlapping date ranges and compute total experience in years.
    """
    if not experience_entries:
        return 0.0

    intervals = sorted(
        [
            (entry["start_date"], entry["end_date"])
            for entry in experience_entries
            if entry.get("start_date") and entry.get("end_date")
        ],
        key=lambda item: item[0],
    )
    if not intervals:
        return 0.0

    merged: List[List[datetime]] = [[intervals[0][0], intervals[0][1]]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1][1] = end
        else:
            merged.append([start, end])

    total_months = 0
    for start, end in merged:
        total_months += max(0, (end.year - start.year) * 12 + (end.month - start.month))

    return round(total_months / 12.0, 1)


def extract_current_company(experience_entries: List[Dict[str, Any]]) -> str:
    """
    Return the company from the most recent experience entry.
    """
    if not experience_entries:
        return ""
    return experience_entries[0].get("company") or ""


def extract_location(text: str) -> str:
    """
    Extract location from explicit lines first, then spaCy GPE/LOC entities.
    """
    if not text:
        return ""

    def normalize_location_candidate(value: str) -> str:
        candidate = re.sub(r"\s+", " ", (value or "").strip(" ,.-"))[:80]
        if not candidate:
            return ""
        if NON_LOCATION_PATTERN.search(candidate) or LOCATION_NOISE_PATTERN.search(candidate):
            return ""
        if any(char.isdigit() for char in candidate) or len(candidate.split()) > 5:
            return ""
        if re.match(r"^[A-Z][a-zA-Z]+(?:[\s-][A-Z][a-zA-Z]+)*(?:,\s*[A-Z][a-zA-Z]+(?:[\s-][A-Z][a-zA-Z]+)*)?$", candidate):
            return candidate
        fragments = [fragment.strip(" ,.-") for fragment in candidate.split(",") if fragment.strip(" ,.-")]
        if 1 <= len(fragments) <= 3 and all(
            re.match(r"^[A-Z][a-zA-Z]+(?:[\s-][A-Z][a-zA-Z]+)*$", fragment) for fragment in fragments
        ):
            return ", ".join(fragments)
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:30]:
        match = LOCATION_PATTERN.search(line)
        if match:
            value = normalize_location_candidate(match.group("value"))
            if value:
                return value

    for line in lines[:20]:
        lowered = line.lower()
        if not any(hint in lowered for hint in LOCATION_HINTS):
            continue
        candidate = normalize_location_candidate(line)
        if candidate:
            return candidate

    if SPACY_AVAILABLE and nlp is not None:
        for line in lines[:20]:
            if len(line) > 60 or LOCATION_NOISE_PATTERN.search(line):
                continue
            doc = nlp(line[:200])
            for ent in doc.ents:
                if ent.label_ in {"GPE", "LOC"}:
                    candidate = normalize_location_candidate(ent.text)
                    if candidate:
                        return candidate
    return ""


def _extract_phone(text: str) -> str:
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text or "")
        if matches:
            return matches[0].strip()
    return ""


def _extract_email(text: str) -> str:
    match = EMAIL_PATTERN.search(text or "")
    if not match:
        compact = (text or "").replace("(at)", "@").replace("[at]", "@").replace(" at ", "@")
        compact = compact.replace("(dot)", ".").replace("[dot]", ".").replace(" dot ", ".")
        match = EMAIL_PATTERN.search(compact)
    return re.sub(r"\s+", "", match.group(0)).strip(".,;:") if match else ""


def _extract_name(text: str, original_filename: Optional[str] = None) -> str:
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    skip_keywords = {
        "resume", "curriculum", "vitae", "profile", "summary", "objective",
        "experience", "education", "skills", "projects", "work", "professional",
        "personal", "contact", "information", "details", "career", "employment",
        "history", "qualifications", "certifications", "achievements", "references",
        "languages", "interests", "engineer", "developer", "manager", "analyst",
        "designer", "consultant", "specialist", "executive", "director", "lead",
        "senior", "junior", "software", "data", "full", "stack",
    }
    for line in lines[:20]:
        if len(line) < 3 or len(line) > 60:
            continue
        if "@" in line or sum(char.isdigit() for char in line) > 5:
            continue
        words = line.split()
        if not (2 <= len(words) <= 4):
            continue
        if any(token.lower() in skip_keywords for token in words):
            continue
        if all(word.replace(".", "").isalpha() and word[0].isupper() for word in words):
            return line

    if original_filename:
        return os.path.splitext(original_filename)[0].replace("_", " ").replace("-", " ").strip().title()
    return "Unknown Candidate"


def _extract_languages(text: str) -> List[str]:
    matches: List[str] = []
    for line in [line.strip() for line in text.splitlines() if line.strip()][:30]:
        header_match = LANGUAGE_HEADER_PATTERN.match(line)
        if header_match:
            for chunk in re.split(r"[,;|/]", header_match.group("value")):
                language = chunk.strip().lower()
                if language in LANGUAGE_TERMS:
                    matches.append(language.title())
    lowered = text.lower()
    for language in LANGUAGE_TERMS:
        if re.search(rf"\b{re.escape(language)}\b", lowered):
            matches.append(language.title())
    return list(dict.fromkeys(matches))


def _classify_experience_level(total_experience_years: float) -> str:
    if total_experience_years >= 10:
        return "Lead/Expert"
    for minimum, maximum, label in EXPERIENCE_LEVELS:
        if minimum <= total_experience_years <= maximum:
            return label
    return "Junior" if total_experience_years <= 2 else "Lead/Expert"


def parse_resume(file_path: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Parse a resume file into production-oriented ATS fields.
    """
    raw_text = extract_text(file_path)
    cleaned_text = clean_text_pipeline(raw_text) if raw_text else ""
    experience_entries = extract_experience(raw_text)
    total_experience_years = calculate_total_experience(experience_entries)
    current_company = extract_current_company(experience_entries)
    designation = experience_entries[0].get("title") if experience_entries else ""
    result = {
        "name": _extract_name(raw_text, original_filename),
        "email": _extract_email(raw_text) or _extract_email(cleaned_text),
        "phone": _extract_phone(cleaned_text),
        "skills": extract_skills(raw_text),
        "total_experience_years": total_experience_years,
        "experience_level": _classify_experience_level(total_experience_years),
        "current_company": current_company,
        "designation": designation or "",
        "location": extract_location(raw_text),
        "languages": _extract_languages(raw_text),
        "experience_entries": [
            {
                **entry,
                "start_date": entry["start_date"].strftime("%b %Y"),
                "end_date": entry["end_date"].strftime("%b %Y"),
            }
            for entry in experience_entries
        ],
        "full_text": cleaned_text,
        "raw_text": raw_text,
    }
    logger.info(
        "Parsed resume: name=%s, skills=%s, experience_years=%s, current_company=%s, location=%s",
        result["name"],
        len(result["skills"]),
        result["total_experience_years"],
        result["current_company"],
        result["location"],
    )
    return result
