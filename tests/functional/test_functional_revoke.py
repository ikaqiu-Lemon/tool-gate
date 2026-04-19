"""Functional disable_skill / revoke tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
explicit disable must emit ``grant.revoke`` (from ``GrantManager``)
before ``skill.disable`` (from the entry point), and subsequently
remove the skill's tools from ``active_tools``.
"""

from __future__ import annotations

import asyncio
import json

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.runtime import runtime_context


class TestDisableSkillRevokesAndAudits:
    def test_active_tools_drops_after_disable(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_read" in state.active_tools

            resp = asyncio.run(mcp_server.disable_skill(skill_id="mock_readonly"))
            assert resp["disabled"] is True

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" not in state.skills_loaded
            assert "mock_read" not in state.active_tools
            assert "mock_glob" not in state.active_tools

    def test_audit_order_revoke_then_disable_with_reason(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            asyncio.run(mcp_server.disable_skill(skill_id="mock_readonly"))

            all_events = rt.store.query_audit(session_id=session_id)
            relevant = [
                e for e in all_events
                if e["event_type"] in ("grant.revoke", "skill.disable")
            ]
            assert [e["event_type"] for e in relevant] == [
                "grant.revoke",
                "skill.disable",
            ]
            revoke_detail = json.loads(relevant[0]["detail"])
            assert revoke_detail["reason"] == "explicit"
            assert relevant[0]["skill_id"] == relevant[1]["skill_id"] == "mock_readonly"
