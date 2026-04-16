"""Tests for PolicyEngine.

Covers the three-tier evaluation precedence (blocked → skill-specific
→ risk-level defaults), TTL capping, and tool-in-active-tools checks.
Each test targets a specific boundary in the policy decision logic.
"""

import pytest

from tool_governance.core.policy_engine import PolicyEngine
from tool_governance.models.policy import GovernancePolicy, SkillPolicy
from tool_governance.models.skill import SkillMetadata
from tool_governance.models.state import SessionState


@pytest.fixture()
def policy() -> GovernancePolicy:
    """Default policy: low=auto, medium=reason, high=approval."""
    return GovernancePolicy()


@pytest.fixture()
def engine(policy: GovernancePolicy) -> PolicyEngine:
    return PolicyEngine(policy)


@pytest.fixture()
def state() -> SessionState:
    return SessionState(session_id="test")


def _meta(skill_id: str, risk: str = "low") -> SkillMetadata:
    """Minimal SkillMetadata with a given risk level — the only field
    that the policy engine's risk-threshold logic reads."""
    return SkillMetadata(skill_id=skill_id, name=skill_id, risk_level=risk)


class TestEvaluate:
    """Tests for the evaluate() precedence chain."""

    def test_low_risk_auto_grant(self, engine: PolicyEngine, state: SessionState) -> None:
        """Low risk → default threshold "auto" → allowed without reason."""
        d = engine.evaluate("repo-read", _meta("repo-read", "low"), state)
        assert d.allowed is True
        assert d.decision == "auto"

    def test_medium_risk_needs_reason(self, engine: PolicyEngine, state: SessionState) -> None:
        """Medium risk → default threshold "reason" → denied when no
        reason is provided."""
        d = engine.evaluate("code-edit", _meta("code-edit", "medium"), state)
        assert d.allowed is False
        assert d.decision == "reason_required"

    def test_medium_risk_with_reason(self, engine: PolicyEngine, state: SessionState) -> None:
        """Medium risk with a reason string supplied → allowed.
        Verifies that providing a reason satisfies the "reason"
        threshold."""
        d = engine.evaluate("code-edit", _meta("code-edit", "medium"), state, reason="fix bug")
        assert d.allowed is True

    def test_high_risk_needs_approval(self, engine: PolicyEngine, state: SessionState) -> None:
        """High risk → default threshold "approval" → denied (requires
        out-of-band approval)."""
        d = engine.evaluate("deploy", _meta("deploy", "high"), state)
        assert d.allowed is False
        assert d.decision == "approval_required"

    def test_blocked_skill_denied(self, state: SessionState) -> None:
        """Step 1 of precedence: a skill in blocked_tools is denied
        regardless of risk level — even "low" risk."""
        p = GovernancePolicy(blocked_tools=["dangerous"])
        engine = PolicyEngine(p)
        d = engine.evaluate("dangerous", _meta("dangerous", "low"), state)
        assert d.allowed is False
        assert d.decision == "denied"

    def test_skill_specific_auto_grant_overrides(self, state: SessionState) -> None:
        """Step 2 of precedence: a skill-specific policy with
        auto_grant=True overrides the risk-level threshold — even
        for a "high" risk skill."""
        p = GovernancePolicy(
            skill_policies={"special": SkillPolicy(skill_id="special", auto_grant=True)}
        )
        engine = PolicyEngine(p)
        d = engine.evaluate("special", _meta("special", "high"), state)
        assert d.allowed is True

    def test_skill_specific_approval_required(self, state: SessionState) -> None:
        """Step 2: approval_required in the skill policy takes
        priority over auto_grant and risk level — even a "low" risk
        skill is blocked."""
        p = GovernancePolicy(
            skill_policies={"guarded": SkillPolicy(skill_id="guarded", approval_required=True)}
        )
        engine = PolicyEngine(p)
        d = engine.evaluate("guarded", _meta("guarded", "low"), state)
        assert d.allowed is False
        assert d.decision == "approval_required"


class TestToolAllowed:
    def test_tool_in_active_tools(self, engine: PolicyEngine) -> None:
        """Simple membership check — present tool allowed, absent
        tool denied."""
        state = SessionState(session_id="t", active_tools=["Read", "Glob"])
        assert engine.is_tool_allowed("Read", state) is True
        assert engine.is_tool_allowed("Write", state) is False


class TestTTLCapping:
    """Tests for get_max_ttl and cap_ttl."""

    def test_cap_to_max(self, engine: PolicyEngine) -> None:
        """Requested TTL above the global default (3600) must be
        clamped down."""
        assert engine.cap_ttl("repo-read", 99999) == 3600

    def test_under_max_unchanged(self, engine: PolicyEngine) -> None:
        """Requested TTL under the max must pass through unchanged."""
        assert engine.cap_ttl("repo-read", 1800) == 1800

    def test_skill_specific_max(self) -> None:
        """A skill-specific max_ttl overrides the global default —
        the tighter limit must apply."""
        p = GovernancePolicy(
            skill_policies={"fast": SkillPolicy(skill_id="fast", max_ttl=300)}
        )
        engine = PolicyEngine(p)
        assert engine.cap_ttl("fast", 600) == 300
