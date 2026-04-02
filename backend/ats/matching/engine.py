from __future__ import annotations

from typing import Dict, List

from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ats.preprocessing.text_cleaning import clean_text_pipeline


class MatchingEngine:
    """Resume-to-JD matching engine using TF-IDF and BM25."""

    def _normalize_text(self, text: str) -> str:
        return clean_text_pipeline(text or "")

    def _tokenize(self, text: str) -> List[str]:
        normalized = self._normalize_text(text)
        return [token for token in normalized.split() if token]

    def tfidf_similarity(self, source_text: str, target_text: str) -> float:
        source = self._normalize_text(source_text)
        target = self._normalize_text(target_text)
        if not source or not target:
            return 0.0

        vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english")
        matrix = vectorizer.fit_transform([source, target])
        similarity = cosine_similarity(matrix[0:1], matrix[1:2])[0][0]
        return float(round(similarity * 100, 2))

    def bm25_similarity(self, source_text: str, target_text: str) -> float:
        query_tokens = self._tokenize(source_text)
        document_tokens = self._tokenize(target_text)
        if not query_tokens or not document_tokens:
            return 0.0

        bm25 = BM25Okapi([document_tokens])
        scores = bm25.get_scores(query_tokens)
        raw_score = float(scores[0]) if len(scores) else 0.0
        raw_score = max(raw_score, 0.0)
        capped_score = min(raw_score, 25.0)
        return float(round((capped_score / 25.0) * 100, 2))

    def compute_match(self, resume_text: str, job_text: str) -> Dict[str, float]:
        tfidf_score = self.tfidf_similarity(resume_text, job_text)
        bm25_score = self.bm25_similarity(job_text, resume_text)
        combined_score = round((tfidf_score * 0.6) + (bm25_score * 0.4), 2)

        return {
            "tfidf_score": tfidf_score,
            "bm25_score": bm25_score,
            "combined_score": combined_score,
        }


def compute_matching_signals(resume_text: str, job_title: str, job_description: str, job_requirements: str) -> Dict[str, float]:
    engine = MatchingEngine()
    job_text = "\n".join(part for part in [job_title, job_description, job_requirements] if part)
    return engine.compute_match(resume_text=resume_text, job_text=job_text)
