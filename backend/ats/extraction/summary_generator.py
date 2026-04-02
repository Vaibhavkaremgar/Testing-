from __future__ import annotations

import logging
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ats.preprocessing.text_cleaning import NLTK_AVAILABLE, _ensure_punkt, clean_text_pipeline

logger = logging.getLogger(__name__)

try:
    from nltk.tokenize import sent_tokenize
except ImportError:  # pragma: no cover - nltk is already a dependency, but keep runtime safe.
    sent_tokenize = None

DEFAULT_SUMMARY = "No relevant summary could be generated."
MAX_RESUME_SENTENCES = 20
MIN_SUMMARY_SENTENCES = 3
MAX_SUMMARY_SENTENCES = 5


def _tokenize_sentences(text: str) -> List[str]:
    """Tokenize text into sentences using NLTK with a regex fallback."""
    if not text:
        return []

    if NLTK_AVAILABLE and sent_tokenize is not None and _ensure_punkt():
        try:
            return [sentence.strip() for sentence in sent_tokenize(text) if sentence.strip()]
        except LookupError:
            logger.warning("NLTK sentence tokenizer unavailable at runtime; using regex fallback.")

    import re

    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+|\n+", text) if sentence.strip()]


def _select_summary_size(sentence_count: int) -> int:
    if sentence_count <= MIN_SUMMARY_SENTENCES:
        return sentence_count
    if sentence_count <= 8:
        return MIN_SUMMARY_SENTENCES
    if sentence_count <= 14:
        return 4
    return MAX_SUMMARY_SENTENCES


def generate_summary(resume_text: str, jd_text: str) -> str:
    """
    Generate a JD-centric extractive summary from resume text.

    Steps:
    1. Sentence tokenize the resume.
    2. Combine JD text with resume sentences into one corpus.
    3. Create TF-IDF vectors.
    4. Compute cosine similarity between the JD vector and each resume sentence.
    5. Rank resume sentences by similarity.
    6. Select the top 3-5 sentences and preserve original resume order.
    """
    if not resume_text or not resume_text.strip():
        logger.info("Summary generation skipped because resume text is empty.")
        return DEFAULT_SUMMARY

    resume_sentences = _tokenize_sentences(resume_text)
    resume_sentences = [sentence for sentence in resume_sentences if sentence.strip()][:MAX_RESUME_SENTENCES]
    if not resume_sentences:
        logger.info("Summary generation skipped because no resume sentences were found.")
        return DEFAULT_SUMMARY

    normalized_jd = clean_text_pipeline(jd_text or "")
    if not normalized_jd:
        top_n = _select_summary_size(len(resume_sentences))
        logger.info("JD text unavailable; using leading resume sentences for extractive summary.")
        return " ".join(resume_sentences[:top_n]) if resume_sentences[:top_n] else DEFAULT_SUMMARY

    corpus = [normalized_jd]
    corpus.extend(clean_text_pipeline(sentence) for sentence in resume_sentences)

    try:
        vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
        matrix = vectorizer.fit_transform(corpus)
        jd_vector = matrix[0:1]
        sentence_vectors = matrix[1:]
        similarity_scores = cosine_similarity(jd_vector, sentence_vectors)[0]
    except ValueError as exc:
        logger.warning("Summary generation failed during TF-IDF computation: %s", exc)
        top_n = _select_summary_size(len(resume_sentences))
        return " ".join(resume_sentences[:top_n]) if resume_sentences[:top_n] else DEFAULT_SUMMARY

    ranked_indices = sorted(
        range(len(resume_sentences)),
        key=lambda index: similarity_scores[index],
        reverse=True,
    )
    top_n = _select_summary_size(len(resume_sentences))
    selected_indices = sorted(ranked_indices[:top_n])
    summary_sentences = [resume_sentences[index] for index in selected_indices if similarity_scores[index] > 0]

    if not summary_sentences:
        logger.info("No JD-relevant sentences scored above zero; using leading resume sentences.")
        summary_sentences = resume_sentences[:top_n]

    return " ".join(summary_sentences) if summary_sentences else DEFAULT_SUMMARY
