"""Database layer — SQLite, stored at ~/.pulse_pm/pulse.db"""
import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Optional

APP_DIR = Path.home() / ".pulse_pm"
DB_PATH = APP_DIR / "pulse.db"


def get_conn() -> sqlite3.Connection:
    APP_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT    NOT NULL UNIQUE,
                category        TEXT,
                priority        INTEGER DEFAULT 3,
                active          INTEGER DEFAULT 1,
                weekly_goal_hrs REAL    DEFAULT 0.0,
                created_at      TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS check_ins (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp       TEXT    DEFAULT (datetime('now','localtime')),
                project_id      INTEGER REFERENCES projects(id),
                status          TEXT    CHECK(status IN ('done','partial','blocked','not_started')),
                note            TEXT,
                energy_level    INTEGER CHECK(energy_level BETWEEN 1 AND 5),
                blocked_reason  TEXT
            );

            CREATE TABLE IF NOT EXISTS work_sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id  INTEGER REFERENCES projects(id),
                start_time  TEXT    NOT NULL,
                end_time    TEXT,
                source      TEXT    DEFAULT 'manual'
            );

            CREATE TABLE IF NOT EXISTS daily_reviews (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                date                TEXT    UNIQUE NOT NULL,
                top_projects        TEXT,
                done_criteria       TEXT,
                time_allocation     TEXT,
                what_moved          TEXT,
                what_blocked        TEXT,
                tomorrow_first      TEXT,
                ai_summary          TEXT,
                created_at          TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS config (
                key     TEXT PRIMARY KEY,
                value   TEXT
            );
        """)


# ── Project helpers ────────────────────────────────────────────────────────────

def get_projects(active_only: bool = True) -> list:
    with get_conn() as conn:
        if active_only:
            return conn.execute(
                "SELECT * FROM projects WHERE active=1 ORDER BY priority, name"
            ).fetchall()
        return conn.execute("SELECT * FROM projects ORDER BY active DESC, priority, name").fetchall()


def add_project(name: str, category: str = "", weekly_goal_hrs: float = 0.0, priority: int = 3) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO projects (name, category, weekly_goal_hrs, priority) VALUES (?,?,?,?)",
            (name.strip(), category.strip(), weekly_goal_hrs, priority),
        )
        return cur.lastrowid


def archive_project(project_id: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE projects SET active=0 WHERE id=?", (project_id,))


def update_project(project_id: int, **kwargs) -> None:
    allowed = {"name", "category", "priority", "weekly_goal_hrs", "active"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE projects SET {set_clause} WHERE id=?",
            (*updates.values(), project_id),
        )


# ── Check-in helpers ───────────────────────────────────────────────────────────

def save_checkin(
    project_id: int,
    status: str,
    note: str = "",
    energy_level: int = 3,
    blocked_reason: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO check_ins
               (project_id, status, note, energy_level, blocked_reason)
               VALUES (?,?,?,?,?)""",
            (project_id, status, note, energy_level, blocked_reason),
        )
        return cur.lastrowid


def get_today_checkins() -> list:
    today = date.today().isoformat()
    with get_conn() as conn:
        return conn.execute(
            """SELECT c.*, p.name as project_name
               FROM check_ins c
               JOIN projects p ON p.id = c.project_id
               WHERE date(c.timestamp) = ?
               ORDER BY c.timestamp""",
            (today,),
        ).fetchall()


def get_checkins_range(start: str, end: str) -> list:
    with get_conn() as conn:
        return conn.execute(
            """SELECT c.*, p.name as project_name
               FROM check_ins c
               JOIN projects p ON p.id = c.project_id
               WHERE date(c.timestamp) BETWEEN ? AND ?
               ORDER BY c.timestamp""",
            (start, end),
        ).fetchall()


# ── Work session helpers ───────────────────────────────────────────────────────

def start_session(project_id: int) -> int:
    # close any open session first
    stop_active_session()
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO work_sessions (project_id, start_time) VALUES (?,?)",
            (project_id, datetime.now().isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def stop_active_session() -> Optional[dict]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM work_sessions WHERE end_time IS NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE work_sessions SET end_time=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), row["id"]),
            )
            return dict(row)
    return None


def get_active_session() -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            """SELECT ws.*, p.name as project_name
               FROM work_sessions ws
               JOIN projects p ON p.id = ws.project_id
               WHERE ws.end_time IS NULL
               ORDER BY ws.id DESC LIMIT 1"""
        ).fetchone()


def get_hours_today() -> dict:
    """Returns {project_id: hours} for today."""
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT project_id,
                      SUM((julianday(COALESCE(end_time, datetime('now','localtime'))) - julianday(start_time)) * 24) as hours
               FROM work_sessions
               WHERE date(start_time) = ?
               GROUP BY project_id""",
            (today,),
        ).fetchall()
    return {r["project_id"]: round(r["hours"] or 0.0, 2) for r in rows}


def get_hours_week() -> dict:
    """Returns {project_id: hours} for this ISO week."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT project_id,
                      SUM((julianday(COALESCE(end_time, datetime('now','localtime'))) - julianday(start_time)) * 24) as hours
               FROM work_sessions
               WHERE strftime('%W-%Y', start_time) = strftime('%W-%Y', 'now', 'localtime')
               GROUP BY project_id"""
        ).fetchall()
    return {r["project_id"]: round(r["hours"] or 0.0, 2) for r in rows}


# ── Daily review helpers ───────────────────────────────────────────────────────

def get_or_create_daily_review(day: str = None) -> sqlite3.Row:
    day = day or date.today().isoformat()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM daily_reviews WHERE date=?", (day,)).fetchone()
        if not row:
            conn.execute("INSERT INTO daily_reviews (date) VALUES (?)", (day,))
            row = conn.execute("SELECT * FROM daily_reviews WHERE date=?", (day,)).fetchone()
        return row


def update_daily_review(day: str, **kwargs) -> None:
    allowed = {"top_projects", "done_criteria", "time_allocation",
               "what_moved", "what_blocked", "tomorrow_first", "ai_summary"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k}=?" for k in updates)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE daily_reviews SET {set_clause} WHERE date=?",
            (*updates.values(), day),
        )


# ── Config helpers ─────────────────────────────────────────────────────────────

def get_config(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default


def set_config(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO config (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
