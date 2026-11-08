import os
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.services.validation_service import run_validation

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "reviews.db"
WRITE_LOCK = Lock()

ROLES = {"preparer", "reviewer", "partner"}
STATUSES = {"open", "in_review", "resolved", "escalated"}

PERMISSIONS = {
    "preparer": {"open", "in_review", "escalated"},
    "reviewer": STATUSES,
    "partner": STATUSES,
}


class ReviewError(Exception):
    def __init__(self, message, status_code=400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def connect():
    path = Path(os.environ.get("REVIEW_DB_PATH", str(DB_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)

    from app.workflow_connection import WorkflowConnection
    connection = sqlite3.connect(
        path,
        timeout=10,
        isolation_level=None,
        factory=WorkflowConnection,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database():
    with connect() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS reviews (
                version TEXT NOT NULL,
                finding_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                note TEXT NOT NULL DEFAULT '',
                updated_by TEXT,
                updated_at TEXT,
                PRIMARY KEY (version, finding_id)
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS review_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL,
                finding_id TEXT NOT NULL,
                previous_status TEXT NOT NULL,
                new_status TEXT NOT NULL,
                note TEXT NOT NULL,
                actor_role TEXT NOT NULL,
                actor_name TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

    from app.migrate import migrate
    with connect() as db:
        migrate(db)


def review_catalog(version):
    from app.services.finding_service import build_catalog
    base = run_validation(version)
    return build_catalog(version, legacy=base) if base is not None else None


def get_valid_finding(version, finding_id):
    validation = review_catalog(version)

    if validation is None:
        raise ReviewError("Return version not found", 404)

    finding = next(
        (item for item in validation["findings"] if item["id"] == finding_id or finding_id in item.get("aliases",[])),
        None,
    )

    if finding is None:
        raise ReviewError("Finding not found", 404)

    return finding


def list_reviews(version="v3"):
    validation = review_catalog(version)

    if validation is None:
        raise ReviewError("Return version not found", 404)

    initialize_database()

    with connect() as db:
        rows = db.execute(
            "SELECT * FROM reviews WHERE version = ?",
            (version,),
        ).fetchall()

    saved = {row["finding_id"]: dict(row) for row in rows}

    findings = []

    for item in validation["findings"]:
        review = saved.get(item["id"])

        findings.append(
            {
                **item,
                "status": review["status"] if review else "open",
                "review_note": review["note"] if review else "",
                "updated_by": review["updated_by"] if review else None,
                "updated_at": review["updated_at"] if review else None,
            }
        )

    return {
        "version": version,
        "total": len(findings),
        "findings": findings,
        "status_counts": {
            status: sum(item["status"] == status for item in findings)
            for status in sorted(STATUSES)
        },
    }


def update_review(
    version,
    finding_id,
    status,
    note,
    actor_role,
    actor_name,
    audit_details=None,
):
    finding_id = get_valid_finding(version, finding_id)["id"]

    if actor_role not in ROLES:
        raise ReviewError("Invalid reviewer role")

    if status not in STATUSES:
        raise ReviewError("Invalid review status")

    if status not in PERMISSIONS[actor_role]:
        raise ReviewError(
            "This demo role cannot set that status",
            403,
        )

    actor_name = actor_name.strip()
    note = note.strip()

    if not actor_name:
        raise ReviewError("Reviewer name is required")

    if not note:
        raise ReviewError("A review note is required")

    if len(actor_name) > 120 or len(note) > 4000:
        raise ReviewError("Review text exceeds allowed length")

    initialize_database()

    timestamp = datetime.now(timezone.utc).isoformat()

    with WRITE_LOCK:
        with connect() as db:
            db.execute("BEGIN IMMEDIATE")

            previous = db.execute(
                """
                SELECT status
                FROM reviews
                WHERE version = ? AND finding_id = ?
                """,
                (version, finding_id),
            ).fetchone()

            previous_status = previous["status"] if previous else "open"

            db.execute(
                """
                INSERT INTO reviews (
                    version, finding_id, status,
                    note, updated_by, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(version, finding_id)
                DO UPDATE SET
                    status = excluded.status,
                    note = excluded.note,
                    updated_by = excluded.updated_by,
                    updated_at = excluded.updated_at
                """,
                (
                    version,
                    finding_id,
                    status,
                    note,
                    f"{actor_name} ({actor_role})",
                    timestamp,
                ),
            )

            cursor = db.execute(
                """
                INSERT INTO review_events (
                    version, finding_id, previous_status,
                    new_status, note, actor_role,
                    actor_name, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version,
                    finding_id,
                    previous_status,
                    status,
                    note,
                    actor_role,
                    actor_name,
                    timestamp,
                ),
            )

            event_id = cursor.lastrowid
            if audit_details is not None:
                from app.services.reconciliation_workflow import append_decision
                append_decision(db,version,finding_id,event_id,audit_details,timestamp)
            db.commit()

    return {
        "event_id": event_id,
        "version": version,
        "finding_id": finding_id,
        "previous_status": previous_status,
        "status": status,
        "note": note,
        "actor_role": actor_role,
        "actor_name": actor_name,
        "updated_at": timestamp,
    }


def get_review_history(version, finding_id):
    finding_id = get_valid_finding(version, finding_id)["id"]
    initialize_database()

    with connect() as db:
        rows = db.execute(
            """
            SELECT *
            FROM review_events
            WHERE version = ? AND finding_id = ?
            ORDER BY id ASC
            """,
            (version, finding_id),
        ).fetchall()

    return {
        "version": version,
        "finding_id": finding_id,
        "events": [dict(row) for row in rows],
    }
