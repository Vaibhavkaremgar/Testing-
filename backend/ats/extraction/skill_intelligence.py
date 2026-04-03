from __future__ import annotations

import logging
import re
from typing import Dict, List, Tuple

from flashtext import KeywordProcessor

from ats.datasets.esco_loader import ESCOLoader

logger = logging.getLogger(__name__)


DOMAIN_SKILLS: Dict[str, List[str]] = {
    "technology": [
        "python", "java", "javascript", "typescript", "react", "nodejs", "fastapi",
        "sql", "postgresql", "mysql", "mongodb", "aws", "azure", "docker",
        "kubernetes", "rest api", "graphql", "machine learning", "data analysis",
        "html", "css",
    ],
    "sales": [
        "b2b sales", "b2c sales", "lead generation", "business development",
        "customer relationship management", "account management", "cold calling",
        "pipeline management", "salesforce", "hubspot", "zoho crm", "saas",
    ],
    "marketing": [
        "digital marketing", "seo", "sem", "content marketing", "social media marketing",
        "email marketing", "google analytics", "google ads", "brand management",
        "campaign management",
    ],
    "finance": [
        "financial analysis", "accounting", "budgeting", "forecasting", "bookkeeping",
        "reconciliation", "accounts payable", "accounts receivable", "audit", "taxation",
        "gst", "tally", "banking", "retail banking",
    ],
    "hr": [
        "recruitment", "talent acquisition", "employee relations", "hr operations",
        "payroll", "performance management", "onboarding", "sourcing", "screening",
    ],
    "admin": [
        "data entry", "calendar management", "document management", "office administration",
        "vendor management", "travel coordination", "microsoft excel", "microsoft office",
    ],
    "design": [
        "figma", "adobe photoshop", "adobe illustrator", "ui design", "ux design",
        "wireframing", "prototyping", "graphic design",
    ],
    "healthcare": [
        "patient care", "clinical documentation", "medical coding", "ehr", "emr",
        "phlebotomy", "nursing", "healthcare administration",
    ],
    "industry": [
        "saas", "fmcg", "retail", "banking", "healthcare", "fintech", "edtech",
        "e-commerce", "manufacturing", "telecom",
    ],
}

SKILL_ALIASES: Dict[str, str] = {
    "react.js": "react",
    "reactjs": "react",
    "node.js": "nodejs",
    "node js": "nodejs",
    "customer relationship management": "customer relationship management",
    "client relationship management": "customer relationship management",
    "crm": "customer relationship management",
    "salesforce crm": "salesforce",
    "hubspot crm": "hubspot",
    "zoho crm": "zoho crm",
    "business dev": "business development",
    "b2b": "b2b sales",
    "b2c": "b2c sales",
    "html5": "html",
    "css3": "css",
}

NOISE_TERMS = {
    "plan",
    "negotiation",
    "presentation",
    "communication",
    "leadership",
    "teamwork",
    "hardworking",
    "motivated",
    "responsible",
    "professional",
    "experienced",
    "computer science",
}

LANGUAGE_TERMS = {
    "english",
    "hindi",
    "telugu",
    "tamil",
    "kannada",
    "malayalam",
    "marathi",
    "gujarati",
    "punjabi",
    "bengali",
    "urdu",
    "french",
    "german",
    "spanish",
    "arabic",
    "japanese",
    "mandarin",
    "chinese",
}

NOISE_ALIASES = {
    "lead others",
    "computer programming",
    "database management systems",
    "tools for software configuration management",
    "ict project management methodologies",
    "use online tools to collaborate",
    "integrated development environment software",
    "electronic communication",
    "perform cleaning duties",
    "advise others",
    "think creatively",
    "report facts",
    "comply with regulations",
    "apply knowledge of science, technology and engineering",
    "source (digital game creation systems)",
    "logic",
}

VERB_LED_NOISE_PREFIXES = {
    "advise",
    "apply",
    "assist",
    "build",
    "clean",
    "collaborate",
    "communicate",
    "comply",
    "create",
    "develop",
    "ensure",
    "follow",
    "improve",
    "lead",
    "maintain",
    "manage",
    "monitor",
    "perform",
    "prepare",
    "provide",
    "report",
    "support",
    "think",
    "use",
    "work",
}

GENERIC_NOISE_TOKENS = {
    "activities",
    "communication",
    "creatively",
    "creation",
    "digital",
    "duties",
    "facts",
    "knowledge",
    "methodologies",
    "others",
    "regulations",
    "science",
    "software",
    "source",
    "systems",
    "technology",
    "tools",
}

BOUNDARY_REPLACEMENTS = {
    "b2b and b2c sales": ["b2b sales", "b2c sales"],
}


class SkillIntelligence:
    """Shared production skill extractor for resumes and job descriptions."""

    def __init__(self, loader: ESCOLoader | None = None):
        self.loader = loader or ESCOLoader()
        self.skill_dictionary = self._dedupe(self.loader.load_skills())
        self.synonym_dictionary = self._build_synonym_dictionary()
        self.ontology = self.loader.load_hierarchy()
        self.category_map = self._build_category_map()
        self.keyword_processor = KeywordProcessor(case_sensitive=False)
        self._build_keyword_index()

    def _dedupe(self, values: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            normalized = self.normalize_skill(value)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _build_synonym_dictionary(self) -> Dict[str, str]:
        synonyms = {
            key: value for key, value in self.loader.load_synonyms().items() if key and value
        }
        for alias, canonical in SKILL_ALIASES.items():
            synonyms[self.normalize_skill(alias)] = self.normalize_skill(canonical)

        for category, skills in DOMAIN_SKILLS.items():
            for skill in skills:
                normalized = self.normalize_skill(skill)
                synonyms[normalized] = normalized
                if category == "sales" and normalized == "customer relationship management":
                    synonyms["crm tool"] = normalized
        return synonyms

    def _build_category_map(self) -> Dict[str, str]:
        category_map: Dict[str, str] = {}
        for category, skills in DOMAIN_SKILLS.items():
            for skill in skills:
                category_map[self.normalize_skill(skill)] = category
        return category_map

    def _build_keyword_index(self) -> None:
        for skill in self.skill_dictionary:
            normalized = self.normalize_skill(skill)
            if self._is_noise(normalized):
                continue
            self.keyword_processor.add_keyword(skill, normalized)

        for synonym, canonical in self.synonym_dictionary.items():
            if self._is_noise(canonical):
                continue
            self.keyword_processor.add_keyword(synonym, canonical)

        for skills in DOMAIN_SKILLS.values():
            for skill in skills:
                normalized = self.normalize_skill(skill)
                if self._is_noise(normalized):
                    continue
                self.keyword_processor.add_keyword(skill, normalized)

    def normalize_skill(self, skill: str) -> str:
        normalized = re.sub(r"\s+", " ", (skill or "").strip().lower())
        normalized = normalized.replace("/", " / ")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = SKILL_ALIASES.get(normalized, normalized)
        return normalized

    def _is_noise(self, skill: str) -> bool:
        normalized = self.normalize_skill(skill)
        return (
            normalized in NOISE_TERMS
            or normalized in LANGUAGE_TERMS
            or normalized in NOISE_ALIASES
            or self._looks_like_generic_noise(normalized)
        )

    def _looks_like_generic_noise(self, skill: str) -> bool:
        tokens = [token for token in re.split(r"[\s/+-]+", skill) if token]
        if not tokens:
            return True

        if len(tokens) >= 5:
            return True

        if any(char in skill for char in "()[]{}") and len(tokens) >= 3:
            return True

        if tokens[0] in VERB_LED_NOISE_PREFIXES and len(tokens) >= 2:
            return True

        generic_noise_hits = sum(1 for token in tokens if token in GENERIC_NOISE_TOKENS)
        if generic_noise_hits >= 2:
            return True

        if (
            len(tokens) >= 4
            and generic_noise_hits >= 1
            and not any(token.isdigit() or token in {"c", "c++", "c#", "sql"} for token in tokens)
        ):
            return True

        return False

    def _extract_boundary_variants(self, text: str) -> List[str]:
        lowered = (text or "").lower()
        matches: List[str] = []
        for phrase, expansions in BOUNDARY_REPLACEMENTS.items():
            if phrase in lowered:
                matches.extend(expansions)
        return matches

    def _extract_regex_skills(self, text: str) -> List[str]:
        if not text:
            return []

        regex_patterns = {
            "b2b sales": r"\bb2b(?:\s+sales)?\b",
            "b2c sales": r"\bb2c(?:\s+sales)?\b",
            "lead generation": r"\blead generation\b",
            "business development": r"\bbusiness development\b",
            "customer relationship management": r"\b(?:customer|client)\s+relationship\s+management\b|\bcrm\b",
            "saas": r"\bsaas\b",
            "fmcg": r"\bfmcg\b",
            "retail": r"\bretail\b",
            "banking": r"\bbanking\b",
        }
        matches: List[str] = []
        for canonical, pattern in regex_patterns.items():
            if re.search(pattern, text, re.IGNORECASE):
                matches.append(canonical)
        return matches

    def _is_supported_match(self, canonical: str, text: str) -> bool:
        lowered = (text or "").lower()
        if canonical in self.category_map:
            return True
        if canonical == lowered.strip():
            return True
        return bool(re.search(rf"(?<!\w){re.escape(canonical)}(?!\w)", lowered))

    def extract_skills(self, text: str) -> List[str]:
        skills, _ = self.extract_skills_with_categories(text)
        return skills

    def extract_skills_with_categories(self, text: str) -> Tuple[List[str], Dict[str, str]]:
        if not text:
            return [], {}

        matches = self.keyword_processor.extract_keywords(text)
        matches.extend(self._extract_boundary_variants(text))
        matches.extend(self._extract_regex_skills(text))

        ordered: List[str] = []
        categories: Dict[str, str] = {}
        seen = set()

        for match in matches:
            canonical = self.normalize_skill(match)
            canonical = self.synonym_dictionary.get(canonical, canonical)
            if (
                not canonical
                or canonical in seen
                or self._is_noise(canonical)
                or not self._is_supported_match(canonical, text)
            ):
                continue
            seen.add(canonical)
            ordered.append(canonical)
            category = self.category_map.get(canonical)
            if category:
                categories[canonical] = category

        return ordered, categories

    def map_skills(self, skills: List[str]) -> List[str]:
        return self._dedupe(
            [self.synonym_dictionary.get(self.normalize_skill(skill), self.normalize_skill(skill)) for skill in skills]
        )

    def get_related_skills(self, skill: str) -> List[str]:
        canonical = self.synonym_dictionary.get(self.normalize_skill(skill), self.normalize_skill(skill))
        return list(self.ontology.get(canonical, []))

    def get_skill_dictionary(self) -> List[str]:
        return list(self.skill_dictionary)

    def get_synonym_dictionary(self) -> Dict[str, str]:
        return dict(self.synonym_dictionary)

    def get_ontology(self) -> Dict[str, List[str]]:
        return dict(self.ontology)
