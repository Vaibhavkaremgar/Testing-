import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.resume_parser import detect_image_resume, detect_scanned_pdf, parse_resume, run_ocr  # noqa: E402


class ResumeOCRAndTypeDetectionTests(unittest.TestCase):
    def test_detect_image_resume_by_extension(self):
        self.assertTrue(detect_image_resume("resume_scan.png"))
        self.assertFalse(detect_image_resume("resume.pdf"))

    def test_detect_scanned_pdf_returns_true_for_empty_native_text(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name
        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=([], [{"is_scanned_pdf": True}])):
                self.assertTrue(detect_scanned_pdf(temp_path))
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_run_ocr_dispatches_to_image_ocr(self):
        with patch("ats.extraction.resume_parser._extract_image_text_via_ocr", return_value=["image text"]) as mocked:
            result = run_ocr("resume.png")
        self.assertEqual(result, ["image text"])
        mocked.assert_called_once()

    def test_parse_resume_reports_resume_type_and_layout_header_signal(self):
        resume_text = """
Rahul Developer
Bengaluru, Karnataka | +91 9876543210 | rahul.dev@gmail.com

Summary
Python backend engineer building APIs on FastAPI, Docker, AWS, and PostgreSQL.

Experience
Senior Backend Engineer
Cloud Nova Systems
2022 - Present
        """
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(resume_text)
            temp_path = handle.name
        try:
            parsed = parse_resume(temp_path, "rahul_dev.txt")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertEqual(parsed["resume_type"], "technical")
        self.assertIn("header_block", parsed["layout_signals"]["layout_labels"])


if __name__ == "__main__":
    unittest.main()
