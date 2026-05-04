"""Functional PreToolUse gating tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
specifically the PreToolUse deny path for tools not in ``active_tools``
and the corresponding guidance ``additionalContext``. Complements the
happy-path allow case by asserting the negative branch.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server

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

    def test_deny_records_tool_not_available_audit(
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
            assert detail.get("error_bucket") == "tool_not_available"

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


class TestPreToolUseClassifiesWrongSkillTool:
    """A deny for a tool that belongs to a *different*, non-enabled skill
    must carry ``error_bucket="wrong_skill_tool"`` — spec's deny-bucket
    scenario #2."""

    def test_tool_owned_by_non_enabled_skill_is_wrong_skill_tool(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mock_dangerous")
            )

            calls = events_of_type(rt, session_id, "tool.call")
            denies = [row for row in calls if row.get("decision") == "deny"]
            assert len(denies) >= 1
            detail = decoded_detail(denies[-1])
            assert detail.get("error_bucket") == "wrong_skill_tool"


class TestPostToolUseClassifiesParameterError:
    """When a tool_response carries an error signal, PostToolUse must
    record ``decision="error"`` with ``error_bucket="parameter_error"``
    — spec's deny-bucket scenario #3."""

    def test_is_error_response_records_parameter_error(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            hook_handler.handle_post_tool_use(
                {
                    "event": "PostToolUse",
                    "session_id": session_id,
                    "tool_name": "mock_read",
                    "tool_response": {"is_error": True, "content": "bad args"},
                }
            )

            calls = events_of_type(rt, session_id, "tool.call")
            errors = [row for row in calls if row.get("decision") == "error"]
            assert len(errors) == 1
            detail = decoded_detail(errors[0])
            assert detail.get("error_bucket") == "parameter_error"

    def test_ok_response_still_records_allow(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            hook_handler.handle_post_tool_use(
                {
                    "event": "PostToolUse",
                    "session_id": session_id,
                    "tool_name": "mock_read",
                    "tool_response": {"content": "ok"},
                }
            )

            calls = events_of_type(rt, session_id, "tool.call")
            allows = [row for row in calls if row.get("decision") == "allow"]
            errors = [row for row in calls if row.get("decision") == "error"]
            assert len(allows) == 1
            assert errors == []
