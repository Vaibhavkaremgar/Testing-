from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

import pdfplumber
from docx.document import Document as DocxDocument
from docx.table import Table, _Cell
from docx.text.paragraph import Paragraph
from pypdf import PdfReader

from ats.extraction.experience_extraction import compute_total_experience, parse_date
from ats.extraction.information_extraction import extract_resume_information
from ats.extraction.validation import validate_parsed_fields
from ats.preprocessing.section_segmentation import segment_resume_sections
from ats.preprocessing.text_cleaning import clean_text_pipeline

logger = logging.getLogger(__name__)

PHONE_PATTERNS = [
    r"\+91[-\s]?\d{5}[-\s]?\d{5}",
    r"\+91[-\s]?\d{10}",
    r"\d{5}[-\s]?\d{5}",
    r"\+?1?[-\s]?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}",
    r"\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}",
]
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+\s*@\s*[A-Za-z0-9.-]+\s*\.\s*[A-Za-z]{2,}\b")
PHONE_LINE_PATTERN = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
INVALID_NAME_TOKENS = {
    "machine", "learning", "python", "java", "react", "sql", "developer",
    "engineer", "manager", "analyst", "summary", "profile", "objective", "resume",
    "curriculum", "vitae", "experience", "skills", "education", "project", "projects",
    "email", "phone", "address", "location",
}


def _iter_docx_blocks(parent):
    parent_element = parent.element.body if isinstance(parent, DocxDocument) else parent._tc
    for child in parent_element.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, parent)
        elif child.tag.endswith("}tbl"):
            yield Table(child, parent)


def _extract_docx_table_lines(table: Table) -> List[str]:
    lines: List[str] = []
    for row in table.rows:
        row_values: List[str] = []
        for cell in row.cells:
            cell_parts: List[str] = []
            for block in _iter_docx_blocks(cell):
                if isinstance(block, Paragraph):
                    text = block.text.strip()
                    if text:
                        cell_parts.append(text)
                elif isinstance(block, Table):
                    nested_lines = _extract_docx_table_lines(block)
                    if nested_lines:
                        cell_parts.extend(nested_lines)
            cell_text = " ".join(part.strip() for part in cell_parts if part.strip()).strip()
            if cell_text:
                row_values.append(cell_text)
        if row_values:
            lines.append(" | ".join(row_values))
    return lines


def extract_text(file_path: str) -> str:
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
                for block in _iter_docx_blocks(document):
                    if isinstance(block, Paragraph):
                        if block.text.strip():
                            text_parts.append(block.text)
                    elif isinstance(block, Table):
                        text_parts.extend(_extract_docx_table_lines(block))
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


def _normalize_name_candidate(value: str) -> str:
    candidate = re.sub(r"\s+", " ", (value or "").strip(" ,.-"))
    if not candidate:
        return ""
    words = candidate.split()
    if not (2 <= len(words) <= 4):
        return ""
    if any(any(char.isdigit() for char in word) for word in words):
        return ""
    lowered_words = [word.lower().strip(".,") for word in words]
    if any(word in INVALID_NAME_TOKENS for word in lowered_words):
        return ""
    if "@" in candidate or PHONE_LINE_PATTERN.search(candidate):
        return ""
    if not all(word.replace(".", "").replace("'", "").isalpha() for word in words):
        return ""
    if not all(word.isupper() or word[:1].isupper() for word in words):
        return ""
    return candidate.title()


def _header_name_candidates(text: str) -> List[str]:
    cleaned_text = clean_text_pipeline(text or "")
    sections = segment_resume_sections(cleaned_text)
    header_text = sections.get("header", "")
    header_lines = [line.strip() for line in header_text.splitlines() if line.strip()]
    raw_lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    return header_lines or raw_lines[:5]


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


def _email_to_name(email: str) -> str:
    local_part = (email or "").split("@")[0]
    tokens = [token for token in re.split(r"[._\-]+", local_part) if token]
    if not (2 <= len(tokens) <= 4):
        return ""
    return _normalize_name_candidate(" ".join(token.title() for token in tokens))


def _extract_name(text: str, original_filename: Optional[str] = None) -> str:
    for line in _header_name_candidates(text):
        normalized = _normalize_name_candidate(line)
        if normalized:
            return normalized
    email_name = _email_to_name(_extract_email(text))
    if email_name:
        return email_name
    if original_filename:
        filename_name = _normalize_name_candidate(
            os.path.splitext(original_filename)[0].replace("_", " ").replace("-", " ").title()
        )
        if filename_name:
            return filename_name
    return "Unknown Candidate"


def extract_skills(text: str) -> List[str]:
    info = extract_resume_information(text)
    return info.get("skills", [])


def extract_experience(text: str) -> List[Dict[str, Any]]:
    info = extract_resume_information(text)
    return info.get("experience", [])


def calculate_total_experience(experience_entries: List[Dict[str, Any]]) -> float:
    if not experience_entries:
        return 0.0
    ranges = []
    for entry in experience_entries:
        start = parse_date(entry.get("start_date", ""), is_end=False)
        end = parse_date(entry.get("end_date", ""), is_end=True)
        if not start or not end or end < start:
            continue
        ranges.append((start, end))
    if not ranges:
        return 0.0
    return compute_total_experience(ranges)


def extract_current_company(experience_entries: List[Dict[str, Any]]) -> str:
    return experience_entries[0].get("company") if experience_entries else ""


def extract_location(text: str) -> str:
    info = extract_resume_information(text)
    return info.get("location", "")


def _classify_experience_level(total_experience_years: Optional[float]) -> str:
    if total_experience_years is None:
        return ""
    if total_experience_years <= 2:
        return "Junior"
    if total_experience_years <= 5:
        return "Mid-level"
    if total_experience_years <= 10:
        return "Senior"
    return "Lead/Expert"


def parse_resume(file_path: str, original_filename: Optional[str] = None) -> Dict[str, Any]:
    raw_text = extract_text(file_path)
    cleaned_text = clean_text_pipeline(raw_text) if raw_text else ""
    extracted_info = extract_resume_information(raw_text) if raw_text else {
        "sections": segment_resume_sections(""),
        "skills": [],
        "experience": [],
        "projects": [],
        "education": [],
        "location": "",
        "current_company": None,
        "current_role": None,
        "designation": None,
        "experience_years": None,
        "total_experience_years": None,
        "experience_level": "",
        "languages": [],
    }

    result = {
        "name": _extract_name(raw_text, original_filename),
        "email": _extract_email(raw_text),
        "phone": _extract_phone(cleaned_text),
        "skills": extracted_info.get("skills", []),
        "total_experience_years": extracted_info.get("total_experience_years"),
        "experience_years": extracted_info.get("experience_years"),
        "experience_level": extracted_info.get("experience_level") or _classify_experience_level(extracted_info.get("total_experience_years")),
        "current_company": extracted_info.get("current_company"),
        "current_role": extracted_info.get("current_role"),
        "designation": extracted_info.get("designation"),
        "location": extracted_info.get("location", ""),
        "languages": extracted_info.get("languages", []),
        "summary": extracted_info.get("sections", {}).get("summary", ""),
        "sections": extracted_info.get("sections", {}),
        "experience_entries": extracted_info.get("experience", []),
        "full_text": cleaned_text,
        "raw_text": raw_text,
    }
    result = validate_parsed_fields(result)
    logger.info(
        "Parsed resume: name=%s, skills=%s, experience_years=%s, current_company=%s, location=%s",
        result["name"],
        len(result["skills"]),
        result["total_experience_years"],
        result["current_company"],
        result["location"],
    )
    return result
