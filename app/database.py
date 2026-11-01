from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from app.clock import utc_now
from app.config import DATABASE_PATH

MAX_AUDIT_ROWS = 200


class StatusConflictError(Exception):
    """Raised when a triage update would not change the current status."""

    def __init__(self, current_status: str) -> None:
        self.current_status = current_status
        super().__init__(f"Incident already has status '{current_status}'")


def connect(path: Path | None = None) -> sqlite3.Connection:
    database_path = path or DATABASE_PATH
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def initialize(path: Path | None = None) -> None:
    with closing(connect(path)) as db:
        db.execute("PRAGMA journal_mode = WAL")
        with db:
            db.executescript(
                """
            CREATE TABLE IF NOT EXISTS incident_status (
                vendor_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK(status IN ('new','reviewed','relevant','dismissed')),
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                actor TEXT NOT NULL,
                old_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                rationale TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_audit_log_incident
                ON audit_log(incident_id, id DESC);
            """
            )


def status_map(path: Path | None = None) -> dict[str, str]:
    with closing(connect(path)) as db:
        rows = db.execute("SELECT * FROM incident_status")
        return {row["vendor_id"]: row["status"] for row in rows}


def update_status(
    incident_id: str,
    vendor_id: str,
    new_status: str,
    actor: str,
    rationale: str,
    path: Path | None = None,
) -> dict[str, Any]:
    with closing(connect(path)) as db:
        # Reserve the write lock before reading so concurrent updates observe a serialized
        # status history instead of both recording the same stale old_status.
        db.execute("BEGIN IMMEDIATE")
        with db:
            row = db.execute(
                "SELECT status FROM incident_status WHERE vendor_id = ?", (vendor_id,)
            ).fetchone()
            old_status = row["status"] if row else "new"
            if old_status == new_status:
                raise StatusConflictError(old_status)

            now = utc_now()
            db.execute(
                "INSERT INTO incident_status(vendor_id, status, updated_at) VALUES(?,?,?) "
                "ON CONFLICT(vendor_id) DO UPDATE SET status=excluded.status, "
                "updated_at=excluded.updated_at",
                (vendor_id, new_status, now),
            )
            cursor = db.execute(
                "INSERT INTO audit_log(incident_id, actor, old_status, new_status, rationale, "
                "created_at) "
                "VALUES(?,?,?,?,?,?)",
                (incident_id, actor, old_status, new_status, rationale, now),
            )
            event_id = cursor.lastrowid

    return {
        "id": event_id,
        "incident_id": incident_id,
        "actor": actor,
        "old_status": old_status,
        "new_status": new_status,
        "rationale": rationale,
        "created_at": now,
    }


def audit_events(
    path: Path | None = None,
    incident_id: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    limit = max(1, min(limit, MAX_AUDIT_ROWS))
    query = "SELECT * FROM audit_log"
    params: tuple[Any, ...] = ()
    if incident_id:
        query += " WHERE incident_id = ?"
        params = (incident_id,)
    query += " ORDER BY id DESC LIMIT ?"
    params += (limit,)
    with closing(connect(path)) as db:
        return [dict(row) for row in db.execute(query, params)]
