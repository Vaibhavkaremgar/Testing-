from __future__ import annotations

from typing import Dict


class RankingEngine:
    """
    Custom feature-based ranking engine.

    score =
    0.4 * skill +
    0.2 * experience +
    0.2 * tfidf +
    0.1 * bm25 +
    0.1 * education
    """

    FEATURE_WEIGHTS = {
        "skill_score": 0.4,
        "experience_score": 0.2,
        "tfidf_score": 0.2,
        "bm25_score": 0.1,
        "education_score": 0.1,
    }

    def _normalize_feature(self, value: float) -> float:
        normalized = float(value or 0.0) / 100.0
        return max(0.0, min(normalized, 1.0))

    def compute_score(self, feature_vector: Dict[str, float]) -> Dict[str, float]:
        normalized_features = {
            key: self._normalize_feature(feature_vector.get(key, 0.0))
            for key in self.FEATURE_WEIGHTS
        }

        weighted_contributions = {
            key: round(normalized_features[key] * weight, 4)
            for key, weight in self.FEATURE_WEIGHTS.items()
        }
        ranking_score = round(sum(weighted_contributions.values()), 4)

        return {
            "ranking_score": ranking_score,
            "ranking_score_percent": round(ranking_score * 100.0, 2),
            "normalized_features": normalized_features,
            "weighted_contributions": weighted_contributions,
        }


def compute_ranking_result(feature_vector: Dict[str, float]) -> Dict[str, float]:
    engine = RankingEngine()
    return engine.compute_score(feature_vector)
