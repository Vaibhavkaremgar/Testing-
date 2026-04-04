import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.routes.candidates import sanitize_candidate_email  # noqa: E402


class CandidateResponseSanitizationTests(unittest.TestCase):
    def test_invalid_legacy_email_is_dropped(self):
        self.assertIsNone(sanitize_candidate_email("rahul.verma.ai"))

    def test_linkedin_appended_email_is_trimmed(self):
        self.assertEqual(
            sanitize_candidate_email("vaibhav@gmail.com.linkedin.com"),
            "vaibhav@gmail.com",
        )


if __name__ == "__main__":
    unittest.main()
