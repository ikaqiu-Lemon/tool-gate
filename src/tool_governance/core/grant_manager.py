"""Grant manager — authorization record lifecycle.

Handles the full lifecycle of Grant objects: creation (with TTL
computation), persistence to SQLite, expiry cleanup, revocation,
and validity checks.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta

from typing import Literal

from tool_governance.models.grant import Grant
from tool_governance.storage.sqlite_store import SQLiteStore


class GrantManager:
    """Manages Grant creation, expiration, and revocation."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def create_grant(
        self,
        session_id: str,
        skill_id: str,
        allowed_ops: list[str],
        scope: Literal["turn", "session"] = "session",
        ttl: int = 3600,
        granted_by: Literal["auto", "user", "policy"] = "auto",
        reason: str | None = None,
    ) -> Grant:
        """Create and persist a new grant.

        Contract:
            Preconditions:
                - ``ttl`` should be a positive integer.  If zero or
                  negative, ``expires_at`` is set to a past or current
                  timestamp — the grant is effectively dead on arrival.
                  No error is raised; ``is_grant_valid`` will simply
                  return ``False`` for it.

            Raises:
                sqlite3.OperationalError: If the database is locked or
                    unwritable (from ``insert_grant``, not caught).
        """
        now = datetime.utcnow()
        grant = Grant(
            grant_id=str(uuid.uuid4()),
            session_id=session_id,
            skill_id=skill_id,
            allowed_ops=allowed_ops,
            scope=scope,
            ttl_seconds=ttl,
            status="active",
            granted_by=granted_by,
            reason=reason,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl),
        )
        # Serialise to a flat dict for the SQLite row.  ``allowed_ops``
        # is JSON-encoded because SQLite has no array column type.
        self._store.insert_grant(
            {
                "grant_id": grant.grant_id,
                "session_id": grant.session_id,
                "skill_id": grant.skill_id,
                "allowed_ops": json.dumps(grant.allowed_ops),
                "scope": grant.scope,
                "ttl_seconds": grant.ttl_seconds,
                "status": grant.status,
                "granted_by": grant.granted_by,
                "reason": grant.reason,
                "created_at": grant.created_at.isoformat(),
                "expires_at": grant.expires_at.isoformat() if grant.expires_at else None,
            }
        )
        return grant

    def revoke_grant(self, grant_id: str, reason: str = "explicit") -> None:
        """Revoke a specific grant and emit a ``grant.revoke`` audit event.

        The audit record is emitted once per revocation with
        ``session_id`` and ``skill_id`` resolved from the stored row
        and ``detail={"grant_id": ..., "reason": reason}``.  ``reason``
        is a free-form discriminator — callers currently pass
        ``"explicit"`` (from ``disable_skill`` paths).  Lifecycle
        expiry takes a different path (``cleanup_expired`` transitions
        status to ``"expired"`` and emits ``grant.expire``), so
        ``grant.revoke`` and ``grant.expire`` never fire for the same
        grant.

        Contract:
            Silences:
                - If ``grant_id`` does not exist in the store, the
                  status update is a no-op and no audit event is
                  emitted.  The caller has no return value to detect
                  this.
        """
        row = self._store.get_grant(grant_id)
        self._store.update_grant_status(grant_id, "revoked")
        if row is not None:
            self._store.append_audit(
                row["session_id"],
                "grant.revoke",
                skill_id=row["skill_id"],
                detail={"grant_id": grant_id, "reason": reason},
            )

    def cleanup_expired(self, session_id: str) -> list[str]:
        """Mark expired grants and return their skill_ids.

        Scans all grants with status ``"active"`` for this session and
        transitions any whose ``expires_at`` is in the past to
        ``"expired"``.

        Contract:
            Raises:
                ValueError: If a stored ``expires_at`` string is not a
                    valid ISO-8601 timestamp (from
                    ``datetime.fromisoformat``, not caught).

            Silences:
                - Grants with no ``expires_at`` (NULL / missing key)
                  are silently skipped — they never expire and are
                  never included in the returned list.
        """
        now = datetime.utcnow()
        expired_skill_ids: list[str] = []
        active = self._store.get_active_grants(session_id)
        for row in active:
            expires_at_str = row.get("expires_at")
            # Grants without an expiry timestamp are treated as
            # perpetual — skip them.
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                if now >= expires_at:
                    self._store.update_grant_status(row["grant_id"], "expired")
                    expired_skill_ids.append(row["skill_id"])
        return expired_skill_ids

    def get_active_grants(self, session_id: str) -> list[Grant]:
        """Return all active grants for a session.

        Reconstructs ``Grant`` objects from raw SQLite rows.  Note that
        "active" here means ``status = 'active'`` in the DB — the
        grant may still be past its ``expires_at`` if
        ``cleanup_expired`` hasn't run yet.

        Contract:
            Raises:
                KeyError: If a row is missing any required field
                    (``grant_id``, ``session_id``, ``skill_id``, etc.)
                    — implicit, from dict subscription.
                ValueError: If ``allowed_ops`` contains invalid JSON,
                    or if ``created_at`` / ``expires_at`` strings are
                    not valid ISO-8601 (from ``json.loads`` /
                    ``datetime.fromisoformat``, not caught).

            Silences:
                - A missing ``reason`` key is silently defaulted to
                  ``None`` via ``.get("reason")``.
                - A missing ``expires_at`` is silently defaulted to
                  ``None`` via ``.get("expires_at")``.
        """
        rows = self._store.get_active_grants(session_id)
        grants: list[Grant] = []
        for row in rows:
            grants.append(
                Grant(
                    grant_id=row["grant_id"],
                    session_id=row["session_id"],
                    skill_id=row["skill_id"],
                    allowed_ops=json.loads(row["allowed_ops"]),
                    scope=row["scope"],
                    ttl_seconds=row["ttl_seconds"],
                    status=row["status"],
                    granted_by=row["granted_by"],
                    reason=row.get("reason"),
                    created_at=datetime.fromisoformat(row["created_at"]),
                    expires_at=datetime.fromisoformat(row["expires_at"]) if row.get("expires_at") else None,
                )
            )
        return grants

    def is_grant_valid(self, session_id: str, skill_id: str) -> bool:
        """Check if the skill has a valid (active, non-expired) grant.

        Queries the DB for all active grants, then checks whether any
        matching grant's ``expires_at`` is still in the future (or
        absent, meaning perpetual).

        Contract:
            Raises:
                ValueError: If a stored ``expires_at`` string is not
                    valid ISO-8601 (from ``datetime.fromisoformat``,
                    not caught).

            Silences:
                - Grants whose ``expires_at`` is ``None`` / missing
                  are treated as perpetually valid — returns ``True``
                  immediately.
                - If multiple grants exist for the same skill, the
                  first valid one short-circuits; remaining grants
                  are not examined.
        """
        now = datetime.utcnow()
        active = self._store.get_active_grants(session_id)
        for row in active:
            if row["skill_id"] == skill_id:
                expires_at_str = row.get("expires_at")
                if expires_at_str:
                    if now < datetime.fromisoformat(expires_at_str):
                        return True
                else:
                    # No expiry — grant is perpetually valid.
                    return True
        return False
