"""Prompt composer — generates additionalContext for model injection.

Assembles a short text blob that the MCP hook injects into the LLM's
context so it knows which skills exist, which are enabled, and what
tools are currently available.

Stage C of ``separate-runtime-and-persisted-state`` narrows the
composer's input to a ``RuntimeContext``: all reads now go through
the per-turn runtime view, never directly against
``SessionState.active_tools`` / ``SessionState.skills_metadata``.
Public methods still accept ``SessionState`` for backward
compatibility with unmigrated MCP meta-tools and the legacy
``PromptComposer`` tests — in that path, the composer internally
derives a runtime view on demand via
``runtime_context.build_runtime_context``.
"""

from __future__ import annotations

from tool_governance.core.runtime_context import RuntimeContext
from tool_governance.core.tool_rewriter import META_TOOLS
from tool_governance.models.state import SessionState

# Hard ceiling on the injected context to avoid bloating the model's
# system prompt.  Chosen to leave room for the model's own instructions.
_MAX_CONTEXT_LEN = 800


class PromptComposer:
    """Generates the additionalContext string injected via hooks."""

    def compose_context(self, source: SessionState | RuntimeContext) -> str:
        """Full context: catalog + active tools + guidance. ≤ 800 chars.

        Accepts either a ``RuntimeContext`` (Stage C preferred path,
        used by ``hook_handler``) or a ``SessionState`` (legacy path,
        kept for unmigrated callers).  In the legacy case, the
        composer trusts the existing ``state.active_tools`` /
        ``state.skills_metadata`` fields byte-for-byte — the goal of
        the fallback is to keep pre-Stage-C callers working without
        silently changing their rendered output.

        Contract:
            Silences:
                - If the combined text exceeds ``_MAX_CONTEXT_LEN``
                  (800 chars), it is hard-truncated with ``"..."``.
                  Information at the tail end is silently lost; the
                  caller has no way to detect truncation other than
                  checking for the trailing ``"..."``.
        """
        parts = [
            self.compose_skill_catalog(source),
            self.compose_active_tools_prompt(source),
        ]
        result = "\n".join(p for p in parts if p)
        if len(result) > _MAX_CONTEXT_LEN:
            result = result[: _MAX_CONTEXT_LEN - 3] + "..."
        return result

    def compose_skill_catalog(self, source: SessionState | RuntimeContext) -> str:
        """Build a one-line-per-skill summary for the model's context.

        Enabled skills get an ``[ENABLED]`` tag plus their active tool
        names; disabled skills show risk level and a truncated description.

        Dispatches on the input type — see ``compose_context`` for the
        compat story.

        Contract:
            Silences:
                - Skill descriptions longer than 60 chars are silently
                  truncated (no ellipsis marker).
                - At most 5 tool names are shown per enabled skill;
                  the rest are silently dropped.
        """
        if isinstance(source, RuntimeContext):
            return self._catalog_from_ctx(source)
        return self._catalog_from_state(source)

    def compose_active_tools_prompt(
        self, source: SessionState | RuntimeContext
    ) -> str:
        """One-line active-tools summary, or a nudge if nothing is enabled.

        Contract:
            Silences:
                - At most 8 tool names are shown; the rest are silently
                  dropped.
        """
        if isinstance(source, RuntimeContext):
            active_tools = source.active_tools
        else:
            # Legacy: trust whatever ``state.active_tools`` carries —
            # tests and unmigrated callers populate this field
            # directly and expect it to be rendered verbatim.
            active_tools = tuple(source.active_tools)
        non_meta = [t for t in active_tools if t not in META_TOOLS]
        if non_meta:
            return f"Active tools: {', '.join(non_meta[:8])}"
        return "No skills enabled. Use list_skills -> read_skill -> enable_skill."

    @staticmethod
    def _catalog_from_ctx(ctx: RuntimeContext) -> str:
        if not ctx.all_skills_metadata:
            return "[Tool Governance] No skills registered."

        enabled_map = {sv.skill_id: sv for sv in ctx.enabled_skills}
        lines = ["[Tool Governance] Skills:"]
        for sid, meta in sorted(ctx.all_skills_metadata.items()):
            sv = enabled_map.get(sid)
            if sv is not None:
                loaded = sv.loaded_info
                stage_info = (
                    f", stage: {loaded.current_stage}" if loaded.current_stage else ""
                )
                if not meta.stages:
                    tools = [
                        t
                        for t in ctx.active_tools
                        if t not in META_TOOLS and t in meta.allowed_tools
                    ]
                else:
                    tools = [t for t in ctx.active_tools if t not in META_TOOLS]
                tools_str = ", ".join(tools[:5])
                lines.append(
                    f"  * {meta.name} [ENABLED{stage_info}] tools: {tools_str}"
                )
            else:
                lines.append(
                    f"  - {meta.name} ({meta.risk_level}): {meta.description[:60]}"
                )

        return "\n".join(lines)

    @staticmethod
    def _catalog_from_state(state: SessionState) -> str:
        """Legacy rendering path that reads directly from ``SessionState``.

        Byte-for-byte equivalent to the pre-Stage-C implementation.
        Kept as a compat branch so unmigrated callers keep working.
        """
        if not state.skills_metadata:
            return "[Tool Governance] No skills registered."

        lines = ["[Tool Governance] Skills:"]
        for sid, meta in sorted(state.skills_metadata.items()):
            loaded = state.skills_loaded.get(sid)
            if loaded:
                stage_info = (
                    f", stage: {loaded.current_stage}" if loaded.current_stage else ""
                )
                if not meta.stages:
                    tools = [
                        t
                        for t in state.active_tools
                        if t not in META_TOOLS and t in meta.allowed_tools
                    ]
                else:
                    tools = [t for t in state.active_tools if t not in META_TOOLS]
                tools_str = ", ".join(tools[:5])
                lines.append(
                    f"  * {meta.name} [ENABLED{stage_info}] tools: {tools_str}"
                )
            else:
                lines.append(
                    f"  - {meta.name} ({meta.risk_level}): {meta.description[:60]}"
                )

        return "\n".join(lines)
