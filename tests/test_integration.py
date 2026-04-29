"""Integration tests — simulate full governance flows through hook and MCP layers.

These tests wire up a real GovernanceRuntime (with SQLite, skill
files on disk, and a YAML policy) and drive it through the hook
handler functions.  They verify that the components compose correctly
end-to-end, not just in isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tool_governance.bootstrap import create_governance_runtime
from tool_governance.core.skill_executor import dispatch
from tool_governance.hook_handler import (
    handle_post_tool_use,
    handle_pre_tool_use,
    handle_session_start,
    handle_user_prompt_submit,
)
import tool_governance.hook_handler as hh


@pytest.fixture()
def runtime(tmp_path: Path):
    """Create a real GovernanceRuntime backed by temp-dir artifacts.

    Sets up two skills on disk (repo-read: low/simple, code-edit:
    medium/staged) and a default policy that mirrors production
    defaults (low=auto, medium=reason, high=approval).

    Injects the runtime into ``hook_handler._runtime`` so that
    handle_* functions use this instance instead of the env-var-based
    singleton.  Tears down on fixture exit.
    """
    skills_dir = tmp_path / "skills"
    # repo-read: low-risk, stage-less, 3 tools
    (skills_dir / "repo-read").mkdir(parents=True)
    (skills_dir / "repo-read" / "SKILL.md").write_text(
        '---\nname: Repo Read\ndescription: "Read code"\nrisk_level: low\n'
        'allowed_tools:\n  - Read\n  - Glob\n  - Grep\n'
        'allowed_ops:\n  - search\n  - read_file\n---\n\n# Repo Read\n',
        encoding="utf-8",
    )
    # code-edit: medium-risk, 2 stages (analysis → execution)
    (skills_dir / "code-edit").mkdir()
    (skills_dir / "code-edit" / "SKILL.md").write_text(
        '---\nname: Code Edit\ndescription: "Edit code"\nrisk_level: medium\n'
        'allowed_ops:\n  - analyze\n  - edit\n'
        'stages:\n'
        '  - stage_id: analysis\n    allowed_tools: [Read, Glob]\n'
        '  - stage_id: execution\n    allowed_tools: [Edit, Write]\n'
        '---\n\n# Code Edit\n',
        encoding="utf-8",
    )

    data_dir = tmp_path / "data"
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "default_policy.yaml").write_text(
        'default_risk_thresholds:\n  low: auto\n  medium: reason\n  high: approval\n'
        'default_ttl: 3600\nblocked_tools: []\n',
        encoding="utf-8",
    )

    rt = create_governance_runtime(str(data_dir), str(skills_dir), str(config_dir))
    # Inject into hook_handler's module-level singleton.
    hh._runtime = rt
    yield rt
    hh._runtime = None


class TestFullFlow:
    """Simulate the happy path: SessionStart → list → read → enable →
    UserPromptSubmit → PreToolUse → PostToolUse."""

    def test_session_start_injects_catalog(self, runtime) -> None:
        """SessionStart must return additionalContext containing the
        skill catalog so the model knows what skills are available."""
        result = handle_session_start({"session_id": "test-flow"})
        assert "additionalContext" in result
        assert "Repo Read" in result["additionalContext"]

    def test_enable_low_risk_auto_grants(self, runtime) -> None:
        """Low-risk skill + default policy → auto-grant.  After
        enabling, the skill's tools (Read, Glob) must appear in
        active_tools.

        This test manually walks the enable flow (evaluate → create
        grant → add to loaded → recompute) to verify each step."""
        handle_session_start({"session_id": "test-flow"})
        state = runtime.state_manager.load_or_init("test-flow")
        # Stage D: read from indexer instead of persisted state.
        meta = runtime.indexer.current_index().get("repo-read")
        assert meta is not None

        # Policy evaluation: low risk → auto → allowed
        decision = runtime.policy_engine.evaluate("repo-read", meta, state)
        assert decision.allowed is True
        grant = runtime.grant_manager.create_grant("test-flow", "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        assert "Read" in state.active_tools
        assert "Glob" in state.active_tools

    def test_user_prompt_submit_updates_context(self, runtime) -> None:
        """UserPromptSubmit must return additionalContext (the per-turn
        context injection)."""
        handle_session_start({"session_id": "test-ups"})
        result = handle_user_prompt_submit({"session_id": "test-ups"})
        assert "additionalContext" in result

    def test_pre_tool_use_allows_meta_tools(self, runtime) -> None:
        """Meta-tools must always be allowed — they are the bootstrap
        tools the model needs to discover and enable skills."""
        handle_session_start({"session_id": "test-pre"})
        result = handle_pre_tool_use({
            "session_id": "test-pre",
            "tool_name": "mcp__tool-governance__list_skills",
        })
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_pre_tool_use_denies_unauthorized(self, runtime) -> None:
        """A tool that is not in active_tools must be denied — this
        is the core gate that enforces skill-based authorization."""
        handle_session_start({"session_id": "test-deny"})
        result = handle_pre_tool_use({
            "session_id": "test-deny",
            "tool_name": "Edit",
        })
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_pre_tool_use_allows_after_enable(self, runtime) -> None:
        """After enabling repo-read, its tools (Read) must be allowed.
        Exercises the full chain: enable → recompute → gate check."""
        handle_session_start({"session_id": "test-allow"})
        state = runtime.state_manager.load_or_init("test-allow")
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant("test-allow", "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        result = handle_pre_tool_use({
            "session_id": "test-allow",
            "tool_name": "Read",
        })
        assert result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_post_tool_use_records_audit(self, runtime) -> None:
        """PostToolUse must write an audit log entry — verify at least
        one tool.call event exists after the handler runs."""
        handle_session_start({"session_id": "test-post"})
        handle_post_tool_use({"session_id": "test-post", "tool_name": "Read"})
        logs = runtime.store.query_audit(session_id="test-post", event_type="tool.call")
        assert len(logs) >= 1


class TestDenyFlow:
    def test_deny_returns_guidance(self, runtime) -> None:
        """A denied tool must include guidance text telling the model
        how to enable skills — the additionalContext must mention
        enable_skill so the model can self-recover."""
        handle_session_start({"session_id": "test-deny2"})
        result = handle_pre_tool_use({
            "session_id": "test-deny2",
            "tool_name": "Bash",
        })
        output = result["hookSpecificOutput"]
        assert output["permissionDecision"] == "deny"
        assert "enable_skill" in output["additionalContext"]


class TestTTLExpiry:
    def test_expired_grant_cleaned_on_prompt_submit(self, runtime) -> None:
        """Create a grant with ttl=0 (effectively already expired),
        then trigger UserPromptSubmit.  The cleanup sweep must remove
        the skill from skills_loaded.

        Uses a short sleep to ensure the grant's expires_at is
        strictly in the past before the cleanup runs."""
        handle_session_start({"session_id": "test-ttl"})
        state = runtime.state_manager.load_or_init("test-ttl")
        meta = runtime.indexer.current_index()["repo-read"]
        # ttl=0 means expires_at == created_at — already expired.
        grant = runtime.grant_manager.create_grant("test-ttl", "repo-read", meta.allowed_ops, ttl=0)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        import time
        time.sleep(0.1)  # ensure expiry timestamp is in the past
        handle_user_prompt_submit({"session_id": "test-ttl"})

        state = runtime.state_manager.load_or_init("test-ttl")
        assert "repo-read" not in state.skills_loaded


class TestStageSwitch:
    def test_stage_switch_changes_tools(self, runtime) -> None:
        """Enable code-edit (medium risk, with reason), verify the
        default stage (analysis) exposes Read but not Edit, then
        switch to execution and verify Edit+Write appear.

        This is the end-to-end test for the staged-skill workflow:
        policy gate → grant → default stage tools → stage switch →
        new tool set."""
        handle_session_start({"session_id": "test-stage"})
        state = runtime.state_manager.load_or_init("test-stage")
        meta = runtime.indexer.current_index()["code-edit"]

        # Medium risk requires a reason — provide one.
        decision = runtime.policy_engine.evaluate("code-edit", meta, state, reason="fixing bug")
        assert decision.allowed is True
        grant = runtime.grant_manager.create_grant("test-stage", "code-edit", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "code-edit")
        state.active_grants["code-edit"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        # Default stage = first stage = analysis → Read-only tools.
        assert "Read" in state.active_tools
        assert "Edit" not in state.active_tools

        # Switch to execution stage → write tools appear.
        state.skills_loaded["code-edit"].current_stage = "execution"
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        assert "Edit" in state.active_tools
        assert "Write" in state.active_tools


class TestSkillExecutor:
    """Tests for the dispatch table (built-in stub handlers)."""

    def test_dispatch_registered_handler(self) -> None:
        """A registered (skill_id, op) pair must return a result dict
        with an "info" key (stub response)."""
        result = dispatch("repo-read", "search", {"pattern": "TODO"})
        assert "info" in result

    def test_dispatch_missing_handler(self) -> None:
        """An unregistered (skill_id, op) pair must return an error
        dict, not raise."""
        result = dispatch("unknown", "op", {})
        assert "error" in result


class TestRunSkillActionMetaMissing:
    """D2: run_skill_action must deny when skill metadata is unresolved.

    Covers the branch where a skill is in ``skills_loaded`` but has no
    corresponding entry in ``skills_metadata`` (e.g. metadata eviction,
    stale session state).  The pre-fix code skipped the ``allowed_ops``
    guard in this branch; the fix denies by default and emits
    ``skill.action.deny``.
    """

    def test_meta_none_denies_without_dispatch(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server
        from tool_governance.core import skill_executor as skill_executor_mod

        sid = "test-d2"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime

        handle_session_start({"session_id": sid})  # populate skills_metadata
        state = runtime.state_manager.load_or_init(sid)
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(sid, "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        # Force the meta-missing branch: skill is loaded but metadata is absent.
        # Remove from indexer's registry so current_index() won't return it
        if "repo-read" in runtime.indexer._indexed_skills:
            runtime.indexer._indexed_skills.pop("repo-read")
        runtime.state_manager.save(state)

        dispatch_calls: list[tuple[str, str]] = []

        def _spy_dispatch(skill_id: str, op: str, args: dict) -> dict:
            dispatch_calls.append((skill_id, op))
            return {"ok": True}

        monkeypatch.setattr(skill_executor_mod, "dispatch", _spy_dispatch)

        result = asyncio.run(mcp_server.run_skill_action("repo-read", "search", {}))

        assert "error" in result
        assert "metadata unavailable" in result["error"]
        assert dispatch_calls == []  # dispatch must not be called

        deny_logs = runtime.store.query_audit(session_id=sid, event_type="skill.action.deny")
        assert len(deny_logs) == 1
        assert deny_logs[0]["skill_id"] == "repo-read"

        mcp_server._runtime = None

    def test_meta_present_still_rejects_disallowed_op(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "test-d2-allowed-ops"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime

        handle_session_start({"session_id": sid})
        state = runtime.state_manager.load_or_init(sid)
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(sid, "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.state_manager.save(state)

        result = asyncio.run(mcp_server.run_skill_action("repo-read", "not_in_allowed", {}))
        assert "error" in result
        assert "allowed_ops" in result["error"]

        mcp_server._runtime = None


class TestPostToolUseSingleStamp:
    """D1: PostToolUse stamps ``last_used_at`` on exactly one skill.

    Two skills are loaded that both advertise the same tool in their
    ``allowed_tools``.  The first-iterated match wins; the second skill's
    ``last_used_at`` must remain unchanged.  A pre-existing (older)
    timestamp on the non-matching skill is the observable proof that it
    was not overwritten.
    """

    def test_only_first_match_is_stamped_top_level(self, runtime) -> None:
        from datetime import datetime, timedelta

        sid = "test-d1-toplevel"
        handle_session_start({"session_id": sid})
        state = runtime.state_manager.load_or_init(sid)

        # Inject a synthetic second skill that also advertises "Read" at
        # the top level.  We reuse repo-read's metadata shape and just
        # substitute skill_id so policy/grant plumbing stays identical.
        original = runtime.indexer.current_index()["repo-read"]
        clone = original.model_copy(update={"skill_id": "repo-read-clone", "name": "Clone"})
        runtime.indexer.current_index()["repo-read-clone"] = clone

        for skill_id in ("repo-read", "repo-read-clone"):
            grant = runtime.grant_manager.create_grant(sid, skill_id, original.allowed_ops)
            runtime.state_manager.add_to_skills_loaded(state, skill_id)
            state.active_grants[skill_id] = grant

        # Mark the SECOND skill with an old timestamp so we can detect
        # overwrite.  Iteration order is insertion order — repo-read
        # was inserted first, so it is the expected winner.
        sentinel = datetime.utcnow() - timedelta(hours=1)
        state.skills_loaded["repo-read-clone"].last_used_at = sentinel
        runtime.state_manager.save(state)

        handle_post_tool_use({"session_id": sid, "tool_name": "Read"})

        state = runtime.state_manager.load_or_init(sid)
        stamped = state.skills_loaded["repo-read"].last_used_at
        untouched = state.skills_loaded["repo-read-clone"].last_used_at

        assert stamped is not None and stamped > sentinel
        assert untouched == sentinel  # not overwritten by outer-loop continuation

    def test_stage_match_does_not_continue_to_later_skill(self, runtime) -> None:
        from datetime import datetime, timedelta

        sid = "test-d1-stage"
        handle_session_start({"session_id": sid})
        state = runtime.state_manager.load_or_init(sid)

        # code-edit has stage "execution" with allowed_tools [Edit, Write].
        # Make sure iteration reaches code-edit first, then have a second
        # skill that also top-level-matches "Edit".  If the stage-level
        # break only exits the inner loop, repo-read-editor would overwrite.
        code_edit_meta = runtime.indexer.current_index()["code-edit"]
        editor_clone = code_edit_meta.model_copy(update={
            "skill_id": "editor-clone",
            "name": "Editor Clone",
            "stages": [],
            "allowed_tools": ["Edit"],
            "allowed_ops": ["edit"],
        })
        runtime.indexer.current_index()["editor-clone"] = editor_clone

        # Enable code-edit with execution stage and the clone.
        grant1 = runtime.grant_manager.create_grant(sid, "code-edit", code_edit_meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "code-edit")
        state.skills_loaded["code-edit"].current_stage = "execution"
        state.active_grants["code-edit"] = grant1

        grant2 = runtime.grant_manager.create_grant(sid, "editor-clone", editor_clone.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "editor-clone")
        state.active_grants["editor-clone"] = grant2

        sentinel = datetime.utcnow() - timedelta(hours=1)
        state.skills_loaded["editor-clone"].last_used_at = sentinel
        runtime.state_manager.save(state)

        handle_post_tool_use({"session_id": sid, "tool_name": "Edit"})

        state = runtime.state_manager.load_or_init(sid)
        stamped = state.skills_loaded["code-edit"].last_used_at
        untouched = state.skills_loaded["editor-clone"].last_used_at

        assert stamped is not None and stamped > sentinel
        assert untouched == sentinel  # stage match must not fall through to later skill

    def test_unknown_tool_is_noop(self, runtime) -> None:
        sid = "test-d1-noop"
        handle_session_start({"session_id": sid})
        state = runtime.state_manager.load_or_init(sid)
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(sid, "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.state_manager.save(state)

        handle_post_tool_use({"session_id": sid, "tool_name": "NotAToolOwnedByAnySkill"})

        state = runtime.state_manager.load_or_init(sid)
        assert state.skills_loaded["repo-read"].last_used_at is None


class TestEnableSkillParity:
    """D6: ``enable_skill_tool`` (LangChain) and ``mcp_server.enable_skill``
    must produce equivalent grants and response shapes for identical
    inputs.  Both entry points MUST coerce ``scope`` to ``"turn" |
    "session"`` and map ``granted_by`` to ``"auto" | "policy"``.
    """

    def _enable_via_mcp(self, runtime, monkeypatch, sid: str, **kwargs):
        import asyncio

        import tool_governance.mcp_server as mcp_server

        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})
        try:
            return asyncio.run(mcp_server.enable_skill(**kwargs))
        finally:
            mcp_server._runtime = None

    def _enable_via_langchain(self, runtime, sid: str, **kwargs):
        from tool_governance.tools.langchain_tools import enable_skill_tool

        handle_session_start({"session_id": sid})
        # LangChain @tool wraps the function — invoke via .invoke with
        # a single dict so positional-vs-keyword conventions don't bite.
        return enable_skill_tool.invoke({"runtime": runtime, "session_id": sid, **kwargs})

    def test_identical_inputs_produce_equivalent_grants(self, runtime, monkeypatch) -> None:
        mcp_sid = "parity-mcp"
        lc_sid = "parity-lc"

        mcp_resp = self._enable_via_mcp(
            runtime, monkeypatch, mcp_sid,
            skill_id="repo-read", scope="session", ttl=3600,
        )
        lc_resp = self._enable_via_langchain(
            runtime, lc_sid,
            skill_id="repo-read", scope="session", ttl=3600,
        )

        assert mcp_resp["granted"] is True
        assert lc_resp["granted"] is True
        assert set(mcp_resp["allowed_tools"]) == set(lc_resp["allowed_tools"])

        mcp_grants = runtime.grant_manager.get_active_grants(mcp_sid)
        lc_grants = runtime.grant_manager.get_active_grants(lc_sid)
        assert len(mcp_grants) == len(lc_grants) == 1
        mg, lg = mcp_grants[0], lc_grants[0]
        assert mg.scope == lg.scope == "session"
        assert mg.granted_by == lg.granted_by == "auto"
        assert mg.allowed_ops == lg.allowed_ops

        mcp_state = runtime.state_manager.load_or_init(mcp_sid)
        lc_state = runtime.state_manager.load_or_init(lc_sid)
        assert "repo-read" in mcp_state.active_grants
        assert "repo-read" in lc_state.active_grants

    def test_unrecognised_scope_is_coerced_on_both_paths(self, runtime, monkeypatch) -> None:
        """Pre-fix: LangChain path raised ``pydantic.ValidationError`` on
        an invalid scope; MCP path coerced to ``"session"``.  After the
        fix both coerce identically."""
        mcp_sid = "parity-mcp-bad-scope"
        lc_sid = "parity-lc-bad-scope"

        self._enable_via_mcp(
            runtime, monkeypatch, mcp_sid,
            skill_id="repo-read", scope="not-a-real-scope", ttl=3600,
        )
        # Must not raise.
        self._enable_via_langchain(
            runtime, lc_sid,
            skill_id="repo-read", scope="not-a-real-scope", ttl=3600,
        )

        mg = runtime.grant_manager.get_active_grants(mcp_sid)[0]
        lg = runtime.grant_manager.get_active_grants(lc_sid)[0]
        assert mg.scope == lg.scope == "session"


class TestRefreshSkillsSingleScan:
    """D3: a single ``refresh_skills()`` call must trigger exactly one
    directory rebuild of the index.  Before the fix the code called
    both ``refresh()`` (which rebuilds internally) and
    ``build_index()`` a second time."""

    def test_single_build_index_call_per_refresh(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "refresh-once"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        calls = {"n": 0}
        real_build = runtime.indexer.build_index

        def counting_build():
            calls["n"] += 1
            return real_build()

        monkeypatch.setattr(runtime.indexer, "build_index", counting_build)

        try:
            result = asyncio.run(mcp_server.refresh_skills())
        finally:
            mcp_server._runtime = None

        assert result["refreshed"] is True
        assert calls["n"] == 1, f"expected exactly one build_index call, got {calls['n']}"


class TestDisableSkillAuditOrdering:
    """D7 event boundary: an explicit ``disable_skill`` emits
    ``grant.revoke`` (from GrantManager) *before* ``skill.disable``
    (from the entry point).  Disabling a skill whose grant was
    already cleaned up emits ``skill.disable`` only."""

    def test_explicit_disable_emits_revoke_then_disable(self, runtime, monkeypatch) -> None:
        import asyncio
        import json as _json

        import tool_governance.mcp_server as mcp_server

        sid = "disable-audit"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        try:
            asyncio.run(mcp_server.enable_skill(skill_id="repo-read"))
            asyncio.run(mcp_server.disable_skill(skill_id="repo-read"))
        finally:
            mcp_server._runtime = None

        all_events = runtime.store.query_audit(session_id=sid)
        relevant = [e for e in all_events if e["event_type"] in ("grant.revoke", "skill.disable")]
        assert [e["event_type"] for e in relevant] == ["grant.revoke", "skill.disable"]
        revoke_detail = _json.loads(relevant[0]["detail"])
        assert revoke_detail["reason"] == "explicit"
        assert relevant[0]["skill_id"] == relevant[1]["skill_id"] == "repo-read"

    def test_disable_without_grant_emits_disable_only(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "disable-no-grant"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        try:
            asyncio.run(mcp_server.enable_skill(skill_id="repo-read"))
            # Simulate the grant already having been cleaned up by
            # clearing active_grants before the disable call.
            state = runtime.state_manager.load_or_init(sid)
            state.active_grants.clear()
            runtime.state_manager.save(state)
            asyncio.run(mcp_server.disable_skill(skill_id="repo-read"))
        finally:
            mcp_server._runtime = None

        revokes = runtime.store.query_audit(session_id=sid, event_type="grant.revoke")
        disables = runtime.store.query_audit(session_id=sid, event_type="skill.disable")
        assert revokes == []
        assert len(disables) == 1


class TestMetaNoneEdgeCases:
    """D4 gap-fill: exercise the ``meta is None`` branch across MCP
    entry points beyond ``run_skill_action`` (already covered by
    ``TestRunSkillActionMetaMissing``).  These tests pin the existing
    error-return contracts so regressions surface immediately.
    """

    def test_change_stage_denies_when_meta_missing(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "meta-none-change-stage"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        # Enable code-edit (staged), then force the meta-missing state.
        state = runtime.state_manager.load_or_init(sid)
        meta = runtime.indexer.current_index()["code-edit"]
        grant = runtime.grant_manager.create_grant(sid, "code-edit", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "code-edit")
        state.active_grants["code-edit"] = grant
        # Remove from indexer's registry so current_index() won't return it
        if "code-edit" in runtime.indexer._indexed_skills:
            runtime.indexer._indexed_skills.pop("code-edit")
        runtime.state_manager.save(state)

        try:
            result = asyncio.run(mcp_server.change_stage("code-edit", "execution"))
        finally:
            mcp_server._runtime = None

        assert "error" in result
        assert "not found" in result["error"]

    def test_enable_skill_denies_when_skill_unknown(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "meta-none-enable"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        try:
            result = asyncio.run(mcp_server.enable_skill(skill_id="does-not-exist"))
        finally:
            mcp_server._runtime = None

        assert result["granted"] is False
        assert "not found" in result["reason"]

    def test_read_skill_returns_error_when_unknown(self, runtime, monkeypatch) -> None:
        import asyncio

        import tool_governance.mcp_server as mcp_server

        sid = "meta-none-read"
        monkeypatch.setenv("CLAUDE_SESSION_ID", sid)
        mcp_server._runtime = runtime
        handle_session_start({"session_id": sid})

        try:
            result = asyncio.run(mcp_server.read_skill(skill_id="does-not-exist"))
        finally:
            mcp_server._runtime = None

        assert "error" in result
        assert "not found" in result["error"]

    def test_recompute_active_tools_skips_loaded_skill_without_meta(self, runtime) -> None:
        """``ToolRewriter.recompute_active_tools`` silently skips a
        loaded skill whose metadata is missing, contributing zero
        tools (meta-tools are still present)."""
        from tool_governance.core.tool_rewriter import META_TOOLS

        sid = "meta-none-rewriter"
        handle_session_start({"session_id": sid})
        state = runtime.state_manager.load_or_init(sid)
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(sid, "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        # Force the meta-missing branch inside ToolRewriter.
        # Remove from indexer so RuntimeContext won't find it.
        if "repo-read" in runtime.indexer._indexed_skills:
            runtime.indexer._indexed_skills.pop("repo-read")

        active = runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)

        assert set(active) == set(META_TOOLS)  # no skill tools contributed
        assert "Read" not in active
