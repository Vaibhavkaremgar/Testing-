import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.preprocessing.section_segmentation import get_section_content, segment_resume_sections  # noqa: E402


class SectionSegmentationTests(unittest.TestCase):
    def test_experience_stops_before_education_and_projects(self):
        resume_text = """
John Doe
Software Engineer

Professional Experience
Senior Software Engineer | ABC Corp
Jan 2020 - Mar 2022
Built APIs.

Education
Bachelor of Technology
2015 - 2019

Projects
Inventory Platform
2021 - 2022
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Senior Software Engineer", sections["experience"])
        self.assertNotIn("Bachelor of Technology", sections["experience"])
        self.assertNotIn("Inventory Platform", sections["experience"])
        self.assertIn("Bachelor of Technology", sections["education"])
        self.assertIn("Inventory Platform", sections["projects"])

    def test_inline_headers_are_segmented(self):
        resume_text = """
Summary: Backend engineer with API experience.
Technical Skills: Python, FastAPI, PostgreSQL
Work Experience: Senior Engineer at Acme Corp
Jan 2020 - Mar 2022
Education: B.Tech in Computer Science
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Backend engineer", sections["summary"])
        self.assertIn("Python", sections["skills"])
        self.assertIn("Senior Engineer at Acme Corp", sections["experience"])
        self.assertIn("B.Tech in Computer Science", sections["education"])

    def test_styled_experience_header_is_detected(self):
        resume_text = """
Alex Johnson

━━ Experience
Senior Software Engineer · Bright Software
May 2022 – Present
Bengaluru, India

Skills
Python, FastAPI, PostgreSQL
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Senior Software Engineer", sections["experience"])
        self.assertNotIn("Python", sections["experience"])
        self.assertIn("Python", sections["skills"])

    def test_internship_header_does_not_pollute_experience(self):
        resume_text = """
Internship
Software Engineering Intern | Acme Corp
Jan 2018 - Dec 2018

Professional Experience
Software Engineer | Acme Corp
2019 - 2021
Built services.
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Software Engineer | Acme Corp", sections["experience"])
        self.assertNotIn("Software Engineering Intern", sections["experience"])

    def test_unknown_boundary_header_stops_previous_known_section(self):
        resume_text = """
Work Experience
Software Engineer | Acme Corp
2019 - 2021
Built services.

Certifications
AWS Certified Developer
        """

        experience = get_section_content(resume_text, "experience")
        self.assertIn("Software Engineer | Acme Corp", experience)
        self.assertNotIn("AWS Certified Developer", experience)

    def test_header_normalization_maps_tool_stack_to_skills(self):
        resume_text = """
Riya Shah

Tool Stack
Python | Docker | AWS

Work History
Backend Engineer | Acme Corp
2022 - Present
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Python", sections["skills"])
        self.assertIn("Backend Engineer", sections["experience"])

    def test_additional_header_variants_are_isolated(self):
        resume_text = """
Priya Nair

Expertise
Python | FastAPI | Docker

Work History
Senior Backend Engineer | Acme Corp
Jan 2022 - Present

Qualification
B.Tech in Computer Science

Certificates
AWS Certified Developer
        """

        sections = segment_resume_sections(resume_text)
        self.assertIn("Python", sections["skills"])
        self.assertIn("Senior Backend Engineer", sections["experience"])
        self.assertIn("B.Tech", sections["education"])
        self.assertIn("AWS Certified Developer", sections["certifications"])
        self.assertNotIn("AWS Certified Developer", sections["experience"])


if __name__ == "__main__":
    unittest.main()
