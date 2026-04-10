import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.evaluation import run_deployment_audit, run_pipeline_audit, run_production_readiness_evaluation  # noqa: E402


class ATSProductionReadinessTests(unittest.TestCase):
    def test_deployment_audit_detects_docker_railway_setup(self):
        result = run_deployment_audit(".")

        self.assertEqual(result["deployment_type"], "Docker")
        self.assertTrue(result["dockerfile_exists"])
        self.assertEqual(result["railway_builder"], "DOCKERFILE")

    def test_pipeline_audit_reports_required_layers(self):
        result = run_pipeline_audit("backend/ats/datasets/benchmarks/resume_parsing_benchmark.json")

        self.assertIn("layer_report", result)
        self.assertEqual(len(result["layer_report"]), 14)
        self.assertTrue(any(layer["layer"] == "Entity Extraction Layer (NER)" for layer in result["layer_report"]))
        self.assertIn("audit_report", result)
        self.assertTrue(result["audit_report"]["section_detection"]["strict_isolation"])
        self.assertGreaterEqual(len(result["resume_test_report"]), 10)

    def test_production_readiness_evaluation_returns_combined_report(self):
        result = run_production_readiness_evaluation("backend/ats/datasets/benchmarks/resume_parsing_benchmark.json")

        self.assertIn("deployment", result)
        self.assertIn("audit", result)
        self.assertIn("parsing_benchmark", result)
        self.assertIn("format_benchmark", result)
        self.assertGreaterEqual(len(result["resume_test_report"]), 16)


if __name__ == "__main__":
    unittest.main()
