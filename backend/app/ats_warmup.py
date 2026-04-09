from __future__ import annotations

import io
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from typing import Any, Dict

import pdfplumber

from app.spacy_nlp import get_nlp
from ats.datasets.parser_config_loader import ParserConfigLoader
from ats.extraction.entity_extraction import warm_entity_extraction
from ats.extraction.information_extraction import (
    HEADER_LOCATION_PATTERN,
    LOCATION_CANDIDATE_PATTERN,
    LOCATION_LINE_LABEL_PATTERN,
    PHONE_PATTERNS,
    PLACE_LINE_PATTERN,
    STRICT_EMAIL_PATTERN,
    warm_skill_keyword_processor,
)
from ats.extraction.resume_parser import fitz, get_parser_runtime_status
from ats.extraction.skill_intelligence import get_skill_engine
from ats.preprocessing.section_segmentation import (
    BOUNDARY_HEADER_PATTERNS,
    SECTION_HEADER_PATTERNS,
    SECTION_PREFIX_PATTERNS,
    segment_resume_sections,
)

logger = logging.getLogger(__name__)

_warmup_lock = Lock()
GLOBAL_MODELS: Dict[str, Any] = {
    "spacy": None,
    "pymupdf": None,
    "pdfplumber": None,
    "skill_engine": None,
    "skill_keyword_processor": None,
    "entity_extraction": None,
    "parser_vocabulary": None,
    "skill_overlays": None,
    "regex_patterns": {},
    "section_patterns": {},
    "ready": False,
}
_warmup_state: Dict[str, Any] = {
    "ready": False,
    "last_run_at": None,
    "duration_ms": None,
    "components": {},
}
_DUMMY_PDF_BYTES = (
    b"%PDF-1.1\n"
    b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
    b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
    b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R >>endobj\n"
    b"4 0 obj<< /Length 44 >>stream\nBT /F1 12 Tf 72 120 Td (warmup) Tj ET\nendstream endobj\n"
    b"xref\n0 5\n0000000000 65535 f \n0000000010 00000 n \n0000000063 00000 n \n0000000122 00000 n \n0000000212 00000 n \n"
    b"trailer<< /Root 1 0 R /Size 5 >>\nstartxref\n306\n%%EOF"
)


def _warm_spacy() -> Dict[str, Any]:
    nlp = get_nlp()
    if nlp is not None:
        _ = nlp("warmup")
    GLOBAL_MODELS["spacy"] = nlp
    return {"ok": nlp is not None, "details": {"loaded": nlp is not None, "executed": nlp is not None}}


def _warm_pdf_stack() -> Dict[str, Any]:
    runtime = get_parser_runtime_status()
    pymupdf_executed = False
    pdfplumber_executed = False
    if fitz is not None:
        try:
            with fitz.open(stream=_DUMMY_PDF_BYTES, filetype="pdf") as document:
                _ = document.page_count
            pymupdf_executed = True
        except Exception:
            pymupdf_executed = False
    try:
        with pdfplumber.open(io.BytesIO(_DUMMY_PDF_BYTES)) as document:
            _ = len(document.pages)
        pdfplumber_executed = True
    except Exception:
        pdfplumber_executed = False
    GLOBAL_MODELS["pymupdf"] = fitz
    GLOBAL_MODELS["pdfplumber"] = pdfplumber
    return {
        "ok": bool(runtime.get("pymupdf_available")) and bool(runtime.get("pdfplumber_available")),
        "details": {
            "pdfplumber_version": getattr(pdfplumber, "__version__", "unknown"),
            "pymupdf_available": bool(runtime.get("pymupdf_available")),
            "pdfplumber_available": bool(runtime.get("pdfplumber_available")),
            "pymupdf_executed": pymupdf_executed,
            "pdfplumber_executed": pdfplumber_executed,
        },
    }


def _warm_skill_engine() -> Dict[str, Any]:
    engine = get_skill_engine()
    sample_skills = engine.extract_skills("Python FastAPI Docker warmup") if engine is not None else []
    GLOBAL_MODELS["skill_engine"] = engine
    return {
        "ok": engine is not None,
        "details": {
            "skills_loaded": len(engine.get_skill_dictionary()) if engine is not None else 0,
            "synonyms_loaded": len(engine.get_synonym_dictionary()) if engine is not None else 0,
            "sample_match_count": len(sample_skills),
        },
    }


def _warm_skill_keywords() -> Dict[str, Any]:
    state = warm_skill_keyword_processor()
    GLOBAL_MODELS["skill_keyword_processor"] = state
    return {"ok": True, "details": state}


def _warm_parser_config() -> Dict[str, Any]:
    loader = ParserConfigLoader()
    vocabulary = loader.load_parser_vocabulary()
    overlays = loader.load_skill_overlays()
    GLOBAL_MODELS["parser_vocabulary"] = vocabulary
    GLOBAL_MODELS["skill_overlays"] = overlays
    GLOBAL_MODELS["section_patterns"] = {
        "headers": SECTION_HEADER_PATTERNS,
        "prefixes": SECTION_PREFIX_PATTERNS,
        "boundaries": BOUNDARY_HEADER_PATTERNS,
    }
    GLOBAL_MODELS["regex_patterns"] = {
        "email": STRICT_EMAIL_PATTERN,
        "phones": PHONE_PATTERNS,
        "header_location": HEADER_LOCATION_PATTERN,
        "location_label": LOCATION_LINE_LABEL_PATTERN,
        "location_candidate": LOCATION_CANDIDATE_PATTERN,
        "place_line": PLACE_LINE_PATTERN,
    }
    regex_checks = {
        "email": bool(STRICT_EMAIL_PATTERN.search("warmup@example.com")),
        "phone": any(pattern.search("+91 9876543210") for pattern in PHONE_PATTERNS),
        "location": bool(HEADER_LOCATION_PATTERN.search("Austin, Texas")),
    }
    sample_sections = segment_resume_sections(
        "Jane Doe\nTechnical Skills\nPython, FastAPI\nWork Experience\nEngineer | Acme Ltd\nJan 2022 - Present"
    )
    return {
        "ok": True,
        "details": {
            "parser_vocabulary_loaded": bool(vocabulary),
            "skill_overlays_loaded": bool(overlays),
            "section_patterns_compiled": bool(sample_sections.get("skills")) and bool(sample_sections.get("experience")),
            "regex_executed": all(regex_checks.values()),
        },
    }


def run_ats_warmup(force: bool = False) -> Dict[str, Any]:
    with _warmup_lock:
        if _warmup_state.get("ready") and not force:
            return dict(_warmup_state)

        started_at = time.perf_counter()
        components: Dict[str, Any] = {}
        warmers = {
            "spacy": _warm_spacy,
            "pdf_stack": _warm_pdf_stack,
            "skill_engine": _warm_skill_engine,
            "skill_keywords": _warm_skill_keywords,
            "parser_config": _warm_parser_config,
        }

        with ThreadPoolExecutor(max_workers=len(warmers)) as executor:
            future_map = {
                executor.submit(warmer): name
                for name, warmer in warmers.items()
            }
            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    components[name] = future.result()
                except Exception as exc:  # pragma: no cover - defensive production path
                    logger.warning("ATS warmup failed for %s: %s", name, exc)
                    components[name] = {"ok": False, "error": str(exc), "details": {}}

        try:
            entity_warmup = warm_entity_extraction()
            GLOBAL_MODELS["entity_extraction"] = entity_warmup
            components["entity_extraction"] = {"ok": True, "details": entity_warmup}
        except Exception as exc:  # pragma: no cover - defensive production path
            logger.warning("ATS warmup failed for entity_extraction: %s", exc)
            components["entity_extraction"] = {"ok": False, "error": str(exc), "details": {}}

        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 2)
        _warmup_state.update(
            {
                "ready": all(component.get("ok") for component in components.values()),
                "last_run_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "duration_ms": duration_ms,
                "components": components,
            }
        )
        GLOBAL_MODELS["ready"] = _warmup_state["ready"]
        return dict(_warmup_state)


def get_ats_warmup_state() -> Dict[str, Any]:
    return dict(_warmup_state)
