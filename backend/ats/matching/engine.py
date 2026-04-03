from __future__ import annotations

import math
import re
from collections import Counter
from typing import Dict, List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ats.preprocessing.text_cleaning import clean_text_pipeline

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9.+#/-]*")


class MatchingEngine:
    """Resume-to-JD matching engine using TF-IDF and BM25."""

    def _normalize_text(self, text: str) -> str:
        return clean_text_pipeline(text or "")

    def _tokenize(self, text: str) -> List[str]:
        normalized = self._normalize_text(text)
        return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(normalized)]

    def _bm25_raw_score(
        self,
        query_tokens: List[str],
        document_tokens: List[str],
        *,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> float:
        if not query_tokens or not document_tokens:
            return 0.0

        doc_length = len(document_tokens)
        avg_doc_length = float(doc_length)
        doc_counts = Counter(document_tokens)
        query_counts = Counter(query_tokens)
        score = 0.0

        for token, query_frequency in query_counts.items():
            term_frequency = doc_counts.get(token, 0)
            if term_frequency <= 0:
                continue

            # Smoothed single-document BM25 IDF to avoid zero or negative scores.
            doc_frequency = 1
            corpus_size = 1
            idf = math.log(1.0 + ((corpus_size - doc_frequency + 0.5) / (doc_frequency + 0.5)))
            numerator = term_frequency * (k1 + 1.0)
            denominator = term_frequency + k1 * (1.0 - b + b * (doc_length / avg_doc_length))
            score += idf * (numerator / denominator) * query_frequency

        return score

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

        raw_score = self._bm25_raw_score(query_tokens, document_tokens)
        ideal_score = self._bm25_raw_score(query_tokens, query_tokens)
        if ideal_score <= 0.0:
            return 0.0
        normalized_score = min(raw_score / ideal_score, 1.0)
        return float(round(normalized_score * 100, 2))

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
