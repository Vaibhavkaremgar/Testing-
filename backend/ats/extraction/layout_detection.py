from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List

try:
    import layoutparser as lp  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    lp = None


TABLE_DELIMITER_PATTERN = re.compile(r"\s{2,}|\t+|\s+\|\s+")
LANDSCAPE_RATIO_THRESHOLD = 1.15
SECTION_HEADER_PATTERN = re.compile(
    r"(?i)^(?:contact(?: details| information)?|profile(?: summary)?|professional summary|summary|"
    r"technical skills|skills|core skills|key skills|work experience|professional experience|"
    r"employment history|experience|education|certifications?|projects?)$"
)
CONTACT_LINE_PATTERN = re.compile(r"(?i)(?:@|linkedin|github|portfolio|\+?\d[\d\s().-]{7,}\d)")


def _normalize_bool(value: Any) -> bool:
    return bool(value)


def _count_table_like_lines(lines: Iterable[str]) -> int:
    count = 0
    for line in lines:
        normalized = (line or "").strip()
        if not normalized:
            continue
        if normalized.count("|") >= 2:
            count += 1
            continue
        if len(TABLE_DELIMITER_PATTERN.findall(normalized)) >= 2:
            count += 1
    return count


def _section_header_positions(lines: List[str]) -> Dict[str, int]:
    positions: Dict[str, int] = {}
    for index, line in enumerate(lines):
        normalized = (line or "").strip()
        if not normalized:
            continue
        if not SECTION_HEADER_PATTERN.match(normalized):
            continue
        lowered = normalized.lower()
        positions.setdefault(lowered, index)
    return positions


def _count_short_lines(lines: Iterable[str], max_words: int = 4) -> int:
    return sum(1 for line in lines if 0 < len((line or "").split()) <= max_words)


def _count_contact_lines(lines: Iterable[str]) -> int:
    return sum(1 for line in lines if CONTACT_LINE_PATTERN.search(line or ""))


def infer_layout_signals(
    *,
    text_parts: List[str] | None = None,
    page_metrics: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    text_parts = text_parts or []
    page_metrics = page_metrics or []
    lines = [line for part in text_parts for line in (part or "").splitlines()]

    page_count = len(page_metrics)
    multi_column_pages = sum(1 for page in page_metrics if _normalize_bool(page.get("has_multi_column")))
    header_block_pages = sum(1 for page in page_metrics if _normalize_bool(page.get("has_header_block")))
    landscape_pages = sum(
        1
        for page in page_metrics
        if float(page.get("width") or 0) > 0
        and float(page.get("height") or 0) > 0
        and (float(page.get("width")) / max(float(page.get("height")), 1.0)) >= LANDSCAPE_RATIO_THRESHOLD
    )
    detected_tables = sum(
        max(
            int(page.get("table_count") or 0),
            1 if _normalize_bool(page.get("has_table_like_structure")) else 0,
        )
        for page in page_metrics
    )
    table_like_lines = _count_table_like_lines(lines)
    scanned_pages = sum(1 for page in page_metrics if _normalize_bool(page.get("is_scanned_pdf")))
    section_positions = _section_header_positions(lines[:40])
    early_lines = [line.strip() for line in lines[:20] if line.strip()]
    short_line_ratio = (_count_short_lines(early_lines) / max(len(early_lines), 1)) if early_lines else 0.0
    contact_line_count = _count_contact_lines(early_lines)

    is_multi_column = multi_column_pages > 0
    is_horizontal = landscape_pages > 0
    is_table_based = detected_tables > 0 or table_like_lines >= 3
    has_header_block = header_block_pages > 0 or contact_line_count >= 2 or (
        bool(early_lines[:3])
        and any("@" in line or CONTACT_LINE_PATTERN.search(line) for line in early_lines[:3])
    )
    has_early_skills = any(
        header in section_positions
        for header in ("technical skills", "skills", "core skills", "key skills")
    )
    experience_index = min(
        (
            position
            for header, position in section_positions.items()
            if header in {"work experience", "professional experience", "employment history", "experience"}
        ),
        default=999,
    )
    skills_index = min(
        (
            position
            for header, position in section_positions.items()
            if header in {"technical skills", "skills", "core skills", "key skills"}
        ),
        default=999,
    )
    is_sidebar = (
        is_multi_column
        and has_early_skills
        and skills_index < experience_index
    ) or (
        is_multi_column
        and short_line_ratio >= 0.45
        and contact_line_count >= 2
    )
    is_vertical = not is_horizontal and not is_multi_column and not is_table_based

    return {
        "is_multi_column": is_multi_column,
        "is_sidebar": is_sidebar,
        "is_vertical": is_vertical,
        "is_horizontal": is_horizontal,
        "is_table_based": is_table_based,
        "has_header_block": has_header_block,
        "is_scanned_pdf": scanned_pages > 0,
        "layoutparser_available": lp is not None,
        "page_count": page_count,
        "multi_column_pages": multi_column_pages,
        "header_block_pages": header_block_pages,
        "landscape_pages": landscape_pages,
        "scanned_pages": scanned_pages,
        "detected_tables": detected_tables,
        "table_like_lines": table_like_lines,
        "short_line_ratio": round(short_line_ratio, 2),
        "contact_line_count": contact_line_count,
        "layout_labels": [
            label
            for label, enabled in (
                ("multi_column", is_multi_column),
                ("sidebar", is_sidebar),
                ("vertical", is_vertical),
                ("horizontal", is_horizontal),
                ("table_based", is_table_based),
                ("header_block", has_header_block),
                ("scanned_pdf", scanned_pages > 0),
            )
            if enabled
        ],
    }


def get_layout_runtime_status() -> Dict[str, bool]:
    return {
        "layoutparser_available": lp is not None,
    }
