from __future__ import annotations

from pathlib import Path

from agent_guard.sandbox import SandboxContext, SandboxError


def list_files(ctx: SandboxContext, directory: str = ".") -> list[str]:
    target = ctx.resolve_workspace_path(directory)
    if not target.is_dir():
        raise SandboxError(f"目录不存在: {directory}")
    return sorted(
        str(p.relative_to(ctx.workspace_dir))
        for p in target.iterdir()
    )


def read_file(ctx: SandboxContext, path: str) -> str:
    target = ctx.resolve_workspace_path(path)
    if not target.is_file():
        raise SandboxError(f"文件不存在: {path}")
    return target.read_text(encoding="utf-8")


def write_file(ctx: SandboxContext, path: str, content: str) -> str:
    target = ctx.resolve_workspace_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {path}，共 {len(content)} 字符"


def delete_file(ctx: SandboxContext, path: str) -> str:
    target = ctx.resolve_workspace_path(path)
    if not target.is_file():
        raise SandboxError(f"文件不存在: {path}")
    target.unlink()
    return f"已删除 {path}"
