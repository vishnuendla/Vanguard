from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import DATABASE_PATH
from app.engine import utc_now


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or DATABASE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize(path: Path | None = None) -> None:
    with connect(path) as db:
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
            """
        )


def status_map(path: Path | None = None) -> dict[str, str]:
    with connect(path) as db:
        rows = db.execute("SELECT * FROM incident_status")
        return {row["vendor_id"]: row["status"] for row in rows}


def update_status(
    incident_id: str, vendor_id: str, new_status: str, actor: str, rationale: str,
    path: Path | None = None,
) -> dict[str, str | int]:
    with connect(path) as db:
        row = db.execute(
            "SELECT status FROM incident_status WHERE vendor_id = ?", (vendor_id,)
        ).fetchone()
        old_status = row["status"] if row else "new"
        now = utc_now()
        db.execute(
            "INSERT INTO incident_status(vendor_id, status, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(vendor_id) DO UPDATE SET status=excluded.status, "
            "updated_at=excluded.updated_at",
            (vendor_id, new_status, now),
        )
        cursor = db.execute(
            "INSERT INTO audit_log(incident_id,actor,old_status,new_status,rationale,created_at) "
            "VALUES(?,?,?,?,?,?)",
            (incident_id, actor, old_status, new_status, rationale, now),
        )
        event_id = cursor.lastrowid
    return {
        "id": event_id, "incident_id": incident_id, "actor": actor,
        "old_status": old_status, "new_status": new_status,
        "rationale": rationale, "created_at": now,
    }


def audit_events(path: Path | None = None, incident_id: str | None = None) -> list[dict]:
    query = "SELECT * FROM audit_log"
    args: tuple[str, ...] = ()
    if incident_id:
        query += " WHERE incident_id = ?"
        args = (incident_id,)
    query += " ORDER BY id DESC LIMIT 200"
    with connect(path) as db:
        return [dict(row) for row in db.execute(query, args)]
