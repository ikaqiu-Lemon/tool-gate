"""Tests for Pydantic data models — serialization roundtrip, validation.

Guards against regressions in default values, field types, and
model_dump / model_validate fidelity.  If a field default changes
or a roundtrip loses data, these tests catch it.
"""

from datetime import datetime

from tool_governance.models.grant import Grant
from tool_governance.models.policy import GovernancePolicy, SkillPolicy
from tool_governance.models.skill import SkillContent, SkillMetadata, StageDefinition
from tool_governance.models.state import LoadedSkillInfo, SessionState, StageTransitionRecord


class TestSkillModels:
    def test_skill_metadata_defaults(self) -> None:
        """Verify that a minimal SkillMetadata gets safe defaults for
        every optional field — prevents silent breakage when new code
        assumes a default that was changed."""
        meta = SkillMetadata(skill_id="test", name="Test Skill")
        assert meta.risk_level == "low"
        assert meta.allowed_tools == []
        assert meta.stages == []
        assert meta.initial_stage is None
        assert meta.default_ttl == 3600
        assert meta.version == "1.0.0"

    def test_skill_metadata_roundtrip(self) -> None:
        """Full-field roundtrip: dump → validate must produce an
        identical object.  Catches serialisation bugs in nested types
        (Literal, list, str)."""
        meta = SkillMetadata(
            skill_id="db-ops",
            name="Database Operations",
            description="Manage database queries",
            risk_level="high",
            allowed_tools=["sql_query"],
            allowed_ops=["query", "migrate"],
            default_ttl=1800,
            source_path="/skills/db-ops/SKILL.md",
            version="2.0.0",
        )
        data = meta.model_dump()
        restored = SkillMetadata.model_validate(data)
        assert restored == meta

    def test_stage_definition(self) -> None:
        stage = StageDefinition(
            stage_id="analysis",
            description="Read-only analysis",
            allowed_tools=["Read", "Grep"],
        )
        assert stage.stage_id == "analysis"
        assert len(stage.allowed_tools) == 2

    def test_skill_metadata_with_stages(self) -> None:
        """Ensure nested StageDefinition objects survive construction
        and preserve ordering — stage[0] is used as the default stage
        by ToolRewriter.get_stage_tools."""
        meta = SkillMetadata(
            skill_id="code-edit",
            name="Code Edit",
            stages=[
                StageDefinition(stage_id="analysis", allowed_tools=["Read"]),
                StageDefinition(stage_id="execution", allowed_tools=["Edit", "Write"]),
            ],
        )
        assert len(meta.stages) == 2
        assert meta.stages[0].stage_id == "analysis"
        assert meta.stages[1].allowed_tools == ["Edit", "Write"]

    def test_skill_content(self) -> None:
        meta = SkillMetadata(skill_id="test", name="Test")
        content = SkillContent(metadata=meta, sop="# Test\n\nWorkflow here.")
        assert content.sop.startswith("# Test")
        assert content.examples == []

    def test_skill_metadata_with_initial_stage(self) -> None:
        """Verify SkillMetadata can be instantiated with initial_stage."""
        meta = SkillMetadata(
            skill_id="staged-skill",
            name="Staged Skill",
            initial_stage="diagnosis",
            stages=[
                StageDefinition(stage_id="diagnosis", allowed_tools=["Read"]),
                StageDefinition(stage_id="execution", allowed_tools=["Write"]),
            ],
        )
        assert meta.initial_stage == "diagnosis"
        assert len(meta.stages) == 2

    def test_stage_definition_with_allowed_next_stages(self) -> None:
        """Verify StageDefinition can be instantiated with allowed_next_stages."""
        stage = StageDefinition(
            stage_id="analysis",
            description="Analysis phase",
            allowed_tools=["Read"],
            allowed_next_stages=["execution", "abort"],
        )
        assert stage.allowed_next_stages == ["execution", "abort"]

    def test_stage_definition_allowed_next_stages_defaults_to_empty_list(self) -> None:
        """Verify allowed_next_stages defaults to empty list (terminal stage)."""
        stage = StageDefinition(stage_id="complete", allowed_tools=["Read"])
        assert stage.allowed_next_stages == []

    def test_stage_definition_terminal_stage_preserved(self) -> None:
        """Verify allowed_next_stages: [] is preserved as empty list, not None."""
        stage = StageDefinition(
            stage_id="terminal",
            allowed_tools=["Read"],
            allowed_next_stages=[],
        )
        assert stage.allowed_next_stages == []
        assert stage.allowed_next_stages is not None


class TestGrantModel:
    def test_grant_defaults(self) -> None:
        """Verify the default grant is session-scoped, active, auto-granted,
        with a 1-hour TTL — the baseline that enable_skill relies on."""
        grant = Grant(grant_id="g1", session_id="s1", skill_id="repo-read")
        assert grant.scope == "session"
        assert grant.status == "active"
        assert grant.granted_by == "auto"
        assert grant.ttl_seconds == 3600

    def test_grant_roundtrip(self) -> None:
        """Roundtrip with every field set, including datetime fields.
        Guards against datetime serialisation losing precision or
        Literal fields being rejected on restore."""
        now = datetime(2026, 4, 15, 12, 0, 0)
        grant = Grant(
            grant_id="g1",
            session_id="s1",
            skill_id="repo-read",
            allowed_ops=["search"],
            scope="turn",
            ttl_seconds=60,
            status="active",
            granted_by="user",
            reason="Need to search code",
            created_at=now,
            expires_at=now,
        )
        data = grant.model_dump()
        restored = Grant.model_validate(data)
        assert restored.grant_id == "g1"
        assert restored.scope == "turn"


class TestStateModels:
    def test_loaded_skill_info_defaults(self) -> None:
        info = LoadedSkillInfo(skill_id="repo-read")
        assert info.version == "1.0.0"
        assert info.current_stage is None
        assert info.last_used_at is None

    def test_loaded_skill_info_stage_lifecycle_defaults(self) -> None:
        """Verify new stage lifecycle fields have safe defaults."""
        info = LoadedSkillInfo(skill_id="test-skill")
        assert info.stage_entered_at is None
        assert info.stage_history == []
        assert info.exited_stages == []

    def test_stage_transition_record_instantiation(self) -> None:
        """Verify StageTransitionRecord can be instantiated."""
        now = datetime(2026, 5, 3, 10, 30, 0)
        record = StageTransitionRecord(
            from_stage="analysis",
            to_stage="execution",
            transitioned_at=now,
        )
        assert record.from_stage == "analysis"
        assert record.to_stage == "execution"
        assert record.transitioned_at == now

    def test_stage_history_default_not_shared(self) -> None:
        """Verify stage_history default list is not shared between instances."""
        info1 = LoadedSkillInfo(skill_id="skill1")
        info2 = LoadedSkillInfo(skill_id="skill2")
        now = datetime(2026, 5, 3, 10, 30, 0)
        info1.stage_history.append(
            StageTransitionRecord(from_stage="a", to_stage="b", transitioned_at=now)
        )
        assert len(info1.stage_history) == 1
        assert len(info2.stage_history) == 0

    def test_exited_stages_default_not_shared(self) -> None:
        """Verify exited_stages default list is not shared between instances."""
        info1 = LoadedSkillInfo(skill_id="skill1")
        info2 = LoadedSkillInfo(skill_id="skill2")
        info1.exited_stages.append("analysis")
        assert len(info1.exited_stages) == 1
        assert len(info2.exited_stages) == 0

    def test_loaded_skill_info_stage_fields_serialization(self) -> None:
        """Verify new stage fields serialize to JSON."""
        now = datetime(2026, 5, 3, 10, 30, 0)
        info = LoadedSkillInfo(
            skill_id="test-skill",
            stage_entered_at=now,
            stage_history=[
                StageTransitionRecord(from_stage="a", to_stage="b", transitioned_at=now)
            ],
            exited_stages=["analysis"],
        )
        data = info.model_dump()
        assert data["stage_entered_at"] == now
        assert len(data["stage_history"]) == 1
        assert data["stage_history"][0]["from_stage"] == "a"
        assert data["exited_stages"] == ["analysis"]

    def test_loaded_skill_info_stage_fields_deserialization(self) -> None:
        """Verify new stage fields restore from JSON."""
        now = datetime(2026, 5, 3, 10, 30, 0)
        data = {
            "skill_id": "test-skill",
            "version": "1.0.0",
            "current_stage": "execution",
            "stage_entered_at": now.isoformat(),
            "stage_history": [
                {
                    "from_stage": "analysis",
                    "to_stage": "execution",
                    "transitioned_at": now.isoformat(),
                }
            ],
            "exited_stages": ["analysis"],
        }
        info = LoadedSkillInfo.model_validate(data)
        assert info.stage_entered_at == now
        assert len(info.stage_history) == 1
        assert info.stage_history[0].from_stage == "analysis"
        assert info.exited_stages == ["analysis"]

    def test_loaded_skill_info_backward_compatibility(self) -> None:
        """Verify old state JSON (missing new fields) still loads."""
        data = {
            "skill_id": "old-skill",
            "version": "1.0.0",
            "current_stage": "analysis",
            "last_used_at": datetime(2026, 5, 3, 10, 0, 0).isoformat(),
        }
        info = LoadedSkillInfo.model_validate(data)
        assert info.skill_id == "old-skill"
        assert info.current_stage == "analysis"
        # New fields should have defaults
        assert info.stage_entered_at is None
        assert info.stage_history == []
        assert info.exited_stages == []

    def test_loaded_skill_info_current_stage_not_broken(self) -> None:
        """Verify existing current_stage behavior is not broken."""
        info = LoadedSkillInfo(skill_id="test", current_stage="execution")
        assert info.current_stage == "execution"
        data = info.model_dump()
        restored = LoadedSkillInfo.model_validate(data)
        assert restored.current_stage == "execution"

    def test_session_state_empty(self) -> None:
        """An empty session must have all collection fields initialised
        to empty containers — prevents KeyError / TypeError on first
        access in StateManager and ToolRewriter."""
        state = SessionState(session_id="test-session")
        assert state.skills_metadata == {}
        assert state.skills_loaded == {}
        assert state.active_tools == []
        assert state.active_grants == {}

    def test_session_state_roundtrip(self) -> None:
        """Nested model roundtrip: SessionState contains SkillMetadata
        and LoadedSkillInfo dicts.  Verifies Pydantic reconstructs the
        inner models correctly from plain dicts."""
        meta = SkillMetadata(skill_id="repo-read", name="Repo Read")
        info = LoadedSkillInfo(skill_id="repo-read")
        state = SessionState(
            session_id="s1",
            skills_metadata={"repo-read": meta},
            skills_loaded={"repo-read": info},
            active_tools=["Read", "Glob"],
        )
        data = state.model_dump()
        restored = SessionState.model_validate(data)
        assert "repo-read" in restored.skills_metadata
        assert restored.active_tools == ["Read", "Glob"]


class TestPolicyModels:
    def test_governance_policy_defaults(self) -> None:
        """Verify the risk-threshold defaults that PolicyEngine.evaluate
        relies on: low=auto, medium=reason, high=approval."""
        policy = GovernancePolicy()
        assert policy.default_risk_thresholds["low"] == "auto"
        assert policy.default_risk_thresholds["high"] == "approval"
        assert policy.default_ttl == 3600
        assert policy.blocked_tools == []

    def test_skill_policy(self) -> None:
        sp = SkillPolicy(skill_id="dangerous", auto_grant=False, approval_required=True)
        assert sp.auto_grant is False
        assert sp.approval_required is True

    def test_governance_policy_roundtrip(self) -> None:
        """Roundtrip with nested SkillPolicy and blocked_tools.
        Ensures the dict[str, SkillPolicy] field survives serialisation."""
        policy = GovernancePolicy(
            skill_policies={
                "db-ops": SkillPolicy(skill_id="db-ops", max_ttl=900)
            },
            blocked_tools=["rm_rf"],
        )
        data = policy.model_dump()
        restored = GovernancePolicy.model_validate(data)
        assert "db-ops" in restored.skill_policies
        assert restored.blocked_tools == ["rm_rf"]
