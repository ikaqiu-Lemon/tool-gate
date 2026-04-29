"""Functional TTL-expiry tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
TTL expiry path: a grant whose ``expires_at`` is in the past must
cause ``run_skill_action`` to fail, and the next ``UserPromptSubmit``
sweep must drop the skill from ``skills_loaded`` and emit
``grant.expire`` (NOT ``grant.revoke``).
"""

from __future__ import annotations

import asyncio
import time

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.audit import events_of_type
from ._support.runtime import runtime_context


class TestTTLExpiryInvalidatesRunSkillAction:
    def test_expired_grant_blocks_run_skill_action(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            state = rt.state_manager.load_or_init(session_id)
            # Stage D: read from indexer instead of persisted state.
            meta = rt.indexer.current_index()["mock_ttl"]
            grant = rt.grant_manager.create_grant(
                session_id, "mock_ttl", meta.allowed_ops, ttl=0
            )
            rt.state_manager.add_to_skills_loaded(state, "mock_ttl")
            state.active_grants["mock_ttl"] = grant
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            rt.state_manager.save(state)

            time.sleep(0.1)  # ensure expires_at < now

            resp = asyncio.run(
                mcp_server.run_skill_action("mock_ttl", "ping", {})
            )
            assert "error" in resp
            assert "expired" in resp["error"].lower()


class TestUserPromptSubmitReclaimsExpiredGrant:
    def test_expire_audit_no_revoke_and_skill_unloaded(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            state = rt.state_manager.load_or_init(session_id)
            # Stage D: read from indexer instead of persisted state.
            meta = rt.indexer.current_index()["mock_ttl"]
            grant = rt.grant_manager.create_grant(
                session_id, "mock_ttl", meta.allowed_ops, ttl=0
            )
            rt.state_manager.add_to_skills_loaded(state, "mock_ttl")
            state.active_grants["mock_ttl"] = grant
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            rt.state_manager.save(state)

            time.sleep(0.1)
            hook_handler.handle_user_prompt_submit(
                events.user_prompt_submit(session_id)
            )

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_ttl" not in state.skills_loaded

            expires = events_of_type(rt, session_id, "grant.expire")
            revokes = events_of_type(rt, session_id, "grant.revoke")
            assert any(row["skill_id"] == "mock_ttl" for row in expires)
            assert revokes == []
