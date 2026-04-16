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
        meta = state.skills_metadata.get("repo-read")
        assert meta is not None

        # Policy evaluation: low risk → auto → allowed
        decision = runtime.policy_engine.evaluate("repo-read", meta, state)
        assert decision.allowed is True
        grant = runtime.grant_manager.create_grant("test-flow", "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state)
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
        meta = state.skills_metadata["repo-read"]
        grant = runtime.grant_manager.create_grant("test-allow", "repo-read", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state)
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
        meta = state.skills_metadata["repo-read"]
        # ttl=0 means expires_at == created_at — already expired.
        grant = runtime.grant_manager.create_grant("test-ttl", "repo-read", meta.allowed_ops, ttl=0)
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state)
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
        meta = state.skills_metadata["code-edit"]

        # Medium risk requires a reason — provide one.
        decision = runtime.policy_engine.evaluate("code-edit", meta, state, reason="fixing bug")
        assert decision.allowed is True
        grant = runtime.grant_manager.create_grant("test-stage", "code-edit", meta.allowed_ops)
        runtime.state_manager.add_to_skills_loaded(state, "code-edit")
        state.active_grants["code-edit"] = grant
        runtime.tool_rewriter.recompute_active_tools(state)
        runtime.state_manager.save(state)

        # Default stage = first stage = analysis → Read-only tools.
        assert "Read" in state.active_tools
        assert "Edit" not in state.active_tools

        # Switch to execution stage → write tools appear.
        state.skills_loaded["code-edit"].current_stage = "execution"
        runtime.tool_rewriter.recompute_active_tools(state)
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
