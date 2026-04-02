from __future__ import annotations

import logging
import re
from typing import Iterable, List

logger = logging.getLogger(__name__)

DEFAULT_SUMMARY = "Candidate Summary:\n• Experience Match: Insufficient data for evaluation.\n• Skill Match: Insufficient data for evaluation.\n• Domain Match: Insufficient data for evaluation.\n• Strengths: Limited structured evidence available.\n• Gaps (if any): Unable to determine from current data.\n• Overall Fit: Not enough structured information to assess fit."


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _normalize_list(values: Iterable[str] | None) -> List[str]:
    if not values:
        return []

    ordered: List[str] = []
    seen = set()
    for value in values:
        normalized = _normalize_text(str(value))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _parse_required_experience(value) -> tuple[float | None, float | None]:
    if value is None:
        return (None, None)

    if isinstance(value, (int, float)):
        numeric = float(value)
        return (numeric, numeric)

    text = _normalize_text(str(value))
    if not text:
        return (None, None)

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        first = float(range_match.group(1))
        second = float(range_match.group(2))
        return (min(first, second), max(first, second))

    plus_match = re.search(r"(\d+(?:\.\d+)?)\s*\+", text)
    if plus_match:
        minimum = float(plus_match.group(1))
        return (minimum, None)

    single_match = re.search(r"(\d+(?:\.\d+)?)", text)
    if single_match:
        numeric = float(single_match.group(1))
        return (numeric, numeric)

    return (None, None)


def _join_skills(skills: List[str], limit: int = 4) -> str:
    if not skills:
        return "none clearly matched"
    selected = [skill.title() for skill in skills[:limit]]
    return ", ".join(selected)


def generate_extractive_summary(resume_text: str, jd_text: str) -> str:
    """
    Deprecated compatibility wrapper.

    The ATS summary generator now produces structured evaluation summaries instead of
    extractive resume snippets. This wrapper remains only to avoid broken imports.
    """
    logger.info("generate_extractive_summary fallback invoked; returning default evaluation summary.")
    return DEFAULT_SUMMARY


def generate_summary(
    *,
    required_skills: List[str] | None,
    preferred_skills: List[str] | None,
    required_experience,
    role_title: str = "",
    industry: str = "",
    candidate_skills: List[str] | None,
    candidate_experience: float | int | None,
    candidate_industries: List[str] | None,
    candidate_roles: List[str] | None,
) -> str:
    """
    Generate a structured ATS evaluation summary from JD-vs-candidate data.

    This summary is comparison-based and uses only structured fields rather than
    copying or rewriting resume text.
    """
    normalized_required = _normalize_list(required_skills)
    normalized_preferred = _normalize_list(preferred_skills)
    normalized_candidate_skills = _normalize_list(candidate_skills)
    normalized_candidate_roles = _normalize_list(candidate_roles)
    normalized_candidate_industries = _normalize_list(candidate_industries)
    normalized_industry = _normalize_text(industry)
    normalized_role_title = _normalize_text(role_title)

    if not any([normalized_required, normalized_candidate_skills, candidate_experience, normalized_candidate_roles]):
        return DEFAULT_SUMMARY

    required_set = set(normalized_required)
    preferred_set = set(normalized_preferred)
    candidate_skill_set = set(normalized_candidate_skills)

    matched_required = [skill for skill in normalized_required if skill in candidate_skill_set]
    matched_preferred = [skill for skill in normalized_preferred if skill in candidate_skill_set]
    missing_required = [skill for skill in normalized_required if skill not in candidate_skill_set]

    min_required_exp, max_required_exp = _parse_required_experience(required_experience)
    candidate_experience_value = float(candidate_experience or 0.0)

    if min_required_exp is None and max_required_exp is None:
        experience_match = f"Candidate shows approximately {candidate_experience_value:.1f} years of experience; the job requirement is not clearly specified."
    elif max_required_exp is None:
        if candidate_experience_value >= min_required_exp:
            experience_match = f"Candidate experience of {candidate_experience_value:.1f} years meets or exceeds the minimum requirement of {min_required_exp:.1f}+ years."
        else:
            experience_match = f"Candidate experience of {candidate_experience_value:.1f} years is below the expected minimum of {min_required_exp:.1f}+ years."
    elif min_required_exp <= candidate_experience_value <= max_required_exp:
        experience_match = f"Candidate experience of {candidate_experience_value:.1f} years is aligned with the required range of {min_required_exp:.1f}-{max_required_exp:.1f} years."
    elif candidate_experience_value < min_required_exp:
        experience_match = f"Candidate experience of {candidate_experience_value:.1f} years falls below the required range of {min_required_exp:.1f}-{max_required_exp:.1f} years."
    else:
        experience_match = f"Candidate experience of {candidate_experience_value:.1f} years exceeds the stated range of {min_required_exp:.1f}-{max_required_exp:.1f} years."

    if matched_required:
        skill_match = f"Matched core skills include {_join_skills(matched_required)}."
        if matched_preferred:
            skill_match += f" Preferred overlap includes {_join_skills(matched_preferred, limit=3)}."
    else:
        skill_match = "No strong overlap was found across the listed required skills."

    if normalized_industry:
        domain_hits = [item for item in normalized_candidate_industries if normalized_industry in item or item in normalized_industry]
        if domain_hits:
            domain_match = f"Relevant domain exposure is visible through experience in {_join_skills(domain_hits, limit=2)}."
        else:
            domain_match = f"No clear direct domain match was identified for {industry}, based on the structured candidate data."
    elif normalized_role_title and normalized_candidate_roles:
        role_hits = [role for role in normalized_candidate_roles if normalized_role_title in role or role in normalized_role_title]
        if role_hits:
            domain_match = f"Role alignment is supported by prior titles such as {_join_skills(role_hits, limit=2)}."
        else:
            domain_match = "Domain alignment is not strongly established from the available structured role history."
    else:
        domain_match = "Domain alignment is not clearly established from the available structured data."

    strengths_items: List[str] = []
    if matched_required:
        strengths_items.append(f"core skill alignment in {_join_skills(matched_required, limit=3)}")
    if matched_preferred:
        strengths_items.append(f"additional value in {_join_skills(matched_preferred, limit=2)}")
    if min_required_exp is not None and candidate_experience_value >= min_required_exp:
        strengths_items.append("experience depth appropriate for the role")
    elif candidate_experience_value > 0:
        strengths_items.append("relevant practical experience")
    if normalized_candidate_roles:
        strengths_items.append(f"role continuity across {_join_skills(normalized_candidate_roles, limit=2)}")
    strengths = "Key strengths are " + ", ".join(strengths_items) + "." if strengths_items else "Key strengths are not strongly evidenced in the current structured comparison."

    gaps_items: List[str] = []
    if missing_required:
        gaps_items.append(f"missing important skills such as {_join_skills(missing_required, limit=4)}")
    if min_required_exp is not None and candidate_experience_value < min_required_exp:
        gaps_items.append("experience below the stated requirement")
    if normalized_industry and not normalized_candidate_industries:
        gaps_items.append("domain background not clearly available in structured candidate data")
    gaps = "Primary gaps include " + ", ".join(gaps_items) + "." if gaps_items else "No major gaps are evident from the structured JD comparison."

    required_coverage = (len(matched_required) / len(normalized_required)) if normalized_required else 0.0
    if required_coverage >= 0.7 and (min_required_exp is None or candidate_experience_value >= min_required_exp):
        overall_fit = "Overall fit appears strong based on required skill coverage and experience alignment."
    elif required_coverage >= 0.4:
        overall_fit = "Overall fit appears moderate, with relevant overlap but some notable gaps to assess further."
    else:
        overall_fit = "Overall fit appears limited due to low alignment on key structured requirements."

    return "\n".join(
        [
            "Candidate Summary:",
            f"• Experience Match: {experience_match}",
            f"• Skill Match: {skill_match}",
            f"• Domain Match: {domain_match}",
            f"• Strengths: {strengths}",
            f"• Gaps (if any): {gaps}",
            f"• Overall Fit: {overall_fit}",
        ]
    )
