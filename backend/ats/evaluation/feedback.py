from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


DEFAULT_FEEDBACK_PATH = Path("backend/ats/datasets/feedback/resume_parser_corrections.jsonl")


def record_resume_parser_feedback(
    case_id: str,
    original_fields: Dict[str, Any],
    corrected_fields: Dict[str, Any],
    *,
    source: str = "manual_review",
    feedback_path: str | Path = DEFAULT_FEEDBACK_PATH,
) -> Path:
    path = Path(feedback_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "case_id": case_id,
        "source": source,
        "timestamp_utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "original_fields": original_fields,
        "corrected_fields": corrected_fields,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")
    return path
