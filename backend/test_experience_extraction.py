import logging
import sys
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ats.extraction.experience_extraction import (  # noqa: E402
    compute_total_experience,
    extract_date_ranges,
    extract_experience_section,
    extract_total_experience,
    merge_overlapping_ranges,
    normalize_date,
    parse_date,
)
from ats.extraction.information_extraction import extract_resume_information  # noqa: E402
from ats.extraction.resume_parser import parse_resume_text  # noqa: E402
from app.routes.candidates import estimate_experience_years_from_text  # noqa: E402


logging.basicConfig(level=logging.DEBUG)


class ExperienceExtractionTests(unittest.TestCase):
    def test_extract_experience_section_only_keeps_approved_headers(self):
        resume_text = """
John Doe

Professional Summary
Backend engineer with 8 years of experience.

Experience Summary
Senior Software Engineer | ABC Corp
Jan 2020 - Mar 2022

Education
Bachelor of Technology
2015 - 2019

Projects
Resume Parser Rewrite
2023 - 2024
        """

        section = extract_experience_section(resume_text)

        self.assertIn("Senior Software Engineer", section)
        self.assertNotIn("Bachelor of Technology", section)
        self.assertNotIn("Resume Parser Rewrite", section)

    def test_date_parsing_supports_required_formats(self):
        today = datetime(2026, 4, 7)

        self.assertEqual(normalize_date("Jan 2022"), datetime(2022, 1, 1))
        self.assertEqual(normalize_date("Feb 2024"), datetime(2024, 2, 1))
        self.assertEqual(normalize_date("2022"), datetime(2022, 1, 1))
        self.assertEqual(normalize_date("02/2022"), datetime(2022, 2, 1))
        self.assertEqual(normalize_date("2022.01"), datetime(2022, 1, 1))
        self.assertEqual(normalize_date("Jan'22"), datetime(2022, 1, 1))
        self.assertEqual(normalize_date("Jan 22"), datetime(2022, 1, 1))
        self.assertEqual(normalize_date("Current", is_end=True, today=today), today)
        self.assertEqual(normalize_date("Till Date", is_end=True, today=today), today)
        self.assertEqual(normalize_date("Ongoing", is_end=True, today=today), today)

    def test_extract_date_ranges_supports_requested_patterns(self):
        text = """
Jan 2022 - Mar 2023
Jan 2022 - Present
2022 - 2023
02/2022 - 05/2023
Feb 2024 – Sep 2024
Jan'22 - Mar'23
Jan 22 - Mar 23
2022.01 - 2023.05
Worked from Jan 2022 to Present
        """

        ranges = extract_date_ranges(text)

        self.assertEqual(len(ranges), 9)
        self.assertEqual(ranges[0]["start"], "Jan 2022")
        self.assertEqual(ranges[-1]["end"], "Present")

    def test_summary_education_projects_and_certifications_are_never_counted(self):
        resume_text = """
Alex Candidate

Professional Summary
Data engineer with 8 years of experience and 15+ production systems delivered.

Education
B.Tech Computer Science
2014 - 2018

Certifications
AWS Certified Solutions Architect - 2023

Projects
Hiring Platform Migration
2022 - 2024
Improved latency by 500+ ms.

Skills
Python
10+
SQL

Professional Experience
Data Engineer | Insight Works
03/2019 - 07/2021
Built ETL jobs and analytics pipelines.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 1)
        self.assertEqual(result["current_company"], "Insight Works")
        self.assertAlmostEqual(result["total_experience_years"], 2.4, delta=0.15)

    def test_work_history_section_stops_at_publications_and_ignores_following_dates(self):
        resume_text = """
Alex Candidate

Work History
Senior Data Engineer
Northwind Technologies
Jan 2021 - Present
Built hiring analytics pipelines.

Publications
Modern Resume Parsing
2024

Education
Bachelor of Engineering
2014 - 2018
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 1)
        self.assertEqual(result["current_company"], "Northwind Technologies")
        self.assertNotIn("2014 - 2018", result["experience"][0]["raw_text"])

    def test_headerless_resume_returns_no_experience_under_section_only_rule(self):
        resume_text = """
Neha Kapoor
Seattle, Washington | neha.kapoor.data@gmail.com

Lead Data Engineer | Northwind Technologies
2021-03 - Present
Built hiring analytics pipelines and warehouse automation.

Senior Data Engineer | Blue River Labs
07/2018 - 02/2021
Designed ETL systems for enterprise reporting.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(result["experiences"], [])
        self.assertIsNone(result["total_experience_years"])
        self.assertIsNone(result["current_company"])

    def test_current_company_detection_prefers_latest_current_role(self):
        resume_text = """
Work Experience
Consultant | Alpha Systems | 2021 - Present
Handled transformation programs.

Senior Consultant | Beta Labs | 2023 - Present
Led enterprise delivery.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(result["current_company"], "Beta Labs")
        self.assertEqual(result["current_role"], "Senior Consultant")
        self.assertEqual(result["experiences"][0]["company"], "Beta Labs")

    def test_current_company_prefers_latest_end_date_when_no_present_role(self):
        resume_text = """
Professional Background
Software Engineer | Alpha Systems | Jan 2020 - Mar 2022
Built internal tools.

Senior Software Engineer | Beta Labs | Apr 2022 - Feb 2024
Led platform delivery.

Skills
Python
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(result["current_company"], "Beta Labs")
        self.assertEqual(result["current_role"], "Senior Software Engineer")
        self.assertEqual(result["current_role_start"], "2022-04")

    def test_future_dated_entry_is_ignored(self):
        resume_text = """
Professional Experience
Principal Engineer | Future Labs
Jan 2027 - Present
Building confidential AI products.

Senior Software Engineer | ABC Corp
Jan 2022 - Present
Built APIs and improved performance.

Software Engineer | XYZ Technologies
04/2020 - 12/2021
Shipped internal tooling.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["current_company"], "ABC Corp")
        self.assertAlmostEqual(result["total_experience_years"], 6.1, delta=0.15)

    def test_overlap_handling_merges_ranges_before_totaling(self):
        resume_text = """
Employment History
Lead Engineer | Nova Labs
Feb 2020 - Present
Leading platform modernization.

Engineering Consultant | Delta Systems
2018 - 2020
Handled architecture and integrations.
        """

        result = extract_total_experience(resume_text)
        expected_total = compute_total_experience(
            [
                (parse_date("2018"), parse_date("2020", is_end=True)),
                (parse_date("Feb 2020"), parse_date("Present", is_end=True)),
            ]
        )

        self.assertEqual(len(result["experiences"]), 2)
        self.assertAlmostEqual(result["total_experience_years"], expected_total, delta=0.05)

    def test_table_format_is_supported(self):
        resume_text = """
Experience
Google | Software Engineer | Jan 2022 - Present
Microsoft | Software Engineer | Jan 2020 - Dec 2021
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["current_company"], "Google")
        self.assertEqual(result["current_role"], "Software Engineer")

    def test_multiline_format_is_supported(self):
        resume_text = """
Work Experience
Senior HR Business Partner
Zoho Corporation Pvt. Ltd.
May 2021 - Present
Act as strategic HRBP for APAC.

HR Business Partner
Cognizant Technology Solutions
Jan 2018 - Apr 2021
Served the Retail vertical.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["current_company"], "Zoho Corporation Pvt. Ltd")
        self.assertEqual(result["current_role"], "Senior HR Business Partner")

    def test_inline_resume_format_is_supported(self):
        resume_text = """
Professional Background
Senior Data Analyst Meesho Pvt. Ltd. | Jun 2022 - Present Bengaluru, Karnataka Built reporting dashboards.
Data Analyst Delhivery Ltd. | Jan 2020 - May 2022 Gurugram, Haryana Built logistics reporting.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["current_company"], "Meesho Pvt. Ltd.")
        self.assertEqual(result["current_role"], "Senior Data Analyst")

    def test_fallback_experience_estimator_uses_role_attached_ranges(self):
        resume_text = """
Tashrif Apon
Queens, NY | tashrifapon2001@gmail.com

Data Engineer | NYC AG, LLC | Aug 2024 - Jan 2025
Developed a data mining pipeline SaaS for real estate arbitrage.

Software Engineer Intern | NYC Department of Health | Aug 2024 - Dec 2024
Automated ETL processes and improved backend performance.
        """

        years = estimate_experience_years_from_text(resume_text)

        self.assertGreater(years, 0.3)

    def test_internship_section_can_be_extracted_and_optionally_excluded(self):
        resume_text = """
Internship Experience
Software Engineering Intern | Acme Corp
Jan 2018 - Dec 2018
Worked on test automation.

Experience
Software Engineer | Acme Corp
2019 - 2021
Built production services.
        """

        included = extract_total_experience(resume_text, ignore_internships=False)
        excluded = extract_total_experience(resume_text, ignore_internships=True)

        self.assertEqual(len(included["experiences"]), 2)
        self.assertEqual(len(excluded["experiences"]), 1)
        self.assertGreater(included["total_experience_years"], excluded["total_experience_years"])

    def test_numeric_only_values_do_not_create_experience(self):
        resume_text = """
Experience
15+
500+
10+

Skills
Python
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(result["experiences"], [])
        self.assertEqual(result["total_experience_months"], 0)
        self.assertIsNone(result["current_company"])

    def test_current_aliases_map_to_today_for_current_company(self):
        resume_text = """
Work History
Backend Engineer | Orbit Systems
Jan 2022 - Till Date
Built APIs.

Software Engineer | Delta Tech
Jan 2020 - Dec 2021
Worked on integrations.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(result["current_company"], "Orbit Systems")
        self.assertEqual(result["current_role"], "Backend Engineer")

    def test_parser_experience_payload_keeps_start_end_duration_fields(self):
        resume_text = """
Work Experience
Senior ML Engineer
AI Labs Pvt Ltd
2022 - Present
        """

        parsed = parse_resume_text(resume_text)

        self.assertEqual(parsed["current_company"], "AI Labs Pvt Ltd")
        self.assertEqual(parsed["experience"][0]["start"], "2022-01")
        self.assertIn("duration", parsed["experience"][0])

    def test_location_stays_blank_when_only_mentioned_inside_experience(self):
        resume_text = """
John Doe
john@example.com
+91 9876543210

Work Experience
Software Engineer | ABC Corp
Jan 2020 - Present
Built backend services for a Bengaluru deployment.
        """

        extracted = extract_resume_information(resume_text)

        self.assertEqual(extracted["location"], "")

    def test_merge_overlapping_ranges(self):
        merged = merge_overlapping_ranges(
            [
                (parse_date("Jan 2020"), parse_date("Dec 2020", is_end=True)),
                (parse_date("Jun 2020"), parse_date("Mar 2021", is_end=True)),
                (parse_date("May 2021"), parse_date("Dec 2021", is_end=True)),
            ]
        )

        self.assertEqual(len(merged), 2)
        self.assertAlmostEqual(compute_total_experience(merged), 1.9, delta=0.15)


if __name__ == "__main__":
    unittest.main()
