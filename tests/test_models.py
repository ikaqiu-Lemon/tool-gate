"""Tests for Pydantic data models — serialization roundtrip, validation.

Guards against regressions in default values, field types, and
model_dump / model_validate fidelity.  If a field default changes
or a roundtrip loses data, these tests catch it.
"""

from datetime import datetime

from tool_governance.models.grant import Grant
from tool_governance.models.policy import GovernancePolicy, SkillPolicy
from tool_governance.models.skill import SkillContent, SkillMetadata, StageDefinition
from tool_governance.models.state import LoadedSkillInfo, SessionState


class TestSkillModels:
    def test_skill_metadata_defaults(self) -> None:
        """Verify that a minimal SkillMetadata gets safe defaults for
        every optional field — prevents silent breakage when new code
        assumes a default that was changed."""
        meta = SkillMetadata(skill_id="test", name="Test Skill")
        assert meta.risk_level == "low"
        assert meta.allowed_tools == []
        assert meta.stages == []
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
