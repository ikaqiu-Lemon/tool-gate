"""Functional PreToolUse gating tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
specifically the PreToolUse deny path for tools not in ``active_tools``
and the corresponding guidance ``additionalContext``. Complements the
happy-path allow case by asserting the negative branch.
"""

from __future__ import annotations

from tool_governance import hook_handler

from ._support import events
from ._support.audit import events_of_type, decoded_detail
from ._support.runtime import runtime_context


class TestPreToolUseDeniesNonAllowlistedTool:
    def test_tool_outside_active_tools_is_denied(self, tmp_path, session_id) -> None:
        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))

            result = hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mock_read")
            )
            out = result["hookSpecificOutput"]
            assert out["hookEventName"] == "PreToolUse"
            assert out["permissionDecision"] == "deny"
            assert "permissionDecisionReason" in out
            assert "enable_skill" in out["additionalContext"]

    def test_meta_tool_is_always_allowed(self, tmp_path, session_id) -> None:
        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))
            result = hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mcp__tool-governance__list_skills")
            )
            assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_deny_records_whitelist_violation_audit(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mock_dangerous")
            )
            calls = events_of_type(rt, session_id, "tool.call")
            denies = [row for row in calls if row.get("decision") == "deny"]
            assert len(denies) >= 1
            detail = decoded_detail(denies[-1])
            assert detail.get("error_bucket") == "whitelist_violation"

    def test_mcp_namespaced_tool_is_denied_when_not_active(
        self, tmp_path, session_id
    ) -> None:
        """``mcp__<server>__<tool>`` naming hits the same gate — no skill
        is enabled, so a mock-namespaced tool must be denied."""
        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))
            result = hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mcp__mock_echo__echo")
            )
            assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
