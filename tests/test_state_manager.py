"""Tests for StateManager.

Covers the session-id discovery priority chain and the StateManager's
load/save/add/remove lifecycle against a real SQLite store in a temp
directory.
"""

from pathlib import Path

import pytest

from tool_governance.core.state_manager import StateManager, discover_session_id
from tool_governance.storage.sqlite_store import SQLiteStore


@pytest.fixture()
def store(tmp_path: Path) -> SQLiteStore:
    """Provides an isolated SQLiteStore in a temp directory."""
    return SQLiteStore(tmp_path / "data")


@pytest.fixture()
def mgr(store: SQLiteStore) -> StateManager:
    return StateManager(store)


class TestDiscoverSessionId:
    """Tests the priority chain: session_id > sessionId >
    conversation_id > env > auto-generate."""

    def test_from_input_session_id(self) -> None:
        assert discover_session_id({"session_id": "abc"}) == "abc"

    def test_from_input_camelcase(self) -> None:
        """Ensures the camelCase variant is also recognised (clients
        may use either convention)."""
        assert discover_session_id({"sessionId": "xyz"}) == "xyz"

    def test_from_input_conversation_id(self) -> None:
        assert discover_session_id({"conversation_id": "conv1"}) == "conv1"

    def test_priority_order(self) -> None:
        """session_id must win over sessionId when both are present."""
        assert discover_session_id({"session_id": "a", "sessionId": "b"}) == "a"

    def test_auto_generate(self) -> None:
        """Empty dict triggers auto-generation (PID + timestamp)."""
        sid = discover_session_id({})
        assert sid.startswith("auto-")

    def test_none_input(self) -> None:
        """None input must not crash — falls through to auto-generate."""
        sid = discover_session_id(None)
        assert sid.startswith("auto-")


class TestStateManager:
    def test_init_new_state(self, mgr: StateManager) -> None:
        """A never-seen session_id must produce a fresh, empty state."""
        state = mgr.load_or_init("new-session")
        assert state.session_id == "new-session"
        assert state.skills_loaded == {}

    def test_save_and_load(self, mgr: StateManager) -> None:
        """Save → load roundtrip through SQLite must preserve the
        skills_loaded dict.  Guards against JSON serialisation bugs
        in SessionState."""
        state = mgr.load_or_init("s1")
        mgr.add_to_skills_loaded(state, "repo-read", "1.0.0")
        mgr.save(state)

        restored = mgr.load_or_init("s1")
        assert "repo-read" in restored.skills_loaded

    def test_add_and_remove_skills(self, mgr: StateManager) -> None:
        state = mgr.load_or_init("s1")
        mgr.add_to_skills_loaded(state, "repo-read")
        assert "repo-read" in state.skills_loaded

        mgr.remove_from_skills_loaded(state, "repo-read")
        assert "repo-read" not in state.skills_loaded

    def test_add_duplicate_no_overwrite(self, mgr: StateManager) -> None:
        """Adding an already-loaded skill must NOT overwrite the
        existing LoadedSkillInfo — this preserves the current_stage
        and last_used_at set by the user.  Regression guard for the
        idempotency check in add_to_skills_loaded."""
        state = mgr.load_or_init("s1")
        mgr.add_to_skills_loaded(state, "repo-read", "1.0.0")
        state.skills_loaded["repo-read"].current_stage = "analysis"
        # Second add with a different version should be a no-op.
        mgr.add_to_skills_loaded(state, "repo-read", "2.0.0")
        assert state.skills_loaded["repo-read"].current_stage == "analysis"

    def test_get_active_tools(self, mgr: StateManager) -> None:
        state = mgr.load_or_init("s1")
        state.active_tools = ["Read", "Glob"]
        assert mgr.get_active_tools(state) == ["Read", "Glob"]


class TestPersistedFieldContract:
    """Contract tests for the runtime/persisted state boundary.

    Enabled in Stage C3 of openspec change
    ``separate-runtime-and-persisted-state``: ``state_manager.save``
    now routes through ``SessionState.to_persisted_dict()`` so
    ``active_tools`` — the pure per-turn derivation named in the
    ``session-lifecycle`` spec — never lands in the ``sessions``
    table.  Stage D of ``migrate-entrypoints-to-runtime-flow``
    expanded the exclusion set to include ``skills_metadata`` after
    all MCP / LangChain entry points migrated to reading from
    ``RuntimeContext.all_skills_metadata``.
    """

    # Stage C3 excluded ``active_tools``; Stage D added
    # ``skills_metadata`` after entry-point migration completed.
    _EXCLUDED_FIELDS: frozenset[str] = frozenset({"active_tools", "skills_metadata"})

    def test_persisted_json_excludes_derived_fields(self, mgr: StateManager) -> None:
        """Round-tripped state JSON must not carry derived fields.

        ``state_manager.save`` dumps the state with
        ``exclude={"active_tools", "skills_metadata"}`` so that
        per-turn derivations never land in the ``sessions`` table.
        Stage C3 excluded ``active_tools``; Stage D added
        ``skills_metadata`` after all entry points migrated to reading
        from ``RuntimeContext.all_skills_metadata``.
        """
        from tool_governance.models.skill import SkillMetadata

        state = mgr.load_or_init("s1")
        mgr.add_to_skills_loaded(state, "repo-read", "1.0.0")
        state.active_tools = ["Read", "Glob"]
        state.skills_metadata = {
            "repo-read": SkillMetadata(
                skill_id="repo-read", name="RR", allowed_tools=["Read"]
            )
        }
        mgr.save(state)

        raw = mgr._store.load_session("s1")  # type: ignore[attr-defined]
        assert raw is not None
        for field in self._EXCLUDED_FIELDS:
            assert field not in raw, (
                f"excluded field '{field}' leaked into persisted JSON; "
                f"to_persisted_dict() should exclude it"
            )

    def test_legacy_json_with_derived_fields_loads_cleanly(self, mgr: StateManager) -> None:
        """Historical JSON containing derived fields must still load.

        Old sessions written before Stage C3 will have ``active_tools``
        in their persisted JSON, and sessions written before Stage D
        will have ``skills_metadata``.  Reading them must succeed
        (pydantic ignores extras) and the runtime view must be derived
        from live sources rather than trusting the legacy fields.
        """
        import json

        legacy_payload = {
            "session_id": "legacy",
            "skills_loaded": {},
            "active_grants": {},
            "active_tools": ["StaleTool"],
            "skills_metadata": {},
            "created_at": "2026-04-01T00:00:00",
            "updated_at": "2026-04-01T00:00:00",
        }
        mgr._store.save_session("legacy", json.dumps(legacy_payload))  # type: ignore[attr-defined]

        state = mgr.load_or_init("legacy")
        assert state.session_id == "legacy"
        # The legacy field must NOT be treated as current-turn
        # authoritative input; Stage C reconstruction will overwrite
        # or ignore it.  Here we only assert the load succeeded.
        assert "StaleTool" in state.active_tools or state.active_tools == []


class TestAuditReplayFromPersistedState:
    """Pins session-lifecycle spec scenario:
    "Audit replay works from persisted state alone".

    The audit trail must be interpretable using only the persisted
    record plus each event's own payload — never by consulting the
    per-turn ``active_tools`` derivation that Stage C3 removed from
    the persisted payload.
    """

    def test_replay_does_not_depend_on_active_tools(
        self, mgr: StateManager, store: SQLiteStore
    ) -> None:
        """Construct a minimal post-Stage-D session on disk, emit a
        couple of audit events, then replay them against the raw
        persisted record (not the pydantic model) and confirm:

        - The raw record has no ``active_tools`` or ``skills_metadata``
          (Stage C3 and D excluded them).
        - Every ``skill_id`` referenced by an audit row lives in the
          durable ``skills_loaded`` map — so replay never needs the
          per-turn runtime view.
        """
        state = mgr.load_or_init("replay-session")
        mgr.add_to_skills_loaded(state, "repo-read", "1.0.0")
        mgr.save(state)

        store.append_audit(
            "replay-session",
            "skill.enable",
            skill_id="repo-read",
            decision="granted",
        )
        store.append_audit(
            "replay-session",
            "tool.call",
            tool_name="Read",
            decision="allow",
        )

        raw = store.load_session("replay-session")
        assert raw is not None
        # Durable fields are the only state anchor a replay needs.
        assert raw["session_id"] == "replay-session"
        assert "repo-read" in raw["skills_loaded"]
        # The per-turn derivations are absent — the replay can't
        # accidentally depend on them.
        assert "active_tools" not in raw
        assert "skills_metadata" not in raw

        events = store.query_audit(session_id="replay-session")
        assert len(events) >= 2
        for event in events:
            assert event["session_id"] == "replay-session"
            if event["skill_id"]:
                # Every skill_id on an audit row must be resolvable
                # from the durable record alone.
                assert event["skill_id"] in raw["skills_loaded"]
