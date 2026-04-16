"""Tests for GrantManager.

Covers the grant lifecycle: creation with TTL, persistence to SQLite,
revocation, expiry cleanup, validity checking, and multi-grant
queries.  All tests run against a real SQLite store in a temp
directory.
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from tool_governance.core.grant_manager import GrantManager
from tool_governance.storage.sqlite_store import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    """Isolated SQLite store in a temp directory."""
    return SQLiteStore(tmp_path / "data")


@pytest.fixture()
def mgr(store: SQLiteStore) -> GrantManager:
    return GrantManager(store)


class TestCreateGrant:
    def test_creates_grant(self, mgr: GrantManager) -> None:
        """New grant must be active, have the right skill_id, and
        compute a non-None expires_at from the TTL."""
        grant = mgr.create_grant("s1", "repo-read", ["search"], ttl=3600)
        assert grant.skill_id == "repo-read"
        assert grant.status == "active"
        assert grant.expires_at is not None

    def test_grant_persisted(self, mgr: GrantManager, store: SQLiteStore) -> None:
        """Grant must survive a round-trip to SQLite — verifies that
        insert_grant actually writes to the DB."""
        grant = mgr.create_grant("s1", "repo-read", ["search"])
        stored = store.get_grant(grant.grant_id)
        assert stored is not None
        assert stored["skill_id"] == "repo-read"


class TestRevoke:
    def test_revoke_grant(self, mgr: GrantManager) -> None:
        """After revocation, get_active_grants must not return it.
        Verifies the status transition active → revoked."""
        grant = mgr.create_grant("s1", "repo-read", [])
        mgr.revoke_grant(grant.grant_id)
        active = mgr.get_active_grants("s1")
        assert len(active) == 0


class TestCleanupExpired:
    def test_cleanup_expired(self, mgr: GrantManager) -> None:
        """Create a grant in the past with a 1-second TTL (already
        expired by the time cleanup runs).  cleanup_expired must
        mark it and return its skill_id.

        Uses mock to shift create_grant's clock backwards so the
        grant's expires_at is in the past relative to real-now."""
        past = datetime.utcnow() - timedelta(seconds=10)
        with patch("tool_governance.core.grant_manager.datetime") as mock_dt:
            mock_dt.utcnow.return_value = past
            # Allow datetime(...) constructor to still work for timedelta ops.
            mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
            mgr.create_grant("s1", "repo-read", [], ttl=1)

        expired = mgr.cleanup_expired("s1")
        assert "repo-read" in expired

    def test_no_cleanup_for_valid(self, mgr: GrantManager) -> None:
        """A grant with a large TTL must not be expired by cleanup."""
        mgr.create_grant("s1", "repo-read", [], ttl=9999)
        expired = mgr.cleanup_expired("s1")
        assert expired == []


class TestGetActiveGrants:
    def test_multiple_grants(self, mgr: GrantManager) -> None:
        """Multiple grants for different skills in the same session
        must all be returned."""
        mgr.create_grant("s1", "repo-read", [])
        mgr.create_grant("s1", "web-search", [])
        grants = mgr.get_active_grants("s1")
        assert len(grants) == 2

    def test_empty_session(self, mgr: GrantManager) -> None:
        """A session with no grants must return an empty list, not
        None or an error."""
        assert mgr.get_active_grants("s1") == []


class TestIsGrantValid:
    def test_valid_grant(self, mgr: GrantManager) -> None:
        """A freshly-created grant with a large TTL must be valid."""
        mgr.create_grant("s1", "repo-read", [], ttl=9999)
        assert mgr.is_grant_valid("s1", "repo-read") is True

    def test_no_grant(self, mgr: GrantManager) -> None:
        """A skill with no grant at all must report as invalid."""
        assert mgr.is_grant_valid("s1", "repo-read") is False
