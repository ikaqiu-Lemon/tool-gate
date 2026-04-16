"""LangChain @tool wrappers for governance meta-tools.

These wrap the core governance operations as LangChain Tool objects
for standardized tool definition. The actual MCP server (Phase 3)
delegates to GovernanceRuntime directly; these are for internal
composition and testing.

.. note:: These wrappers differ from the MCP tools in
   ``mcp_server.py`` in two ways: (1) ``scope`` is passed as-is
   to ``create_grant`` without coercion to the ``Literal["turn",
   "session"]`` type; (2) ``granted_by`` is set to
   ``decision.decision`` directly (e.g. ``"auto"``), which happens
   to be valid for the ``allowed=True`` path but would break Pydantic
   validation if somehow reached with ``"reason_required"`` or
   ``"approval_required"``.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import tool


@tool
def list_skills_tool(runtime: Any) -> list[dict[str, Any]]:
    """List all available skills for the current session."""
    return [m.model_dump() for m in runtime.indexer.list_skills()]


@tool
def read_skill_tool(skill_id: str, runtime: Any) -> dict[str, Any]:
    """Read the complete SOP of a skill.

    Contract:
        Silences:
            - Unknown ``skill_id`` returns
              ``{"error": "... not found"}`` instead of raising.
    """
    content = runtime.indexer.read_skill(skill_id)
    if content is None:
        return {"error": f"Skill '{skill_id}' not found"}
    return dict(content.model_dump())


@tool
def enable_skill_tool(
    skill_id: str,
    runtime: Any,
    session_id: str = "",
    reason: str = "",
    scope: str = "session",
    ttl: int = 3600,
) -> dict[str, Any]:
    """Enable a skill for the current session.

    Contract:
        Preconditions:
            - ``session_id`` must be a non-empty string for
              meaningful state persistence.  An empty string is
              accepted but produces a session keyed by ``""``,
              which may collide across calls.

        Raises:
            pydantic.ValidationError: If ``scope`` is not
                ``"turn"`` or ``"session"`` — unlike
                ``mcp_server.enable_skill``, no coercion is applied
                here (from ``Grant`` constructor via
                ``create_grant``, not caught).

        Silences:
            - Already-enabled skill returns success immediately
              without re-evaluating policy or extending TTL.
    """
    state = runtime.state_manager.load_or_init(session_id)
    meta = state.skills_metadata.get(skill_id)
    if meta is None:
        return {"granted": False, "reason": f"Skill '{skill_id}' not found"}

    if skill_id in state.skills_loaded:
        return {"granted": True, "reason": "Already enabled", "allowed_tools": state.active_tools}

    decision = runtime.policy_engine.evaluate(skill_id, meta, state, reason or None)
    if not decision.allowed:
        return {"granted": False, "decision": decision.decision, "reason": decision.reason}

    capped_ttl = runtime.policy_engine.cap_ttl(skill_id, ttl)
    # NB: granted_by receives decision.decision directly (e.g. "auto").
    # This only works because this path is reached when allowed=True,
    # which means decision.decision is always "auto" in practice.
    grant = runtime.grant_manager.create_grant(
        session_id=session_id,
        skill_id=skill_id,
        allowed_ops=meta.allowed_ops,
        scope=scope,
        ttl=capped_ttl,
        granted_by=decision.decision,
        reason=reason or None,
    )
    runtime.state_manager.add_to_skills_loaded(state, skill_id, version=meta.version)
    state.active_grants[skill_id] = grant
    active = runtime.tool_rewriter.recompute_active_tools(state)
    runtime.state_manager.save(state)
    return {"granted": True, "allowed_tools": active}


@tool
def disable_skill_tool(skill_id: str, runtime: Any, session_id: str = "") -> dict[str, Any]:
    """Disable a skill and revoke its grant.

    Contract:
        Silences:
            - If the skill has no grant in ``active_grants``,
              the revoke step is silently skipped.
    """
    state = runtime.state_manager.load_or_init(session_id)
    if skill_id not in state.skills_loaded:
        return {"disabled": False, "reason": "Skill not enabled"}

    grant = state.active_grants.get(skill_id)
    if grant:
        runtime.grant_manager.revoke_grant(grant.grant_id)

    runtime.state_manager.remove_from_skills_loaded(state, skill_id)
    runtime.tool_rewriter.recompute_active_tools(state)
    runtime.state_manager.save(state)
    return {"disabled": True}


@tool
def grant_status_tool(runtime: Any, session_id: str = "") -> list[dict[str, Any]]:
    """Return all active grants for the current session."""
    grants = runtime.grant_manager.get_active_grants(session_id)
    return [g.model_dump() for g in grants]
