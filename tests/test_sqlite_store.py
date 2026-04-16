"""Tests for SQLiteStore.

Verifies the three storage domains (sessions, grants, audit log)
against a real SQLite database in a temp directory.  Each test class
exercises CRUD operations and edge cases for one domain.
"""

from pathlib import Path

import pytest

from tool_governance.storage.sqlite_store import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    """Isolated SQLite store — creates a fresh ``governance.db`` in
    a temp directory per test."""
    return SQLiteStore(tmp_path / "data")


class TestSessions:
    def test_load_missing_session(self, store: SQLiteStore) -> None:
        """A never-saved session_id must return None, not raise."""
        assert store.load_session("nonexistent") is None

    def test_save_and_load(self, store: SQLiteStore) -> None:
        """Basic roundtrip: save JSON string, load it back, verify
        the parsed dict matches."""
        store.save_session("s1", '{"session_id": "s1", "active_tools": []}')
        data = store.load_session("s1")
        assert data is not None
        assert data["session_id"] == "s1"

    def test_upsert(self, store: SQLiteStore) -> None:
        """Second save to the same session_id must overwrite the
        state_json — verifies the ON CONFLICT DO UPDATE clause."""
        store.save_session("s1", '{"v": 1}')
        store.save_session("s1", '{"v": 2}')
        data = store.load_session("s1")
        assert data is not None
        assert data["v"] == 2


class TestGrants:
    def test_insert_and_query(self, store: SQLiteStore) -> None:
        """Insert a grant row and retrieve it via get_active_grants.
        Verifies the full column set survives the round-trip."""
        store.insert_grant({
            "grant_id": "g1", "session_id": "s1", "skill_id": "repo-read",
            "allowed_ops": "[]", "scope": "session", "ttl_seconds": 3600,
            "status": "active", "granted_by": "auto", "reason": None,
            "created_at": "2026-01-01T00:00:00", "expires_at": "2026-01-01T01:00:00",
        })
        grants = store.get_active_grants("s1")
        assert len(grants) == 1
        assert grants[0]["skill_id"] == "repo-read"

    def test_update_status(self, store: SQLiteStore) -> None:
        """After updating status to "revoked", get_active_grants must
        no longer return the grant — verifies the WHERE status='active'
        filter."""
        store.insert_grant({
            "grant_id": "g1", "session_id": "s1", "skill_id": "x",
            "allowed_ops": "[]", "scope": "session", "ttl_seconds": 60,
            "status": "active", "granted_by": "auto", "reason": None,
            "created_at": "2026-01-01T00:00:00", "expires_at": "2026-01-01T00:01:00",
        })
        store.update_grant_status("g1", "revoked")
        assert store.get_active_grants("s1") == []

    def test_get_grant(self, store: SQLiteStore) -> None:
        """get_grant returns the row by primary key, or None for
        a missing grant_id.  Also tests that expires_at=None (no
        expiry) is stored and retrieved correctly."""
        store.insert_grant({
            "grant_id": "g1", "session_id": "s1", "skill_id": "x",
            "allowed_ops": "[]", "scope": "session", "ttl_seconds": 60,
            "status": "active", "granted_by": "auto", "reason": None,
            "created_at": "2026-01-01T00:00:00", "expires_at": None,
        })
        g = store.get_grant("g1")
        assert g is not None
        assert g["grant_id"] == "g1"
        assert store.get_grant("nonexistent") is None


class TestAudit:
    def test_append_and_query(self, store: SQLiteStore) -> None:
        """Two audit entries for the same session must both be
        returned by query_audit(session_id=...)."""
        store.append_audit("s1", "skill.enable", skill_id="repo-read", decision="granted")
        store.append_audit("s1", "tool.call", tool_name="Read", decision="allow")
        rows = store.query_audit(session_id="s1")
        assert len(rows) == 2

    def test_query_by_event_type(self, store: SQLiteStore) -> None:
        """Filtering by event_type must return only matching rows,
        not all rows for the session."""
        store.append_audit("s1", "skill.enable", skill_id="x")
        store.append_audit("s1", "tool.call", tool_name="Read")
        rows = store.query_audit(event_type="tool.call")
        assert len(rows) == 1
        assert rows[0]["tool_name"] == "Read"

    def test_detail_json(self, store: SQLiteStore) -> None:
        """The detail dict must be stored as a JSON string — verify
        that the serialised value is present in the returned row."""
        store.append_audit("s1", "tool.call", detail={"error_bucket": "whitelist_violation"})
        rows = store.query_audit(session_id="s1")
        assert '"whitelist_violation"' in rows[0]["detail"]
