from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class AppConfig:
    project_root: Path
    sandbox_root: Path
    workspace_dir: Path
    data_dir: Path
    policies_path: Path
    audit_log_path: Path
    default_role: str = "readonly"


def load_policies(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(project_root: Path | None = None) -> AppConfig:
    root = project_root or Path(__file__).resolve().parents[2]
    sandbox_root = Path(os.getenv("SANDBOX_ROOT", root / "sandbox"))
    return AppConfig(
        project_root=root,
        sandbox_root=sandbox_root,
        workspace_dir=sandbox_root / "workspace",
        data_dir=sandbox_root / "data",
        policies_path=root / "config" / "policies.yaml",
        audit_log_path=root / "logs" / "audit.jsonl",
    )
