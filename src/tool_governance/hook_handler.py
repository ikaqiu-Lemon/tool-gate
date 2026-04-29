"""Hook handler entry point — processes SessionStart, UserPromptSubmit, PreToolUse, PostToolUse.

This module is the **stdin/stdout boundary** of the governance system.
Claude's hook mechanism invokes ``main()`` as a subprocess, passes a
JSON event on stdin, and reads the JSON result from stdout.  Each
event type dispatches to a dedicated handler that orchestrates the
governance modules via the singleton ``GovernanceRuntime``.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from typing import Any

from tool_governance.bootstrap import create_governance_runtime, GovernanceRuntime
from tool_governance.core.runtime_context import (
    RuntimeContext,
    build_runtime_context,
)
from tool_governance.core.state_manager import discover_session_id
from tool_governance.core.tool_rewriter import META_TOOLS
from tool_governance.models.state import SessionState

# Lazy singleton — initialised on first call to _get_runtime().
_runtime: GovernanceRuntime | None = None

# Short names of meta-tools (extracted from full MCP names) so that
# PreToolUse can fast-path them without a state lookup.
_META_SHORT_NAMES: frozenset[str] = frozenset(
    name.split("__")[-1] for name in META_TOOLS
)


def _get_runtime() -> GovernanceRuntime:
    """Return (and lazily create) the process-wide GovernanceRuntime.

    Reads directory paths from environment variables, falling back to
    current-directory defaults.

    Contract:
        Raises:
            sqlite3.OperationalError: If the SQLite database cannot
                be opened (from ``create_governance_runtime``, on
                first call only, not caught).
            yaml.YAMLError / pydantic.ValidationError: If the policy
                config file is corrupt (on first call only,
                not caught).

        Silences:
            - Missing env vars (``GOVERNANCE_DATA_DIR``,
              ``GOVERNANCE_SKILLS_DIR``, ``GOVERNANCE_CONFIG_DIR``,
              ``CLAUDE_PLUGIN_DATA``, ``CLAUDE_PLUGIN_ROOT``) silently
              fall back to ``"."`` or ``"./skills"`` / ``"./config"``.
    """
    global _runtime
    if _runtime is None:
        data_dir = os.environ.get("GOVERNANCE_DATA_DIR", os.environ.get("CLAUDE_PLUGIN_DATA", "."))
        skills_dir = os.environ.get("GOVERNANCE_SKILLS_DIR", os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/skills")
        config_dir = os.environ.get("GOVERNANCE_CONFIG_DIR", os.environ.get("CLAUDE_PLUGIN_ROOT", ".") + "/config")
        _runtime = create_governance_runtime(data_dir, skills_dir, config_dir)
    return _runtime


def _extract_tool_short_name(tool_name: str) -> str:
    """Extract short name: mcp__tool-governance__list_skills → list_skills.

    Falls back to the full ``tool_name`` when fewer than 3 ``__``
    segments are present.
    """
    parts = tool_name.split("__")
    return parts[-1] if len(parts) >= 3 else tool_name


def _build_runtime_ctx(rt: GovernanceRuntime, state: SessionState) -> RuntimeContext:
    """Build the per-turn ``RuntimeContext`` for a hook invocation.

    Introduced in Stage B of ``separate-runtime-and-persisted-state``
    so that derived-field reads within the hook layer (deny-bucket
    classification, post-tool-use skill lookup) flow through the
    runtime view instead of ``SessionState`` directly.

    Metadata preference order:
        1. ``rt.indexer.current_index()`` — authoritative since the
           cache-layer formalization.
        2. ``state.skills_metadata`` — legacy session snapshot, kept
           as a fallback so a cold start (empty indexer) still yields
           a usable context.  Stage C will drop this fallback once
           every writer populates the indexer.

    The function is a thin wrapper: callers can build a context by
    hand (see the unit tests) when they need to inject a specific
    metadata map or clock.
    """
    metadata = rt.indexer.current_index() or state.skills_metadata
    return build_runtime_context(
        state,
        metadata=metadata,
        blocked_tools=rt.tool_rewriter.blocked_tools,
    )


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def handle_session_start(input_data: dict[str, Any]) -> dict[str, Any]:
    """SessionStart: init state, cleanup grants, build index, inject catalog.

    Called once when a new Claude session begins.  Stage C lifecycle
    for ``separate-runtime-and-persisted-state``:

        1. Load persisted state (+ reconcile: cleanup expired grants,
           populate skill index if empty — both are durable
           mutations applied directly to ``SessionState``).
        2. Derive the per-turn ``RuntimeContext`` from the reconciled
           state, the live skill index, and the current policy.
        3. Let rewrite (``active_tools``) and prompt composition both
           consume the runtime view.  Mirror ``active_tools`` onto
           the persisted snapshot for unmigrated readers.
        4. Persist durable fields.

    Contract:
        Raises:
            Any unhandled exception from the runtime modules
            (SQLite errors, Pydantic validation errors, etc.)
            propagates to ``main()`` and crashes the hook process.

        Silences:
            - Expired grants are removed from ``skills_loaded`` and
              logged to audit, but the model receives no notification
              that a skill it previously used is no longer available.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)

    # 1. Load persisted (+ reconcile).
    state = rt.state_manager.load_or_init(session_id)
    expired = rt.grant_manager.cleanup_expired(session_id)
    for skill_id in expired:
        rt.state_manager.remove_from_skills_loaded(state, skill_id)
        rt.store.append_audit(
            session_id, "grant.expire", skill_id=skill_id, decision="expired"
        )
    if not state.skills_metadata:
        state.skills_metadata = rt.indexer.build_index()

    # 2. Derive runtime view.
    ctx = _build_runtime_ctx(rt, state)

    # 3. Rewrite / compose consume the runtime view.
    state.sync_from_runtime(ctx.active_tools)
    additional_context = rt.prompt_composer.compose_skill_catalog(ctx)

    # 4. Persist durable fields.
    rt.state_manager.save(state)

    return {"additionalContext": additional_context}


def handle_user_prompt_submit(input_data: dict[str, Any]) -> dict[str, Any]:
    """UserPromptSubmit: per-turn cleanup, recompute, inject context.

    Called before every user message is processed.  Follows the same
    Stage C lifecycle as ``handle_session_start``: load (+ reconcile)
    → derive → rewrite/compose on the runtime view → persist.

    Contract:
        Raises:
            Same propagation rules as ``handle_session_start``.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)

    # 1. Load persisted (+ reconcile).
    state = rt.state_manager.load_or_init(session_id)
    expired = rt.grant_manager.cleanup_expired(session_id)
    for skill_id in expired:
        rt.state_manager.remove_from_skills_loaded(state, skill_id)
        rt.store.append_audit(
            session_id, "grant.expire", skill_id=skill_id, decision="expired"
        )

    # 2. Derive runtime view.
    ctx = _build_runtime_ctx(rt, state)

    # 3. Rewrite / compose consume the runtime view.
    state.sync_from_runtime(ctx.active_tools)
    additional_context = rt.prompt_composer.compose_context(ctx)

    # 4. Persist durable fields.
    rt.state_manager.save(state)

    rt.store.append_audit(
        session_id,
        "prompt.submit",
        detail={
            "active_skills": list(state.skills_loaded.keys()),
            "active_tools_count": len(ctx.active_tools),
        },
    )

    return {"additionalContext": additional_context}


def _is_error_response(tool_response: Any) -> bool:
    """Return True if the PostToolUse tool_response signals a failure.

    Recognises the two common error shapes seen across Claude Code
    tools: a dict with a truthy ``is_error`` flag or a non-empty
    ``error`` field.  Non-dict responses never signal failure here.
    """
    if not isinstance(tool_response, dict):
        return False
    if tool_response.get("is_error"):
        return True
    err = tool_response.get("error")
    return bool(err) and err != ""


def _classify_deny_bucket(tool_name: str, runtime_ctx: RuntimeContext) -> str:
    """Return the ``error_bucket`` for a PreToolUse deny decision.

    Matches the spec's two gate-time buckets:

    - ``wrong_skill_tool``: at least one skill IS enabled, the tool is
      not in any enabled skill's ``allowed_tools`` (top-level or stage),
      but it IS in some *other* indexed skill's ``allowed_tools`` — the
      model picked a known tool without enabling the skill that owns it.
    - ``whitelist_violation``: every other deny — no skill is enabled
      at all, the tool is unknown to every indexed skill, or the tool
      belongs to an enabled skill but was stripped from ``active_tools``
      by policy (e.g. ``blocked_tools`` or stage gating).

    The third bucket (``parameter_error``) is not gate-detectable; it is
    classified in :func:`handle_post_tool_use` when the tool response
    carries an error signal.

    Stage B of ``separate-runtime-and-persisted-state`` switched this
    helper from consuming ``SessionState`` directly to consuming the
    per-turn ``RuntimeContext`` — the runtime view is the authoritative
    input for this classification, not the persisted snapshot.
    """
    enabled_ids = runtime_ctx.enabled_skill_ids()

    if not enabled_ids:
        return "whitelist_violation"

    for sv in runtime_ctx.enabled_skills:
        if tool_name in sv.metadata.allowed_tools:
            return "whitelist_violation"
        for stage in sv.metadata.stages or []:
            if tool_name in stage.allowed_tools:
                return "whitelist_violation"

    for skill_id, meta in runtime_ctx.all_skills_metadata.items():
        if not meta or skill_id in enabled_ids:
            continue
        if tool_name in meta.allowed_tools:
            return "wrong_skill_tool"
        for stage in meta.stages or []:
            if tool_name in stage.allowed_tools:
                return "wrong_skill_tool"

    return "whitelist_violation"


def handle_pre_tool_use(input_data: dict[str, Any]) -> dict[str, Any]:
    """PreToolUse: gate-check a tool against the runtime view's active tools.

    Meta-tools (list_skills, enable_skill, etc.) are always allowed
    without a state lookup.  For every other tool call, the Stage C
    lifecycle is:

        1. Load persisted state.
        2. Derive the per-turn ``RuntimeContext``.
        3. Execute: check ``ctx.active_tools_set()``; allow or deny
           and record the audit event.

    No persistence step is needed — gate check is read-only on state.

    Contract:
        Silences:
            - Missing ``tool_name`` in ``input_data`` defaults to
              ``""`` via ``.get()``.  An empty tool name will fail
              the active_tools check and be denied — no explicit
              error for the malformed input.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)
    tool_name = input_data.get("tool_name", "")

    short_name = _extract_tool_short_name(tool_name)

    # Meta-tools bypass the active_tools gate entirely — they are
    # needed to discover and enable skills in the first place.
    if short_name in _META_SHORT_NAMES or tool_name in META_TOOLS:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    # 1. Load persisted.
    state = rt.state_manager.load_or_init(session_id)

    # 2. Derive runtime view.
    ctx = _build_runtime_ctx(rt, state)

    # 3. Execute: gate check off the runtime view.
    if tool_name in ctx.active_tools_set():
        rt.store.append_audit(
            session_id, "tool.call", tool_name=tool_name, decision="allow"
        )
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    bucket = _classify_deny_bucket(tool_name, ctx)
    rt.store.append_audit(
        session_id,
        "tool.call",
        tool_name=tool_name,
        decision="deny",
        detail={"error_bucket": bucket},
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                f"Tool '{tool_name}' is not in active_tools. "
                "Please use read_skill and enable_skill to authorize the required skill first."
            ),
            "additionalContext": (
                "To use this tool, first discover available skills with list_skills, "
                "then read_skill to understand the workflow, then enable_skill to authorize."
            ),
        }
    }


def handle_post_tool_use(input_data: dict[str, Any]) -> dict[str, Any]:
    """PostToolUse: update last_used_at, record audit log.

    Stage C lifecycle:
        1. Load persisted state.
        2. Derive the per-turn ``RuntimeContext``.
        3. Execute: find the skill that owns ``tool_name`` via the
           runtime view, then stamp ``last_used_at`` onto the
           persisted ``LoadedSkillInfo`` — the durable field.
        4. Persist durable fields.

    Exactly one skill is stamped per event — the first match wins,
    top-level ``allowed_tools`` taking precedence over stage-level.

    Contract:
        Silences:
            - If ``tool_name`` does not belong to any loaded skill,
              ``last_used_at`` is not updated for any skill.  No
              error is raised; the audit log still records the call.
            - Missing ``tool_name`` in ``input_data`` silently
              defaults to ``""``.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)
    tool_name = input_data.get("tool_name", "")

    # 1. Load persisted.
    state = rt.state_manager.load_or_init(session_id)

    # 2. Derive runtime view.
    ctx = _build_runtime_ctx(rt, state)

    # 3. Execute: lookup via runtime view, mutate the persisted
    # ``skills_loaded`` dict with the durable ``last_used_at`` stamp.
    matched = False
    for sv in ctx.enabled_skills:
        meta = sv.metadata
        if tool_name in meta.allowed_tools:
            state.skills_loaded[sv.skill_id].last_used_at = datetime.utcnow()
            matched = True
            break
        if meta.stages:
            for stage in meta.stages:
                if tool_name in stage.allowed_tools:
                    state.skills_loaded[sv.skill_id].last_used_at = datetime.utcnow()
                    matched = True
                    break
            if matched:
                break

    # 4. Persist durable fields.
    rt.state_manager.save(state)

    tool_response = input_data.get("tool_response")
    if _is_error_response(tool_response):
        rt.store.append_audit(
            session_id,
            "tool.call",
            tool_name=tool_name,
            decision="error",
            detail={"error_bucket": "parameter_error"},
        )
    else:
        rt.store.append_audit(
            session_id, "tool.call", tool_name=tool_name, decision="allow"
        )
    return {}


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

def main() -> None:
    """Process hook events from stdin and output results to stdout.

    Reads a single JSON object from stdin, dispatches to the matching
    handler, and prints the JSON result to stdout.  This is the
    process entry point invoked by Claude's hook mechanism.

    Contract:
        Raises:
            json.JSONDecodeError: If stdin contains non-empty,
                non-JSON text (not caught — crashes the process).
            Any unhandled exception from a handler propagates and
            crashes the process; Claude sees the non-zero exit code
            as a hook failure.

        Silences:
            - Empty stdin → prints ``{}`` and exits cleanly.
            - Unrecognised event names → prints ``{}`` and exits
              cleanly.  No log or error for unknown events.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({}))
        return

    input_data = json.loads(raw)
    event_name = input_data.get("event", "")

    handlers = {
        "SessionStart": handle_session_start,
        "UserPromptSubmit": handle_user_prompt_submit,
        "PreToolUse": handle_pre_tool_use,
        "PostToolUse": handle_post_tool_use,
    }

    handler = handlers.get(event_name)
    if handler:
        result = handler(input_data)
    else:
        result = {}

    print(json.dumps(result))


if __name__ == "__main__":
    main()
