from __future__ import annotations

from typing import Dict, List

from flashtext import KeywordProcessor

from ats.datasets.esco_loader import ESCOLoader


class SkillIntelligence:
    """Canonical skill lookup with ESCO-backed synonyms and ontology support."""

    def __init__(self, loader: ESCOLoader | None = None):
        self.loader = loader or ESCOLoader()
        self.skill_dictionary = self._dedupe(self.loader.load_skills())
        self.synonym_dictionary = {
            key: value for key, value in self.loader.load_synonyms().items() if key and value
        }
        self.ontology = self.loader.load_hierarchy()
        self.keyword_processor = KeywordProcessor(case_sensitive=False)
        self._build_keyword_index()

    def _dedupe(self, values: List[str]) -> List[str]:
        seen = set()
        ordered: List[str] = []
        for value in values:
            normalized = str(value).strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return ordered

    def _build_keyword_index(self) -> None:
        for skill in self.skill_dictionary:
            self.keyword_processor.add_keyword(skill, skill)
        for synonym, canonical in self.synonym_dictionary.items():
            self.keyword_processor.add_keyword(synonym, canonical)

    def normalize_skill(self, skill: str) -> str:
        normalized = skill.strip().lower()
        return self.synonym_dictionary.get(normalized, normalized)

    def extract_skills(self, text: str) -> List[str]:
        if not text:
            return []

        matches = self.keyword_processor.extract_keywords(text)
        ordered: List[str] = []
        seen = set()
        for match in matches:
            canonical = self.normalize_skill(match)
            if canonical and canonical not in seen:
                seen.add(canonical)
                ordered.append(canonical)
        return ordered

    def map_skills(self, skills: List[str]) -> List[str]:
        return self._dedupe([self.normalize_skill(skill) for skill in skills])

    def get_related_skills(self, skill: str) -> List[str]:
        canonical = self.normalize_skill(skill)
        return list(self.ontology.get(canonical, []))

    def get_skill_dictionary(self) -> List[str]:
        return list(self.skill_dictionary)

    def get_synonym_dictionary(self) -> Dict[str, str]:
        return dict(self.synonym_dictionary)

    def get_ontology(self) -> Dict[str, List[str]]:
        return dict(self.ontology)
