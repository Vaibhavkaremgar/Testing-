from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from ats.evaluation.benchmark import run_resume_parsing_benchmark
from ats.evaluation.deployment_audit import run_deployment_audit
from ats.evaluation.format_benchmark import run_resume_format_benchmark
from ats.evaluation.pipeline_audit import run_pipeline_audit


def _build_resume_test_report(parsing_benchmark: Dict[str, Any], format_benchmark: Dict[str, Any]) -> List[Dict[str, Any]]:
    report_rows: List[Dict[str, Any]] = []
    for case in parsing_benchmark.get("case_results", []):
        fields = case.get("fields", {})
        report_rows.append(
            {
                "resume": case.get("id"),
                "name": "Correct" if fields.get("name", {}).get("match", True) else "Incorrect",
                "email": "Correct" if fields.get("email", {}).get("match", True) else "Incorrect",
                "skills": "Correct" if fields.get("skills", {}).get("recall", 1.0) >= 0.8 else "Needs Review",
                "confidence": f"{int(round((sum(1 for field in fields.values() if field.get('match', True)) / max(len(fields), 1)) * 100))}%",
                "type": "benchmark_text",
            }
        )
    for case in format_benchmark.get("case_results", []):
        report_rows.append(
            {
                "resume": case.get("id"),
                "name": "Correct" if case.get("after", {}).get("parsed", {}).get("name") == case.get("expected", {}).get("name") else "Incorrect",
                "email": "Correct" if case.get("after", {}).get("parsed", {}).get("email") == case.get("expected", {}).get("email") else "Incorrect",
                "skills": "N/A",
                "confidence": f"{int(round(float(case.get('after', {}).get('score', 0.0)) * 100))}%",
                "type": "format_case",
            }
        )
    return report_rows


def run_production_readiness_evaluation(
    dataset_path: str | Path = "backend/ats/datasets/benchmarks/resume_parsing_benchmark.json",
) -> Dict[str, Any]:
    parsing_benchmark = run_resume_parsing_benchmark(dataset_path)
    format_benchmark = run_resume_format_benchmark()
    pipeline_audit = run_pipeline_audit(dataset_path)
    deployment_audit = run_deployment_audit(".")
    return {
        "deployment": deployment_audit,
        "audit": pipeline_audit,
        "parsing_benchmark": parsing_benchmark,
        "format_benchmark": format_benchmark,
        "resume_test_report": _build_resume_test_report(parsing_benchmark, format_benchmark),
    }
