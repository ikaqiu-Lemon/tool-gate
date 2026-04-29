"""Tool rewriter — computes active_tools from current session state.

The rewriter is the single authority on which MCP tools are visible
in a given turn.  Every enable/disable/stage-change funnels through
``recompute_active_tools`` to rebuild the set.

Stage C of ``separate-runtime-and-persisted-state`` adds a parallel
runtime-view-driven entry point, :func:`compute_active_tools`, which
is the migration target for callers that have switched to consuming
the pre-built ``RuntimeContext``.  The legacy
``ToolRewriter.recompute_active_tools`` remains unchanged for MCP
meta-tools and other callers that still thread ``SessionState``
through.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import SessionState

if TYPE_CHECKING:
    from tool_governance.core.runtime_context import RuntimeContext

# Meta-tools are always visible regardless of skills_loaded.
# They form the "bootstrap" set that lets the model discover and
# enable skills in the first place.
META_TOOLS: frozenset[str] = frozenset(
    {
        "mcp__tool-governance__list_skills",
        "mcp__tool-governance__read_skill",
        "mcp__tool-governance__enable_skill",
        "mcp__tool-governance__disable_skill",
        "mcp__tool-governance__grant_status",
        "mcp__tool-governance__run_skill_action",
        "mcp__tool-governance__change_stage",
        "mcp__tool-governance__refresh_skills",
    }
)


class ToolRewriter:
    """Computes the minimal active_tools set based on current state."""

    def __init__(self, blocked_tools: list[str] | None = None) -> None:
        self._blocked: set[str] = set(blocked_tools or [])

    @property
    def blocked_tools(self) -> frozenset[str]:
        """Immutable view of the global deny-list.

        Added in Stage B of ``separate-runtime-and-persisted-state``
        so that external callers (``build_runtime_context``) can read
        the blocked set without reaching into the private attribute.
        """
        return frozenset(self._blocked)

    def recompute_active_tools(
        self,
        state: SessionState,
        indexer: "SkillIndexer | None" = None,
    ) -> list[str]:
        """DEPRECATED: Use compute_active_tools(RuntimeContext) instead.

        This function is a thin adapter for backward compatibility.
        It will be removed in a future version.

        Builds a minimal RuntimeContext from the current state and calls
        compute_active_tools(). Updates state.active_tools in place for
        backward compatibility.

        Args:
            state: The session state to recompute tools for.
            indexer: Optional SkillIndexer to read metadata from. If not
                provided, falls back to state.skills_metadata (which will
                be empty after Stage D if state was loaded from disk).

        Contract:
            Preconditions:
                - Every skill_id in ``state.skills_loaded`` should have
                  a matching entry in the metadata source.  If a
                  loaded skill has no metadata, it is silently skipped
                  and contributes zero tools — the model loses access
                  to that skill's tools with no error raised.

            Silences:
                - Missing metadata for a loaded skill (see above).
                - Blocked tools are silently removed from the final
                  set; the caller cannot tell whether any tools were
                  stripped by the deny-list.
        """
        import warnings
        warnings.warn(
            "recompute_active_tools(state) is deprecated. "
            "Use compute_active_tools(RuntimeContext) instead.",
            DeprecationWarning,
            stacklevel=2
        )

        # Stage D: skills_metadata is no longer persisted, so after
        # loading from disk it will be empty. Prefer indexer if provided.
        metadata = indexer.current_index() if indexer else state.skills_metadata

        # Build minimal RuntimeContext for compatibility
        from tool_governance.core.runtime_context import build_runtime_context
        ctx = build_runtime_context(
            state,
            metadata=metadata,
            blocked_tools=self._blocked,
        )
        active_tools = compute_active_tools(ctx)
        # In-place mutation for backward compatibility
        state.active_tools = active_tools
        return active_tools

    @staticmethod
    def get_stage_tools(skill_meta: SkillMetadata, current_stage: str | None) -> list[str]:
        """Get allowed_tools for a skill at the given stage.

        Resolution order:
        - No stages defined → use skill-level allowed_tools
        - Stages defined, current_stage matches → use that stage's tools
        - Stages defined, current_stage is None → use first stage's tools
        - Stages defined, current_stage not found → empty list

        Contract:
            Silences:
                - If ``current_stage`` names a stage_id that does not
                  exist in ``skill_meta.stages``, the function returns
                  ``[]`` — the skill effectively loses all tools with
                  no error raised.  This can happen if a stage was
                  renamed in the SKILL.md but the session still holds
                  the old stage_id.
        """
        if not skill_meta.stages:
            return list(skill_meta.allowed_tools)

        # Default to the first stage when no explicit stage is set,
        # so a freshly-enabled staged skill starts with *some* tools.
        if current_stage is None:
            return list(skill_meta.stages[0].allowed_tools)

        for stage in skill_meta.stages:
            if stage.stage_id == current_stage:
                return list(stage.allowed_tools)

        # Stage name mismatch — return nothing rather than guessing.
        return []


def compute_active_tools(ctx: "RuntimeContext") -> list[str]:
    """Return the runtime view's active tool list.

    Stage C migration target for ``separate-runtime-and-persisted-state``.
    Callers that used to invoke ``ToolRewriter.recompute_active_tools(state)``
    and then read ``state.active_tools`` should instead build a
    ``RuntimeContext`` once per turn and pass it here — the result is
    the same list, without the side effect of mutating
    ``SessionState.active_tools``.

    The function is a thin passthrough on purpose: the derivation
    formula (meta ∪ stage_tools − blocked) lives exclusively in
    ``runtime_context.build_runtime_context`` so there is a single
    source of truth for "what the model sees this turn".
    """
    return list(ctx.active_tools)
