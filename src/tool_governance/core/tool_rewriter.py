"""Tool rewriter — computes active_tools from current session state.

The rewriter is the single authority on which MCP tools are visible
in a given turn.  Every enable/disable/stage-change funnels through
``recompute_active_tools`` to rebuild the set.
"""

from __future__ import annotations

from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import SessionState

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

    def recompute_active_tools(self, state: SessionState) -> list[str]:
        """Full recomputation: meta_tools ∪ stage_tools(loaded) − blocked.

        Updates ``state.active_tools`` **in place** and returns the list.

        Contract:
            Preconditions:
                - Every skill_id in ``state.skills_loaded`` should have
                  a matching entry in ``state.skills_metadata``.  If a
                  loaded skill has no metadata, it is silently skipped
                  and contributes zero tools — the model loses access
                  to that skill's tools with no error raised.

            Silences:
                - Missing metadata for a loaded skill (see above).
                - Blocked tools are silently removed from the final
                  set; the caller cannot tell whether any tools were
                  stripped by the deny-list.
        """
        tools: set[str] = set(META_TOOLS)

        for skill_id, loaded_info in state.skills_loaded.items():
            meta = state.skills_metadata.get(skill_id)
            if meta is None:
                # Loaded skill with no metadata — skip silently.
                continue
            stage_tools = self.get_stage_tools(meta, loaded_info.current_stage)
            tools.update(stage_tools)

        # Apply global deny-list last so it always wins.
        tools -= self._blocked
        state.active_tools = sorted(tools)
        return state.active_tools

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
