from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd


class ESCOLoader:
    def __init__(self, base_path="ats/datasets/esco"):
        self.base_path = Path(base_path)

    def _candidate_base_paths(self) -> List[Path]:
        candidates = [self.base_path, Path("backend") / self.base_path]
        seen = []
        for path in candidates:
            if path not in seen:
                seen.append(path)
        return seen

    def _resolve_existing_path(self, filenames: Sequence[str]) -> Path:
        for base_path in self._candidate_base_paths():
            for filename in filenames:
                candidate = base_path / filename
                if candidate.exists():
                    return candidate
        return self._candidate_base_paths()[0] / filenames[0]

    def _read_csv(self, filename: str) -> pd.DataFrame:
        path = self._resolve_existing_path([filename])
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path)

    def _read_json(self, filename: str) -> Dict:
        path = self._resolve_existing_path([filename])
        if not path.exists() or path.stat().st_size == 0:
            return {}
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def _read_first_available_csv(self, filenames: Sequence[str]) -> pd.DataFrame:
        path = self._resolve_existing_path(filenames)
        if not path.exists() or path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path)

    def load_skills(self) -> List[str]:
        skills_df = self._read_first_available_csv(["skills_en.csv", "skills.csv"])
        if skills_df.empty:
            return []

        candidate_columns = ["preferred_label", "skill", "name", "title", "label"]
        if "preferredLabel" in skills_df.columns:
            candidate_columns = ["preferredLabel"] + candidate_columns

        for column in candidate_columns:
            if column in skills_df.columns:
                series = skills_df[column].replace({np.nan: None}).dropna()
                return [str(value).strip().lower() for value in series if str(value).strip()]

        first_column = skills_df.columns[0]
        series = skills_df[first_column].replace({np.nan: None}).dropna()
        return [str(value).strip().lower() for value in series if str(value).strip()]

    def load_synonyms(self) -> Dict[str, str]:
        synonyms: Dict[str, str] = {}

        skills_df = self._read_first_available_csv(["skills_en.csv", "skills.csv"])
        if not skills_df.empty and "preferredLabel" in skills_df.columns:
            alt_columns = [column for column in ["altLabels", "hiddenLabels"] if column in skills_df.columns]
            for _, row in skills_df.iterrows():
                preferred_label = str(row.get("preferredLabel", "")).strip().lower()
                if not preferred_label:
                    continue

                synonyms[preferred_label] = preferred_label
                for column in alt_columns:
                    raw_value = row.get(column)
                    if pd.isna(raw_value) or not raw_value:
                        continue
                    for synonym in str(raw_value).split("\n"):
                        normalized = synonym.strip().lower()
                        if normalized:
                            synonyms[normalized] = preferred_label

        file_synonyms = self._read_json("synonyms.json")
        for key, value in file_synonyms.items():
            normalized_key = str(key).strip().lower()
            normalized_value = str(value).strip().lower()
            if normalized_key and normalized_value:
                synonyms[normalized_key] = normalized_value

        return synonyms

    def load_hierarchy(self) -> Dict[str, List[str]]:
        ontology = self._read_json("ontology.json")
        normalized_ontology: Dict[str, List[str]] = {}
        if ontology:
            for key, values in ontology.items():
                if isinstance(values, list):
                    normalized_ontology[str(key).strip().lower()] = [
                        str(value).strip().lower() for value in values if str(value).strip()
                    ]
                elif values:
                    normalized_ontology[str(key).strip().lower()] = [str(values).strip().lower()]

        skills_df = self._read_first_available_csv(["skills_en.csv", "skills.csv"])
        uri_to_label: Dict[str, str] = {}
        if not skills_df.empty and {"conceptUri", "preferredLabel"}.issubset(skills_df.columns):
            for _, row in skills_df.iterrows():
                concept_uri = str(row.get("conceptUri", "")).strip()
                preferred_label = str(row.get("preferredLabel", "")).strip().lower()
                if concept_uri and preferred_label:
                    uri_to_label[concept_uri] = preferred_label

        hierarchy_df = self._read_first_available_csv(["skillsHierarchy_en.csv", "hierarchy.csv"])
        if not hierarchy_df.empty:
            preferred_term_columns = [column for column in hierarchy_df.columns if "preferred term" in column.lower()]
            for _, row in hierarchy_df.iterrows():
                labels = []
                for column in preferred_term_columns:
                    value = row.get(column)
                    if pd.isna(value) or not value:
                        continue
                    labels.append(str(value).strip().lower())

                for parent, child in zip(labels, labels[1:]):
                    if parent and child:
                        normalized_ontology.setdefault(parent, [])
                        if child not in normalized_ontology[parent]:
                            normalized_ontology[parent].append(child)

        relation_df = self._read_first_available_csv(["skillSkillRelations_en.csv"])
        if not relation_df.empty and {"originalSkillUri", "relatedSkillUri"}.issubset(relation_df.columns):
            for _, row in relation_df.iterrows():
                original_uri = str(row.get("originalSkillUri", "")).strip()
                related_uri = str(row.get("relatedSkillUri", "")).strip()
                original_label = uri_to_label.get(original_uri)
                related_label = uri_to_label.get(related_uri)
                if original_label and related_label:
                    normalized_ontology.setdefault(original_label, [])
                    if related_label not in normalized_ontology[original_label]:
                        normalized_ontology[original_label].append(related_label)

        return normalized_ontology
