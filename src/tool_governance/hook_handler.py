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
from tool_governance.core.state_manager import discover_session_id
from tool_governance.core.tool_rewriter import META_TOOLS

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


# ---------------------------------------------------------------------------
# Hook handlers
# ---------------------------------------------------------------------------

def handle_session_start(input_data: dict[str, Any]) -> dict[str, Any]:
    """SessionStart: init state, cleanup grants, build index, inject catalog.

    Called once when a new Claude session begins.  Performs first-time
    setup: loads or creates the session state, expires stale grants,
    populates the skill index (if the state was fresh), recomputes
    the active tool set, and returns a catalog for the model's context.

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
    state = rt.state_manager.load_or_init(session_id)

    # Cleanup expired grants and unload the corresponding skills.
    expired = rt.grant_manager.cleanup_expired(session_id)
    for skill_id in expired:
        rt.state_manager.remove_from_skills_loaded(state, skill_id)
        rt.store.append_audit(session_id, "grant.expire", skill_id=skill_id, decision="expired")

    # Populate index on first session (empty metadata means fresh state).
    if not state.skills_metadata:
        state.skills_metadata = rt.indexer.build_index()

    rt.tool_rewriter.recompute_active_tools(state)
    rt.state_manager.save(state)

    context = rt.prompt_composer.compose_skill_catalog(state)
    return {"additionalContext": context}


def handle_user_prompt_submit(input_data: dict[str, Any]) -> dict[str, Any]:
    """UserPromptSubmit: per-turn cleanup, recompute, inject context.

    Called before every user message is processed.  Repeats the
    grant-expiry sweep and tool recomputation, then injects the
    full context (catalog + active tools summary).

    Contract:
        Raises:
            Same propagation rules as ``handle_session_start``.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)
    state = rt.state_manager.load_or_init(session_id)

    expired = rt.grant_manager.cleanup_expired(session_id)
    for skill_id in expired:
        rt.state_manager.remove_from_skills_loaded(state, skill_id)
        rt.store.append_audit(session_id, "grant.expire", skill_id=skill_id, decision="expired")

    # Full recompute — not incremental — so the tool set is always
    # consistent with the current loaded-skills snapshot.
    rt.tool_rewriter.recompute_active_tools(state)

    context = rt.prompt_composer.compose_context(state)
    rt.state_manager.save(state)

    rt.store.append_audit(session_id, "prompt.submit",
                          detail={"active_skills": list(state.skills_loaded.keys()),
                                  "active_tools_count": len(state.active_tools)})

    return {"additionalContext": context}


def handle_pre_tool_use(input_data: dict[str, Any]) -> dict[str, Any]:
    """PreToolUse: gate-check a tool against active_tools.

    Meta-tools (list_skills, enable_skill, etc.) are always allowed
    without a state lookup.  All other tools must appear in the
    session's ``active_tools`` list; if not, the call is denied with
    a guidance message telling the model how to enable skills.

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

    state = rt.state_manager.load_or_init(session_id)

    if rt.policy_engine.is_tool_allowed(tool_name, state):
        rt.store.append_audit(session_id, "tool.call", tool_name=tool_name, decision="allow")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        }

    rt.store.append_audit(session_id, "tool.call", tool_name=tool_name, decision="deny",
                          detail={"error_bucket": "whitelist_violation"})
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

    Scans loaded skills to find which one owns the tool that was
    just used, then stamps ``last_used_at`` on the corresponding
    ``LoadedSkillInfo``.

    Contract:
        Silences:
            - If ``tool_name`` does not belong to any loaded skill,
              ``last_used_at`` is not updated for any skill.  No
              error is raised; the audit log still records the call.
            - Missing ``tool_name`` in ``input_data`` silently
              defaults to ``""``.

    .. note:: **Latent bug** — the inner ``break`` on the stage
       match only exits the stage loop, not the outer skill loop.
       If the tool is found in a stage's ``allowed_tools``, the
       outer loop continues to the next skill instead of stopping.
       The ``last_used_at`` is still set correctly for the matching
       skill, but unnecessary iterations occur and a later skill
       with the same tool in its top-level ``allowed_tools`` could
       overwrite the timestamp.
    """
    rt = _get_runtime()
    session_id = discover_session_id(input_data)
    tool_name = input_data.get("tool_name", "")

    state = rt.state_manager.load_or_init(session_id)

    # Find which skill owns this tool and update last_used_at.
    # Checks top-level allowed_tools first, then stage-level.
    for skill_id, loaded in state.skills_loaded.items():
        meta = state.skills_metadata.get(skill_id)
        if meta and tool_name in meta.allowed_tools:
            loaded.last_used_at = datetime.utcnow()
            break
        # NB: inner break only exits the stage loop — see docstring note.
        if meta and meta.stages:
            for stage in meta.stages:
                if tool_name in stage.allowed_tools:
                    loaded.last_used_at = datetime.utcnow()
                    break

    rt.state_manager.save(state)
    rt.store.append_audit(session_id, "tool.call", tool_name=tool_name, decision="allow")
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
