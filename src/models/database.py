"""FlowPilot -- SQLite database for persistent audit trail and task storage."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path("data/flowpilot.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            date TEXT NOT NULL,
            raw_text TEXT,
            participants TEXT,  -- JSON array
            quality_score REAL DEFAULT 1.0,
            status TEXT DEFAULT 'processed',
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            meeting_id TEXT NOT NULL,
            text TEXT NOT NULL,
            made_by TEXT,
            context TEXT,
            confidence REAL DEFAULT 0.9,
            source_segment_index INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            meeting_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            assignee TEXT,
            status TEXT DEFAULT 'todo',
            priority TEXT DEFAULT 'medium',
            deadline TEXT,
            dependencies TEXT,  -- JSON array
            created_from_action_id TEXT,
            assignment_history TEXT,  -- JSON array
            estimated_hours REAL DEFAULT 4.0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (meeting_id) REFERENCES meetings(id)
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            event_type TEXT NOT NULL,
            agent TEXT NOT NULL,
            description TEXT NOT NULL,
            data TEXT,  -- JSON
            meeting_id TEXT,
            task_id TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS corrections (
            id TEXT PRIMARY KEY,
            agent TEXT NOT NULL,
            correction_type TEXT NOT NULL,
            description TEXT NOT NULL,
            before_state TEXT,  -- JSON
            after_state TEXT,   -- JSON
            meeting_id TEXT,
            timestamp TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT,
            type TEXT NOT NULL,
            recipient TEXT,
            message TEXT NOT NULL,
            sent_at TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def save_meeting(meeting_id: str, title: str, date: str, raw_text: str,
                 participants: list[str], quality_score: float = 1.0):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO meetings (id, title, date, raw_text, participants, quality_score) VALUES (?,?,?,?,?,?)",
        (meeting_id, title, date, raw_text, json.dumps(participants), quality_score),
    )
    conn.commit()
    conn.close()


def save_decision(decision_id: str, meeting_id: str, text: str,
                  made_by: Optional[str], context: str, confidence: float,
                  source_segment_index: Optional[int]):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO decisions (id, meeting_id, text, made_by, context, confidence, source_segment_index) VALUES (?,?,?,?,?,?,?)",
        (decision_id, meeting_id, text, made_by, context, confidence, source_segment_index),
    )
    conn.commit()
    conn.close()


def save_task(task: dict):
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO tasks
        (id, meeting_id, title, description, assignee, status, priority, deadline,
         dependencies, created_from_action_id, assignment_history, estimated_hours, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            task["id"], task.get("meeting_id"), task["title"], task.get("description", ""),
            task.get("assignee"), task.get("status", "todo"), task.get("priority", "medium"),
            task.get("deadline"), json.dumps(task.get("dependencies", [])),
            task.get("created_from_action_id"),
            json.dumps(task.get("assignment_history", [])),
            task.get("estimated_hours", 4.0),
            task.get("created_at", datetime.now().isoformat()),
            datetime.now().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def save_audit_event(event: dict):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_events (id, event_type, agent, description, data, meeting_id, task_id, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (
            event["id"], event["event_type"], event["agent"], event["description"],
            json.dumps(event.get("data", {})), event.get("meeting_id"),
            event.get("task_id"), event.get("timestamp", datetime.now().isoformat()),
        ),
    )
    conn.commit()
    conn.close()


def save_correction(correction: dict):
    conn = get_connection()
    conn.execute(
        "INSERT INTO corrections (id, agent, correction_type, description, before_state, after_state, meeting_id, timestamp) VALUES (?,?,?,?,?,?,?,?)",
        (
            correction["id"], correction["agent"], correction["correction_type"],
            correction["description"], json.dumps(correction.get("before_state", {})),
            json.dumps(correction.get("after_state", {})), correction.get("meeting_id"),
            correction.get("timestamp", datetime.now().isoformat()),
        ),
    )
    conn.commit()
    conn.close()


def get_all_meetings() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_tasks() -> list[dict]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM tasks ORDER BY created_at DESC").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["dependencies"] = json.loads(d.get("dependencies") or "[]")
        d["assignment_history"] = json.loads(d.get("assignment_history") or "[]")
        results.append(d)
    return results


def get_audit_trail(meeting_id: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    if meeting_id:
        rows = conn.execute(
            "SELECT * FROM audit_events WHERE meeting_id = ? ORDER BY timestamp", (meeting_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 200").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["data"] = json.loads(d.get("data") or "{}")
        results.append(d)
    return results


def get_corrections(meeting_id: Optional[str] = None) -> list[dict]:
    conn = get_connection()
    if meeting_id:
        rows = conn.execute(
            "SELECT * FROM corrections WHERE meeting_id = ? ORDER BY timestamp", (meeting_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM corrections ORDER BY timestamp DESC LIMIT 100").fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        d["before_state"] = json.loads(d.get("before_state") or "{}")
        d["after_state"] = json.loads(d.get("after_state") or "{}")
        results.append(d)
    return results


# Initialize on import
init_db()
