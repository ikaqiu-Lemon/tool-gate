"""Tests for ``RuntimeContext`` and ``build_runtime_context``.

Stage B of ``separate-runtime-and-persisted-state``.  These tests
establish the runtime/persisted boundary and serve as the
behavioural anchor that Stage C will rely on when it flips the
remaining callers (``tool_rewriter`` / ``prompt_composer`` /
``mcp_server``) to consume the runtime view.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest

from tool_governance.core.runtime_context import (
    RuntimeContext,
    build_runtime_context,
)
from tool_governance.core.tool_rewriter import META_TOOLS, ToolRewriter
from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata, StageDefinition
from tool_governance.models.state import LoadedSkillInfo, SessionState


@pytest.fixture()
def empty_state() -> SessionState:
    return SessionState(session_id="t")


@pytest.fixture()
def repo_read_meta() -> SkillMetadata:
    return SkillMetadata(skill_id="repo-read", name="RR", allowed_tools=["Read", "Glob"])


@pytest.fixture()
def web_search_meta() -> SkillMetadata:
    return SkillMetadata(
        skill_id="web-search", name="WS", allowed_tools=["WebSearch", "WebFetch"]
    )


def _state_with(
    loaded: dict[str, LoadedSkillInfo],
    metadata: dict[str, SkillMetadata],
) -> SessionState:
    """Match the fixture idiom used in tests/test_tool_rewriter.py.

    Stage D: creates grants for all loaded skills so they are considered
    enabled in the runtime view.
    """
    grants = {
        skill_id: Grant(
            grant_id=f"g-{skill_id}",
            session_id="t",
            skill_id=skill_id,
            allowed_ops=[],
        )
        for skill_id in loaded
    }
    return SessionState(
        session_id="t",
        skills_loaded=loaded,
        skills_metadata=metadata,
        active_grants=grants,
    )


class TestBuildRuntimeContext:
    def test_empty_state_has_only_meta_tools(self, empty_state: SessionState) -> None:
        """Baseline: no skills loaded → meta-tools only, no blocked."""
        ctx = build_runtime_context(empty_state)
        assert set(ctx.active_tools) == META_TOOLS
        assert ctx.enabled_skills == ()
        assert ctx.policy.blocked_tools == frozenset()

    def test_empty_state_with_blocked_subtracts_meta(
        self, empty_state: SessionState
    ) -> None:
        """Blocked tools are stripped even from meta-tools — the
        runtime view never grants something the policy forbids."""
        a_meta_tool = next(iter(META_TOOLS))
        ctx = build_runtime_context(empty_state, blocked_tools=[a_meta_tool])
        assert a_meta_tool not in ctx.active_tools
        assert ctx.policy.blocked_tools == frozenset({a_meta_tool})

    def test_unknown_skill_is_skipped_safely(
        self, repo_read_meta: SkillMetadata
    ) -> None:
        """Persisted ``skills_loaded`` may reference a skill that no
        longer resolves in the metadata map — the runtime view must
        drop it without error and without granting any of its tools.

        Covers session-lifecycle spec "System degrades safely when
        persisted state is missing, stale, or incomplete".
        """
        state = _state_with(
            loaded={
                "repo-read": LoadedSkillInfo(skill_id="repo-read"),
                "ghost": LoadedSkillInfo(skill_id="ghost"),
            },
            metadata={"repo-read": repo_read_meta},
        )
        ctx = build_runtime_context(state)
        enabled_ids = ctx.enabled_skill_ids()
        assert enabled_ids == {"repo-read"}
        assert "ghost" not in enabled_ids
        assert "Read" in ctx.active_tools
        # Nothing from the unknown skill leaked in.
        assert all(
            t in META_TOOLS or t in {"Read", "Glob"} for t in ctx.active_tools
        )

    def test_idempotent_under_same_inputs(
        self,
        repo_read_meta: SkillMetadata,
        web_search_meta: SkillMetadata,
    ) -> None:
        """Two builds with identical inputs must yield equivalent
        contexts — the same ``active_tools``, the same enabled-skill
        ids, the same policy snapshot.

        Covers session-lifecycle spec "Identical inputs yield
        equivalent runtime views".
        """
        state = _state_with(
            loaded={
                "repo-read": LoadedSkillInfo(skill_id="repo-read"),
                "web-search": LoadedSkillInfo(skill_id="web-search"),
            },
            metadata={"repo-read": repo_read_meta, "web-search": web_search_meta},
        )
        pinned_clock = datetime(2026, 4, 21, 12, 0, 0)

        ctx_a = build_runtime_context(state, blocked_tools=["Write"], clock=pinned_clock)
        ctx_b = build_runtime_context(state, blocked_tools=["Write"], clock=pinned_clock)

        assert ctx_a.active_tools == ctx_b.active_tools
        assert ctx_a.enabled_skill_ids() == ctx_b.enabled_skill_ids()
        assert ctx_a.policy == ctx_b.policy
        assert ctx_a.clock == ctx_b.clock

    def test_matches_tool_rewriter_output(
        self,
        repo_read_meta: SkillMetadata,
        web_search_meta: SkillMetadata,
    ) -> None:
        """Regression anchor for Stage C.

        ``build_runtime_context`` must compute the same ``active_tools``
        set that ``ToolRewriter.recompute_active_tools`` produces for
        the same inputs.  When Stage C flips the rewriter's callers
        to consume the runtime view, this equivalence is what keeps
        behaviour identical.

        The rewriter mutates its input state in place, so we clone
        the state before each call to avoid cross-contamination.
        """
        loaded = {
            "repo-read": LoadedSkillInfo(skill_id="repo-read"),
            "web-search": LoadedSkillInfo(skill_id="web-search"),
        }
        metadata = {"repo-read": repo_read_meta, "web-search": web_search_meta}
        blocked = ["WebFetch"]
        state = _state_with(loaded=loaded, metadata=metadata)

        rewriter = ToolRewriter(blocked_tools=blocked)
        state_for_rewriter = deepcopy(state)
        rewriter_output = rewriter.recompute_active_tools(state_for_rewriter)

        ctx = build_runtime_context(state, blocked_tools=blocked)

        assert set(ctx.active_tools) == set(rewriter_output)
        # State passed into build_runtime_context is NOT mutated —
        # this is the runtime/persisted boundary.
        assert state.active_tools == []

    def test_indexer_metadata_supersedes_persisted_snapshot(
        self,
        repo_read_meta: SkillMetadata,
    ) -> None:
        """When an explicit metadata map is provided, it takes
        precedence over the persisted ``state.skills_metadata``
        snapshot.  This is how Stage B wiring hands the indexer's
        authoritative map to the builder; the persisted snapshot
        remains a fallback for cold-start scenarios only.
        """
        stale_meta = SkillMetadata(
            skill_id="repo-read", name="RR-stale", allowed_tools=["Read"]
        )
        # The persisted state carries a stale entry (only "Read"),
        # but the caller supplies the live index (with "Read", "Glob").
        state = _state_with(
            loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            metadata={"repo-read": stale_meta},
        )
        ctx = build_runtime_context(state, metadata={"repo-read": repo_read_meta})
        assert "Read" in ctx.active_tools
        assert "Glob" in ctx.active_tools


class TestRuntimeContextIsImmutable:
    def test_frozen_dataclass_rejects_mutation(
        self, repo_read_meta: SkillMetadata
    ) -> None:
        """``RuntimeContext`` must be a frozen dataclass — any attempt
        to reassign a field from outside raises ``FrozenInstanceError``.
        Guards the invariant that a once-built runtime view is a
        stable per-turn snapshot.
        """
        state = _state_with(
            loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            metadata={"repo-read": repo_read_meta},
        )
        ctx = build_runtime_context(state)

        with pytest.raises(Exception):  # FrozenInstanceError in stdlib dataclasses
            ctx.active_tools = ("hacked",)  # type: ignore[misc]
