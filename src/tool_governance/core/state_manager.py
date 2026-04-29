"""Session state management — create, load, update, persist."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from typing import Any

from tool_governance.models.state import LoadedSkillInfo, SessionState
from tool_governance.storage.sqlite_store import SQLiteStore


def discover_session_id(input_data: dict[str, Any] | None = None) -> str:
    """Discover session ID using priority chain (design D2).

    Priority: input.session_id → input.sessionId → input.conversation_id
    → env CLAUDE_SESSION_ID → auto-generate from PID+timestamp.

    Always returns a non-empty string — the auto-generate fallback
    ensures this function never fails.

    Contract:
        Silences:
            - Missing dict keys in ``input_data`` are silently skipped
              via ``.get()``.  Falsy values (empty string, ``None``,
              ``0``) are treated the same as absent keys.
            - A missing ``CLAUDE_SESSION_ID`` env var is silently
              skipped; the caller gets an auto-generated ID with no
              indication that the env var was expected.
    """
    if input_data:
        for key in ("session_id", "sessionId", "conversation_id"):
            val = input_data.get(key)
            if val:
                return str(val)

    env_val = os.environ.get("CLAUDE_SESSION_ID")
    if env_val:
        return env_val

    # Fallback: PID + epoch seconds gives a locally-unique ID that is
    # stable within a single process lifetime.
    return f"auto-{os.getpid()}-{int(time.time())}"


class StateManager:
    """Manages session-level governance state lifecycle.

    Wraps a SQLiteStore to load/save ``SessionState`` and provides
    helpers that mutate the in-memory state (the caller is responsible
    for calling ``save()`` afterwards to persist changes).
    """

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

    def load_or_init(self, session_id: str) -> SessionState:
        """Load existing state from SQLite or create a new one.

        Contract:
            Raises:
                pydantic.ValidationError: If the stored JSON is
                    present but does not match the ``SessionState``
                    schema (from ``model_validate``, not caught).

            Silences:
                - If no row exists for ``session_id``,
                  ``load_session`` returns ``None`` and a fresh
                  ``SessionState`` is silently created.  The caller
                  cannot distinguish "new session" from "store was
                  wiped" without inspecting ``created_at``.
        """
        data = self._store.load_session(session_id)
        if data is not None:
            return SessionState.model_validate(data)
        now = datetime.utcnow()
        return SessionState(session_id=session_id, created_at=now, updated_at=now)

    def save(self, state: SessionState) -> None:
        """Persist state to SQLite, updating the timestamp.

        Side effect: mutates ``state.updated_at`` to ``utcnow()``
        before serialising.

        Stage C3 of ``separate-runtime-and-persisted-state`` narrowed
        this path from a full ``model_dump_json()`` to
        ``SessionState.to_persisted_dict()``.  Stage D of
        ``migrate-entrypoints-to-runtime-flow`` expanded the exclusion
        set to include both ``active_tools`` and ``skills_metadata``
        after all MCP / LangChain entry points migrated to reading from
        ``RuntimeContext`` instead of the persisted mirror.  Legacy rows
        written before the narrowing still load cleanly: pydantic's
        default ``extra="ignore"`` handling silently drops any
        obsolete keys on ``model_validate``.

        Contract:
            Raises:
                sqlite3.OperationalError: If the database file is
                    locked or unwritable (from ``save_session``,
                    not caught).
        """
        state.updated_at = datetime.utcnow()
        payload = state.to_persisted_dict()
        self._store.save_session(state.session_id, json.dumps(payload))

    def add_to_skills_loaded(
        self, state: SessionState, skill_id: str, version: str = "1.0.0"
    ) -> None:
        """Add a skill to the loaded set.  Idempotent — no-op if
        ``skill_id`` is already present.
        """
        if skill_id not in state.skills_loaded:
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

    def remove_from_skills_loaded(self, state: SessionState, skill_id: str) -> None:
        """Remove a skill from the loaded set and its grant (if any).

        ``state.active_grants`` is keyed by **skill_id** — see
        ``models/state.py::SessionState.active_grants``.  At most one
        active Grant exists per ``(session_id, skill_id)`` pair, so a
        single ``pop(skill_id, None)`` is sufficient to detach the
        grant record from the session state.  The authoritative
        ``grant_id`` lives inside the stored ``Grant`` object and on
        the DB row, not as the dict key.
        """
        state.skills_loaded.pop(skill_id, None)
        state.active_grants.pop(skill_id, None)

    def get_active_tools(self, state: SessionState) -> list[str]:
        """Return current active_tools list."""
        return list(state.active_tools)
