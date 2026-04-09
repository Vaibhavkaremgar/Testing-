import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.resume_parser import parse_resume_text  # noqa: E402


class ResumePdfRegressionTests(unittest.TestCase):
    def test_name_with_skill_descriptors_keeps_only_person_name(self):
        resume_text = """
Rahul Deshmukh
Cybersecurity Engineer | SOC Analyst | Penetration Tester
Hyderabad, Telangana | rahul.deshmukh@email.com | +91 99887 66554
        """

        result = parse_resume_text(resume_text)

        self.assertEqual(result["name"], "Rahul Deshmukh")

    def test_sidebar_resume_interleaving_keeps_all_experience_roles(self):
        resume_text = """
CONTACT DETAILS
nithinreddy502@gmail.com
+91 - 9989890734
LinkedIn
JOB OBJECTIVE
Targeting challenging opportunities in software automation testing, preferably in Bangalore or Hyderabad.
EDUCATION
CMR Engineering College, Hyderabad
TECHNICAL SKILLS
Python, Selenium, Robot Framework, Playwright
Nithin Reddy Lekkala
Python Automation Test Engineer
PROFILE SUMMARY
Possess nearly 3 years of experience in UI/API automation.
WORK EXPERIENCE
Software Engineer | Nouveau Labs - Bangalore | Nov 2025 - Present
Responsibilities:
Designed and executed automation suites.
PREVIOUS EXPERIENCE
Project Engineer | Wipro Limited - Bangalore | May 2024 - Oct 2025
Responsibilities:
Created and maintained UI automation test cases.
CERTIFICATIONS
Cisco Certified Network Associate | Cisco | 07/2023 - 07/2026
SOFT SKILLS
Communication
Software Test Engineer | Cisco - Bangalore | Dec 2022 - Dec 2023
Responsibilities:
Executed system and feature test cases.
INTERNSHIP
Automation Test Engineer Intern | Cognizant - Remote | Mar 2022 - Nov 2022
Responsibilities:
Built automation for UI workflows.
        """

        result = extract_resume_information(resume_text)

        companies = [entry.get("company") for entry in result["experience"]]
        self.assertIn("Nouveau Labs", companies)
        self.assertIn("Wipro Limited", companies)
        self.assertGreaterEqual(result["experience_years"], 2.0)
        self.assertNotEqual(result["location"], "JOB")


if __name__ == "__main__":
    unittest.main()
