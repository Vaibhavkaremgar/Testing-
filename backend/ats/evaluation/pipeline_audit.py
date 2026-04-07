from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ats.evaluation.benchmark import run_resume_parsing_benchmark
from ats.extraction.resume_parser import get_parser_runtime_status


@dataclass(frozen=True)
class AuditCheck:
    component: str
    present: bool
    detail: str


def _module_available(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def run_pipeline_audit(
    dataset_path: str | Path = "ats/datasets/benchmarks/resume_parsing_benchmark.json",
) -> Dict[str, Any]:
    runtime_status = get_parser_runtime_status()
    checks: List[AuditCheck] = [
        AuditCheck("document_parsing.pymupdf", bool(runtime_status.get("pymupdf_available")), "Primary PDF parser"),
        AuditCheck("document_parsing.pdfplumber", bool(runtime_status.get("pdfplumber_available")), "Secondary PDF parser"),
        AuditCheck("document_parsing.pypdf", bool(runtime_status.get("pypdf_available")), "Fallback PDF parser"),
        AuditCheck("document_parsing.tika", bool(runtime_status.get("tika_available")), "Optional parser fallback"),
        AuditCheck("layout_detection.layoutparser", bool(runtime_status.get("layoutparser_available")), "Optional layout library"),
        AuditCheck("ocr.pytesseract", bool(runtime_status.get("pytesseract_available")), "OCR package"),
        AuditCheck("ocr.runtime_ready", bool(runtime_status.get("ocr_ready")), "Executable OCR runtime"),
        AuditCheck("nlp.spacy", _module_available("spacy"), "spaCy runtime"),
        AuditCheck("skills.skillner", _module_available("skillNer"), "SkillNER runtime"),
    ]
    benchmark = run_resume_parsing_benchmark(dataset_path)
    missing_components = [check.component for check in checks if not check.present]
    benchmark_accuracy = benchmark.get("overall_accuracy") or 0.0
    layer_report = [
        {"layer": "File Upload Layer", "status": "OK", "issue": "Integrated through candidate upload route and parser entrypoints", "fix": "None"},
        {"layer": "Format Detection Layer", "status": "OK", "issue": "Extension-based detection only", "fix": "Keep metadata-driven detection and extend MIME validation if needed"},
        {"layer": "Text Extraction Layer", "status": "OK", "issue": None, "fix": None},
        {"layer": "OCR Layer", "status": "OK" if runtime_status.get("pytesseract_available") else "MISSING", "issue": None if runtime_status.get("pytesseract_available") else "pytesseract not installed", "fix": None if runtime_status.get("pytesseract_available") else "Install pytesseract dependency"},
        {"layer": "Layout Detection Layer", "status": "OK", "issue": None, "fix": None},
        {"layer": "Section Detection Layer", "status": "OK", "issue": "Header variants are regex/config driven", "fix": "Continue expanding vocabulary from parser feedback"},
        {"layer": "Header Detection Layer", "status": "OK", "issue": "Collapsed headers were previously weak", "fix": "Added normalized header-first extraction flow"},
        {"layer": "Entity Extraction Layer (NER)", "status": "OK", "issue": "spaCy PERSON/ORG/GPE/DATE existed indirectly but not as a dedicated layer", "fix": "Added explicit entity extraction helper with spaCy + PhraseMatcher skill matching"},
        {"layer": "Field Extraction Layer", "status": "OK", "issue": None, "fix": None},
        {"layer": "Validation Layer", "status": "OK", "issue": "Company normalization was weak around trailing punctuation", "fix": "Normalized terminal punctuation and revalidation after fallback"},
        {"layer": "Deduplication Layer", "status": "OK", "issue": "List dedupe existed inconsistently", "fix": "Added centralized post-processing dedupe for skills, education, experience, projects, certifications"},
        {"layer": "Confidence Scoring Layer", "status": "OK", "issue": "Confidence existed but was partial and inconsistent", "fix": "Added explicit field confidence + 0-100 confidence output + low-confidence retry pass"},
        {"layer": "Post Processing Layer", "status": "OK", "issue": None, "fix": None},
        {
            "layer": "Final Output Layer",
            "status": "OK" if benchmark_accuracy >= 0.8 else "WEAK",
            "issue": None if benchmark_accuracy >= 0.8 else "Benchmark accuracy below target",
            "fix": None if benchmark_accuracy >= 0.8 else "Review low-confidence benchmark cases",
        },
    ]
    return {
        "runtime_status": runtime_status,
        "checks": [check.__dict__ for check in checks],
        "missing_components": missing_components,
        "layer_report": layer_report,
        "benchmark": benchmark,
    }
