"""Tests for ToolRewriter.

Verifies the tool-set computation logic: meta-tools always present,
skill tools added on enable, blocked tools removed, stage resolution,
and full (non-incremental) recomputation semantics.
"""

import pytest

from tool_governance.core.runtime_context import build_runtime_context
from tool_governance.core.tool_rewriter import (
    META_TOOLS,
    ToolRewriter,
    compute_active_tools,
)
from tool_governance.models.grant import Grant
from tool_governance.models.skill import SkillMetadata, StageDefinition
from tool_governance.models.state import LoadedSkillInfo, SessionState


@pytest.fixture()
def rewriter() -> ToolRewriter:
    return ToolRewriter()


def _state_with_skills(
    loaded: dict[str, LoadedSkillInfo],
    metadata: dict[str, SkillMetadata],
) -> SessionState:
    """Build a SessionState pre-populated with loaded skills and their
    metadata — the two dicts that recompute_active_tools reads.

    Stage D: creates grants for all loaded skills so they are considered
    enabled in the runtime view.
    """
    grants = {
        skill_id: Grant(
            grant_id=f"g-{skill_id}",
            session_id="test",
            skill_id=skill_id,
            allowed_ops=[],
        )
        for skill_id in loaded
    }
    return SessionState(
        session_id="test",
        skills_loaded=loaded,
        skills_metadata=metadata,
        active_grants=grants,
    )


class TestRecomputeActiveTools:
    """Tests for the DEPRECATED recompute_active_tools adapter.

    This method is now a thin wrapper around compute_active_tools(RuntimeContext)
    and emits a DeprecationWarning. Tests verify backward compatibility.
    """

    def test_empty_state(self, rewriter: ToolRewriter) -> None:
        """With no skills loaded, only the meta-tools should be active.
        Guards the invariant that meta-tools are always present."""
        state = SessionState(session_id="test")
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            tools = rewriter.recompute_active_tools(state)
        assert set(tools) == META_TOOLS

    def test_single_skill(self, rewriter: ToolRewriter) -> None:
        """Enabling one skill must add its allowed_tools alongside
        all meta-tools."""
        meta = SkillMetadata(skill_id="repo-read", name="RR", allowed_tools=["Read", "Glob"])
        state = _state_with_skills(
            loaded={"repo-read": LoadedSkillInfo(skill_id="repo-read")},
            metadata={"repo-read": meta},
        )
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            tools = rewriter.recompute_active_tools(state)
        assert "Read" in tools
        assert "Glob" in tools
        assert all(mt in tools for mt in META_TOOLS)

    def test_multiple_skills_union(self, rewriter: ToolRewriter) -> None:
        """Two skills with disjoint tool sets — result must be the
        union.  Guards against first-skill-only or last-skill-wins."""
        m1 = SkillMetadata(skill_id="a", name="A", allowed_tools=["Read"])
        m2 = SkillMetadata(skill_id="b", name="B", allowed_tools=["Write"])
        state = _state_with_skills(
            loaded={"a": LoadedSkillInfo(skill_id="a"), "b": LoadedSkillInfo(skill_id="b")},
            metadata={"a": m1, "b": m2},
        )
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            tools = rewriter.recompute_active_tools(state)
        assert "Read" in tools
        assert "Write" in tools

    def test_blocked_tools_removed(self) -> None:
        """A tool in the blocked list must be stripped from the result
        even if a skill declares it.  Guards the global deny-list."""
        rewriter = ToolRewriter(blocked_tools=["Read"])
        meta = SkillMetadata(skill_id="a", name="A", allowed_tools=["Read", "Glob"])
        state = _state_with_skills(
            loaded={"a": LoadedSkillInfo(skill_id="a")},
            metadata={"a": meta},
        )
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            tools = rewriter.recompute_active_tools(state)
        assert "Read" not in tools
        assert "Glob" in tools

    def test_full_recompute_not_incremental(self, rewriter: ToolRewriter) -> None:
        """After clearing skills_loaded, a recompute must drop the
        skill's tools.  Guards against additive/append-only behaviour
        where old tools linger from a previous computation."""
        meta = SkillMetadata(skill_id="a", name="A", allowed_tools=["Read"])
        state = _state_with_skills(
            loaded={"a": LoadedSkillInfo(skill_id="a")},
            metadata={"a": meta},
        )
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            rewriter.recompute_active_tools(state)
        assert "Read" in state.active_tools
        # Simulate disable: remove the skill then recompute.
        state.skills_loaded.clear()
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            rewriter.recompute_active_tools(state)
        assert "Read" not in state.active_tools

    def test_recompute_active_tools_emits_deprecation_warning(self, rewriter: ToolRewriter) -> None:
        """Verify that recompute_active_tools emits a DeprecationWarning.

        This test explicitly checks the deprecation warning is raised,
        ensuring callers are notified to migrate to compute_active_tools(RuntimeContext).
        """
        state = SessionState(session_id="test")
        with pytest.warns(DeprecationWarning, match="recompute_active_tools.*deprecated"):
            rewriter.recompute_active_tools(state)


class TestGetStageTools:
    def test_no_stages(self) -> None:
        """Stage-less skill must return its top-level allowed_tools."""
        meta = SkillMetadata(skill_id="a", name="A", allowed_tools=["Read"])
        assert ToolRewriter.get_stage_tools(meta, None) == ["Read"]

    def test_stage_match(self) -> None:
        """Requesting a specific stage must return only that stage's
        tools, not the union of all stages."""
        meta = SkillMetadata(
            skill_id="ce", name="CE",
            stages=[
                StageDefinition(stage_id="analysis", allowed_tools=["Read"]),
                StageDefinition(stage_id="execution", allowed_tools=["Edit"]),
            ],
        )
        assert ToolRewriter.get_stage_tools(meta, "execution") == ["Edit"]

    def test_stage_none_defaults_to_first(self) -> None:
        """When current_stage is None (freshly enabled), the first
        defined stage is used.  Guards against returning empty tools
        for newly-enabled staged skills."""
        meta = SkillMetadata(
            skill_id="ce", name="CE",
            stages=[
                StageDefinition(stage_id="analysis", allowed_tools=["Read"]),
                StageDefinition(stage_id="execution", allowed_tools=["Edit"]),
            ],
        )
        assert ToolRewriter.get_stage_tools(meta, None) == ["Read"]

    def test_stage_not_found(self) -> None:
        """An unknown stage_id must return [] — the skill loses all
        tools rather than getting an unexpected set.  Guards against
        fallback-to-all-tools behaviour on stale stage names."""
        meta = SkillMetadata(
            skill_id="ce", name="CE",
            stages=[StageDefinition(stage_id="analysis", allowed_tools=["Read"])],
        )
        assert ToolRewriter.get_stage_tools(meta, "nonexistent") == []


class TestComputeActiveToolsFromRuntimeContext:
    """Stage C of ``separate-runtime-and-persisted-state``.

    The rewrite main path is migrating to consume a pre-built
    ``RuntimeContext`` instead of mutating ``SessionState.active_tools``
    in place.  These tests pin the new entry point and the "no
    in-place mutation" invariant that Stage C relies on.
    """

    def test_compute_active_tools_returns_ctx_tools(
        self, repo_read_meta_and_loaded: tuple[SkillMetadata, LoadedSkillInfo]
    ) -> None:
        """Covers tool-surface-control spec:
        "Prompt and tool rewrite consume runtime state, not persisted
        snapshot" — the rewrite entry point returns exactly what the
        pre-built runtime view carries.
        """
        meta, loaded = repo_read_meta_and_loaded
        state = _state_with_skills(
            loaded={"repo-read": loaded},
            metadata={"repo-read": meta},
        )
        ctx = build_runtime_context(state)
        result = compute_active_tools(ctx)
        assert set(result) == set(ctx.active_tools)
        assert "Read" in result and "Glob" in result

    def test_compute_active_tools_does_not_mutate_state(
        self, repo_read_meta_and_loaded: tuple[SkillMetadata, LoadedSkillInfo]
    ) -> None:
        """Covers session-lifecycle spec:
        "Runtime state and persisted state are semantically distinct"
        — computing the active tools from a ``RuntimeContext`` must
        NOT write anything back into the originating ``SessionState``.
        This is the invariant that makes the runtime/persisted
        boundary meaningful.
        """
        meta, loaded = repo_read_meta_and_loaded
        state = _state_with_skills(
            loaded={"repo-read": loaded},
            metadata={"repo-read": meta},
        )
        assert state.active_tools == []
        ctx = build_runtime_context(state)
        compute_active_tools(ctx)
        # The persisted field is untouched — only the runtime view
        # knows the current active tools.
        assert state.active_tools == []


@pytest.fixture()
def repo_read_meta_and_loaded() -> tuple[SkillMetadata, LoadedSkillInfo]:
    return (
        SkillMetadata(skill_id="repo-read", name="RR", allowed_tools=["Read", "Glob"]),
        LoadedSkillInfo(skill_id="repo-read"),
    )
