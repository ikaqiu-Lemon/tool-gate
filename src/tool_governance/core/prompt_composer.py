"""Prompt composer — generates additionalContext for model injection.

Assembles a short text blob that the MCP hook injects into the LLM's
context so it knows which skills exist, which are enabled, and what
tools are currently available.
"""

from __future__ import annotations

from tool_governance.core.tool_rewriter import META_TOOLS
from tool_governance.models.state import SessionState

# Hard ceiling on the injected context to avoid bloating the model's
# system prompt.  Chosen to leave room for the model's own instructions.
_MAX_CONTEXT_LEN = 800


class PromptComposer:
    """Generates the additionalContext string injected via hooks."""

    def compose_context(self, state: SessionState) -> str:
        """Full context: catalog + active tools + guidance. ≤ 800 chars.

        Contract:
            Silences:
                - If the combined text exceeds ``_MAX_CONTEXT_LEN``
                  (800 chars), it is hard-truncated with ``"..."``.
                  Information at the tail end is silently lost; the
                  caller has no way to detect truncation other than
                  checking for the trailing ``"..."``.
        """
        parts = [
            self.compose_skill_catalog(state),
            self.compose_active_tools_prompt(state),
        ]
        result = "\n".join(p for p in parts if p)
        # Hard-truncate to keep the injected context within budget.
        if len(result) > _MAX_CONTEXT_LEN:
            result = result[:_MAX_CONTEXT_LEN - 3] + "..."
        return result

    def compose_skill_catalog(self, state: SessionState) -> str:
        """Build a one-line-per-skill summary for the model's context.

        Enabled skills get an ``[ENABLED]`` tag plus their active tool
        names; disabled skills show risk level and a truncated description.

        Contract:
            Silences:
                - Skill descriptions longer than 60 chars are silently
                  truncated (no ellipsis marker).
                - At most 5 tool names are shown per enabled skill;
                  the rest are silently dropped.
        """
        if not state.skills_metadata:
            return "[Tool Governance] No skills registered."

        lines = ["[Tool Governance] Skills:"]
        for sid, meta in sorted(state.skills_metadata.items()):
            loaded = state.skills_loaded.get(sid)
            if loaded:
                stage_info = f", stage: {loaded.current_stage}" if loaded.current_stage else ""
                # For stage-less skills, show only tools that are both
                # active AND declared by this skill (intersection).
                # For staged skills, show all active non-meta tools
                # because the stage already scopes the tool set.
                tools = [
                    t for t in state.active_tools
                    if t not in META_TOOLS and t in meta.allowed_tools
                ] if not meta.stages else [
                    t for t in state.active_tools if t not in META_TOOLS
                ]
                tools_str = ", ".join(tools[:5])
                lines.append(f"  * {meta.name} [ENABLED{stage_info}] tools: {tools_str}")
            else:
                lines.append(f"  - {meta.name} ({meta.risk_level}): {meta.description[:60]}")

        return "\n".join(lines)

    def compose_active_tools_prompt(self, state: SessionState) -> str:
        """One-line active-tools summary, or a nudge if nothing is enabled.

        Contract:
            Silences:
                - At most 8 tool names are shown; the rest are silently
                  dropped.
        """
        non_meta = [t for t in state.active_tools if t not in META_TOOLS]
        if non_meta:
            return f"Active tools: {', '.join(non_meta[:8])}"
        return "No skills enabled. Use list_skills -> read_skill -> enable_skill."
