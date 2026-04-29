"""Functional change_stage tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
``change_stage`` path: enable a medium-risk stageful mock, verify the
default stage's tools appear, switch stage, verify the new stage's
tools replace the old set, and a ``stage.change`` audit row is written.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.audit import events_of_type, decoded_detail
from ._support.runtime import runtime_context


class TestChangeStageSwapsToolSet:
    def test_analysis_to_execution_changes_active_tools(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            # Medium risk → reason required by default policy.
            enable_resp = asyncio.run(
                mcp_server.enable_skill(skill_id="mock_stageful", reason="fixing bug")
            )
            assert enable_resp["granted"] is True

            # Default stage is the first listed (analysis) — read tools only.
            # Stage C3 excluded ``active_tools`` from the persisted
            # payload, so we recompute the in-memory view from the
            # still-persisted skills_metadata + skills_loaded.
            state = rt.state_manager.load_or_init(session_id)
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            assert "mock_read" in state.active_tools
            assert "mock_glob" in state.active_tools
            assert "mock_edit" not in state.active_tools
            assert "mock_write" not in state.active_tools

            change_resp = asyncio.run(
                mcp_server.change_stage(
                    skill_id="mock_stageful", stage_id="execution"
                )
            )
            assert change_resp["changed"] is True
            new_tools = set(change_resp["new_active_tools"])
            assert "mock_edit" in new_tools
            assert "mock_write" in new_tools
            assert "mock_read" not in new_tools
            assert "mock_glob" not in new_tools

            audits = events_of_type(rt, session_id, "stage.change")
            assert len(audits) == 1
            assert audits[0]["skill_id"] == "mock_stageful"
            assert decoded_detail(audits[0])["new_stage"] == "execution"
