from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def run_deployment_audit(project_root: str | Path = ".") -> Dict[str, Any]:
    root = Path(project_root)
    backend_root = root / "backend"
    dockerfile_exists = (backend_root / "Dockerfile").exists()
    nixpacks_exists = (backend_root / "nixpacks.toml").exists()
    procfile_exists = (backend_root / "Procfile").exists()
    railway_json_path = root / "railway.json"
    railway_config: Dict[str, Any] = {}
    if railway_json_path.exists():
        railway_config = json.loads(railway_json_path.read_text(encoding="utf-8"))

    railway_builder = str((railway_config.get("build") or {}).get("builder") or "").upper()
    root_directory = str((railway_config.get("deploy") or {}).get("rootDirectory") or "")

    deployment_type = "Default Railway"
    if railway_builder == "DOCKERFILE" and dockerfile_exists:
        deployment_type = "Docker"
    elif nixpacks_exists:
        deployment_type = "Nixpacks"

    return {
        "deployment_type": deployment_type,
        "dockerfile_exists": dockerfile_exists,
        "nixpacks_exists": nixpacks_exists,
        "procfile_exists": procfile_exists,
        "railway_builder": railway_builder or None,
        "railway_root_directory": root_directory or None,
        "uses_docker": deployment_type == "Docker",
        "uses_nixpacks": deployment_type == "Nixpacks",
        "uses_default_railway": deployment_type == "Default Railway",
    }
