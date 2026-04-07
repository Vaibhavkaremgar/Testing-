from __future__ import annotations

import re
from typing import Dict


RESUME_TYPE_PATTERNS = {
    "technical": re.compile(
        r"(?i)\b(?:python|java|sql|aws|docker|kubernetes|react|fastapi|api|backend|frontend|machine learning|data engineer)\b"
    ),
    "sales": re.compile(
        r"(?i)\b(?:sales|business development|lead generation|crm|territory|pipeline|prospecting|account management)\b"
    ),
    "academic": re.compile(
        r"(?i)\b(?:research|publication|thesis|university|professor|teaching|curriculum|phd|academic)\b"
    ),
    "medical": re.compile(
        r"(?i)\b(?:patient|clinical|hospital|nurse|physician|medical|treatment|diagnosis|healthcare)\b"
    ),
}


def detect_resume_type(text: str) -> Dict[str, object]:
    normalized = str(text or "")
    scores = {
        resume_type: len(pattern.findall(normalized))
        for resume_type, pattern in RESUME_TYPE_PATTERNS.items()
    }
    best_type = max(scores, key=scores.get) if scores else "general"
    if not scores or scores.get(best_type, 0) == 0:
        best_type = "general"
    return {
        "resume_type": best_type,
        "resume_type_scores": scores,
    }
