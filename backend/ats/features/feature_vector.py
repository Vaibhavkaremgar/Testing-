from __future__ import annotations

from typing import Dict


def _coerce_float(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _normalize_component_score(score: float, max_score: float) -> float:
    coerced_max = _coerce_float(max_score)
    if coerced_max <= 0:
        return 0.0
    normalized = (_coerce_float(score) / coerced_max) * 100.0
    return round(max(0.0, min(normalized, 100.0)), 2)


def build_feature_vector(components: Dict, matching_signals: Dict) -> Dict[str, float]:
    """
    Build a compact ATS feature vector for downstream ranking or ML use.
    """
    skills_component = components.get("skills", {})
    experience_component = components.get("experience", {})
    education_component = components.get("education", {})

    return {
        "skill_score": round(max(0.0, min(_coerce_float(skills_component.get("match_percentage", 0.0)), 100.0)), 2),
        "experience_score": _normalize_component_score(
            experience_component.get("score", 0.0),
            experience_component.get("max", 0.0),
        ),
        "tfidf_score": round(max(0.0, min(_coerce_float(matching_signals.get("tfidf_score", 0.0)), 100.0)), 2),
        "bm25_score": round(max(0.0, min(_coerce_float(matching_signals.get("bm25_score", 0.0)), 100.0)), 2),
        "education_score": _normalize_component_score(
            education_component.get("score", 0.0),
            education_component.get("max", 0.0),
        ),
    }
