from __future__ import annotations

import re
from threading import Lock
from typing import Any, Dict, Iterable, List, Tuple

from ats.extraction.skill_intelligence import get_skill_engine
from app.spacy_nlp import SPACY_AVAILABLE, get_nlp, get_section_doc

try:
    from spacy.matcher import PhraseMatcher
except ImportError:  # pragma: no cover - spaCy is a hard dependency in this repo, but keep import-safe.
    PhraseMatcher = None

_skill_matcher = None
_skill_patterns_loaded = False
_skill_matcher_lock = Lock()
_whitespace_pattern = re.compile(r"\s+")
_MAX_MATCHER_TERMS = 1200


def _normalize_text(value: str) -> str:
    return _whitespace_pattern.sub(" ", (value or "").strip())


def _dedupe(values: Iterable[str]) -> List[str]:
    ordered: List[str] = []
    seen = set()
    for value in values:
        normalized = _normalize_text(value)
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _ensure_skill_matcher() -> None:
    global _skill_matcher, _skill_patterns_loaded
    if _skill_patterns_loaded:
        return

    with _skill_matcher_lock:
        if _skill_patterns_loaded:
            return

        nlp = get_nlp()
        if not SPACY_AVAILABLE or nlp is None or PhraseMatcher is None:
            _skill_patterns_loaded = True
            return

        skill_engine = get_skill_engine()
        matcher = PhraseMatcher(nlp.vocab, attr="LOWER")
        matcher_terms = _build_minimal_matcher_terms(skill_engine)
        patterns = list(nlp.pipe(matcher_terms, disable=["parser", "tagger", "ner"]))
        if patterns:
            matcher.add("SKILL", patterns)
        _skill_matcher = matcher
        _skill_patterns_loaded = True


def _build_minimal_matcher_terms(skill_engine) -> List[str]:
    terms: List[str] = []
    for skills in getattr(skill_engine, "domain_skills", {}).values():
        terms.extend(skills)
    terms.extend(getattr(skill_engine, "skill_aliases", {}).keys())
    terms.extend(getattr(skill_engine, "skill_aliases", {}).values())

    curated = []
    seen = set()
    for term in _dedupe(terms):
        normalized = _normalize_text(term).lower()
        if not normalized or normalized in seen:
            continue
        if len(normalized.split()) > 4:
            continue
        seen.add(normalized)
        curated.append(term)
        if len(curated) >= _MAX_MATCHER_TERMS:
            break
    return curated


def warm_entity_extraction() -> Dict[str, Any]:
    _ensure_skill_matcher()
    sample = extract_resume_entities(
        "Jane Doe\nSkills\nPython, FastAPI, Docker",
        header_text="Jane Doe",
        skills_text="Python, FastAPI, Docker",
        experience_text="Engineer | Acme Corp",
    )
    return {
        "skill_matcher_ready": _skill_patterns_loaded,
        "matcher_term_count": len(_build_minimal_matcher_terms(get_skill_engine())),
        "sample_skill_count": len(sample.get("skills") or []),
        "sample_person_count": len(sample.get("persons") or []),
    }


def _collect_person_candidates(window: str, *, prefer_first: bool = False) -> List[Tuple[int, str]]:
    ranked: List[Tuple[int, str]] = []
    doc = get_section_doc(window)
    if doc is None:
        return ranked
    for ent in doc.ents:
        if ent.label_ != "PERSON":
            continue
        cleaned = _normalize_text(ent.text.strip(" ,.-|"))
        if not cleaned:
            continue
        rank = ent.start_char
        if prefer_first:
            rank -= 1000
        ranked.append((rank, cleaned))
    return ranked


def extract_resume_entities(
    text: str,
    *,
    header_text: str = "",
    skills_text: str = "",
    experience_text: str = "",
) -> Dict[str, Any]:
    entities: Dict[str, Any] = {
        "persons": [],
        "organizations": [],
        "locations": [],
        "dates": [],
        "skills": [],
        "top_person": "",
        "top_location": "",
    }
    if not SPACY_AVAILABLE:
        return entities

    search_windows = [
        _normalize_text(header_text),
        _normalize_text(skills_text),
        _normalize_text(experience_text),
        _normalize_text(text)[:2500],
    ]
    person_hits: List[str] = []
    ranked_person_hits: List[Tuple[int, str]] = []
    org_hits: List[str] = []
    location_hits: List[str] = []
    date_hits: List[str] = []

    filtered_text = "\n".join(
        line for line in _normalize_text(text).split("\n")
        if "references" not in line.lower()
    )
    search_windows = [
        _normalize_text(header_text),
        _normalize_text(skills_text),
        _normalize_text(experience_text),
        filtered_text[:2500],
    ]

    for index, window in enumerate(search_windows):
        if not window:
            continue
        doc = get_section_doc(window)
        if doc is None:
            continue
        ranked_person_hits.extend(_collect_person_candidates(window, prefer_first=index == 0))
        for ent in doc.ents:
            cleaned = _normalize_text(ent.text.strip(" ,.-|"))
            if not cleaned:
                continue
            if ent.label_ == "PERSON":
                person_hits.append(cleaned)
            elif ent.label_ == "ORG":
                org_hits.append(cleaned)
            elif ent.label_ == "GPE":
                location_hits.append(cleaned)
            elif ent.label_ == "DATE":
                date_hits.append(cleaned)

    _ensure_skill_matcher()
    skill_hits: List[str] = []
    if _skill_matcher is not None:
        skill_engine = get_skill_engine()
        skill_sources = [skills_text, header_text, experience_text, text]
        for source in skill_sources:
            normalized_source = _normalize_text(source)
            if not normalized_source:
                continue
            doc = get_section_doc(normalized_source)
            if doc is None:
                continue
            for _, start, end in _skill_matcher(doc):
                candidate = skill_engine.normalize_skill(doc[start:end].text)
                canonical = skill_engine.get_synonym_dictionary().get(candidate, candidate)
                if canonical:
                    skill_hits.append(canonical)

    entities["persons"] = _dedupe(person_hits)
    entities["organizations"] = _dedupe(org_hits)
    entities["locations"] = _dedupe(location_hits)
    entities["dates"] = _dedupe(date_hits)
    entities["skills"] = _dedupe(skill_hits)
    ranked_person_hits.sort(key=lambda item: item[0])
    entities["top_person"] = ranked_person_hits[0][1] if ranked_person_hits else (entities["persons"][0] if entities["persons"] else "")
    entities["top_location"] = entities["locations"][0] if entities["locations"] else ""
    return entities
