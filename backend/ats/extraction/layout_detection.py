from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


TABLE_DELIMITER_PATTERN = re.compile(r"\s{2,}|\t+|\s+\|\s+")
LANDSCAPE_RATIO_THRESHOLD = 1.15


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

    is_multi_column = multi_column_pages > 0
    is_horizontal = landscape_pages > 0
    is_table_based = detected_tables > 0 or table_like_lines >= 3

    return {
        "is_multi_column": is_multi_column,
        "is_horizontal": is_horizontal,
        "is_table_based": is_table_based,
        "page_count": page_count,
        "multi_column_pages": multi_column_pages,
        "landscape_pages": landscape_pages,
        "detected_tables": detected_tables,
        "table_like_lines": table_like_lines,
        "layout_labels": [
            label
            for label, enabled in (
                ("multi_column", is_multi_column),
                ("horizontal", is_horizontal),
                ("table_based", is_table_based),
            )
            if enabled
        ],
    }
