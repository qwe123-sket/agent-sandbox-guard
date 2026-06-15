from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class SandboxError(Exception):
    pass


@dataclass
class SandboxContext:
    workspace_dir: Path
    data_dir: Path

    def __post_init__(self) -> None:
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def resolve_workspace_path(self, relative_path: str) -> Path:
        candidate = (self.workspace_dir / relative_path).resolve()
        workspace_root = self.workspace_dir.resolve()
        if workspace_root not in candidate.parents and candidate != workspace_root:
            raise SandboxError(f"路径越界: {relative_path}")
        return candidate
