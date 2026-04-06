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
    parse_date,
)


logging.basicConfig(level=logging.DEBUG)


class ExperienceExtractionTests(unittest.TestCase):
    def test_extract_experience_section_ignores_education_and_projects(self):
        resume_text = """
John Doe

Professional Summary
Backend engineer with 5 years of experience.

Work Experience
Senior Software Engineer | ABC Corp
Jan 2020 - Mar 2022
Built APIs and led backend delivery.

Software Engineer | XYZ Technologies
03/2019 - 07/2021
Worked on microservices and integrations.

Education
Bachelor of Technology
2015 - 2019

Projects
Inventory Platform
2021 - 2022
        """

        section = extract_experience_section(resume_text)
        self.assertIn("Senior Software Engineer", section)
        self.assertNotIn("Bachelor of Technology", section)
        self.assertNotIn("Inventory Platform", section)

    def test_extract_date_ranges_supports_common_formats(self):
        text = """
May 2022 - Present
Jan 2020 - Apr 2022
Jul 2018 - Dec 2019
03/2019 - 07/2021
2018 to Present
        """

        ranges = extract_date_ranges(text)
        self.assertEqual(len(ranges), 5)
        self.assertEqual(ranges[0]["start"], "May 2022")
        self.assertEqual(ranges[2]["end"], "Dec 2019")

    def test_parse_date_handles_present_and_year_only(self):
        today = datetime(2026, 4, 3)
        self.assertEqual(parse_date("2020"), datetime(2020, 1, 1))
        self.assertEqual(parse_date("2020", is_end=True), datetime(2020, 12, 31))
        self.assertEqual(parse_date("Present", is_end=True, today=today), today)

    def test_multiple_jobs_with_different_date_formats(self):
        resume_text = """
Jane Smith

Professional Experience
Senior Software Engineer | ABC Corp
Jan 2020 - Mar 2022
Built APIs and improved performance.

Software Engineer | XYZ Technologies
04/2022 - 07/2023
Shipped internal tooling.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["experiences"][0]["company"], "XYZ Technologies")
        self.assertEqual(result["experiences"][1]["company"], "ABC Corp")
        self.assertAlmostEqual(result["total_experience_years"], 3.6, delta=0.15)

    def test_present_roles_and_overlap_are_not_double_counted(self):
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
        self.assertEqual(len(result["experiences"]), 2)

        first_start = parse_date("2018")
        first_end = parse_date("2020", is_end=True)
        second_start = parse_date("Feb 2020")
        second_end = parse_date("Present", is_end=True)
        expected_total = compute_total_experience([(first_start, first_end), (second_start, second_end)])

        self.assertAlmostEqual(result["total_experience_years"], expected_total, delta=0.05)

    def test_education_and_projects_dates_are_not_counted(self):
        resume_text = """
Summary
Data engineer with strong Python experience.

Education
Bachelor of Engineering
2016 - 2020

Projects
Fraud Analytics Platform
2021 - 2022

Professional Experience
Data Engineer at Insight Works
03/2019 - 07/2021
Built ETL jobs and analytics pipelines.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 1)
        self.assertEqual(result["experiences"][0]["company"], "Insight Works")
        self.assertAlmostEqual(result["total_experience_years"], 2.4, delta=0.15)

    def test_ignore_internships_flag(self):
        resume_text = """
Work Experience
Software Engineering Intern | Acme Corp
Jan 2018 - Dec 2018
Worked on test automation.

Software Engineer | Acme Corp
2019 - 2021
Built production services.
        """

        included = extract_total_experience(resume_text, ignore_internships=False)
        excluded = extract_total_experience(resume_text, ignore_internships=True)

        self.assertEqual(len(included["experiences"]), 2)
        self.assertEqual(len(excluded["experiences"]), 1)
        self.assertGreater(included["total_experience_years"], excluded["total_experience_years"])
        self.assertAlmostEqual(excluded["total_experience_years"], 3.0, delta=0.15)

    def test_multiline_unicode_resume_structure_extracts_three_jobs(self):
        resume_text = """
Alex Johnson

━━ Experience
Senior Software Engineer · Bright Software
May 2022 – Present
Bengaluru, India

Software Engineer
CloudWave Technologies
Jan 2020 – Apr 2022
Hyderabad, India

Associate Developer · DataForge Labs
Jul 2018 – Dec 2019
Chennai, India

Skills
Python, FastAPI, PostgreSQL

Education
B.Tech Computer Science
2014 - 2018
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 3)
        self.assertEqual(result["experiences"][0]["role"], "Senior Software Engineer")
        self.assertEqual(result["experiences"][0]["company"], "Bright Software")
        self.assertEqual(result["experiences"][1]["role"], "Software Engineer")
        self.assertEqual(result["experiences"][1]["company"], "CloudWave Technologies")
        self.assertEqual(result["experiences"][2]["role"], "Associate Developer")
        self.assertEqual(result["experiences"][2]["company"], "DataForge Labs")
        self.assertGreater(result["total_experience_years"], 6.0)

    def test_fallback_without_experience_header_ignores_project_dates(self):
        resume_text = """
John Candidate

Senior Backend Engineer | Orbit Systems
01/2020 - 02/2022
Built APIs and hiring tools.

Projects
Resume Parser Rewrite
2022 - 2023
Implemented a side project parser.

Education
B.Tech Computer Science
2014 - 2018
        """

        result = extract_total_experience(resume_text)
        self.assertEqual(len(result["experiences"]), 1)
        self.assertEqual(result["experiences"][0]["company"], "Orbit Systems")
        self.assertAlmostEqual(result["total_experience_years"], 2.2, delta=0.15)

    def test_year_only_ranges_assume_full_years(self):
        resume_text = """
Professional Experience
Software Engineer | Acme Corp
2019 - 2021
Built production services.
        """

        result = extract_total_experience(resume_text)
        self.assertEqual(result["experiences"][0]["start_date"], "2019-01")
        self.assertEqual(result["experiences"][0]["end_date"], "2021-12")
        self.assertAlmostEqual(result["total_experience_years"], 3.0, delta=0.05)

    def test_company_trims_trailing_city_token(self):
        resume_text = """
Professional Experience
Junior Mobile Developer | Byjus Bengaluru
2019 - 2021
Built Android features and internal tooling.
        """

        result = extract_total_experience(resume_text)
        self.assertEqual(len(result["experiences"]), 1)
        self.assertEqual(result["experiences"][0]["role"], "Junior Mobile Developer")
        self.assertEqual(result["experiences"][0]["company"], "Byjus")

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

    def test_extract_date_ranges_supports_year_month_and_short_year_formats(self):
        text = """
2021/03 - Present
Mar-21 - Dec-22
09.2018 - 02.2021
        """

        ranges = extract_date_ranges(text)

        self.assertEqual(len(ranges), 3)
        self.assertEqual(ranges[0]["start"], "2021/03")
        self.assertEqual(ranges[1]["end"], "Dec-22")

    def test_multiple_entries_are_split_when_each_line_contains_a_date_range(self):
        resume_text = """
Professional Experience
Lead Engineer | Nova Systems | 2021/03 - Present
Built platform services.
Senior Engineer | Acme Works | 09.2018 - 02.2021
Delivered hiring workflow automation.
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["experiences"][0]["company"], "Nova Systems")
        self.assertEqual(result["experiences"][1]["company"], "Acme Works")

    def test_parse_date_keeps_exact_day_for_full_numeric_dates(self):
        self.assertEqual(parse_date("06-10-2025"), datetime(2025, 10, 6))
        self.assertEqual(parse_date("04-10-2025", is_end=True), datetime(2025, 10, 4))

    def test_extract_date_ranges_supports_from_and_till_phrases(self):
        text = """
from Jan 2020 till Present
from 06-10-2025 till 04-10-2026
        """

        ranges = extract_date_ranges(text)

        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0]["start"], "Jan 2020")
        self.assertEqual(ranges[1]["end"], "04-10-2026")

    def test_structured_organization_designation_period_entries_are_counted_correctly(self):
        resume_text = """
Sooram Niharika

PROFESSIONAL EXPERIENCE
Organization: ODT
Designation: Senior Power Platform Developer
Period: 06-10-2025 - Present
Project - EOL Workflow

Organization: DXC Technology
Designation: Power Platform Developer
Period: July 2020 - 04-10-2025
Project 1 - Trigger Email for Odyssey Data Older than 30 Days
        """

        result = extract_total_experience(resume_text)

        self.assertEqual(len(result["experiences"]), 2)
        self.assertEqual(result["experiences"][0]["company"], "ODT")
        self.assertEqual(result["experiences"][1]["company"], "DXC Technology")
        self.assertEqual(result["experiences"][1]["start_date"], "2020-07")
        self.assertGreater(result["total_experience_years"], 5.0)


if __name__ == "__main__":
    unittest.main()
