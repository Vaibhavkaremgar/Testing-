from __future__ import annotations

from typing import Dict


def _normalize_component_score(score: float, max_score: float) -> float:
    if max_score <= 0:
        return 0.0
    return round((score / max_score) * 100.0, 2)


def build_feature_vector(components: Dict, matching_signals: Dict) -> Dict[str, float]:
    """
    Build a compact ATS feature vector for downstream ranking or ML use.
    """
    skills_component = components.get("skills", {})
    experience_component = components.get("experience", {})
    education_component = components.get("education", {})

    return {
        "skill_score": round(float(skills_component.get("match_percentage", 0.0)), 2),
        "experience_score": _normalize_component_score(
            float(experience_component.get("score", 0.0)),
            float(experience_component.get("max", 0.0)),
        ),
        "tfidf_score": round(float(matching_signals.get("tfidf_score", 0.0)), 2),
        "bm25_score": round(float(matching_signals.get("bm25_score", 0.0)), 2),
        "education_score": _normalize_component_score(
            float(education_component.get("score", 0.0)),
            float(education_component.get("max", 0.0)),
        ),
    }
