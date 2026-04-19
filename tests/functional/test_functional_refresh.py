"""Functional refresh_skills tests (Stage C).

Covers the spec Requirement "Lifecycle and Interception Coverage" —
``refresh_skills`` single-scan + visibility semantics. Pattern: start
with a tmp skills tree that excludes ``mock_refreshable``, verify it
is absent, drop the fixture in, call ``refresh_skills``, assert the
new skill becomes visible via ``list_skills``.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.runtime import runtime_context
from ._support.skills import copy_fixture_skills


class TestRefreshSkillsMakesNewFixtureVisible:
    def test_new_skill_visible_after_refresh(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        tmp_skills = tmp_path / "skills"
        copy_fixture_skills(tmp_skills, ["mock_readonly"])

        with runtime_context(tmp_path, skills_dir=tmp_skills):
            hook_handler.handle_session_start(events.session_start(session_id))

            before = asyncio.run(mcp_server.list_skills())
            before_ids = {entry["skill_id"] for entry in before}
            assert "mock_readonly" in before_ids
            assert "mock_refreshable" not in before_ids

            # Drop mock_refreshable into the tmp tree, then refresh.
            copy_fixture_skills(tmp_skills, ["mock_refreshable"])
            resp = asyncio.run(mcp_server.refresh_skills())
            assert resp["refreshed"] is True
            assert resp["skill_count"] == 2

            after = asyncio.run(mcp_server.list_skills())
            after_ids = {entry["skill_id"] for entry in after}
            assert "mock_refreshable" in after_ids
            assert "mock_readonly" in after_ids


class TestRefreshSkillsSingleScan:
    """D3 invariant re-asserted at the functional layer: one
    ``refresh_skills`` call triggers exactly one ``build_index``
    invocation."""

    def test_single_build_index_call_per_refresh(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        tmp_skills = tmp_path / "skills"
        copy_fixture_skills(tmp_skills, ["mock_readonly"])

        with runtime_context(tmp_path, skills_dir=tmp_skills) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            calls = {"n": 0}
            real_build = rt.indexer.build_index

            def counting_build():
                calls["n"] += 1
                return real_build()

            monkeypatch.setattr(rt.indexer, "build_index", counting_build)

            resp = asyncio.run(mcp_server.refresh_skills())
            assert resp["refreshed"] is True
            assert calls["n"] == 1
