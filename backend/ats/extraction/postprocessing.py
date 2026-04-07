from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


_space_pattern = re.compile(r"\s+")


def normalize_compact_text(value: str) -> str:
    return _space_pattern.sub(" ", (value or "").strip())


def dedupe_strings(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values or []:
        normalized = normalize_compact_text(str(value))
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def dedupe_dict_list(values: Iterable[Dict[str, Any]], *, identity_keys: Iterable[str]) -> List[Dict[str, Any]]:
    ordered: List[Dict[str, Any]] = []
    seen = set()
    keys = list(identity_keys)
    for item in values or []:
        if not isinstance(item, dict):
            continue
        identity_parts = [normalize_compact_text(str(item.get(key, ""))).lower() for key in keys]
        if not any(identity_parts):
            continue
        identity = tuple(identity_parts)
        if identity in seen:
            continue
        seen.add(identity)
        ordered.append(item)
    return ordered


def apply_postprocessing(result: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(result)
    normalized["skills"] = dedupe_strings(normalized.get("skills") or [])
    normalized["languages"] = dedupe_strings(normalized.get("languages") or [])
    normalized["education"] = dedupe_dict_list(normalized.get("education") or [], identity_keys=("degree", "institution", "year"))
    normalized["experience"] = dedupe_dict_list(normalized.get("experience") or [], identity_keys=("role", "company", "start_date", "end_date"))
    normalized["experience_entries"] = list(normalized["experience"])
    normalized["projects"] = dedupe_dict_list(normalized.get("projects") or [], identity_keys=("name", "title", "description"))
    normalized["certifications"] = dedupe_dict_list(normalized.get("certifications") or [], identity_keys=("name",))
    return normalized
