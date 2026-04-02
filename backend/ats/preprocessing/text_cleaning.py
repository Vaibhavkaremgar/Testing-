from __future__ import annotations

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

try:
    import nltk
    from nltk.data import find
    from nltk.tokenize import sent_tokenize, word_tokenize

    NLTK_AVAILABLE = True
except ImportError:
    nltk = None
    find = None
    sent_tokenize = None
    word_tokenize = None
    NLTK_AVAILABLE = False

_PUNKT_READY = False
_URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)
_BULLET_LINE_PATTERN = re.compile(r"(?m)^\s*[\u2022\u2023\u25E6\u2043\u2219\-\*\u00B7]+\s*")
_SPECIAL_CHARACTER_PATTERN = re.compile(r"[^\w\s@.,;:/+#&()\-\n]")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def _ensure_punkt() -> bool:
    
    global _PUNKT_READY

    if _PUNKT_READY or not NLTK_AVAILABLE:
        return _PUNKT_READY

    try:
        find("tokenizers/punkt")
    except LookupError:
        try:
            nltk.download("punkt", quiet=True)
            find("tokenizers/punkt")
        except Exception as exc:
            logger.warning("Unable to download NLTK punkt tokenizer: %s", exc)
            return False

    try:
        find("tokenizers/punkt_tab/english/")
    except LookupError:
        try:
            nltk.download("punkt_tab", quiet=True)
            find("tokenizers/punkt_tab/english/")
        except Exception as exc:
            logger.warning("Unable to download NLTK punkt_tab tokenizer data: %s", exc)
            return False

    try:
        _PUNKT_READY = True
        return True
    except Exception as exc:
        logger.warning("Unable to initialize NLTK punkt tokenizers: %s", exc)
        return False


def _tokenize_sentences(text: str) -> List[str]:
    if not text:
        return []

    if NLTK_AVAILABLE and _ensure_punkt():
        try:
            return [sentence for sentence in sent_tokenize(text) if sentence.strip()]
        except LookupError:
            logger.warning("NLTK sentence tokenizer unavailable at runtime; using regex fallback.")

    return [sentence.strip() for sentence in re.split(r"[.!?\n]+", text) if sentence.strip()]


def _tokenize_words(text: str) -> List[str]:
    if not text:
        return []

    if NLTK_AVAILABLE and _ensure_punkt():
        try:
            return word_tokenize(text)
        except LookupError:
            logger.warning("NLTK word tokenizer unavailable at runtime; using regex fallback.")

    return re.findall(r"\b\w+(?:[.+#-]\w+)*\b|[.,;:/+#&()\-]", text)


def normalize_text(text: str) -> str:
    
    if not text:
        return ""

    text = text.lower().replace("\r", "\n")
    text = re.sub(r"\n+", "\n", text)

    normalized_sentences: List[str] = []
    for sentence in _tokenize_sentences(text):
        tokens = _tokenize_words(sentence)
        normalized_sentence = " ".join(token for token in tokens if token.strip())
        if normalized_sentence:
            normalized_sentences.append(normalized_sentence)

    if not normalized_sentences:
        text = text.replace("\n", " ")
        return _WHITESPACE_PATTERN.sub(" ", text).strip()

    normalized_text = " ".join(normalized_sentences)
    return _WHITESPACE_PATTERN.sub(" ", normalized_text).strip()


def remove_special_characters(text: str) -> str:
    
    if not text:
        return ""
    return _SPECIAL_CHARACTER_PATTERN.sub(" ", text)


def remove_bullets(text: str) -> str:
    
    if not text:
        return ""
    return _BULLET_LINE_PATTERN.sub("", text)


def remove_urls(text: str) -> str:
    
    if not text:
        return ""
    return _URL_PATTERN.sub(" ", text)


def clean_text_pipeline(text: str) -> str:
    
    cleaned_text = remove_urls(text)
    cleaned_text = remove_bullets(cleaned_text)
    cleaned_text = remove_special_characters(cleaned_text)
    cleaned_text = normalize_text(cleaned_text)
    return cleaned_text


def clean_text(text: str) -> str:
    """Public text-cleaning entrypoint for resume and JD parsing."""
    cleaned_text = clean_text_pipeline(text)
    logger.info("Text Cleaning Applied")
    print("Text Cleaning Applied")
    return cleaned_text