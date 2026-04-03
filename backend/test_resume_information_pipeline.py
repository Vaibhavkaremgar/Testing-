import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.resume_parser import parse_resume  # noqa: E402


class ResumeInformationPipelineTests(unittest.TestCase):
    def _parse_resume_text(self, resume_text: str, filename: str = "resume.txt"):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(resume_text)
            temp_path = handle.name
        try:
            return parse_resume(temp_path, filename)
        finally:
            Path(temp_path).unlink(missing_ok=True)

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

    def test_parse_resume_prefers_header_name_over_email_local_part(self):
        resume_text = """
Priyanka Nair Senior Data Analyst | Hyderabad, Telangana | +91 99887 66554 | talent.pool1989@outlook.com
PROFILE Data analyst with 5 years of experience building hiring dashboards.
WORK EXPERIENCE Senior Data Analyst Meesho Pvt. Ltd. | Jun 2022 - Present Bengaluru, Karnataka Built reporting dashboards.
TECHNICAL SKILLS SQL | Python | Power BI | Tableau
        """

        result = self._parse_resume_text(resume_text, "talent_pool1989_resume.txt")

        self.assertEqual(result["name"], "Priyanka Nair")
        self.assertNotEqual(result["name"], "Talent Pool")

    def test_technical_skills_section_keeps_real_skills_and_drops_noise(self):
        resume_text = """
Karan Shah

Technical Skills
Programming Languages: Python | SQL | Java
Frameworks: FastAPI | React
Tools and Technologies: Docker | AWS | Git
Core Skills: Communication | Leadership | Teamwork
        """

        result = extract_resume_information(resume_text)

        self.assertIn("python", result["skills"])
        self.assertIn("sql", result["skills"])
        self.assertIn("fastapi", result["skills"])
        self.assertIn("docker", result["skills"])
        self.assertNotIn("communication", result["skills"])
        self.assertNotIn("leadership", result["skills"])
        self.assertNotIn("teamwork", result["skills"])

    def test_explicit_total_experience_pattern_is_used_when_present(self):
        resume_text = """
Rahul Menon

Professional Summary
Backend engineer with 5 years and 6 months of experience building APIs and distributed systems.

Skills
Python, FastAPI, PostgreSQL, Docker
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["experience_years"], 5.5)
        self.assertEqual(result["total_experience_years"], 5.5)

    def test_latest_experience_entry_drives_current_role_and_company(self):
        resume_text = """
Rakesh Kumar

Profile
Regional sales leader with 10 years of experience.

Work Experience
Senior Sales Manager
Growth Enterprises Pvt Ltd
2018 - Present
Led enterprise and government sales across assigned territory.

Senior Sales Executive
Prime Marketing Services
2016 - 2018
Managed retail and walk-in lead conversion.

Sales Executive
Prime Marketing Services
2012 - 2014
Worked in field sales and door to door sales.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Senior Sales Manager")
        self.assertEqual(result["current_company"], "Growth Enterprises Pvt Ltd")
        self.assertGreaterEqual(result["experience_years"], 8.0)

    def test_skill_section_ignores_dates_roles_and_communication_noise(self):
        resume_text = """
Vikram Patel

Skills
b2g
pipeline mgmt
closing
forecasting
territory mgmt
cold calling
pipeline
prospecting
deal closing
retention
cross sell
business development
growth enterprises
2016 - 2018
product demos
closing deals
senior sales executive
retail
2014 - 2016
walk-in leads
sales executive
prime marketing services
2012 - 2014
worked in field sales
door to door sales
salesforce
hubspot
zoho
pipedrive
communication: email
whatsapp
meet
teams
short
sales
account mgmt
        """

        result = extract_resume_information(resume_text)

        self.assertIn("b2g sales", result["skills"])
        self.assertIn("pipeline management", result["skills"])
        self.assertIn("forecasting", result["skills"])
        self.assertIn("territory management", result["skills"])
        self.assertIn("cold calling", result["skills"])
        self.assertIn("prospecting", result["skills"])
        self.assertIn("deal closing", result["skills"])
        self.assertIn("retention", result["skills"])
        self.assertIn("cross-selling", result["skills"])
        self.assertIn("business development", result["skills"])
        self.assertIn("product demos", result["skills"])
        self.assertIn("salesforce", result["skills"])
        self.assertIn("hubspot", result["skills"])
        self.assertIn("zoho crm", result["skills"])
        self.assertIn("pipedrive", result["skills"])
        self.assertIn("account management", result["skills"])
        self.assertNotIn("2016 - 2018", result["skills"])
        self.assertNotIn("growth enterprises", result["skills"])
        self.assertNotIn("senior sales executive", result["skills"])
        self.assertNotIn("prime marketing services", result["skills"])
        self.assertNotIn("email", result["skills"])
        self.assertNotIn("whatsapp", result["skills"])
        self.assertNotIn("meet", result["skills"])
        self.assertNotIn("teams", result["skills"])
        self.assertNotIn("short", result["skills"])
        self.assertNotIn("sales", result["skills"])

    def test_header_name_and_skills_are_extracted_from_ananya_style_header(self):
        resume_text = """
Ananya Krishnan Data Analyst | Business Intelligence | Visualization Hyderabad, Telangana | +91 98001 23456 | ananya.krishnan@outlook.com
PROFILE Data Analyst with 5 years of experience turning complex datasets into insights.
WORK EXPERIENCE Senior Data Analyst Meesho Pvt. Ltd. | Jun 2022 - Present Bengaluru, Karnataka Built reporting dashboards.
Data Analyst Delhivery Ltd. | Jan 2020 - May 2022 Gurugram, Haryana Built logistics reporting.
TECHNICAL SKILLS Languages & Querying SQL (Advanced) Python (pandas, numpy) | R (ggplot2, dplyr) DAX / M Query | Bash scripting BI & Visualization Power BI Tableau | Looker / LookML Google Data Studio | Metabase Matplotlib / Seaborn Data Platforms & Tools Google BigQuery AWS Redshift Snowflake | Apache Airflow dbt (data build tool) Excel / Google Sheets | Mixpanel Amplitude Git
        """

        parsed = self._parse_resume_text(resume_text, "R1_Ananya_Krishnan_DataAnalyst.docx")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["name"], "Ananya Krishnan")
        self.assertEqual(result["location"], "Hyderabad, Telangana")
        self.assertIn("sql", result["skills"])
        self.assertIn("python", result["skills"])
        self.assertIn("power bi", result["skills"])
        self.assertIn("tableau", result["skills"])
        self.assertIn("mixpanel", result["skills"])
        self.assertIn("git", result["skills"])
        self.assertNotEqual(parsed["name"], "Business Intelligence")

    def test_location_is_blank_when_not_in_header(self):
        resume_text = """
Bhimaraju Kowshik
bhimaraju.kowshik@gmail.com | +91 8106148797

Professional Summary
QA Automation Engineer with 4.2 years of experience in Java, Selenium WebDriver and API testing.

Skills
rest assured
java
sql
testng
cucumber
apache maven
gcp
accelq
stibo
postman
soap

Experience
QA Automation Engineer
Cognizant Technology Solutions
Dec-2022 to Present
Using JIRA, Maven while continuously improving regression suites.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["location"], "")
        self.assertGreaterEqual(result["experience_years"], 2.0)

    def test_month_based_experience_ranges_are_counted(self):
        resume_text = """
Deepak Sharma

Work Experience
QA Automation Engineer
Cognizant Technology Solutions
Dec-2022 to Present
Built automation for API and UI workflows.

QEA Intern
Acme Labs
Jun-2022 to Nov-2022
Supported test automation execution.
        """

        result = extract_resume_information(resume_text)

        self.assertGreaterEqual(result["experience_years"], 3.0)
        self.assertEqual(result["current_role"], "QA Automation Engineer")
        self.assertEqual(result["current_company"], "Cognizant Technology Solutions")

    def test_teacher_resume_extracts_role_company_location_and_skills(self):
        resume_text = """
Anita Sharma
Bengaluru, Karnataka | +91 98765 43210 | anita.sharma@email.com

Work Experience
Senior Mathematics Teacher
Green Valley Public School
Jun-2021 to Present
Led grade 9 and 10 mathematics curriculum planning, student assessment, and parent communication.

Mathematics Teacher
Sunrise High School
Apr-2017 to May-2021
Managed classroom instruction and lesson planning for secondary students.

Skills
Classroom Management
Lesson Planning
Curriculum Development
Student Assessment
Parent Communication
Pedagogy
Online Teaching
        """

        result = extract_resume_information(resume_text)
        parsed = self._parse_resume_text(resume_text, "anita_teacher.txt")

        self.assertEqual(parsed["name"], "Anita Sharma")
        self.assertEqual(result["location"], "Bengaluru, Karnataka")
        self.assertEqual(result["current_role"], "Senior Mathematics Teacher")
        self.assertEqual(result["current_company"], "Green Valley Public School")
        self.assertIn("classroom management", result["skills"])
        self.assertIn("lesson planning", result["skills"])
        self.assertIn("student assessment", result["skills"])
        self.assertIn("pedagogy", result["skills"])


if __name__ == "__main__":
    unittest.main()
