"""Tests for enforce-stage-transition-governance change.

Stage B: enable_skill stage initialization
Stage C: change_stage transition enforcement
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from tool_governance.models.skill import SkillMetadata, StageDefinition
from tool_governance.models.state import LoadedSkillInfo, SessionState
from tool_governance.models.grant import Grant
from tool_governance.core.policy_engine import PolicyDecision


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
def clean_state():
    """Create a clean SessionState."""
    return SessionState(
        session_id="test-session",
        skills_metadata={},
        skills_loaded={},
        active_grants={},
        active_tools=[],
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def staged_skill_metadata():
    """Create a staged skill with two stages."""
    return SkillMetadata(
        skill_id="staged-skill",
        name="Staged Skill",
        description="A skill with stages",
        risk_level="low",
        allowed_tools=[],
        allowed_ops=["query"],
        source_path="/test/path",
        version="1.0.0",
        stages=[
            StageDefinition(
                stage_id="stage1",
                name="Stage 1",
                description="First stage",
                allowed_tools=["Read"],
                allowed_next_stages=["stage2"],
            ),
            StageDefinition(
                stage_id="stage2",
                name="Stage 2",
                description="Second stage",
                allowed_tools=["Write"],
                allowed_next_stages=[],
            ),
        ],
    )


@pytest.fixture
def no_stage_skill_metadata():
    """Create a skill without stages."""
    return SkillMetadata(
        skill_id="no-stage-skill",
        name="No Stage Skill",
        description="A skill without stages",
        risk_level="low",
        allowed_tools=["Read", "Write"],
        allowed_ops=["query"],
        source_path="/test/path",
        version="1.0.0",
    )


class TestEnableSkillStageInit:
    """Stage B: enable_skill stage initialization tests."""

    @pytest.mark.asyncio
    async def test_enable_skill_with_valid_initial_stage(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.11: Skill with valid initial_stage enters that stage."""
        from tool_governance import mcp_server

        # Set initial_stage
        staged_skill_metadata.initial_stage = "stage2"

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="staged-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        # Mock add_to_skills_loaded to actually add to state
        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.current_stage == "stage2"
        assert loaded_info.stage_entered_at is not None
        assert loaded_info.stage_history == []
        assert loaded_info.exited_stages == []

    @pytest.mark.asyncio
    async def test_enable_skill_without_initial_stage(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.12: Skill without initial_stage enters first stage."""
        from tool_governance import mcp_server

        # No initial_stage set
        staged_skill_metadata.initial_stage = None

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="staged-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.current_stage == "stage1"  # First stage
        assert loaded_info.stage_entered_at is not None

    @pytest.mark.asyncio
    async def test_enable_skill_invalid_initial_stage_fails_safely(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.13: Invalid initial_stage returns error without creating grant."""
        from tool_governance import mcp_server

        # Set invalid initial_stage
        staged_skill_metadata.initial_stage = "invalid-stage"

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is False
        assert result["error"] == "invalid_initial_stage"
        # Grant should NOT be created
        mock_runtime.grant_manager.create_grant.assert_not_called()

    @pytest.mark.asyncio
    async def test_enable_skill_invalid_initial_stage_no_skills_loaded(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.14: Invalid initial_stage does NOT add skill to skills_loaded."""
        from tool_governance import mcp_server

        staged_skill_metadata.initial_stage = "invalid-stage"

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is False
        assert "staged-skill" not in clean_state.skills_loaded
        mock_runtime.state_manager.add_to_skills_loaded.assert_not_called()

    @pytest.mark.asyncio
    async def test_enable_skill_invalid_initial_stage_audit(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.16: Invalid initial_stage records audit with error_bucket."""
        from tool_governance import mcp_server

        staged_skill_metadata.initial_stage = "invalid-stage"

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is False
        # Check audit was recorded
        mock_runtime.store.append_audit.assert_called_once()
        call_args = mock_runtime.store.append_audit.call_args
        assert call_args[0][1] == "skill.enable"
        assert call_args[1]["decision"] == "deny"
        assert call_args[1]["detail"]["error_bucket"] == "invalid_initial_stage"

    @pytest.mark.asyncio
    async def test_enable_skill_no_stage_skill_compatibility(
        self, mock_runtime, clean_state, no_stage_skill_metadata
    ):
        """B.17: No-stage skill sets current_stage=None, no lifecycle fields."""
        from tool_governance import mcp_server

        mock_runtime.indexer.current_index.return_value = {
            "no-stage-skill": no_stage_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="no-stage-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("no-stage-skill")

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["no-stage-skill"]
        assert loaded_info.current_stage is None
        # Lifecycle fields should NOT be initialized
        assert loaded_info.stage_entered_at is None
        assert loaded_info.stage_history == []
        assert loaded_info.exited_stages == []

    @pytest.mark.asyncio
    async def test_enable_skill_initializes_stage_entered_at(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.18: stage_entered_at is set to current UTC timestamp."""
        from tool_governance import mcp_server

        staged_skill_metadata.initial_stage = None

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="staged-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        before = datetime.now(timezone.utc)
        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")
        after = datetime.now(timezone.utc)

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.stage_entered_at is not None
        assert before <= loaded_info.stage_entered_at <= after

    @pytest.mark.asyncio
    async def test_enable_skill_initializes_empty_stage_history(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.19: stage_history is initialized to empty list."""
        from tool_governance import mcp_server

        staged_skill_metadata.initial_stage = None

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="staged-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.stage_history == []
        assert isinstance(loaded_info.stage_history, list)

    @pytest.mark.asyncio
    async def test_enable_skill_initializes_empty_exited_stages(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """B.20: exited_stages is initialized to empty list."""
        from tool_governance import mcp_server

        staged_skill_metadata.initial_stage = None

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state
        mock_runtime.policy_engine.evaluate.return_value = PolicyDecision(
            allowed=True, decision="auto"
        )
        mock_runtime.policy_engine.cap_ttl.return_value = 3600
        mock_runtime.grant_manager.create_grant.return_value = Grant(
            grant_id="grant-123",
            session_id="test-session",
            skill_id="staged-skill",
            allowed_ops=["query"],
            scope="session",
            ttl_seconds=3600,
            status="active",
            granted_by="auto",
            created_at=datetime.now(timezone.utc),
            expires_at=None,
        )

        def add_to_loaded(state, skill_id, version):
            state.skills_loaded[skill_id] = LoadedSkillInfo(
                skill_id=skill_id, version=version
            )

        mock_runtime.state_manager.add_to_skills_loaded.side_effect = add_to_loaded

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                result = await mcp_server.enable_skill("staged-skill")

        assert result["granted"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.exited_stages == []
        assert isinstance(loaded_info.exited_stages, list)


class TestChangeStageTransitionEnforcement:
    """Stage C: change_stage transition enforcement tests."""

    @pytest.mark.asyncio
    async def test_change_stage_legal_transition_succeeds(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.19: Valid transition updates state and returns success."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView

        # Setup: skill enabled in stage1
        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage1",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=[],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        # Mock RuntimeContext
        from tool_governance.core.runtime_context import PolicySnapshot
        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage2")

        assert result["changed"] is True
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.current_stage == "stage2"
        assert loaded_info.stage_entered_at is not None
        assert "stage1" in loaded_info.exited_stages
        assert len(loaded_info.stage_history) == 1
        assert loaded_info.stage_history[0].from_stage == "stage1"
        assert loaded_info.stage_history[0].to_stage == "stage2"

    @pytest.mark.asyncio
    async def test_change_stage_target_not_found(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.20: Returns stage_not_found for invalid target stage."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage1",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=[],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Read",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "invalid-stage")

        assert "error" in result
        assert result.get("error_bucket") == "stage_not_found"
        # Verify audit was recorded
        mock_runtime.store.append_audit.assert_called_once()
        call_args = mock_runtime.store.append_audit.call_args
        assert call_args[0][1] == "stage.transition.deny"
        assert call_args[1]["detail"]["error_bucket"] == "stage_not_found"

    @pytest.mark.asyncio
    async def test_change_stage_terminal_stage_denies(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.21: Terminal stage (allowed_next_stages=[]) blocks transitions."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        # Setup: skill in stage2 (terminal)
        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage2",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=["stage1"],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage1")

        assert "error" in result
        assert result.get("error_bucket") == "stage_transition_not_allowed"
        # Verify audit
        mock_runtime.store.append_audit.assert_called_once()
        call_args = mock_runtime.store.append_audit.call_args
        assert call_args[0][1] == "stage.transition.deny"
        assert call_args[1]["detail"]["error_bucket"] == "stage_transition_not_allowed"

    @pytest.mark.asyncio
    async def test_change_stage_target_not_in_allowlist(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.22: Returns stage_transition_not_allowed if target not in allowed_next_stages."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        # Create skill with stage1 -> stage3 only (not stage2)
        skill_meta = SkillMetadata(
            skill_id="staged-skill",
            name="Staged Skill",
            description="A skill with stages",
            risk_level="low",
            allowed_tools=[],
            allowed_ops=["query"],
            source_path="/test/path",
            version="1.0.0",
            stages=[
                StageDefinition(
                    stage_id="stage1",
                    name="Stage 1",
                    description="First stage",
                    allowed_tools=["Read"],
                    allowed_next_stages=["stage3"],  # Only stage3 allowed
                ),
                StageDefinition(
                    stage_id="stage2",
                    name="Stage 2",
                    description="Second stage",
                    allowed_tools=["Write"],
                    allowed_next_stages=[],
                ),
                StageDefinition(
                    stage_id="stage3",
                    name="Stage 3",
                    description="Third stage",
                    allowed_tools=["Bash"],
                    allowed_next_stages=[],
                ),
            ],
        )

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage1",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=[],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": skill_meta
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": skill_meta},
            active_tools=("Read",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=skill_meta,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage2")

        assert "error" in result
        assert result.get("error_bucket") == "stage_transition_not_allowed"

    @pytest.mark.asyncio
    async def test_change_stage_no_stage_skill_denies(
        self, mock_runtime, clean_state, no_stage_skill_metadata
    ):
        """C.23: Returns skill_has_no_stages for no-stage skills."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["no-stage-skill"] = LoadedSkillInfo(
            skill_id="no-stage-skill",
            version="1.0.0",
            current_stage=None,
        )

        mock_runtime.indexer.current_index.return_value = {
            "no-stage-skill": no_stage_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"no-stage-skill": no_stage_skill_metadata},
            active_tools=("Read", "Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="no-stage-skill",
                metadata=no_stage_skill_metadata,
                loaded_info=clean_state.skills_loaded["no-stage-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("no-stage-skill", "any-stage")

        assert "error" in result
        assert result.get("error_bucket") == "skill_has_no_stages"

    @pytest.mark.asyncio
    async def test_change_stage_current_stage_missing(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.24: Returns stage_not_initialized if current_stage is None."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        # Skill loaded but current_stage not initialized
        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage=None,  # Not initialized
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=(),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage2")

        assert "error" in result
        assert result.get("error_bucket") == "stage_not_initialized"

    @pytest.mark.asyncio
    async def test_change_stage_denied_no_state_mutation(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.25: Denied transition leaves all state unchanged."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        original_stage = "stage2"
        original_entered_at = datetime.now(timezone.utc)
        original_history = []
        original_exited = ["stage1"]

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage=original_stage,
            stage_entered_at=original_entered_at,
            stage_history=original_history.copy(),
            exited_stages=original_exited.copy(),
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    # Try to transition from terminal stage
                    result = await mcp_server.change_stage("staged-skill", "stage1")

        assert "error" in result
        loaded_info = clean_state.skills_loaded["staged-skill"]
        # Verify nothing changed
        assert loaded_info.current_stage == original_stage
        assert loaded_info.stage_entered_at == original_entered_at
        assert loaded_info.stage_history == original_history
        assert loaded_info.exited_stages == original_exited

    @pytest.mark.asyncio
    async def test_change_stage_stage_history_only_successful(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.26: Denied transition NOT in stage_history."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage2",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=["stage1"],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage1")

        assert "error" in result
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert len(loaded_info.stage_history) == 0  # No record added

    @pytest.mark.asyncio
    async def test_change_stage_exited_stages_only_on_success(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.27: exited_stages only updated on allow."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage2",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=["stage1"],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage1")

        assert "error" in result
        loaded_info = clean_state.skills_loaded["staged-skill"]
        assert loaded_info.exited_stages == ["stage1"]  # Unchanged

    @pytest.mark.asyncio
    async def test_change_stage_allow_audit_exists(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.28: stage.transition.allow audit record created."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage1",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=[],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage2")

        assert result["changed"] is True
        # Verify audit
        mock_runtime.store.append_audit.assert_called_once()
        call_args = mock_runtime.store.append_audit.call_args
        assert call_args[0][1] == "stage.transition.allow"
        assert call_args[1]["detail"]["from_stage"] == "stage1"
        assert call_args[1]["detail"]["to_stage"] == "stage2"

    @pytest.mark.asyncio
    async def test_change_stage_deny_audit_exists(
        self, mock_runtime, clean_state, staged_skill_metadata
    ):
        """C.29: stage.transition.deny audit record created with error_bucket."""
        from tool_governance import mcp_server
        from tool_governance.core.runtime_context import RuntimeContext, EnabledSkillView, PolicySnapshot

        clean_state.skills_loaded["staged-skill"] = LoadedSkillInfo(
            skill_id="staged-skill",
            version="1.0.0",
            current_stage="stage2",
            stage_entered_at=datetime.now(timezone.utc),
            stage_history=[],
            exited_stages=["stage1"],
        )

        mock_runtime.indexer.current_index.return_value = {
            "staged-skill": staged_skill_metadata
        }
        mock_runtime.state_manager.load_or_init.return_value = clean_state

        mock_ctx = RuntimeContext(
            all_skills_metadata={"staged-skill": staged_skill_metadata},
            active_tools=("Write",),
            enabled_skills=(EnabledSkillView(
                skill_id="staged-skill",
                metadata=staged_skill_metadata,
                loaded_info=clean_state.skills_loaded["staged-skill"]
            ),),
            policy=PolicySnapshot(blocked_tools=frozenset()),
            clock=datetime.now(timezone.utc),
        )

        with patch("tool_governance.mcp_server._get_runtime", return_value=mock_runtime):
            with patch("tool_governance.mcp_server._session_id", return_value="test-session"):
                with patch("tool_governance.mcp_server._build_runtime_ctx", return_value=mock_ctx):
                    result = await mcp_server.change_stage("staged-skill", "stage1")

        assert "error" in result
        # Verify audit
        mock_runtime.store.append_audit.assert_called_once()
        call_args = mock_runtime.store.append_audit.call_args
        assert call_args[0][1] == "stage.transition.deny"
        assert call_args[1]["detail"]["error_bucket"] == "stage_transition_not_allowed"
        assert call_args[1]["detail"]["from_stage"] == "stage2"
        assert call_args[1]["detail"]["to_stage"] == "stage1"
