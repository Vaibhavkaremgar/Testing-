import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.routes.candidates import build_safe_candidate_response, sanitize_candidate_email  # noqa: E402
from app.models import CandidateStage, ParsingStatus  # noqa: E402


class CandidateResponseSanitizationTests(unittest.TestCase):
    def test_invalid_legacy_email_is_dropped(self):
        self.assertIsNone(sanitize_candidate_email("rahul.verma.ai"))

    def test_linkedin_appended_email_is_trimmed(self):
        self.assertEqual(
            sanitize_candidate_email("vaibhav@gmail.com.linkedin.com"),
            "vaibhav@gmail.com",
        )

    def test_safe_candidate_response_drops_invalid_email_without_crashing(self):
        payload = {
            "id": "00000000-0000-0000-0000-000000000001",
            "name": "Rahul Verma",
            "email": "rahul.verma.ai",
            "phone": None,
            "current_company": None,
            "current_role": None,
            "experience_years": None,
            "location": None,
            "linkedin_url": None,
            "resume_file_path": None,
            "resume_text": None,
            "parsing_status": ParsingStatus.COMPLETED,
            "resume_score": None,
            "score_threshold": None,
            "skills": [],
            "education": [],
            "work_experience": [],
            "stage": CandidateStage.APPLIED,
            "stage_updated_at": "2026-04-04T12:00:00",
            "stage_entered_at": None,
            "applied_at": None,
            "job_id": None,
            "job_title": None,
            "summary": None,
            "predefined_questions": None,
            "created_at": "2026-04-04T12:00:00",
        }

        response = build_safe_candidate_response(payload)

        self.assertIsNone(response.email)


if __name__ == "__main__":
    unittest.main()
