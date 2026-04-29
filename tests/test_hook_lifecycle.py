"""Integration-style tests for the hook-handler Stage C lifecycle.

Stage C of ``separate-runtime-and-persisted-state`` — pins the
explicit lifecycle (load persisted → derive runtime → rewrite/compose
on the runtime view → execute → persist durable fields), the safe
degradation paths, and backwards compatibility with legacy sessions
that carry derived fields in their persisted JSON.

Test strategy: each test bootstraps a real ``GovernanceRuntime`` in
a tmp directory and monkey-patches it into ``hook_handler._runtime``
so the hook entry points run end-to-end without subprocess spawning.
Skills are injected by stubbing ``indexer.current_index`` rather than
materialising SKILL.md files on disk — the goal is to exercise the
state-flow lifecycle, not the skill discovery path.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

import pytest

import tool_governance.hook_handler as hook_handler
from tool_governance.bootstrap import create_governance_runtime, GovernanceRuntime
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import LoadedSkillInfo, SessionState


@pytest.fixture()
def runtime(tmp_path: Path) -> Iterator[GovernanceRuntime]:
    """Bootstrap a real runtime wired into ``hook_handler._runtime``.

    Each test gets its own SQLite database and empty skills/config
    directories.  The fixture restores the singleton on exit so that
    tests in other modules (which may monkey-patch or rely on None)
    see a clean slate.
    """
    (tmp_path / "skills").mkdir()
    (tmp_path / "config").mkdir()
    rt = create_governance_runtime(
        tmp_path / "data", tmp_path / "skills", tmp_path / "config"
    )
    prev = hook_handler._runtime
    hook_handler._runtime = rt
    try:
        yield rt
    finally:
        hook_handler._runtime = prev


def _stub_indexer_with(rt: GovernanceRuntime, metadata: dict[str, SkillMetadata]) -> None:
    """Make the indexer return a canned metadata map without disk I/O.

    Tests that want a skill populated in the runtime view call this
    instead of writing a SKILL.md file, keeping the lifecycle tests
    focused on state flow rather than the indexer's cache machinery.
    """
    rt.indexer.current_index = lambda: metadata  # type: ignore[method-assign]
    rt.indexer.build_index = lambda: metadata  # type: ignore[method-assign]


def _hook_input(session_id: str, **extra: object) -> dict[str, object]:
    return {"session_id": session_id, **extra}


class TestLifecycleLoadDeriveRewritePersist:
    """Pins the "load → derive → rewrite/compose → persist" order."""

    def test_session_start_persists_durable_fields_only_after_derive(
        self, runtime: GovernanceRuntime
    ) -> None:
        """Covers session-lifecycle spec:
        "Runtime state is reconstructed safely from persisted state
        plus current context" — ``handle_session_start`` loads the
        persisted record, derives a runtime view, then persists the
        durable fields.  The returned additionalContext reflects the
        derivation; the saved state carries the durable anchors.
        """
        meta = SkillMetadata(skill_id="repo-read", name="Repo Read", allowed_tools=["Read"])
        _stub_indexer_with(runtime, {"repo-read": meta})

        result = hook_handler.handle_session_start(_hook_input("s-start"))
        assert "additionalContext" in result
        assert "Repo Read" in result["additionalContext"]

        # Durable fields are what ended up on disk.  ``session_id``,
        # ``skills_loaded`` (empty — no skill was enabled yet),
        # ``active_grants``, and the two audit-anchor timestamps.
        persisted = runtime.state_manager.load_or_init("s-start")
        assert persisted.session_id == "s-start"
        assert persisted.skills_loaded == {}
        assert persisted.active_grants == {}

    def test_user_prompt_submit_composes_from_runtime_view(
        self, runtime: GovernanceRuntime
    ) -> None:
        """Covers tool-surface-control spec:
        "Prompt and tool rewrite consume runtime state, not persisted
        snapshot" — ``handle_user_prompt_submit`` renders the context
        from the freshly-derived runtime view.  Swap the indexer's
        metadata between turns and observe the change propagate.
        """
        # Seed a loaded skill in the persisted state before the turn.
        # Stage D: skills need both skills_loaded entry AND active grant.
        state = runtime.state_manager.load_or_init("s-turn")
        runtime.state_manager.add_to_skills_loaded(state, "repo-read", "1.0.0")
        grant = runtime.grant_manager.create_grant("s-turn", "repo-read", ["read"])
        state.active_grants["repo-read"] = grant
        runtime.state_manager.save(state)

        meta = SkillMetadata(skill_id="repo-read", name="Repo Read", allowed_tools=["Read"])
        _stub_indexer_with(runtime, {"repo-read": meta})

        first = hook_handler.handle_user_prompt_submit(_hook_input("s-turn"))
        assert "Read" in first["additionalContext"]

        # Policy change between turns: swap metadata to grant Glob instead.
        meta2 = SkillMetadata(skill_id="repo-read", name="Repo Read", allowed_tools=["Glob"])
        _stub_indexer_with(runtime, {"repo-read": meta2})

        second = hook_handler.handle_user_prompt_submit(_hook_input("s-turn"))
        assert "Glob" in second["additionalContext"]
        # Old value must not leak — the new turn's runtime view
        # supersedes any stale derived field on the persisted record.
        assert "Read" not in second["additionalContext"].split("Active tools:")[-1]

    def test_post_tool_use_writes_durable_last_used_at(
        self, runtime: GovernanceRuntime
    ) -> None:
        """Covers session-lifecycle spec:
        "Persisted state contains only recovery, continuity, and
        audit fields" — PostToolUse looks up the owning skill via
        the runtime view but writes the durable ``last_used_at``
        field onto the persisted ``skills_loaded`` entry.
        """
        # Seed enable + durable record.
        # Stage D: skills need both skills_loaded entry AND active grant.
        state = runtime.state_manager.load_or_init("s-post")
        runtime.state_manager.add_to_skills_loaded(state, "repo-read", "1.0.0")
        grant = runtime.grant_manager.create_grant("s-post", "repo-read", ["read"])
        state.active_grants["repo-read"] = grant
        runtime.state_manager.save(state)

        meta = SkillMetadata(skill_id="repo-read", name="Repo Read", allowed_tools=["Read"])
        _stub_indexer_with(runtime, {"repo-read": meta})

        hook_handler.handle_post_tool_use(
            _hook_input("s-post", tool_name="Read", tool_response={})
        )

        persisted = runtime.state_manager.load_or_init("s-post")
        assert "repo-read" in persisted.skills_loaded
        # Durable field written back.
        assert persisted.skills_loaded["repo-read"].last_used_at is not None


class TestDegradationAndCompat:
    """Covers session-lifecycle spec
    "System degrades safely when persisted state is missing, stale,
    or incomplete" and the legacy fallback requirement from Stage C.
    """

    def test_pre_tool_use_on_missing_persisted_state(
        self, runtime: GovernanceRuntime
    ) -> None:
        """Session id with no prior record → a fresh empty runtime
        view is constructed (meta-tools minus blocked) and the gate
        denies any non-meta tool call without crashing.
        """
        result = hook_handler.handle_pre_tool_use(
            _hook_input("never-seen", tool_name="Read")
        )
        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"
        assert "active_tools" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_pre_tool_use_with_unknown_loaded_skill(
        self, runtime: GovernanceRuntime
    ) -> None:
        """Persisted state references ``ghost`` which no longer
        resolves in the skill index.  The runtime view must exclude
        it, the gate must deny tools the unknown skill would have
        granted, and the persisted record must survive unchanged
        for audit purposes.
        """
        state = runtime.state_manager.load_or_init("s-ghost")
        runtime.state_manager.add_to_skills_loaded(state, "ghost", "1.0.0")
        runtime.state_manager.save(state)
        # Index knows nothing about ``ghost``.
        _stub_indexer_with(runtime, {})

        result = hook_handler.handle_pre_tool_use(
            _hook_input("s-ghost", tool_name="Read")
        )
        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "deny"

        # Persisted entry survives for audit even though the runtime
        # view dropped it.
        persisted = runtime.state_manager.load_or_init("s-ghost")
        assert "ghost" in persisted.skills_loaded

    def test_session_start_with_legacy_derived_fields(
        self, runtime: GovernanceRuntime, tmp_path: Path
    ) -> None:
        """Covers compat fallback:
        a legacy session JSON written before Stage C may carry
        ``active_tools`` / ``skills_metadata`` populated with stale
        values.  The new handler must load the record without error
        and derive its own runtime view; the legacy derived fields
        must not leak back out as authoritative.
        """
        legacy_payload = {
            "session_id": "legacy",
            "skills_loaded": {},
            "active_grants": {},
            # Legacy stale derivations — these must be ignored for
            # governance purposes.
            "active_tools": ["StaleTool"],
            "skills_metadata": {},
            "created_at": "2026-04-01T00:00:00",
            "updated_at": "2026-04-01T00:00:00",
        }
        runtime.store.save_session("legacy", json.dumps(legacy_payload))

        # No skills in the current index → runtime view has only
        # meta-tools, and "StaleTool" must not appear anywhere.
        _stub_indexer_with(runtime, {})

        result = hook_handler.handle_session_start(_hook_input("legacy"))
        assert "StaleTool" not in result["additionalContext"]
        # The record is still loadable afterward.
        persisted = runtime.state_manager.load_or_init("legacy")
        assert persisted.session_id == "legacy"
