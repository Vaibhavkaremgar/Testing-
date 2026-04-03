from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Sequence


class ParserConfigLoader:
    def __init__(self, base_path: str = "ats/datasets/parser"):
        self.base_path = Path(base_path)

    def _candidate_base_paths(self) -> List[Path]:
        candidates = [self.base_path, Path("backend") / self.base_path]
        seen: List[Path] = []
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

    def _read_json(self, filename: str) -> Dict[str, Any]:
        path = self._resolve_existing_path([filename])
        if not path.exists() or path.stat().st_size == 0:
            return {}
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}

    def load_skill_overlays(self) -> Dict[str, Any]:
        return self._read_json("skill_overlays.json")

    def load_parser_vocabulary(self) -> Dict[str, Any]:
        return self._read_json("parser_vocabulary.json")
