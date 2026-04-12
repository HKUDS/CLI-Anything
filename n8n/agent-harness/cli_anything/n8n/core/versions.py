"""Workflow version tracking — local SQLite storage for snapshots and rollback.

Stores a snapshot of each workflow before any write operation (update, patch, autofix).
Enables viewing history and rolling back to any previous version.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any


DB_DIR = Path.home() / ".cli-anything" / "n8n"
DB_PATH = DB_DIR / "versions.db"


def _connect() -> sqlite3.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(str(DB_DIR), 0o700)
    except OSError:
        pass
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS workflow_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            version_number INTEGER NOT NULL,
            workflow_name TEXT,
            snapshot TEXT NOT NULL,
            trigger TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_wf_versions_wfid
        ON workflow_versions (workflow_id, version_number DESC)
    """)
    conn.commit()
    return conn


def save_snapshot(
    workflow_id: str,
    workflow_data: dict[str, Any],
    trigger: str = "manual",
) -> int:
    """Save a workflow snapshot before modifying it. Returns version number."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT COALESCE(MAX(version_number), 0) FROM workflow_versions WHERE workflow_id = ?",
            (workflow_id,),
        ).fetchone()
        next_version = row[0] + 1

        conn.execute(
            """INSERT INTO workflow_versions
               (workflow_id, version_number, workflow_name, snapshot, trigger, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                workflow_id,
                next_version,
                workflow_data.get("name", ""),
                json.dumps(workflow_data, default=str),
                trigger,
                time.strftime("%Y-%m-%dT%H:%M:%S"),
            ),
        )
        conn.commit()

        # Auto-prune: keep max 50 versions per workflow
        _auto_prune(conn, workflow_id, keep=50)

        return next_version
    finally:
        conn.close()


def _auto_prune(conn: sqlite3.Connection, workflow_id: str, keep: int = 50) -> None:
    """Auto-prune old versions to prevent infinite DB growth."""
    rows = conn.execute(
        "SELECT id FROM workflow_versions WHERE workflow_id = ? ORDER BY version_number DESC",
        (workflow_id,),
    ).fetchall()
    to_delete = [r["id"] for r in rows[keep:]]
    if to_delete:
        placeholders = ",".join("?" for _ in to_delete)
        with conn:
            conn.execute(f"DELETE FROM workflow_versions WHERE id IN ({placeholders})", to_delete)


def list_versions(workflow_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
    """List stored versions for a workflow, newest first."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT id, workflow_id, version_number, workflow_name, trigger, created_at
               FROM workflow_versions
               WHERE workflow_id = ?
               ORDER BY version_number DESC
               LIMIT ?""",
            (workflow_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_version(version_id: int) -> dict[str, Any] | None:
    """Get a specific version by its database ID."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM workflow_versions WHERE id = ?", (version_id,)
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["snapshot"] = json.loads(result["snapshot"])
        except (json.JSONDecodeError, TypeError):
            result["snapshot"] = {}
        return result
    finally:
        conn.close()


def get_snapshot(workflow_id: str, version_number: int) -> dict[str, Any] | None:
    """Get the workflow snapshot for a specific version number."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT snapshot FROM workflow_versions WHERE workflow_id = ? AND version_number = ?",
            (workflow_id, version_number),
        ).fetchone()
        if not row:
            return None
        try:
            return json.loads(row["snapshot"])
        except (json.JSONDecodeError, TypeError):
            return None
    finally:
        conn.close()


def prune_versions(workflow_id: str, *, keep: int = 10) -> int:
    """Delete old versions, keeping only the N most recent. Returns count deleted."""
    conn = _connect()
    try:
        rows = conn.execute(
            """SELECT id FROM workflow_versions
               WHERE workflow_id = ?
               ORDER BY version_number DESC""",
            (workflow_id,),
        ).fetchall()
        to_delete = [r["id"] for r in rows[keep:]]
        if to_delete:
            placeholders = ",".join("?" for _ in to_delete)
            with conn:
                conn.execute(
                    f"DELETE FROM workflow_versions WHERE id IN ({placeholders})",
                    to_delete,
                )
        return len(to_delete)
    finally:
        conn.close()


def stats() -> dict[str, Any]:
    """Get overall version storage stats."""
    conn = _connect()
    try:
        total = conn.execute("SELECT COUNT(*) FROM workflow_versions").fetchone()[0]
        workflows = conn.execute("SELECT COUNT(DISTINCT workflow_id) FROM workflow_versions").fetchone()[0]
        db_size = DB_PATH.stat().st_size if DB_PATH.exists() else 0
        return {"total_versions": total, "workflows_tracked": workflows, "db_size_bytes": db_size, "db_path": str(DB_PATH)}
    finally:
        conn.close()
