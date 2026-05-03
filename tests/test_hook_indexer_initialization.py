"""Regression test for hook indexer initialization bug.

This test verifies that handle_user_prompt_submit and handle_pre_tool_use
correctly initialize the skill indexer when state.skills_metadata is empty
(which happens when skills_metadata is excluded from persistence).

Bug context:
- handle_session_start explicitly calls rt.indexer.build_index() if skills_metadata is empty
- handle_user_prompt_submit and handle_pre_tool_use were missing this check
- Result: empty metadata → empty active_tools → all tool calls denied

The fix adds the same indexer initialization check to both handlers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tool_governance.bootstrap import create_governance_runtime
from tool_governance.hook_handler import (
    handle_pre_tool_use,
    handle_session_start,
    handle_user_prompt_submit,
)
import tool_governance.hook_handler as hh


@pytest.fixture()
def runtime(tmp_path: Path):
    """Create a real GovernanceRuntime backed by temp-dir artifacts."""
    skills_dir = tmp_path / "skills"
    # repo-read: low-risk, stage-less, 3 tools
    (skills_dir / "repo-read").mkdir(parents=True)
    (skills_dir / "repo-read" / "SKILL.md").write_text(
        '---\nname: Repo Read\ndescription: "Read code"\nrisk_level: low\n'
        'allowed_tools:\n  - Read\n  - Glob\n  - Grep\n'
        'allowed_ops:\n  - search\n  - read_file\n---\n\n# Repo Read\n',
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


class TestHookIndexerInitialization:
    """Test that hooks initialize the skill indexer when metadata is empty."""

    def test_user_prompt_submit_initializes_indexer_when_metadata_empty(
        self, runtime
    ) -> None:
        """UserPromptSubmit must initialize indexer when skills_metadata is empty.

        Regression test for the bug where UserPromptSubmit did not call
        rt.indexer.build_index() when skills_metadata was empty, causing
        the skill catalog to be missing from additionalContext.
        """
        # Step 1: SessionStart to create the session
        session_start_result = handle_session_start({"session_id": "test-user-prompt"})
        assert "additionalContext" in session_start_result
        # Should contain skill catalog
        assert "Repo Read" in session_start_result["additionalContext"]

        # Step 2: Clear skills_metadata to simulate subprocess isolation
        # (In real scenarios, this happens because skills_metadata is excluded from persistence)
        state = runtime.state_manager.load_or_init("test-user-prompt")
        state.skills_metadata = {}
        runtime.state_manager.save(state)

        # Step 3: UserPromptSubmit in a "new subprocess" (empty indexer)
        # Before the fix, this would return "No skills registered"
        # After the fix, it should initialize the indexer and return the skill catalog
        user_prompt_result = handle_user_prompt_submit(
            {"session_id": "test-user-prompt"}
        )

        # Verify that skills are indexed and available
        assert "additionalContext" in user_prompt_result
        # The key assertion: should contain skill catalog, not "No skills registered"
        assert "Repo Read" in user_prompt_result["additionalContext"]

    def test_pre_tool_use_initializes_indexer_when_metadata_empty(
        self, runtime
    ) -> None:
        """PreToolUse must initialize indexer when skills_metadata is empty.

        Regression test for the bug where PreToolUse did not call
        rt.indexer.build_index() when skills_metadata was empty, causing
        all tool calls to be denied with whitelist_violation.
        """
        # Step 1: SessionStart to create the session
        handle_session_start({"session_id": "test-pre-tool"})

        # Step 2: Enable a skill by directly manipulating state
        state = runtime.state_manager.load_or_init("test-pre-tool")
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(
            "test-pre-tool", "repo-read", meta.allowed_ops
        )
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        # Step 3: Clear skills_metadata to simulate subprocess isolation
        state.skills_metadata = {}
        runtime.state_manager.save(state)

        # Step 4: PreToolUse in a "new subprocess" (empty indexer)
        # Before the fix, this would deny the tool with whitelist_violation
        # After the fix, it should initialize the indexer and allow the tool
        pre_tool_result = handle_pre_tool_use(
            {"session_id": "test-pre-tool", "tool_name": "Read"}
        )

        # The key assertion: tool should be allowed, not denied
        assert pre_tool_result["hookSpecificOutput"]["permissionDecision"] == "allow"

    def test_pre_tool_use_denies_unauthorized_tool_after_indexer_init(
        self, runtime
    ) -> None:
        """PreToolUse must correctly deny unauthorized tools after indexer init.

        This verifies that the indexer initialization doesn't break the authorization logic.
        """
        # Step 1: SessionStart to create the session
        handle_session_start({"session_id": "test-deny"})

        # Step 2: Enable a skill
        state = runtime.state_manager.load_or_init("test-deny")
        meta = runtime.indexer.current_index()["repo-read"]
        grant = runtime.grant_manager.create_grant(
            "test-deny", "repo-read", meta.allowed_ops
        )
        runtime.state_manager.add_to_skills_loaded(state, "repo-read")
        state.active_grants["repo-read"] = grant
        runtime.tool_rewriter.recompute_active_tools(state, runtime.indexer)
        runtime.state_manager.save(state)

        # Step 3: Clear skills_metadata to simulate subprocess isolation
        state.skills_metadata = {}
        runtime.state_manager.save(state)

        # Step 4: Try to call an unauthorized tool
        pre_tool_result = handle_pre_tool_use(
            {"session_id": "test-deny", "tool_name": "unauthorized_tool"}
        )

        # Verify that the tool is denied
        assert pre_tool_result["hookSpecificOutput"]["permissionDecision"] == "deny"
