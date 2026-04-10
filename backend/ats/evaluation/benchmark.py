from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.ats_warmup import run_ats_warmup
from ats.extraction.information_extraction import extract_resume_information
from ats.extraction.resume_parser import parse_resume


EXACT_MATCH_FIELDS = [
    "name",
    "email",
    "phone",
    "location",
    "current_role",
    "current_company",
]


@dataclass
class BenchmarkCase:
    case_id: str
    domain: str
    source_text: str
    filename: str
    expected: Dict[str, Any]


def _normalize_string(value: Any) -> str:
    normalized = " ".join(str(value or "").strip().split()).lower()
    normalized = normalized.rstrip(".,;:")
    normalized = normalized.replace(" pvt ltd.", " pvt ltd")
    normalized = normalized.replace(" corp.", " corp")
    normalized = normalized.replace(" ltd.", " ltd")
    return normalized


def _normalize_skill_list(values: Any) -> List[str]:
    if not values:
        return []
    normalized = []
    seen = set()
    for value in values:
        item = _normalize_string(value)
        if item and item not in seen:
            seen.add(item)
            normalized.append(item)
    return normalized


def _load_benchmark_cases(dataset_path: str | Path) -> List[BenchmarkCase]:
    path = Path(dataset_path)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    cases: List[BenchmarkCase] = []
    for index, item in enumerate(payload.get("cases", []), start=1):
        case_id = str(item.get("id") or f"case_{index}")
        domain = str(item.get("domain") or "general")
        source_text = str(item.get("resume_text") or "")
        filename = str(item.get("filename") or f"{case_id}.txt")
        expected = dict(item.get("expected") or {})
        cases.append(BenchmarkCase(case_id=case_id, domain=domain, source_text=source_text, filename=filename, expected=expected))
    return cases


class ResumeParsingBenchmark:
    def __init__(self, dataset_path: str | Path):
        self.dataset_path = Path(dataset_path)
        self.cases = _load_benchmark_cases(dataset_path)

    def _parse_case(self, case: BenchmarkCase) -> Dict[str, Any]:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(case.source_text)
            temp_path = handle.name
        try:
            parsed_resume = parse_resume(temp_path, case.filename)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        extracted = extract_resume_information(case.source_text)
        debug_timings = parsed_resume.get("debug_timings") or {}
        confidence_map = parsed_resume.get("confidence") or {}
        average_confidence = round(mean(confidence_map.values()), 1) if confidence_map else None
        return {
            "name": parsed_resume.get("name"),
            "email": parsed_resume.get("email"),
            "phone": parsed_resume.get("phone"),
            "location": extracted.get("location") or parsed_resume.get("location"),
            "current_role": extracted.get("current_role") or parsed_resume.get("current_role"),
            "current_company": extracted.get("current_company") or parsed_resume.get("current_company"),
            "experience_years": extracted.get("total_experience_years") or parsed_resume.get("total_experience_years"),
            "skills": extracted.get("skills") or parsed_resume.get("skills") or [],
            "processing_time_ms": round(float(debug_timings.get("Total Time", 0.0) or 0.0), 2),
            "extraction_method": parsed_resume.get("extraction_method") or "unknown",
            "confidence": average_confidence,
            "confidence_by_field": confidence_map,
        }

    def run(self) -> Dict[str, Any]:
        run_ats_warmup(force=False)
        exact_field_results: Dict[str, List[bool]] = {field: [] for field in EXACT_MATCH_FIELDS}
        experience_errors: List[float] = []
        skill_precisions: List[float] = []
        skill_recalls: List[float] = []
        case_results: List[Dict[str, Any]] = []
        domain_counts: Dict[str, int] = {}
        processing_times_ms: List[float] = []
        confidence_scores: List[float] = []

        for case in self.cases:
            actual = self._parse_case(case)
            expected = case.expected
            case_result: Dict[str, Any] = {
                "id": case.case_id,
                "filename": case.filename,
                "domain": case.domain,
                "fields": {},
                "processing_time_ms": actual.get("processing_time_ms"),
                "extraction_method": actual.get("extraction_method"),
                "confidence": actual.get("confidence"),
                "confidence_by_field": actual.get("confidence_by_field") or {},
            }
            domain_counts[case.domain] = domain_counts.get(case.domain, 0) + 1
            if actual.get("processing_time_ms") is not None:
                processing_times_ms.append(float(actual["processing_time_ms"]))
            if actual.get("confidence") is not None:
                confidence_scores.append(float(actual["confidence"]))

            for field in EXACT_MATCH_FIELDS:
                if field not in expected:
                    continue
                is_match = _normalize_string(actual.get(field)) == _normalize_string(expected.get(field))
                exact_field_results[field].append(is_match)
                case_result["fields"][field] = {
                    "expected": expected.get(field),
                    "actual": actual.get(field),
                    "match": is_match,
                }

            if "experience_years" in expected and expected.get("experience_years") is not None:
                actual_years = actual.get("experience_years")
                if actual_years is not None:
                    error = abs(float(actual_years) - float(expected["experience_years"]))
                    experience_errors.append(error)
                    case_result["fields"]["experience_years"] = {
                        "expected": expected["experience_years"],
                        "actual": actual_years,
                        "absolute_error": round(error, 2),
                    }

            if "skills" in expected:
                expected_skills = set(_normalize_skill_list(expected.get("skills")))
                actual_skills = set(_normalize_skill_list(actual.get("skills")))
                true_positives = len(expected_skills & actual_skills)
                precision = true_positives / len(actual_skills) if actual_skills else 1.0
                recall = true_positives / len(expected_skills) if expected_skills else 1.0
                skill_precisions.append(precision)
                skill_recalls.append(recall)
                case_result["fields"]["skills"] = {
                    "expected_count": len(expected_skills),
                    "actual_count": len(actual_skills),
                    "true_positives": true_positives,
                    "precision": round(precision, 3),
                    "recall": round(recall, 3),
                    "missing": sorted(expected_skills - actual_skills),
                    "unexpected": sorted(actual_skills - expected_skills),
                }

            case_results.append(case_result)

        exact_metrics = {
            field: {
                "cases": len(values),
                "accuracy": round(sum(values) / len(values), 3) if values else None,
            }
            for field, values in exact_field_results.items()
        }
        exact_accuracy_values = [
            metric["accuracy"]
            for metric in exact_metrics.values()
            if metric["accuracy"] is not None
        ]
        avg_precision = mean(skill_precisions) if skill_precisions else None
        avg_recall = mean(skill_recalls) if skill_recalls else None
        avg_f1 = (
            (2 * avg_precision * avg_recall) / (avg_precision + avg_recall)
            if avg_precision is not None and avg_recall is not None and (avg_precision + avg_recall) > 0
            else None
        )
        experience_within_half_year = (
            sum(error <= 0.5 for error in experience_errors) / len(experience_errors)
            if experience_errors else None
        )
        aggregate_components = [value for value in exact_accuracy_values if value is not None]
        if avg_f1 is not None:
            aggregate_components.append(avg_f1)
        if experience_within_half_year is not None:
            aggregate_components.append(experience_within_half_year)
        overall_accuracy = round(mean(aggregate_components), 3) if aggregate_components else None
        resume_time_report = [
            {
                "resume": case_result["filename"],
                "time_ms": case_result.get("processing_time_ms"),
                "method": case_result.get("extraction_method"),
                "accuracy": round(
                    mean(
                        [
                            float(field_result["match"])
                            for field_result in case_result["fields"].values()
                            if isinstance(field_result, dict) and "match" in field_result
                        ]
                    ),
                    3,
                ) if any(
                    isinstance(field_result, dict) and "match" in field_result
                    for field_result in case_result["fields"].values()
                ) else None,
                "confidence": case_result.get("confidence"),
            }
            for case_result in case_results
        ]

        return {
            "dataset_path": str(self.dataset_path),
            "total_cases": len(self.cases),
            "exact_match_metrics": exact_metrics,
            "overall_accuracy": overall_accuracy,
            "performance_metrics": {
                "mean_time_ms": round(mean(processing_times_ms), 2) if processing_times_ms else None,
                "max_time_ms": round(max(processing_times_ms), 2) if processing_times_ms else None,
                "under_5_seconds_rate": round(
                    sum(value <= 5000.0 for value in processing_times_ms) / len(processing_times_ms),
                    3,
                ) if processing_times_ms else None,
            },
            "confidence_metrics": {
                "mean_confidence": round(mean(confidence_scores), 1) if confidence_scores else None,
                "min_confidence": round(min(confidence_scores), 1) if confidence_scores else None,
            },
            "experience_metrics": {
                "cases": len(experience_errors),
                "mean_absolute_error_years": round(mean(experience_errors), 3) if experience_errors else None,
                "within_half_year_rate": round(experience_within_half_year, 3)
                if experience_within_half_year is not None else None,
            },
            "skills_metrics": {
                "cases": len(skill_precisions),
                "avg_precision": round(avg_precision, 3) if avg_precision is not None else None,
                "avg_recall": round(avg_recall, 3) if avg_recall is not None else None,
                "avg_f1": round(avg_f1, 3) if avg_f1 is not None else None,
            },
            "domain_coverage": domain_counts,
            "case_results": case_results,
            "resume_test_report": resume_time_report,
        }


def run_resume_parsing_benchmark(
    dataset_path: str | Path = "backend/ats/datasets/benchmarks/resume_parsing_benchmark.json",
) -> Dict[str, Any]:
    benchmark = ResumeParsingBenchmark(dataset_path)
    return benchmark.run()
