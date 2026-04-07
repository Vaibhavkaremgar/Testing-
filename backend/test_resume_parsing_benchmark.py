import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.evaluation import run_resume_parsing_benchmark  # noqa: E402


class ResumeParsingBenchmarkTests(unittest.TestCase):
    def test_benchmark_runner_reports_expected_metric_shape(self):
        result = run_resume_parsing_benchmark()

        self.assertEqual(result["total_cases"], 10)
        self.assertIn("exact_match_metrics", result)
        self.assertIn("skills_metrics", result)
        self.assertIn("experience_metrics", result)
        self.assertIn("domain_coverage", result)
        self.assertGreaterEqual(result["exact_match_metrics"]["name"]["accuracy"], 0.8)
        self.assertGreaterEqual(result["skills_metrics"]["avg_recall"], 0.75)


if __name__ == "__main__":
    unittest.main()
