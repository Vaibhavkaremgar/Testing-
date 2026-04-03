import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.resume_parser import parse_resume  # noqa: E402


class ResumeInformationPipelineTests(unittest.TestCase):
    def test_bullet_heavy_resume_ignores_skill_like_heading_for_current_role(self):
        resume_text = """
Jane Doe

Professional Experience
Go-to-Market Strategy
▪ Expanded enterprise adoption across new markets
Senior Product Manager at Bright Technologies Pvt Ltd
Jan 2022 - Present
▪ Led roadmap planning and cross-functional execution

Skills
SEO, Machine Learning, Product Analytics
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Senior Product Manager")
        self.assertEqual(result["current_company"], "Bright Technologies Pvt Ltd")
        self.assertGreater(result["experience_years"], 4.0)
        self.assertNotEqual(result["current_role"], "Go-to-Market Strategy")

    def test_unstructured_experience_section_still_extracts_role_and_company(self):
        resume_text = """
John Doe

Career History
Principal Data Engineer
Orbit Technologies Pvt Ltd
Jan 2021 - Present
Built hiring analytics pipelines and data products.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Principal Data Engineer")
        self.assertEqual(result["current_company"], "Orbit Technologies Pvt Ltd")
        self.assertGreater(result["experience_years"], 5.0)

    def test_missing_experience_section_returns_null_fields(self):
        resume_text = """
Alex Candidate

Summary
Machine Learning specialist with strong SEO and analytics experience.

Projects
Recommendation Engine
2021 - 2023

Skills
Python, Machine Learning, SEO
        """

        result = extract_resume_information(resume_text)

        self.assertIsNone(result["current_role"])
        self.assertIsNone(result["current_company"])
        self.assertIsNone(result["experience_years"])

    def test_parse_resume_uses_validated_current_role_and_company(self):
        resume_text = """
Taylor Candidate

Work Experience
Growth Strategy
Sales Director at Nova Systems Ltd
2019 - Present
Managed enterprise revenue operations.

Skills
Strategy, CRM, Leadership
        """

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(resume_text)
            temp_path = handle.name

        try:
            result = parse_resume(temp_path, "taylor_candidate.txt")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertEqual(result["current_role"], "Sales Director")
        self.assertEqual(result["current_company"], "Nova Systems Ltd")
        self.assertGreater(result["total_experience_years"], 6.0)
        self.assertNotEqual(result["current_role"], "Growth Strategy")

    def test_skills_are_extracted_only_from_skills_section(self):
        resume_text = """
Jordan Candidate

Professional Experience
Engineering Manager at Bright Solutions Ltd
Jan 2021 - Present
Built Python and FastAPI services for internal hiring systems.

Projects
Resume Intelligence Platform
Used React, Docker, Kubernetes, and PostgreSQL.

Skills
Leadership, Stakeholder Management, Hiring
        """

        result = extract_resume_information(resume_text)

        self.assertNotIn("python", result["skills"])
        self.assertNotIn("react", result["skills"])
        self.assertNotIn("docker", result["skills"])
        self.assertEqual(result["current_role"], "Engineering Manager")
        self.assertEqual(result["current_company"], "Bright Solutions Ltd")

    def test_multiline_role_and_company_are_not_replaced_by_responsibility_text(self):
        resume_text = """
Divya Menon
Human Resources Business Partner
Chennai, Tamil Nadu | +91 93210 45678 | divya.menon.hr@gmail.com

Work Experience
Senior HR Business Partner
Zoho Corporation Pvt. Ltd. | Chennai, Tamil Nadu
May 2021 - Present
Act as strategic HRBP for the Finance Plus division across India and APAC.

HR Business Partner
Cognizant Technology Solutions | Chennai, Tamil Nadu
Jan 2018 - Apr 2021
Served as HRBP for the Retail & Consumer Goods vertical.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Senior HR Business Partner")
        self.assertEqual(result["current_company"], "Zoho Corporation Pvt. Ltd")
        self.assertEqual(result["location"], "Chennai, Tamil Nadu")
        self.assertEqual(len(result["experience"]), 2)

    def test_inline_section_headers_do_not_pollute_location_or_current_role(self):
        resume_text = """
Ananya Krishnan Data Analyst | Business Intelligence | Visualization Hyderabad, Telangana | +91 98001 23456 | ananya.krishnan@outlook.com
PROFILE Data Analyst with 5 years of experience turning complex datasets into insights.
WORK EXPERIENCE Senior Data Analyst Meesho Pvt. Ltd. | Jun 2022 - Present Bengaluru, Karnataka Built reporting dashboards.
Data Analyst Delhivery Ltd. | Jan 2020 - May 2022 Gurugram, Haryana Built logistics reporting.
TECHNICAL SKILLS SQL | Python | Power BI | Tableau | Mixpanel | Git
Languages: English (Fluent) Tamil (Native) Telugu (Conversational) Hindi (Working)
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["location"], "Hyderabad, Telangana")
        self.assertEqual(result["current_role"], "Senior Data Analyst")
        self.assertEqual(result["current_company"], "Meesho Pvt. Ltd.")
        self.assertIn("sql", result["skills"])
        self.assertIn("python", result["skills"])
        self.assertIn("English", result["languages"])


if __name__ == "__main__":
    unittest.main()
