"""SQLite-based persistent storage for sessions, grants, and audit logs.

Single-file database (``governance.db``) using WAL journal mode for
concurrent read access.  Each public method opens its own connection
(no connection pooling), which is safe for single-process use but
means every call pays the connection overhead.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS grants (
    grant_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    allowed_ops TEXT NOT NULL,
    scope TEXT NOT NULL,
    ttl_seconds INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    granted_by TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    skill_id TEXT,
    tool_name TEXT,
    decision TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_grants_session ON grants(session_id, status);
CREATE INDEX IF NOT EXISTS idx_audit_session ON audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
"""


class SQLiteStore:
    """Persistent storage backed by SQLite with WAL journal mode.

    Contract:
        Raises:
            sqlite3.OperationalError: From the constructor if the
                ``data_dir`` cannot be created or the database file
                cannot be opened / initialised.
    """

    def __init__(self, data_dir: str | Path) -> None:
        self._data_dir = Path(data_dir)
        # Create the directory tree if it doesn't exist.
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._data_dir / "governance.db"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        """Open a new connection with Row factory.

        Uses a 5-second timeout for acquiring the write lock.
        """
        conn = sqlite3.connect(str(self._db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables and indices if they don't already exist.

        Enables WAL journal mode and sets a 5-second busy timeout
        to reduce ``SQLITE_BUSY`` errors under contention.
        """
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=5000")
            conn.executescript(_SCHEMA_SQL)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    def load_session(self, session_id: str) -> dict[str, Any] | None:
        """Load session state JSON. Returns ``None`` if not found.

        Contract:
            Raises:
                json.JSONDecodeError: If the stored ``state_json``
                    is not valid JSON (from ``json.loads``,
                    not caught).
                sqlite3.OperationalError: If the database is locked
                    or corrupt (not caught).
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT state_json FROM sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row["state_json"])  # type: ignore[no-any-return]

    def save_session(self, session_id: str, state_json: str) -> None:
        """Upsert session state.

        Uses ``INSERT ... ON CONFLICT DO UPDATE`` so that the first
        call creates the row and subsequent calls only update
        ``state_json`` and ``updated_at`` (``created_at`` is
        preserved after the initial insert).

        Contract:
            Preconditions:
                - ``state_json`` should be valid JSON.  The column is
                  ``TEXT`` so SQLite will store anything, but
                  ``load_session`` will fail on non-JSON content.

            Raises:
                sqlite3.OperationalError: If the database is locked
                    or the disk is full (not caught).
        """
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO sessions (session_id, state_json, created_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at""",
                (session_id, state_json, now, now),
            )

    # ------------------------------------------------------------------
    # Grants
    # ------------------------------------------------------------------

    def insert_grant(self, grant_data: dict[str, Any]) -> None:
        """Insert a new grant row.

        Contract:
            Preconditions:
                - ``grant_data`` must contain all named bind
                  parameters (``:grant_id``, ``:session_id``, etc.).
                  Missing keys raise ``sqlite3.ProgrammingError``
                  (implicit).

            Raises:
                sqlite3.IntegrityError: If ``grant_id`` already
                    exists (PRIMARY KEY violation, not caught).
        """
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO grants
                   (grant_id, session_id, skill_id, allowed_ops, scope, ttl_seconds, status, granted_by, reason, created_at, expires_at)
                   VALUES (:grant_id, :session_id, :skill_id, :allowed_ops, :scope, :ttl_seconds, :status, :granted_by, :reason, :created_at, :expires_at)""",
                grant_data,
            )

    def update_grant_status(self, grant_id: str, status: str) -> None:
        """Update a grant's status.

        Contract:
            Silences:
                - If ``grant_id`` does not exist, zero rows are
                  updated — no error is raised and the caller has
                  no return value to detect this.
        """
        with self._connect() as conn:
            conn.execute(
                "UPDATE grants SET status = ? WHERE grant_id = ?",
                (status, grant_id),
            )

    def get_active_grants(self, session_id: str) -> list[dict[str, Any]]:
        """Return all grants with ``status='active'`` for a session.

        Note: "active" is purely a DB status flag.  Grants past their
        ``expires_at`` are still returned here until
        ``cleanup_expired`` transitions them to ``"expired"``.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM grants WHERE session_id = ? AND status = 'active'",
                (session_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_grant(self, grant_id: str) -> dict[str, Any] | None:
        """Return a single grant by ID, or ``None`` if not found."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM grants WHERE grant_id = ?",
                (grant_id,),
            ).fetchone()
        return dict(row) if row else None

    # ------------------------------------------------------------------
    # Audit log (append-only)
    # ------------------------------------------------------------------

    def append_audit(
        self,
        session_id: str,
        event_type: str,
        skill_id: str | None = None,
        tool_name: str | None = None,
        decision: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        """Append an entry to the audit log.

        The ``detail`` dict is JSON-serialised into the ``detail``
        TEXT column; ``None`` is stored as SQL NULL.

        Contract:
            Raises:
                sqlite3.OperationalError: If the database is locked
                    or the disk is full (not caught).
        """
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO audit_log (timestamp, session_id, event_type, skill_id, tool_name, decision, detail, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now,
                    session_id,
                    event_type,
                    skill_id,
                    tool_name,
                    decision,
                    json.dumps(detail) if detail else None,
                    now,
                ),
            )

    def query_audit(
        self,
        session_id: str | None = None,
        event_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Query audit log with optional filters.

        Contract:
            Silences:
                - Falsy ``session_id`` or ``event_type`` (empty
                  string, ``None``) are treated as "no filter" —
                  the corresponding WHERE clause is omitted.  An
                  empty string is indistinguishable from ``None``
                  here, which may be surprising if the caller
                  intended to match literally-empty values.
        """
        clauses: list[str] = []
        params: list[str] = []
        if session_id:
            clauses.append("session_id = ?")
            params.append(session_id)
        if event_type:
            clauses.append("event_type = ?")
            params.append(event_type)
        where = " AND ".join(clauses) if clauses else "1=1"
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM audit_log WHERE {where} ORDER BY timestamp",
                params,
            ).fetchall()
        return [dict(r) for r in rows]
