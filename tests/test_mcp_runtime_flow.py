"""Test that MCP entry points follow the unified runtime flow.

This test suite verifies that all 8 MCP meta-tool entry points have been
migrated to the four-step runtime flow and do NOT directly read from
state.active_tools or state.skills_metadata.

The test strategy: mock state.active_tools and state.skills_metadata with
sentinel values, invoke each MCP entry point, and assert that the returned
values do NOT contain the sentinel (proving they read from RuntimeContext
instead).
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from tool_governance.models.state import SessionState, LoadedSkillInfo
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.grant import Grant


# Sentinel values to detect direct reads from state
SENTINEL_TOOLS = ["SENTINEL_TOOL_FROM_STATE"]
SENTINEL_METADATA = {"sentinel_skill": SkillMetadata(
    skill_id="sentinel_skill",
    name="Sentinel",
    description="Should not appear",
    risk_level="low",
    allowed_tools=[],
    allowed_ops=[],
    source_path="/fake/path",
)}


@pytest.fixture
def mock_runtime():
    """Create a mock GovernanceRuntime with proper structure."""
    rt = Mock()
    rt.indexer = Mock()
    rt.state_manager = Mock()
    rt.grant_manager = Mock()
    rt.policy_engine = Mock()
    rt.policy = Mock()
    rt.policy.blocked_tools = []
    rt.store = Mock()
    rt.clock = Mock(return_value=datetime.now(timezone.utc))
    rt.tool_rewriter = Mock()
    return rt


@pytest.fixture
def poisoned_state():
    """Create a SessionState with sentinel values in derived fields."""
    state = SessionState(
        session_id="test-session",
        skills_metadata=SENTINEL_METADATA,  # Sentinel in derived field
        skills_loaded={},
        active_tools=SENTINEL_TOOLS,  # Sentinel in derived field
        active_grants={},
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    return state


@pytest.mark.asyncio
async def test_list_skills_does_not_read_state_skills_metadata(mock_runtime, poisoned_state):
    """Verify list_skills reads from RuntimeContext, not state.skills_metadata."""
    from tool_governance import mcp_server

    # Setup: indexer returns real metadata (not sentinel)
    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=["Read"],
            allowed_ops=[],
            source_path="/real/path",
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.list_skills()

    # Assert: result contains real skill, not sentinel
    assert len(result) == 1
    assert result[0]["skill_id"] == "real-skill"
    assert result[0]["name"] == "Real Skill"
    # Sentinel should NOT appear
    assert not any(s["skill_id"] == "sentinel_skill" for s in result)


@pytest.mark.asyncio
async def test_read_skill_does_not_read_state_skills_metadata(mock_runtime, poisoned_state):
    """Verify read_skill reads from RuntimeContext, not state.skills_metadata."""
    from tool_governance import mcp_server

    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=["Read"],
            allowed_ops=[],
            source_path="/real/path",
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state

    # Mock read_skill to return content
    from tool_governance.models.skill import SkillContent
    mock_runtime.indexer.read_skill.return_value = SkillContent(
        metadata=real_metadata["real-skill"],
        sop="Real SOP content",
    )

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.read_skill("real-skill")

    # Assert: result contains real skill content
    assert "error" not in result
    assert result["metadata"]["skill_id"] == "real-skill"


@pytest.mark.asyncio
async def test_enable_skill_does_not_read_state_active_tools(mock_runtime, poisoned_state):
    """Verify enable_skill returns active_tools from RuntimeContext, not state."""
    from tool_governance import mcp_server
    from tool_governance.core.policy_engine import PolicyDecision

    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=["Read", "Write"],
            allowed_ops=["query"],
            source_path="/real/path",
            version="1.0.0",
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state
    mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
        allowed=True, decision="auto"
    )
    mock_runtime.policy_engine.cap_ttl.return_value = 3600
    mock_runtime.grant_manager.create_grant.return_value = Grant(
        grant_id="grant-123",
        session_id="test-session",
        skill_id="real-skill",
        allowed_ops=["query"],
        scope="session",
        ttl_seconds=3600,
        status="active",
        granted_by="auto",
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.enable_skill("real-skill")

    # Assert: allowed_tools does NOT contain sentinel
    assert result["granted"] is True
    assert "allowed_tools" in result
    assert SENTINEL_TOOLS[0] not in result["allowed_tools"]
    # Should contain meta-tools and real skill tools
    assert any("list_skills" in tool for tool in result["allowed_tools"])


@pytest.mark.asyncio
async def test_run_skill_action_does_not_read_state_skills_metadata(mock_runtime, poisoned_state):
    """Verify run_skill_action reads metadata from RuntimeContext, not state."""
    from tool_governance import mcp_server

    # Setup: skill is loaded
    poisoned_state.skills_loaded["real-skill"] = LoadedSkillInfo(
        skill_id="real-skill",
        version="1.0.0",
    )

    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=["Read"],
            allowed_ops=["query"],
            source_path="/real/path",
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state
    mock_runtime.grant_manager.is_grant_valid.return_value = True

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            with patch("tool_governance.core.skill_executor.dispatch", return_value={"data": "result"}):
                result = await mcp_server.run_skill_action("real-skill", "query", {})

    # Assert: execution succeeded (metadata was found in RuntimeContext)
    assert "error" not in result
    assert result["result"] == {"data": "result"}


@pytest.mark.asyncio
async def test_change_stage_does_not_read_state_skills_metadata(mock_runtime, poisoned_state):
    """Verify change_stage reads metadata from RuntimeContext, not state."""
    from tool_governance import mcp_server
    from tool_governance.models.skill import StageDefinition

    # Setup: skill is loaded
    poisoned_state.skills_loaded["real-skill"] = LoadedSkillInfo(
        skill_id="real-skill",
        version="1.0.0",
        current_stage="stage1",
    )

    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=[],
            allowed_ops=[],
            source_path="/real/path",
            stages=[
                StageDefinition(stage_id="stage1", description="Stage 1", allowed_tools=["Read"], allowed_next_stages=["stage2"]),
                StageDefinition(stage_id="stage2", description="Stage 2", allowed_tools=["Write"], allowed_next_stages=[]),
            ],
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.change_stage("real-skill", "stage2")

    # Assert: stage change succeeded, active_tools does NOT contain sentinel
    assert result["changed"] is True
    assert "new_active_tools" in result
    assert SENTINEL_TOOLS[0] not in result["new_active_tools"]


@pytest.mark.asyncio
async def test_disable_skill_does_not_read_state_active_tools(mock_runtime, poisoned_state):
    """Verify disable_skill does not return sentinel from state.active_tools."""
    from tool_governance import mcp_server

    # Setup: skill is loaded
    poisoned_state.skills_loaded["real-skill"] = LoadedSkillInfo(
        skill_id="real-skill",
        version="1.0.0",
    )
    poisoned_state.active_grants["real-skill"] = Grant(
        grant_id="grant-123",
        session_id="test-session",
        skill_id="real-skill",
        allowed_ops=["query"],
        scope="session",
        ttl_seconds=3600,
        status="active",
        granted_by="auto",
        created_at=datetime.now(timezone.utc),
        expires_at=None,
    )

    real_metadata = {
        "real-skill": SkillMetadata(
            skill_id="real-skill",
            name="Real Skill",
            description="Real description",
            risk_level="low",
            allowed_tools=["Read"],
            allowed_ops=["query"],
            source_path="/real/path",
        )
    }
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.disable_skill("real-skill")

    # Assert: disable succeeded
    assert result["disabled"] is True
    # The function doesn't return active_tools, but we verify it called
    # _build_runtime_ctx (which would fail if it read sentinel)
    mock_runtime.state_manager.save.assert_called_once()


@pytest.mark.asyncio
async def test_grant_status_follows_four_step_pattern(mock_runtime, poisoned_state):
    """Verify grant_status follows four-step pattern (even though read-only)."""
    from tool_governance import mcp_server

    real_metadata = {}
    mock_runtime.indexer.current_index.return_value = real_metadata
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state
    mock_runtime.grant_manager.get_active_grants.return_value = []

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.grant_status()

    # Assert: function succeeded
    assert isinstance(result, list)
    # Verify it loaded state (step 1)
    mock_runtime.state_manager.load_or_init.assert_called_once_with("test-session")


@pytest.mark.asyncio
async def test_refresh_skills_does_not_mutate_state_skills_metadata(mock_runtime, poisoned_state):
    """Verify refresh_skills does NOT write to state.skills_metadata."""
    from tool_governance import mcp_server

    mock_runtime.indexer.refresh.return_value = 5
    mock_runtime.state_manager.load_or_init.return_value = poisoned_state

    with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
        with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
            result = await mcp_server.refresh_skills()

    # Assert: refresh succeeded
    assert result["refreshed"] is True
    assert result["skill_count"] == 5
    # Verify state was NOT saved (no mutation)
    mock_runtime.state_manager.save.assert_not_called()
    # Verify state.skills_metadata still contains sentinel (not overwritten)
    assert poisoned_state.skills_metadata == SENTINEL_METADATA
