import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.layout_detection import infer_layout_signals  # noqa: E402
from ats.extraction.resume_parser import _order_pdf_segments, parse_resume_text  # noqa: E402


class ResumeLayoutAndValidationTests(unittest.TestCase):
    def test_block_ordering_keeps_left_column_before_right_column(self):
        ordered = _order_pdf_segments(
            [
                {"text": "Skills\nPython\nDocker", "x0": 340.0, "x1": 520.0, "top": 120.0},
                {"text": "Ananya Rao", "x0": 40.0, "x1": 220.0, "top": 20.0},
                {"text": "Experience\nSenior Engineer | Acme Ltd", "x0": 40.0, "x1": 250.0, "top": 90.0},
                {"text": "ananya.rao@email.com", "x0": 340.0, "x1": 520.0, "top": 10.0},
            ],
            595.0,
        )

        self.assertLess(ordered.find("Ananya Rao"), ordered.find("Skills"))
        self.assertLess(ordered.find("Experience"), ordered.find("Skills"))

    def test_sidebar_layout_is_detected(self):
        text_parts = [
            """
Priya Nair
Hyderabad, Telangana
priya.nair@email.com
+91 99887 66554
LinkedIn

TECHNICAL SKILLS
Python
FastAPI
PostgreSQL
Docker

WORK EXPERIENCE
Senior Backend Engineer | Orbit Labs | Nov 2025 - Present
Backend Engineer | Delta Systems | May 2024 - Oct 2025
            """
        ]
        page_metrics = [{"width": 595.0, "height": 842.0, "has_multi_column": True, "table_count": 0, "has_table_like_structure": False}]

        layout = infer_layout_signals(text_parts=text_parts, page_metrics=page_metrics)

        self.assertTrue(layout["is_multi_column"])
        self.assertTrue(layout["is_sidebar"])
        self.assertIn("sidebar", layout["layout_labels"])

    def test_vertical_layout_is_detected(self):
        text_parts = [
            """
Arjun Mehta
PROFILE SUMMARY
Backend engineer with 4 years of experience.
WORK EXPERIENCE
Software Engineer | Nova Labs | 2022 - Present
EDUCATION
B.Tech Computer Science
            """
        ]

        layout = infer_layout_signals(text_parts=text_parts, page_metrics=[{"width": 595.0, "height": 842.0, "has_multi_column": False, "table_count": 0, "has_table_like_structure": False}])

        self.assertTrue(layout["is_vertical"])
        self.assertFalse(layout["is_sidebar"])
        self.assertFalse(layout["is_horizontal"])

    def test_resume_without_skills_section_extracts_skills_from_experience(self):
        resume_text = """
Vaibhav Kumar
Bengaluru, Karnataka | vaibhav.kumar@gmail.com | +91 91234 56789

PROFILE SUMMARY
Backend engineer building hiring platforms.

WORK EXPERIENCE
Software Engineer | Nouveau Labs - Bangalore | Nov 2025 - Present
Worked with FastAPI and PostgreSQL to build ATS workflows.

Software Engineer | Delta Systems - Bengaluru | May 2024 - Oct 2025
Built APIs using Python and Docker.
        """

        result = extract_resume_information(resume_text)

        self.assertIn("fastapi", result["skills"])
        self.assertIn("postgresql", result["skills"])
        self.assertIn("python", result["skills"])
        self.assertNotIn("communication", result["skills"])

    def test_location_email_and_name_are_validated(self):
        resume_text = """
CONTACT
Rohit Sharma
rohit@gmail.com.linkedin.com | LinkedIn | GitHub
Hyderabad

WORK EXPERIENCE
Software Engineer | Orbit Labs | 2020 - 2023
        """

        result = parse_resume_text(resume_text)

        self.assertEqual(result["name"], "Rohit Sharma")
        self.assertEqual(result["email"], "rohit@gmail.com")
        self.assertEqual(result["location"], "Hyderabad")
        self.assertTrue(result["validation_summary"]["name_valid"])
        self.assertTrue(result["validation_summary"]["location_valid"])

    def test_name_extraction_drops_trailing_location_from_header_line(self):
        resume_text = """
Tashrif Apon Queens, NY | (929) 346-9867 | tashrifapon2001@gmail.com

WORK EXPERIENCE
Data Engineer | NYC AG, LLC | Aug 2024 - Jan 2025
Built a data mining pipeline SaaS for real estate arbitrage.
        """

        result = parse_resume_text(resume_text)

        self.assertEqual(result["name"], "Tashrif Apon")

    def test_name_label_supports_single_token_names(self):
        resume_text = """
Name: Praveen
Email: p@example.com

EXPERIENCE
Developer | ABC Ltd | 2021 - Present
        """

        result = parse_resume_text(resume_text)

        self.assertEqual(result["name"], "Praveen")

    def test_header_name_strips_portfolio_suffix_noise(self):
        resume_text = """
Akhil Portfolio | akhil@gmail.com | GitHub | Bengaluru

EXPERIENCE
Software Engineer | Acme Ltd | 2022 - Present
        """

        result = parse_resume_text(resume_text)

        self.assertEqual(result["name"], "Akhil")

    def test_multi_column_resume_keeps_experience_structure(self):
        resume_text = """
Ananya Rao
Chennai, Tamil Nadu | ananya.rao@email.com | +91 98765 43210

TECHNICAL SKILLS
React | TypeScript | Docker

WORK EXPERIENCE
Software Engineer | Nouveau Labs - Bangalore | Nov 2025 - Present
Built frontend and platform integrations.

Support Engineer | Delta Systems - Chennai | 2020 - 2023
Maintained internal hiring workflows.
        """

        result = parse_resume_text(
            resume_text,
            layout_signals={
                "is_multi_column": True,
                "is_sidebar": True,
                "is_vertical": False,
                "is_horizontal": False,
                "is_table_based": False,
                "layout_labels": ["multi_column", "sidebar"],
            },
        )

        self.assertEqual(result["experience_entries"][0]["role"], "Software Engineer")
        self.assertEqual(result["experience_entries"][0]["company"], "Nouveau Labs")
        self.assertGreaterEqual(result["total_experience_years"], 4.0)


if __name__ == "__main__":
    unittest.main()
