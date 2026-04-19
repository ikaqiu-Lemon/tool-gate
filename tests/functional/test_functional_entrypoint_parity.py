"""Functional MCP ↔ LangChain entry-point parity (Stage C).

Covers the spec Requirement "MCP and LangChain Entry-Point Parity
Coverage". Minimal — just enough to assert the two wrappers produce
equivalent grants and agree on ``scope`` coercion. The deeper
per-field parity matrix already lives in ``tests/test_integration.py``.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server
from tool_governance.tools.langchain_tools import enable_skill_tool

from ._support import events
from ._support.runtime import runtime_context


class TestEntryPointParity:
    def test_identical_inputs_produce_equivalent_grants(
        self, tmp_path, monkeypatch
    ) -> None:
        mcp_sid = "func-parity-mcp"
        lc_sid = "func-parity-lc"
        monkeypatch.setenv("CLAUDE_SESSION_ID", mcp_sid)

        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(mcp_sid))
            hook_handler.handle_session_start(events.session_start(lc_sid))

            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            enable_skill_tool.invoke(
                {"runtime": rt, "session_id": lc_sid, "skill_id": "mock_readonly"}
            )

            mcp_grants = rt.grant_manager.get_active_grants(mcp_sid)
            lc_grants = rt.grant_manager.get_active_grants(lc_sid)
            assert len(mcp_grants) == len(lc_grants) == 1
            mg, lg = mcp_grants[0], lc_grants[0]
            assert mg.scope == lg.scope == "session"
            assert mg.granted_by == lg.granted_by == "auto"
            assert mg.allowed_ops == lg.allowed_ops

    def test_unrecognised_scope_coerces_to_session_on_both_paths(
        self, tmp_path, monkeypatch
    ) -> None:
        mcp_sid = "func-parity-bad-mcp"
        lc_sid = "func-parity-bad-lc"
        monkeypatch.setenv("CLAUDE_SESSION_ID", mcp_sid)

        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(mcp_sid))
            hook_handler.handle_session_start(events.session_start(lc_sid))

            asyncio.run(
                mcp_server.enable_skill(
                    skill_id="mock_readonly", scope="not-a-real-scope"
                )
            )
            # Must not raise on the LangChain path.
            enable_skill_tool.invoke(
                {
                    "runtime": rt,
                    "session_id": lc_sid,
                    "skill_id": "mock_readonly",
                    "scope": "not-a-real-scope",
                }
            )

            mg = rt.grant_manager.get_active_grants(mcp_sid)[0]
            lg = rt.grant_manager.get_active_grants(lc_sid)[0]
            assert mg.scope == lg.scope == "session"
