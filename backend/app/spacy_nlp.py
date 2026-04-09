"""
spaCy NLP helpers used by the ATS extraction pipeline.
The model is loaded lazily so API startup stays fast in production.
"""

from __future__ import annotations

from threading import Lock
from typing import Dict

from app.config import settings

try:
    import spacy
except ImportError:
    spacy = None


SPACY_AVAILABLE = spacy is not None
_nlp = None
_nlp_lock = Lock()
_nlp_load_error = None


def get_nlp():
    """Return a shared spaCy model, loading it only on first use."""
    global _nlp, _nlp_load_error

    if _nlp is not None:
        return _nlp
    if not SPACY_AVAILABLE:
        return None

    with _nlp_lock:
        if _nlp is not None:
            return _nlp
        if _nlp_load_error is not None:
            return None

        try:
            _nlp = spacy.load("en_core_web_md")
            print("[OK] spaCy model loaded lazily")
        except (OSError, ImportError) as exc:
            _nlp_load_error = exc
            print(f"[ERROR] spaCy model unavailable: {exc}")
            print("   Install with: pip install spacy && python -m spacy download en_core_web_md")
            return None

    return _nlp


def get_section_doc(section_text: str):
    nlp = get_nlp()
    if nlp is None or not section_text:
        return None
    return nlp(section_text[: settings.NLP_MAX_TEXT_LENGTH])


def get_experience_doc(experience_text: str):
    return get_section_doc(experience_text)


def get_nlp_signals(text: str) -> Dict:
    doc = get_section_doc(text)
    if doc is None:
        return {
            "action_verbs": [],
            "action_verb_count": 0,
            "verb_density": 0.0,
            "impact_metrics": [],
            "impact_count": 0,
            "has_percentages": False,
            "has_money": False,
            "leadership_verbs": [],
            "leadership_count": 0,
            "collaboration_count": 0,
            "action_sentences": 0,
            "total_sentences": 0,
        }

    action_verb_set = {
        "develop", "build", "create", "design", "implement", "architect",
        "deploy", "maintain", "optimize", "improve", "increase", "reduce",
        "achieve", "deliver", "launch", "establish", "execute", "drive",
    }
    leadership_verb_set = {
        "lead", "manage", "coordinate", "mentor", "supervise",
        "direct", "oversee", "guide", "train", "spearhead",
    }

    action_verbs = []
    leadership_verbs = []
    action_sentences = 0
    total_sentences = 0

    for sent in doc.sents:
        total_sentences += 1
        has_action = False
        for token in sent:
            if token.pos_ == "VERB" and token.tag_ in ["VBD", "VBN", "VBG"]:
                lemma = token.lemma_.lower()
                if lemma in action_verb_set:
                    action_verbs.append(lemma)
                    has_action = True
                if lemma in leadership_verb_set:
                    leadership_verbs.append(lemma)
        if has_action:
            action_sentences += 1

    impact_metrics = []
    has_percentages = False
    has_money = False
    for ent in doc.ents:
        if ent.label_ in ["PERCENT", "MONEY", "CARDINAL", "QUANTITY"]:
            impact_metrics.append({"text": ent.text, "type": ent.label_})
            if ent.label_ == "PERCENT":
                has_percentages = True
            elif ent.label_ == "MONEY":
                has_money = True

    text_lower = text.lower()
    collab_keywords = ["team", "collaborated", "cross-functional", "partnered"]
    collaboration_count = sum(1 for kw in collab_keywords if kw in text_lower)
    word_count = len([t for t in doc if not t.is_punct and not t.is_space])
    verb_density = (len(action_verbs) / word_count * 100) if word_count > 0 else 0.0

    return {
        "action_verbs": list(set(action_verbs)),
        "action_verb_count": len(action_verbs),
        "verb_density": round(verb_density, 2),
        "impact_metrics": impact_metrics[:10],
        "impact_count": len(impact_metrics),
        "has_percentages": has_percentages,
        "has_money": has_money,
        "leadership_verbs": list(set(leadership_verbs)),
        "leadership_count": len(leadership_verbs),
        "collaboration_count": collaboration_count,
        "action_sentences": action_sentences,
        "total_sentences": total_sentences,
    }


def extract_action_verbs(text: str) -> Dict:
    signals = get_nlp_signals(text)
    return {
        "verbs": signals["action_verbs"],
        "count": signals["action_verb_count"],
        "density": signals["verb_density"],
    }


def extract_impact_entities(text: str) -> Dict:
    signals = get_nlp_signals(text)
    return {
        "metrics": signals["impact_metrics"],
        "count": signals["impact_count"],
        "has_money": signals["has_money"],
        "has_percent": signals["has_percentages"],
    }


def extract_soft_skill_signals(text: str) -> Dict:
    signals = get_nlp_signals(text)
    return {
        "leadership": signals["leadership_count"],
        "collaboration": signals["collaboration_count"],
        "communication": 0,
    }
