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
