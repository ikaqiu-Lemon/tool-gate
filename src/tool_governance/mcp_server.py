"""MCP Server entry point — exposes 8 governance meta-tools via stdio.

This is the primary interface for Claude.  Each ``@mcp.tool()`` function
is invoked by the model through the MCP protocol.  All tools share a
process-wide ``GovernanceRuntime`` singleton and use the session ID
from the environment or auto-discovery.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP

from tool_governance.bootstrap import create_governance_runtime, GovernanceRuntime
from tool_governance.core.runtime_context import RuntimeContext, build_runtime_context
from tool_governance.core.state_manager import discover_session_id
from tool_governance.models.state import SessionState

# Lazy singleton — initialised on first tool call.
_runtime: GovernanceRuntime | None = None


def _get_runtime() -> GovernanceRuntime:
    """Return (and lazily create) the process-wide GovernanceRuntime.

    Same env-var fallback chain as ``hook_handler._get_runtime``.

    Contract:
        Raises:
            sqlite3.OperationalError / yaml.YAMLError /
            pydantic.ValidationError: On first call if the DB or
            config are inaccessible or corrupt (not caught).

        Silences:
            - Missing env vars silently fall back to ``"."`` /
              ``"./skills"`` / ``"./config"``.
    """
    global _runtime
    if _runtime is None:
        data_dir = os.environ.get("GOVERNANCE_DATA_DIR", os.environ.get("CLAUDE_PLUGIN_DATA", "."))
        skills_dir = os.environ.get("GOVERNANCE_SKILLS_DIR", os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/skills")
        config_dir = os.environ.get("GOVERNANCE_CONFIG_DIR", os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/config")
        _runtime = create_governance_runtime(data_dir, skills_dir, config_dir)
    return _runtime


def _session_id() -> str:
    """Return the current session ID from env or auto-discovery."""
    return os.environ.get("CLAUDE_SESSION_ID", discover_session_id(None))


def _build_runtime_ctx(rt: GovernanceRuntime, state: SessionState) -> RuntimeContext:
    """Build the per-turn RuntimeContext for an MCP tool invocation.

    Mirrors the hook_handler._build_runtime_ctx implementation.
    Metadata preference order:
        1. rt.indexer.current_index() — authoritative
        2. state.skills_metadata — legacy fallback for cold start
    """
    metadata = rt.indexer.current_index() or state.skills_metadata
    return build_runtime_context(
        state,
        metadata=metadata,
        blocked_tools=rt.policy.blocked_tools,
    )


mcp = FastMCP("tool-governance")


@mcp.tool()
async def list_skills() -> list[dict[str, Any]]:
    """List all available skills with their metadata.

    Lazily builds the skill index on first call (same semantics as
    ``SkillIndexer.list_skills``).
    """
    rt = _get_runtime()
    sid = _session_id()
    state = rt.state_manager.load_or_init(sid)

    # Build runtime context to get current metadata
    ctx = _build_runtime_ctx(rt, state)

    result = []
    for skill_id, meta in ctx.all_skills_metadata.items():
        result.append({
            "skill_id": meta.skill_id,
            "name": meta.name,
            "description": meta.description,
            "risk_level": meta.risk_level,
            "is_enabled": skill_id in state.skills_loaded,
        })
    rt.store.append_audit(sid, "skill.list")
    return result


@mcp.tool()
async def read_skill(skill_id: str) -> dict[str, Any]:
    """Read the full SOP and details of a specific skill.

    Contract:
        Silences:
            - Unknown ``skill_id`` returns
              ``{"error": "... not found"}`` instead of raising.
    """
    rt = _get_runtime()
    sid = _session_id()
    state = rt.state_manager.load_or_init(sid)

    # Build runtime context to get current metadata
    ctx = _build_runtime_ctx(rt, state)

    # Check if skill exists in runtime metadata
    if skill_id not in ctx.all_skills_metadata:
        return {"error": f"Skill '{skill_id}' not found"}

    # Read full content from indexer
    content = rt.indexer.read_skill(skill_id)
    if content is None:
        return {"error": f"Skill '{skill_id}' not found"}
    rt.store.append_audit(sid, "skill.read", skill_id=skill_id)
    return dict(content.model_dump())


@mcp.tool()
async def enable_skill(
    skill_id: str,
    reason: str = "",
    scope: str = "session",
    ttl: int = 3600,
) -> dict[str, Any]:
    """Enable a skill for the current session.

    Workflow: look up metadata → check if already enabled → evaluate
    policy → cap TTL → create grant → add to loaded → recompute
    tools → persist.

    Contract:
        Silences:
            - Unknown ``skill_id`` returns an error dict (not an
              exception).
            - Already-enabled skill returns success immediately
              without re-evaluating policy or extending TTL.
            - ``scope`` is coerced: any value other than ``"turn"``
              silently becomes ``"session"``.
            - ``granted_by`` is set to ``"auto"`` when the policy
              decision is ``"auto"``, otherwise ``"policy"`` —
              never ``"user"`` in this code path.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state
    state = rt.state_manager.load_or_init(sid)

    # Step 2: Derive runtime context
    ctx = _build_runtime_ctx(rt, state)

    meta = ctx.all_skills_metadata.get(skill_id)
    if meta is None:
        return {"granted": False, "reason": f"Skill '{skill_id}' not found"}

    if skill_id in state.skills_loaded:
        # Return current active_tools from runtime context
        return {"granted": True, "reason": "Already enabled", "allowed_tools": list(ctx.active_tools)}

    decision = rt.policy_engine.evaluate(skill_id, meta, state, reason or None)
    if not decision.allowed:
        rt.store.append_audit(sid, "skill.enable", skill_id=skill_id, decision=decision.decision)
        return {"granted": False, "decision": decision.decision, "reason": decision.reason}

    # Step 3: Mutate persisted-only fields
    capped_ttl = rt.policy_engine.cap_ttl(skill_id, ttl)
    scope_val: Literal["turn", "session"] = "turn" if scope == "turn" else "session"
    granted_by_val: Literal["auto", "user", "policy"] = "auto" if decision.decision == "auto" else "policy"
    grant = rt.grant_manager.create_grant(
        session_id=sid, skill_id=skill_id, allowed_ops=meta.allowed_ops,
        scope=scope_val, ttl=capped_ttl, granted_by=granted_by_val, reason=reason or None,
    )
    rt.state_manager.add_to_skills_loaded(state, skill_id, version=meta.version)
    state.active_grants[skill_id] = grant

    # Rebuild runtime context after mutation to get updated active_tools
    ctx = _build_runtime_ctx(rt, state)
    # Mirror to state for backward compatibility
    state.sync_from_runtime(ctx.active_tools)

    # Step 4: Save persisted state
    rt.state_manager.save(state)
    rt.store.append_audit(sid, "skill.enable", skill_id=skill_id, decision="granted",
                          detail={"scope": scope, "ttl": capped_ttl})
    return {"granted": True, "allowed_tools": list(ctx.active_tools)}


@mcp.tool()
async def disable_skill(skill_id: str) -> dict[str, Any]:
    """Disable a skill and revoke its grant.

    Contract:
        Silences:
            - If the skill has no grant in ``active_grants``
              (e.g. the grant expired and was cleaned up), the
              revoke step is silently skipped.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state
    state = rt.state_manager.load_or_init(sid)

    if skill_id not in state.skills_loaded:
        return {"disabled": False, "reason": "Skill not enabled"}

    # Step 3: Mutate persisted-only fields
    grant = state.active_grants.get(skill_id)
    if grant:
        rt.grant_manager.revoke_grant(grant.grant_id, reason="explicit")

    rt.state_manager.remove_from_skills_loaded(state, skill_id)

    # Step 2: Derive runtime context after mutation
    ctx = _build_runtime_ctx(rt, state)
    # Mirror to state for backward compatibility
    state.sync_from_runtime(ctx.active_tools)

    # Step 4: Save persisted state
    rt.state_manager.save(state)
    rt.store.append_audit(sid, "skill.disable", skill_id=skill_id, decision="revoked")
    return {"disabled": True}


@mcp.tool()
async def grant_status() -> list[dict[str, Any]]:
    """View current authorization status for the session.

    Returns all grants with ``status='active'`` in the DB.  Note
    that these may include grants past their ``expires_at`` if
    ``cleanup_expired`` hasn't run since they expired.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state (for consistency with other entry points)
    state = rt.state_manager.load_or_init(sid)
    # Step 2: Derive runtime context (not used, but maintains four-step pattern)
    ctx = _build_runtime_ctx(rt, state)
    # Step 3: No mutation (read-only operation)
    # Step 4: No save needed (read-only operation)
    grants = rt.grant_manager.get_active_grants(sid)
    return [g.model_dump() for g in grants]


@mcp.tool()
async def run_skill_action(skill_id: str, op: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute an operation within an enabled skill.

    Contract:
        Silences:
            - **Any exception** from the dispatch handler is caught
              by ``except Exception`` and returned as
              ``{"error": str(e)}``.  The caller cannot distinguish
              a handler that intentionally returned an error dict
              from one that crashed.

        Denies:
            - If ``skill_id`` is loaded but has no metadata
              (``meta`` is ``None``), the call is denied
              (``meta_missing``) without dispatching.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state
    state = rt.state_manager.load_or_init(sid)

    if skill_id not in state.skills_loaded:
        return {"error": f"Skill '{skill_id}' is not enabled"}

    if not rt.grant_manager.is_grant_valid(sid, skill_id):
        return {"error": f"Grant for '{skill_id}' has expired. Re-enable the skill."}

    # Step 2: Derive runtime context to get metadata
    ctx = _build_runtime_ctx(rt, state)

    # Deny-by-default when metadata is unresolved: we cannot evaluate
    # allowed_ops without it, so dispatching would bypass the guard.
    meta = ctx.all_skills_metadata.get(skill_id)
    if meta is None:
        rt.store.append_audit(
            sid, "skill.action.deny", skill_id=skill_id,
            detail={"op": op, "reason": "meta_missing"},
        )
        return {"error": f"Skill '{skill_id}' metadata unavailable; operation denied"}

    if op not in meta.allowed_ops:
        return {"error": f"Operation '{op}' is not in allowed_ops for '{skill_id}'"}

    # Step 3: No mutation (execution only)
    # Step 4: No save needed (execution only)
    from tool_governance.core.skill_executor import dispatch
    try:
        result = dispatch(skill_id, op, args or {})
    except Exception as e:
        return {"error": str(e)}

    return {"result": result}


@mcp.tool()
async def change_stage(skill_id: str, stage_id: str) -> dict[str, Any]:
    """Switch a skill's active stage, updating allowed tools.

    This is the best-validated tool — explicitly checks that the
    skill is enabled, has metadata, supports stages, and that the
    requested stage_id exists.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state
    state = rt.state_manager.load_or_init(sid)

    if skill_id not in state.skills_loaded:
        return {"error": f"Skill '{skill_id}' must be enabled first"}

    # Step 2: Derive runtime context to get metadata
    ctx = _build_runtime_ctx(rt, state)

    meta = ctx.all_skills_metadata.get(skill_id)
    if meta is None:
        return {"error": f"Skill '{skill_id}' not found"}

    if not meta.stages:
        return {"error": f"Skill '{skill_id}' does not support stages"}

    valid_stages = {s.stage_id for s in meta.stages}
    if stage_id not in valid_stages:
        return {"error": f"Stage '{stage_id}' not defined. Valid: {sorted(valid_stages)}"}

    # Step 3: Mutate persisted-only field (current_stage)
    state.skills_loaded[skill_id].current_stage = stage_id

    # Rebuild runtime context after mutation to get updated active_tools
    ctx = _build_runtime_ctx(rt, state)
    # Mirror to state for backward compatibility
    state.sync_from_runtime(ctx.active_tools)

    # Step 4: Save persisted state
    rt.state_manager.save(state)
    rt.store.append_audit(sid, "stage.change", skill_id=skill_id,
                          detail={"new_stage": stage_id})
    return {"changed": True, "new_active_tools": list(ctx.active_tools)}


@mcp.tool()
async def refresh_skills() -> dict[str, Any]:
    """Force-refresh the skill index (clear caches, rescan directory).

    Performs exactly one directory scan per call: ``refresh()``
    clears the content cache and rebuilds the internal index, and
    the current state is then read back via ``current_index()``
    without a second rescan.
    """
    rt = _get_runtime()
    sid = _session_id()
    # Step 1: Load persisted state (for consistency)
    state = rt.state_manager.load_or_init(sid)

    # Step 2: Refresh indexer (clears caches and rescans)
    count = rt.indexer.refresh()

    # Step 3: No mutation to state.skills_metadata (it's a derived field)
    # The next turn's build_runtime_context will pick up fresh metadata
    # from indexer.current_index()

    # Step 4: No save needed (no state mutation)
    return {"refreshed": True, "skill_count": count}


def main() -> None:
    """Start the stdio MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
