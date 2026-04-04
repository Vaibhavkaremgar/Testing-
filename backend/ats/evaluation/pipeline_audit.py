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
    return {
        "runtime_status": runtime_status,
        "checks": [check.__dict__ for check in checks],
        "missing_components": missing_components,
        "benchmark": benchmark,
    }
