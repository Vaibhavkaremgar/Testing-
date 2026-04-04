import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.evaluation import run_resume_format_benchmark  # noqa: E402


class ResumeFormatBenchmarkTests(unittest.TestCase):
    def test_format_benchmark_reports_four_resume_formats(self):
        result = run_resume_format_benchmark()

        self.assertEqual(result["total_cases"], 4)
        self.assertIn("before_accuracy", result)
        self.assertIn("after_accuracy", result)
        self.assertIn("absolute_improvement", result)
        self.assertEqual(len(result["case_results"]), 4)
        self.assertGreaterEqual(result["after_accuracy"], result["before_accuracy"])


if __name__ == "__main__":
    unittest.main()
