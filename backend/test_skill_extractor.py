from __future__ import annotations

import sys
from pathlib import Path

from ats.extraction.skill_intelligence import SkillIntelligence

SAMPLE_RESUME_TEXT = (
    "Experienced sales and business development professional with over 9 years of experience "
    "in B2B and B2C sales environments across FMCG, retail, SaaS, and banking industries. "
    "Proven track record in achieving revenue targets, managing client relationships, "
    "conducting cold calling, lead generation, negotiation, and closing deals."
)


def load_resume_text() -> str:
    if len(sys.argv) > 1:
        from ats.extraction.resume_parser import extract_text

        file_path = Path(sys.argv[1])
        if file_path.exists():
            return extract_text(str(file_path))
    return SAMPLE_RESUME_TEXT


def main() -> None:
    extractor = SkillIntelligence()
    resume_text = load_resume_text()
    skills, categories = extractor.extract_skills_with_categories(resume_text)

    print("Extracted skills:")
    for skill in skills:
        category = categories.get(skill, "unknown")
        print(f"- {skill} [{category}]")


if __name__ == "__main__":
    main()
