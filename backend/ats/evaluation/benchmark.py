from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

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
    source_text: str
    filename: str
    expected: Dict[str, Any]


def _normalize_string(value: Any) -> str:
    return " ".join(str(value or "").strip().split()).lower()


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
        source_text = str(item.get("resume_text") or "")
        filename = str(item.get("filename") or f"{case_id}.txt")
        expected = dict(item.get("expected") or {})
        cases.append(BenchmarkCase(case_id=case_id, source_text=source_text, filename=filename, expected=expected))
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
        return {
            "name": parsed_resume.get("name"),
            "email": parsed_resume.get("email"),
            "phone": parsed_resume.get("phone"),
            "location": extracted.get("location") or parsed_resume.get("location"),
            "current_role": extracted.get("current_role") or parsed_resume.get("current_role"),
            "current_company": extracted.get("current_company") or parsed_resume.get("current_company"),
            "experience_years": extracted.get("total_experience_years") or parsed_resume.get("total_experience_years"),
            "skills": extracted.get("skills") or parsed_resume.get("skills") or [],
        }

    def run(self) -> Dict[str, Any]:
        exact_field_results: Dict[str, List[bool]] = {field: [] for field in EXACT_MATCH_FIELDS}
        experience_errors: List[float] = []
        skill_precisions: List[float] = []
        skill_recalls: List[float] = []
        case_results: List[Dict[str, Any]] = []

        for case in self.cases:
            actual = self._parse_case(case)
            expected = case.expected
            case_result: Dict[str, Any] = {"id": case.case_id, "fields": {}}

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
        avg_precision = mean(skill_precisions) if skill_precisions else None
        avg_recall = mean(skill_recalls) if skill_recalls else None
        avg_f1 = (
            (2 * avg_precision * avg_recall) / (avg_precision + avg_recall)
            if avg_precision is not None and avg_recall is not None and (avg_precision + avg_recall) > 0
            else None
        )

        return {
            "dataset_path": str(self.dataset_path),
            "total_cases": len(self.cases),
            "exact_match_metrics": exact_metrics,
            "experience_metrics": {
                "cases": len(experience_errors),
                "mean_absolute_error_years": round(mean(experience_errors), 3) if experience_errors else None,
                "within_half_year_rate": round(sum(error <= 0.5 for error in experience_errors) / len(experience_errors), 3)
                if experience_errors else None,
            },
            "skills_metrics": {
                "cases": len(skill_precisions),
                "avg_precision": round(avg_precision, 3) if avg_precision is not None else None,
                "avg_recall": round(avg_recall, 3) if avg_recall is not None else None,
                "avg_f1": round(avg_f1, 3) if avg_f1 is not None else None,
            },
            "case_results": case_results,
        }


def run_resume_parsing_benchmark(
    dataset_path: str | Path = "backend/ats/datasets/benchmarks/resume_parsing_benchmark.json",
) -> Dict[str, Any]:
    benchmark = ResumeParsingBenchmark(dataset_path)
    return benchmark.run()
