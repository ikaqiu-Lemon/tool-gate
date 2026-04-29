"""Functional happy-path tests (Stage B).

Drives the real ``hook_handler`` and ``mcp_server`` entry points
in-process against a tmp-dir ``GovernanceRuntime`` backed by the
``mock_*`` fixtures under ``tests/fixtures/skills/``. Stage C will add
deny / ttl / stage / refresh / revoke / parity coverage.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server
from tool_governance.core import skill_executor as skill_executor_mod

from ._support import events
from ._support.audit import events_of_type
from ._support.runtime import runtime_context


class TestSessionStartIndexesMockSkills:
    """SessionStart must build the index from the mock fixture tree."""

    def test_index_contains_all_valid_mocks(self, tmp_path, session_id) -> None:
        with runtime_context(tmp_path) as rt:
            result = hook_handler.handle_session_start(events.session_start(session_id))

            # Stage D of ``migrate-entrypoints-to-runtime-flow``:
            # ``skills_metadata`` is no longer persisted.  Read from
            # the authoritative indexer instead.
            metadata = rt.indexer.current_index()
            ids = set(metadata.keys())
            for expected in (
                "mock_readonly",
                "mock_stageful",
                "mock_sensitive",
                "mock_ttl",
                "mock_refreshable",
            ):
                assert expected in ids, f"missing fixture skill: {expected}"

            assert "additionalContext" in result
            assert "Mock Readonly" in result["additionalContext"]


class TestListSkillsReturnsMocks:
    def test_list_skills_includes_mock_readonly(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))
            listed = asyncio.run(mcp_server.list_skills())

            by_id = {entry["skill_id"]: entry for entry in listed}
            assert "mock_readonly" in by_id
            assert by_id["mock_readonly"]["risk_level"] == "low"
            assert by_id["mock_readonly"]["is_enabled"] is False


class TestReadSkillReturnsSop:
    def test_read_skill_returns_body(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))
            content = asyncio.run(mcp_server.read_skill("mock_readonly"))

            assert "metadata" in content
            assert content["metadata"]["skill_id"] == "mock_readonly"
            assert "Fixture skill for the functional test harness" in content["sop"]


class TestEnableSkillGrantsLowRisk:
    def test_enable_adds_tools_and_creates_grant(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(
                    skill_id="mock_readonly", scope="session", ttl=3600
                )
            )

            assert resp["granted"] is True
            tools = set(resp["allowed_tools"])
            assert "mock_read" in tools
            assert "mock_glob" in tools

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" in state.skills_loaded

            grants = rt.grant_manager.get_active_grants(session_id)
            assert len(grants) == 1
            assert grants[0].skill_id == "mock_readonly"
            assert grants[0].scope == "session"
            assert grants[0].granted_by == "auto"


class TestUserPromptSubmitRefreshesContext:
    def test_additional_context_mentions_active_tools_after_enable(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            result = hook_handler.handle_user_prompt_submit(
                events.user_prompt_submit(session_id)
            )
            ctx = result["additionalContext"]
            assert "mock_read" in ctx
            assert "mock_glob" in ctx
            assert "[ENABLED" in ctx

            state = rt.state_manager.load_or_init(session_id)
            # Stage C3 excluded ``active_tools`` from the persisted
            # payload; recompute the in-memory derivation before
            # asserting against it.
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            assert "mock_read" in state.active_tools
            assert "mock_glob" in state.active_tools


class TestRunSkillActionDispatch:
    """Happy-path ``run_skill_action``.

    The production ``skill_executor.dispatch`` ships stub handlers for
    real skills only, so we monkeypatch it here — functional tests must
    not depend on production-skill handlers being registered. The call
    still exercises the full MCP entry-point gate chain (load state,
    grant check, allowed_ops check, dispatch).
    """

    def test_run_skill_action_returns_result(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        captured: list[tuple[str, str, dict]] = []

        def stub_dispatch(skill_id: str, op: str, args: dict) -> dict:
            captured.append((skill_id, op, dict(args)))
            return {"info": f"{skill_id}:{op}"}

        monkeypatch.setattr(skill_executor_mod, "dispatch", stub_dispatch)

        with runtime_context(tmp_path):
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            resp = asyncio.run(
                mcp_server.run_skill_action(
                    "mock_readonly", "search", {"pattern": "foo"}
                )
            )
            assert resp == {"result": {"info": "mock_readonly:search"}}
            assert captured == [("mock_readonly", "search", {"pattern": "foo"})]


class TestPostToolUseWriteback:
    def test_last_used_at_stamped_and_audit_logged(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            # Set up grant directly so the assertion is scoped to the
            # PostToolUse handler and does not depend on enable_skill.
            state = rt.state_manager.load_or_init(session_id)
            # Stage D: read from indexer instead of persisted state.
            meta = rt.indexer.current_index()["mock_readonly"]
            grant = rt.grant_manager.create_grant(
                session_id, "mock_readonly", meta.allowed_ops
            )
            rt.state_manager.add_to_skills_loaded(state, "mock_readonly")
            state.active_grants["mock_readonly"] = grant
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            rt.state_manager.save(state)

            hook_handler.handle_post_tool_use(
                events.post_tool_use(session_id, "mock_read")
            )

            state = rt.state_manager.load_or_init(session_id)
            assert state.skills_loaded["mock_readonly"].last_used_at is not None

            tool_calls = events_of_type(rt, session_id, "tool.call")
            assert any(row.get("tool_name") == "mock_read" for row in tool_calls)
