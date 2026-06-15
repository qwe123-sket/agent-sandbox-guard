from __future__ import annotations

import sqlite3
from pathlib import Path

from agent_guard.sandbox import SandboxContext, SandboxError


def _db_path(ctx: SandboxContext) -> Path:
    return ctx.data_dir / "sandbox.db"


def ensure_database(ctx: SandboxContext) -> None:
    db = _db_path(ctx)
    with sqlite3.connect(db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                body TEXT NOT NULL
            )
            """
        )
        count = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
        if count == 0:
            conn.executemany(
                "INSERT INTO notes (title, body) VALUES (?, ?)",
                [
                    ("公开说明", "这是沙箱内的示例数据，Agent 只能在这里查询。"),
                    ("内部备忘", "请勿将数据库文件复制到 workspace 外。"),
                ],
            )


def query(ctx: SandboxContext, sql: str, params: tuple = ()) -> list[dict]:
    ensure_database(ctx)
    sql_stripped = sql.strip().lower()
    if not sql_stripped.startswith("select"):
        raise SandboxError("query 仅允许 SELECT 语句")
    with sqlite3.connect(_db_path(ctx)) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def execute(ctx: SandboxContext, sql: str, params: tuple = ()) -> str:
    ensure_database(ctx)
    with sqlite3.connect(_db_path(ctx)) as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return f"影响行数: {cursor.rowcount}"
