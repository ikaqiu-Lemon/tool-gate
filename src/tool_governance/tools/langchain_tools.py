"""LangChain @tool wrappers for governance meta-tools.

These wrap the core governance operations as LangChain Tool objects
for standardized tool definition. The actual MCP server (Phase 3)
delegates to GovernanceRuntime directly; these are for internal
composition and testing.

.. note:: ``enable_skill_tool`` mirrors ``mcp_server.enable_skill``
   exactly for ``scope`` coercion and ``granted_by`` mapping so that
   the two entry points build equivalent ``Grant`` objects and
   ``state.active_grants`` rows for identical inputs.
"""

from __future__ import annotations

from typing import Any, Literal

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

    Mirrors ``mcp_server.enable_skill``: ``scope`` is coerced to
    ``"turn" | "session"`` (any other value falls back to
    ``"session"``); ``granted_by`` is ``"auto"`` when the policy
    decision is auto, otherwise ``"policy"``.  Both entry points
    therefore build equivalent ``Grant`` objects and write
    ``state.active_grants[skill_id]`` identically.

    Contract:
        Preconditions:
            - ``session_id`` must be a non-empty string for
              meaningful state persistence.  An empty string is
              accepted but produces a session keyed by ``""``,
              which may collide across calls.

        Silences:
            - Already-enabled skill returns success immediately
              without re-evaluating policy or extending TTL.
            - An unrecognised ``scope`` string is coerced to
              ``"session"`` rather than raising.
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
    # Mirror mcp_server.enable_skill for scope + granted_by so both
    # entry points produce equivalent grants.
    scope_val: Literal["turn", "session"] = "turn" if scope == "turn" else "session"
    granted_by_val: Literal["auto", "user", "policy"] = (
        "auto" if decision.decision == "auto" else "policy"
    )
    grant = runtime.grant_manager.create_grant(
        session_id=session_id,
        skill_id=skill_id,
        allowed_ops=meta.allowed_ops,
        scope=scope_val,
        ttl=capped_ttl,
        granted_by=granted_by_val,
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
        runtime.grant_manager.revoke_grant(grant.grant_id, reason="explicit")

    runtime.state_manager.remove_from_skills_loaded(state, skill_id)
    runtime.tool_rewriter.recompute_active_tools(state)
    runtime.state_manager.save(state)
    return {"disabled": True}


@tool
def grant_status_tool(runtime: Any, session_id: str = "") -> list[dict[str, Any]]:
    """Return all active grants for the current session."""
    grants = runtime.grant_manager.get_active_grants(session_id)
    return [g.model_dump() for g in grants]
