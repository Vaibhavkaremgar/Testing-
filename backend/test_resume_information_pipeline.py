import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.resume_parser import extract_document, extract_text, parse_resume, run_ocr  # noqa: E402
from app.routes.candidates import resolve_current_company_for_storage, resolve_current_role_for_storage  # noqa: E402


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

    def test_summary_and_project_dates_do_not_backfill_experience(self):
        resume_text = """
Alex Candidate

Summary
5 years of experience building candidate pipelines.

Projects
Hiring Platform
Jan 2021 - Mar 2023
Built internal automation.

Skills
Python, FastAPI, SQL
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["experience"], [])
        self.assertIsNone(result["current_role"])
        self.assertIsNone(result["current_company"])
        self.assertIsNone(result["total_experience_years"])

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

    def test_parse_resume_includes_bottleneck_debug_fields(self):
        resume_text = """
Taylor Candidate

Work Experience
Sales Director at Nova Systems Ltd
2019 - Present
Managed enterprise revenue operations.
        """

        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as handle:
            handle.write(resume_text)
            temp_path = handle.name

        try:
            result = parse_resume(temp_path, "timed_resume.txt")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertIn("bottleneck_stage", result["debug_timings"])
        self.assertIn("bottleneck_time_ms", result["debug_timings"])
        self.assertIn("bottleneck_exceeds_threshold", result["debug_timings"])
        self.assertIn("extraction_method", result)

    def test_current_company_for_storage_uses_latest_valid_experience_company(self):
        work_experience = [
            {"company": "Acme Organization", "title": "Senior Teacher"},
            {"company": "Old School Ltd", "title": "Teacher"},
        ]
        experience_text = """
Senior Teacher | Acme Organization | Jan 2024 - Present
Teacher | Old School Ltd | Jun 2020 - Dec 2023
        """

        resolved = resolve_current_company_for_storage(work_experience, "Random Narrative Text", experience_text)

        self.assertEqual(resolved, "Acme Organization")

    def test_current_company_for_storage_rejects_non_text_or_invalid_values(self):
        work_experience = [
            {"company": {"name": "Acme Organization"}, "title": "Senior Teacher"},
            {"company": "managed school operations across regions", "title": "Teacher"},
        ]
        experience_text = """
Senior Teacher | Acme Organization | Jan 2024 - Present
Teacher | Old School Ltd | Jun 2020 - Dec 2023
        """

        resolved = resolve_current_company_for_storage(work_experience, {"name": "bad"}, experience_text)

        self.assertIsNone(resolved)

    def test_current_role_for_storage_uses_latest_valid_experience_role(self):
        work_experience = [
            {"company": "Acme Organization", "title": "Senior Teacher"},
            {"company": "Old School Ltd", "title": "Teacher"},
        ]

        resolved = resolve_current_role_for_storage(work_experience, "Narrative text", ["pedagogy"])

        self.assertEqual(resolved, "Senior Teacher")

    def test_current_role_for_storage_rejects_invalid_values(self):
        work_experience = [
            {"company": "Acme Organization", "title": {"name": "bad"}},
            {"company": "Old School Ltd", "title": "communication"},
        ]

        resolved = resolve_current_role_for_storage(work_experience, {"name": "bad"}, ["communication"])

        self.assertIsNone(resolved)

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

    @patch("ats.extraction.resume_parser._run_ocr_internal")
    def test_run_ocr_times_out_after_five_seconds(self, mock_run_ocr_internal):
        def delayed_ocr(_file_path):
            import time
            time.sleep(0.05)
            return ["late text"]

        mock_run_ocr_internal.side_effect = delayed_ocr

        parts, timed_out = run_ocr("resume.pdf", timeout_seconds=0.01)

        self.assertEqual(parts, [])
        self.assertTrue(timed_out)

    def test_missing_skills_section_does_not_promote_project_technologies(self):
        resume_text = """
Jordan Candidate

Professional Experience
Engineering Manager at Bright Solutions Ltd
Jan 2021 - Present
Built Python and FastAPI services for internal hiring systems.

Projects
Resume Intelligence Platform
Used React, Docker, Kubernetes, and PostgreSQL.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["skills"], [])

    def test_parse_resume_low_confidence_retry_keeps_skills_empty_without_skills_section(self):
        resume_text = """
Jordan Candidate

Professional Experience
Engineering Manager at Bright Solutions Ltd
Jan 2021 - Present
Built Python and FastAPI services for internal hiring systems.

Projects
Resume Intelligence Platform
Used React, Docker, Kubernetes, and PostgreSQL.
        """

        result = self._parse_resume_text(resume_text, "jordan_candidate.txt")

        self.assertEqual(result["skills"], [])

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
        self.assertEqual(result["current_company"], "Meesho Pvt. Ltd")
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

    def test_parse_resume_rejects_company_name_as_candidate_name(self):
        resume_text = """
COGNIZANT TECHNOLOGY SOLUTIONS
Senior Software Engineer
Hyderabad, Telangana | +91 99887 66554 | engineer@example.com

Work Experience
Senior Software Engineer | Cognizant Technology Solutions
Jan 2022 - Present
Built hiring workflow APIs.
        """

        result = self._parse_resume_text(resume_text, "cognizant_resume.txt")

        self.assertIsNone(result["name"])
        self.assertEqual(result["current_company"], "Cognizant Technology Solutions")

    def test_parse_resume_extracts_uppercase_header_name_without_company_fallback(self):
        resume_text = """
A K REDDY
Lead QA Engineer
Chennai, Tamil Nadu | +91 98765 43210 | ak.reddy@example.com

Professional Experience
Lead QA Engineer | Nova Systems Ltd
Jan 2021 - Present
Led automation initiatives across release trains.
        """

        result = self._parse_resume_text(resume_text, "ak_reddy_resume.txt")

        self.assertEqual(result["name"], "A K Reddy")
        self.assertEqual(result["current_company"], "Nova Systems Ltd")

    def test_first_line_name_and_third_line_role_are_extracted_separately(self):
        resume_text = """
John Doe
john.doe@example.com | +91 99887 66554
Senior QA Automation Engineer

Work Experience
QA Automation Engineer
Acme Systems Ltd
Dec 2022 - Present
        """

        parsed = self._parse_resume_text(resume_text, "john_doe.txt")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["name"], "John Doe")
        self.assertEqual(result["current_role"], "QA Automation Engineer")
        self.assertEqual(result["header_role"], "Senior QA Automation Engineer")

    def test_first_line_name_with_attached_role_is_split(self):
        resume_text = """
John Doe Senior Developer
john.doe@example.com | +91 99887 66554
Hyderabad, Telangana

Work Experience
Senior Developer
Acme Systems Ltd
Jan 2023 - Current
        """

        parsed = self._parse_resume_text(resume_text, "john_doe_senior_dev.txt")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["name"], "John Doe")
        self.assertEqual(parsed["current_role"], "Senior Developer")
        self.assertEqual(result["current_role"], "Senior Developer")

    def test_first_line_name_with_parenthesized_role_is_split(self):
        resume_text = """
John Doe (Senior QA Engineer)
john.doe@example.com | +91 99887 66554
Hyderabad, Telangana

Work Experience
Senior QA Engineer
Acme Systems Ltd
Jan 2023 - Current
        """

        parsed = self._parse_resume_text(resume_text, "john_doe_parenthesized_role.txt")

        self.assertEqual(parsed["name"], "John Doe")
        self.assertEqual(parsed["current_role"], "Senior QA Engineer")

    def test_present_and_current_month_ranges_calculate_experience(self):
        resume_text = """
Rahul Sharma
rahul.sharma@example.com | +91 99887 66554
Backend Engineer

Work Experience
Backend Engineer
Acme Systems Ltd
Dec 2022 - Present

Software Engineer
Nova Labs
Jan 2023 - Current
        """

        parsed = self._parse_resume_text(resume_text, "rahul_sharma.txt")

        self.assertGreater(parsed["total_experience_years"], 2.0)
        self.assertEqual(len(parsed["experience"]), 2)

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

    def test_summary_total_experience_does_not_override_missing_experience_section(self):
        resume_text = """
Rahul Menon

Professional Summary
Backend engineer with 5 years and 6 months of experience building APIs and distributed systems.

Skills
Python, FastAPI, PostgreSQL, Docker
        """

        result = extract_resume_information(resume_text)

        self.assertIsNone(result["experience_years"])
        self.assertIsNone(result["total_experience_years"])

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

    def test_collapsed_header_line_is_normalized_before_field_extraction(self):
        resume_text = """
Anita Sharma Bengaluru, Karnataka | +91 98765 43210 | anita.sharma@email.com
WORK EXPERIENCE
Senior Mathematics Teacher
Green Valley Public School
Jun-2021 to Present
Led grade 9 and 10 mathematics curriculum planning and student assessment.

SKILLS
Classroom Management | Lesson Planning | Pedagogy
        """

        result = extract_resume_information(resume_text)
        parsed = self._parse_resume_text(resume_text, "anita_teacher_collapsed_header.txt")

        self.assertEqual(parsed["name"], "Anita Sharma")
        self.assertEqual(result["location"], "Bengaluru, Karnataka")
        self.assertEqual(result["current_role"], "Senior Mathematics Teacher")
        self.assertEqual(result["current_company"], "Green Valley Public School")

    def test_parse_resume_does_not_take_email_from_body_text(self):
        resume_text = """
Ravi Kumar
Hyderabad, Telangana

Summary
Backend engineer with strong API experience.

Projects
Hiring Platform
Contact references at recruiter.team@agency.com for project validation.
        """

        result = self._parse_resume_text(resume_text, "ravi_kumar.txt")

        self.assertEqual(result["name"], "Ravi Kumar")
        self.assertEqual(result["email"], "")

    def test_parse_resume_does_not_take_phone_from_body_text(self):
        resume_text = """
Meera Nair
Bengaluru, Karnataka

Professional Summary
Delivery manager with global stakeholder experience.

Experience
Program Manager
Bright Systems Ltd
2021 - Present
Managed an escalation queue and vendor support line 1800 555 1111.
        """

        result = self._parse_resume_text(resume_text, "meera_nair.txt")

        self.assertEqual(result["name"], "Meera Nair")
        self.assertEqual(result["phone"], "")

    def test_email_extraction_stops_before_linkedin_domain_noise(self):
        resume_text = "Vaibhav Sharma | vaibhav@gmail.com.linkedin.com | Hyderabad, Telangana"

        parsed = self._parse_resume_text(resume_text, "vaibhav.txt")

        self.assertEqual(parsed["email"], "vaibhav@gmail.com")

    def test_missing_skills_section_keeps_skill_list_empty_even_if_mentioned_elsewhere(self):
        resume_text = """
Maya Thomas
Austin, Texas | maya.thomas.engineer@gmail.com

Work Experience
Principal Backend Engineer
Acme Cloud Systems
2023 - Present
Worked on FastAPI and PostgreSQL services deployed on AWS with Docker.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["skills"], [])

    def test_locations_and_soft_skills_are_filtered_from_skills(self):
        resume_text = """
Rahul Verma
Chennai, Tamil Nadu | +91 9876543210 | rahul.verma@email.com

Skills
Python
FastAPI
Communication
Leadership
Motivated
Hyderabad
Bangalore
Teamwork
        """

        result = extract_resume_information(resume_text)

        self.assertIn("python", result["skills"])
        self.assertIn("fastapi", result["skills"])
        self.assertNotIn("communication", result["skills"])
        self.assertNotIn("leadership", result["skills"])
        self.assertNotIn("motivated", result["skills"])
        self.assertNotIn("hyderabad", result["skills"])
        self.assertNotIn("bangalore", result["skills"])

    def test_pdf_ocr_fallback_is_used_when_native_extraction_is_empty(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        ocr_text = "\n".join(
            [
                "Ravi Kumar",
                "Hyderabad, Telangana | +91 99887 66554 | ravi.kumar@email.com",
                "WORK EXPERIENCE",
                "Backend Engineer",
                "Acme Systems Ltd",
                "Jan 2022 - Present",
            ]
        )

        try:
            with patch("ats.extraction.resume_parser.pdfplumber.open", side_effect=Exception("no text layer")), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[ocr_text]):
                extracted = extract_text(temp_path)
                parsed = parse_resume(temp_path, "ravi_kumar.pdf")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertIn("Ravi Kumar", extracted)
        self.assertEqual(parsed["name"], "Ravi Kumar")
        self.assertEqual(parsed["email"], "ravi.kumar@email.com")
        self.assertEqual(parsed["phone"], "+91 99887 66554")
        self.assertEqual(parsed["location"], "Hyderabad, Telangana")

    def test_pdf_parser_selection_prefers_higher_quality_output(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        pymupdf_text = [
            "\n".join(
                [
                    "Ritika Sharma",
                    "Bengaluru, Karnataka | +91 90123 45678 | ritika.sharma@email.com",
                    "WORK EXPERIENCE",
                    "Training Coordinator",
                    "Bright Academy",
                    "2021 - Present",
                ]
            )
        ]
        noisy_text = ["ri tika sha rma bright aca demy 2021 pre sent"]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=(pymupdf_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=(noisy_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[]):
                extracted = extract_text(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertIn("Ritika Sharma", extracted)
        self.assertIn("Bright Academy", extracted)
        self.assertNotIn("ri tika sha rma", extracted)

    def test_pdf_parser_falls_back_when_header_contact_block_is_delayed(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        pymupdf_text = [
            "\n".join(
                [
                    "SUMMARY",
                    "Dec 2022 - Present",
                    "Cognizant Technology Solutions, Hyderabad",
                    "Built automation coverage across UI and APIs.",
                    "BHIMARAJU KOWSHIK",
                    "Hyderabad | +91 8106148797 | bhimaraju.kowshik@gmail.com",
                    "QA AUTOMATION ENGINEER",
                ]
            )
        ]
        pdfplumber_text = [
            "\n".join(
                [
                    "BHIMARAJU KOWSHIK",
                    "QA AUTOMATION ENGINEER",
                    "Hyderabad | +91 8106148797 | bhimaraju.kowshik@gmail.com",
                    "PROFESSIONAL EXPERIENCE",
                    "Cognizant Technology Solutions, Hyderabad",
                    "Dec 2022 - Present",
                    "QA Automation Engineer",
                ]
            )
        ]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=(pymupdf_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=(pdfplumber_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[]):
                parsed = parse_resume(temp_path, "bhimaraju_kowshik.pdf")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertEqual(parsed["name"], "Bhimaraju Kowshik")
        self.assertEqual(parsed["email"], "bhimaraju.kowshik@gmail.com")

    def test_pdf_parser_selection_breaks_ties_in_favor_of_pymupdf(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        shared_text = [
            "\n".join(
                [
                    "Karan Shah",
                    "Pune, Maharashtra | +91 98989 12121 | karan.shah@email.com",
                    "WORK EXPERIENCE",
                    "Senior Engineer",
                    "Nova Systems",
                    "2022 - Present",
                ]
            )
        ]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=(shared_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=(shared_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[]), \
                 patch("ats.extraction.resume_parser.logger.info") as logger_info:
                extract_text(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        selected_parser = logger_info.call_args[0][0] if logger_info.call_args else ""
        self.assertIn("Selected PDF parser '%s'", selected_parser)
        self.assertEqual(logger_info.call_args[0][1], "pymupdf")

    def test_pdf_ocr_replaces_native_text_when_quality_is_better(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        native_text = ["ravi kum ar hyd erabad back end engi neer 2022 pre sent"]
        ocr_text = [
            "\n".join(
                [
                    "Ravi Kumar",
                    "Hyderabad, Telangana | +91 99887 66554 | ravi.kumar@email.com",
                    "WORK EXPERIENCE",
                    "Backend Engineer",
                    "Acme Systems Ltd",
                    "Jan 2022 - Present",
                ]
            )
        ]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=(native_text, [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=([], [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=ocr_text):
                extracted = extract_text(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertIn("Ravi Kumar", extracted)
        self.assertIn("Acme Systems Ltd", extracted)
        self.assertNotIn("ravi kum ar", extracted)

    def test_image_resume_uses_ocr_extraction(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".png", delete=False) as handle:
            handle.write(b"fake-image")
            temp_path = handle.name

        ocr_text = "\n".join(
            [
                "Sneha Iyer",
                "Chennai, Tamil Nadu | +91 90111 22334 | sneha.iyer@email.com",
                "WORK EXPERIENCE",
                "QA Engineer",
                "Acme Testing Labs",
                "2023 - Present",
            ]
        )

        try:
            with patch("ats.extraction.resume_parser._extract_image_text_via_ocr", return_value=[ocr_text]):
                extracted = extract_text(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertIn("Sneha Iyer", extracted)
        self.assertIn("Acme Testing Labs", extracted)

    def test_extract_document_reports_multi_column_and_table_layout(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        parser_text = [
            "\n".join(
                [
                    "Ananya Krishnan",
                    "Hyderabad, Telangana | +91 98001 23456 | ananya.krishnan@outlook.com",
                    "TECHNICAL SKILLS | SQL | Python | Power BI",
                ]
            )
        ]
        page_metrics = [
            {
                "width": 612.0,
                "height": 792.0,
                "has_multi_column": True,
                "table_count": 1,
                "has_table_like_structure": True,
            }
        ]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=([], [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=(parser_text, page_metrics)), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pypdf", return_value=([], [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[]):
                document = extract_document(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertTrue(document["layout"]["is_multi_column"])
        self.assertTrue(document["layout"]["is_table_based"])
        self.assertIn("multi_column", document["layout"]["layout_labels"])
        self.assertIn("table_based", document["layout"]["layout_labels"])

    def test_parse_resume_reports_horizontal_layout_signal(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as handle:
            handle.write(b"")
            temp_path = handle.name

        parser_text = [
            "\n".join(
                [
                    "Maya Thomas",
                    "Austin, Texas | maya.thomas.engineer@gmail.com",
                    "Principal Backend Engineer at Acme Cloud Systems",
                    "2023 - Present",
                ]
            )
        ]
        page_metrics = [
            {
                "width": 1000.0,
                "height": 700.0,
                "has_multi_column": False,
                "table_count": 0,
                "has_table_like_structure": False,
            }
        ]

        try:
            with patch("ats.extraction.resume_parser._extract_pdf_text_with_pymupdf", return_value=(parser_text, page_metrics)), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pdfplumber", return_value=([], [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_with_pypdf", return_value=([], [])), \
                 patch("ats.extraction.resume_parser._extract_pdf_text_via_ocr", return_value=[]):
                parsed = parse_resume(temp_path, "maya_thomas.pdf")
        finally:
            Path(temp_path).unlink(missing_ok=True)

        self.assertTrue(parsed["layout_signals"]["is_horizontal"])
        self.assertIn("horizontal", parsed["layout_signals"]["layout_labels"])

    def test_name_falls_back_beyond_contact_block_and_skills_ignore_noise_lines(self):
        resume_text = """
CONTACT DETAILS
nithinreddy502@gmail.com
+91 - 9989890734
LinkedIn

JOB OBJECTIVE
Targeting challenging opportunities in software automation testing.

TECHNICAL SKILLS
Programming: C, Python, Core Java, SQL, TypeScript
Automation / Frameworks: Selenium WebDriver, Robot Framework, PyTest, Playwright, Postman, RestAssured, JMeter, PYATS
Networking & Protocols: Cisco Switching & Routing, TCP/IP, OSPF, EIGRP, VLAN, STP, BGP, ACLs, HSRP
DevOps Tools: Docker, Jenkins
Nithin Reddy Lekkala
Python Automation Test Engineer

PROFILE SUMMARY
Possess nearly 3 years of experience in UI/API automation.

WORK EXPERIENCE
Software Engineer | Nouveau Labs - Bangalore | Nov 2025 - Present
        """

        result = extract_resume_information(resume_text)
        parsed = self._parse_resume_text(resume_text, "nithin_reddy_software_test_engineer.txt")

        self.assertEqual(parsed["name"], "Nithin Reddy Lekkala")
        self.assertIn("python", result["skills"])
        self.assertIn("java", result["skills"])
        self.assertIn("selenium webdriver", result["skills"])
        self.assertIn("robot framework", result["skills"])
        self.assertIn("rest assured", result["skills"])
        self.assertIn("docker", result["skills"])
        self.assertNotIn("contact details", result["skills"])
        self.assertNotIn("nithin reddy lekkala", result["skills"])
        self.assertNotIn("python automation test engineer", result["skills"])
        self.assertNotIn("communication", result["skills"])
        self.assertNotIn("analytical", result["skills"])

    def test_section_variants_drive_education_languages_and_certifications(self):
        resume_text = """
Nisha Verma
Pune, Maharashtra | +91 98765 11111 | nisha.verma@email.com

Profile
Worked with English-speaking customers and global teams across multiple programs.

Academic Qualifications
Master of Business Administration
St. Joseph's College
2020

Professional Certifications
AWS Certified Cloud Practitioner
Scrum Master Certification

Language Proficiency
English | Hindi
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["education"][0]["degree"], "Master of Business Administration")
        self.assertEqual(result["education"][0]["institution"], "St. Joseph's College")
        self.assertIn({"name": "AWS Certified Cloud Practitioner"}, result["certifications"])
        self.assertIn({"name": "Scrum Master Certification"}, result["certifications"])
        self.assertEqual(result["languages"], ["English", "Hindi"])

    def test_languages_are_not_extracted_from_summary_without_language_zone(self):
        resume_text = """
Arjun Menon
Chennai, Tamil Nadu | +91 90000 11111 | arjun.menon@email.com

Summary
Worked with English-speaking enterprise customers across India and APAC.

Skills
Python | SQL | FastAPI
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["languages"], [])

    def test_education_is_taken_only_from_education_section(self):
        resume_text = """
Ritika Sharma
Bengaluru, Karnataka | +91 90123 45678 | ritika.sharma@email.com

Experience
Training Coordinator
Bright Academy
2021 - Present
Conducted university outreach and college onboarding programs.

Education
B.Com
Delhi University
2019
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(len(result["education"]), 1)
        self.assertEqual(result["education"][0]["institution"], "Delhi University")
        self.assertNotEqual(result["current_company"], "Delhi University")

    def test_attached_summary_header_does_not_pollute_location(self):
        resume_text = """
PAINOORI RANGANATH
QA AUTOMATION ENGINEER
Hyderabad | +91 9704256023 | pranganath.pr@gmail.com | SUMMARY
QA Automation Engineer with 3+ years of hands-on experience in developing and maintaining automated test scripts.
TECHNICAL SKILLS
Automation Tools: Selenium WebDriver
Languages & Frameworks: Java, TestNG, Maven
        """

        parsed = self._parse_resume_text(resume_text, "ranganath.txt")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["location"], "Hyderabad")
        self.assertEqual(result["location"], "Hyderabad")

    def test_fragmented_sap_resume_still_extracts_contact_and_sap_skills(self):
        resume_text = """
RESUME
RUDRAVARAM NARE SH SAI ANEESH
Contact: +91 8977816703
Email Id: aneeshrudravaram@gma il.com
CAREER OBJECTIVE
An Electronics and Communication professional seeking chal lenging o ppurtunities.
CERTIFICATIONS
SAP Certified Application Associate - Extended Warehouse Management in SAP S4/HANA
SKILLS
SAP Extended Wareho use Management
SAP ECC integrations with Extended
Warehouse Management module
WORK EXPERIENCE
1) SAP EWM CON SU LTANT in COGNIZ ANT ( S eptember 2022 - Present)
        """

        parsed = self._parse_resume_text(resume_text, "aneesh.txt")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["email"], "aneeshrudravaram@gmail.com")
        self.assertIn("sap extended warehouse management", result["skills"])
        self.assertIn("sap ecc", result["skills"])

    def test_labeled_header_name_is_extracted(self):
        resume_text = """
Name: Rahul Verma
Location: Bangalore / Hyderabad / Remote
Email: rahul.verma.ai.dev@gmail.com
Phone: +91 9876543210

Work Experience
Senior ML Engineer
AI Labs Pvt Ltd
2022 - Present
        """

        parsed = self._parse_resume_text(resume_text, "unknown_candidate.txt")

        self.assertEqual(parsed["name"], "Rahul Verma")

    def test_company_is_extracted_from_role_in_all_caps_org_line(self):
        resume_text = """
Rudravaram Nareshsai Aneesh
+91 8977816703 | aneeshrudravaram@gmail.com

Work Experience
SAP EWM CONSULTANT in COGNIZANT (September 2022 - Present)
Handled logistics execution support.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_company"], "COGNIZANT")

    def test_tools_section_and_full_text_fallback_extract_skills_for_unstructured_resume(self):
        resume_text = """
Maya Thomas
Austin, Texas
maya.thomas.engineer@
gmail.com

Principal Backend Engineer at Acme Cloud Systems
2023/01 - Present
Building Python and FastAPI services on AWS with Docker and PostgreSQL.

Tool Stack
Docker | AWS | GitHub Actions | Terraform
        """

        parsed = self._parse_resume_text(resume_text, "maya_thomas.txt")
        result = extract_resume_information(resume_text)

        self.assertEqual(parsed["email"], "maya.thomas.engineer@gmail.com")
        self.assertEqual(result["current_role"], "Principal Backend Engineer")
        self.assertEqual(result["current_company"], "Acme Cloud Systems")
        self.assertIn("docker", result["skills"])
        self.assertIn("aws", result["skills"])

    def test_unstructured_resume_without_sections_still_extracts_latest_role_company_location_and_education(self):
        resume_text = """
Neha Kapoor
Seattle, Washington | neha.kapoor.data@gmail.com

Lead Data Engineer | Northwind Technologies
2021-03 - Present
Built hiring analytics pipelines and warehouse automation using Python, Airflow, and Snowflake.

Senior Data Engineer | Blue River Labs
07/2018 - 02/2021
Designed ETL systems for enterprise reporting.

Bachelor of Technology
National Institute of Technology
2018
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Lead Data Engineer")
        self.assertEqual(result["current_company"], "Northwind Technologies")
        self.assertEqual(result["location"], "Seattle, Washington")
        self.assertEqual(result["education"], [])
        self.assertEqual(result["skills"], [])

    def test_spacy_person_name_fallback_handles_non_header_name_line(self):
        resume_text = """
CONTACT DETAILS
abhishek.verma.dev@gmail.com
+1 (425) 555-0123

Professional Snapshot
Abhishek Verma is a senior backend engineer focused on distributed systems and hiring platforms.

Experience
Senior Backend Engineer | Delta Systems
Jan 2024 - Present
        """

        parsed = self._parse_resume_text(resume_text, "candidate_profile.txt")

        self.assertEqual(parsed["name"], "Abhishek Verma")

    def test_comma_broken_email_is_normalized(self):
        resume_text = """
Rahul Candidate
Email: rahul.dev@gm,ail.com
Phone: +91 9876543210
        """

        parsed = self._parse_resume_text(resume_text, "rahul_candidate.txt")

        self.assertEqual(parsed["email"], "rahul.dev@gmail.com")

    def test_email_with_multiple_dots_before_at_is_not_truncated(self):
        resume_text = """
Shriya Bose
shriya.bose.design@gmail.com
        """

        parsed = self._parse_resume_text(resume_text, "shriya_candidate.txt")

        self.assertEqual(parsed["email"], "shriya.bose.design@gmail.com")

    def test_email_with_name_line_between_local_and_domain_is_recovered(self):
        resume_text = """
Email Id: aneeshrudravaram@
RUDRAVARAM NARESH SAI ANEESH
gmail.com
        """

        parsed = self._parse_resume_text(resume_text, "aneesh_candidate.txt")

        self.assertEqual(parsed["email"], "aneeshrudravaram@gmail.com")

    def test_email_with_domain_split_across_newline_is_recovered(self):
        resume_text = """
Rudravaram Naresh Sai
Aneesh
(+91) 8977816703 aneeshrudravaram@gma
il.com
        """

        parsed = self._parse_resume_text(resume_text, "aneesh_resume.txt")

        self.assertEqual(parsed["email"], "aneeshrudravaram@gmail.com")

    def test_bracketed_email_is_extracted_from_contact_section(self):
        resume_text = """
Rahul Verma
Contact Details
Email: (rahul.verma.dev@gmail.com)
Phone: +91 9876543210
        """

        parsed = self._parse_resume_text(resume_text, "rahul_bracketed_email.txt")

        self.assertEqual(parsed["email"], "rahul.verma.dev@gmail.com")

    def test_phone_extraction_prefers_mobile_over_tollfree(self):
        resume_text = """
Nisha Verma
Contact Details
Support Line: 1800 555 1111
Mobile: +91 98765 43210
Email: nisha.verma@email.com
        """

        parsed = self._parse_resume_text(resume_text, "nisha_contact.txt")

        self.assertEqual(parsed["phone"], "+91 98765 43210")

    def test_us_phone_format_is_extracted(self):
        resume_text = """
Abhishek Verma
Contact Information
(425) 555-0123
abhishek.verma.dev@gmail.com
        """

        parsed = self._parse_resume_text(resume_text, "abhishek_us_phone.txt")

        self.assertEqual(parsed["phone"], "(425) 555-0123")

    def test_information_extraction_name_overrides_skill_label_false_positive(self):
        resume_text = """
----Image alt text----><----media/fa77278ed5db745edceea64248cc78adea6d269d.png----
Sameer Qureshi
Senior Mobile App Developer (iOS & Android)
Hyderabad, Telangana +91 99887 76655 sameer.qureshi.dev@gmail.com
linkedin.com/in/sameerqureshidev github.com/sameerqdev play.google.com/store/apps/developer?id=SameerQ
ABOUTME
Senior Mobile Developer with 7 years of experience building polished, high-performance iOS and Android applications.
TECHNICAL SKILLS
Mobile Development
React Native (Expert)
Swift / SwiftUI
Kotlin / Jetpack Compose
Flutter (Intermediate)
Expo
        """

        parsed = self._parse_resume_text(resume_text, "R4_Sameer_Qureshi_MobileApp.docx")

        self.assertEqual(parsed["name"], "Sameer Qureshi")

    def test_information_extraction_falls_back_to_summary_experience_years(self):
        resume_text = """
Bhimaraju Koushik
bhimaraju.koushik@gmail.com | +91 8106148797

Professional Summary
QA Automation Engineer with 4.2 years of experience in Java, Selenium WebDriver and API testing.

Skills
Java
Selenium
API Testing

Expe rience
QA Automation Engineer
Cognizant Technology Solutions
Dec-2022 to Present
Using JIRA and Maven while continuously improving regression suites.
        """

        parsed = self._parse_resume_text(resume_text, "koushik_resume.pdf")

        self.assertAlmostEqual(parsed["total_experience_years"], 4.2, delta=0.1)

    def test_first_valid_email_is_selected_when_multiple_candidates_exist(self):
        resume_text = """
Rahul Candidate
Primary Email: rahul.candidate@example.com | Alternate: rahul.alt@example.org
Phone: +91 9876543210
        """

        parsed = self._parse_resume_text(resume_text, "rahul_candidate.txt")

        self.assertEqual(parsed["email"], "rahul.candidate@example.com")

    def test_skill_fallback_extracts_labeled_technology_lines_without_skills_section(self):
        resume_text = """
Maya Thomas
Austin, Texas | maya.thomas.engineer@gmail.com

Technologies: Python, FastAPI, PostgreSQL, Docker
Cloud: AWS, Terraform

Professional Experience
Principal Backend Engineer | Acme Cloud Systems
2023/01 - Present
Built backend services for hiring workflows.
        """

        result = extract_resume_information(resume_text)

        self.assertIn("python", result["skills"])
        self.assertIn("fastapi", result["skills"])
        self.assertIn("docker", result["skills"])
        self.assertIn("aws", result["skills"])

    def test_parse_resume_keeps_late_skills_section_beyond_initial_text_window(self):
        filler = "Experience summary line. " * 320
        resume_text = f"""
Late Skills Candidate
late.skills@example.com

Summary
{filler}

Skills
Python, FastAPI, Docker
        """

        parsed = self._parse_resume_text(resume_text, "late_skills_candidate.txt")

        self.assertIn("python", parsed["skills"])
        self.assertIn("fastapi", parsed["skills"])
        self.assertIn("docker", parsed["skills"])

    def test_current_role_is_trimmed_without_company_and_location_suffix(self):
        resume_text = """
Rhea Kapoor

Work Experience
Senior Graphic Designer Ogilvy India Bengaluru, Karnataka
Jan 2022 - Present
Designed brand identity systems.
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Senior Graphic Designer")

    def test_bullet_separator_experience_extracts_company_role_and_total_years(self):
        resume_text = """
WORK EXPERIENCE
Senior Product Manager · PhonePe Pvt. Ltd. · Mumbai
Aug 2021 – Present | Insurance & Wealth Products
Owned the Insurance vertical product.
Product Manager · Myntra Designs Pvt. Ltd. · Bengaluru
Jun 2018 – Jul 2021 | Discovery & Search
Owned Search & Discovery experience.
Associate Product Manager · OYO Rooms · Gurugram
Jul 2016 – May 2018 | Supply & Property Management
Built OYO Krypt
        """

        result = extract_resume_information(resume_text)

        self.assertEqual(result["current_role"], "Senior Product Manager")
        self.assertEqual(result["current_company"], "PhonePe Pvt. Ltd")
        self.assertEqual(result["location"], "")
        self.assertAlmostEqual(result["total_experience_years"], 9.8, delta=0.2)


if __name__ == "__main__":
    unittest.main()
