"""Stage F — policy-fixture-driven functional tests.

Every test in this file loads a real YAML policy via
``bootstrap.load_policy`` (through ``make_runtime(..., policy_file=...)``)
and asserts that ``PolicyEngine`` — unmodified — produces the expected
decision. **Nothing here monkey-patches ``PolicyEngine.evaluate``**; the
only patched symbol anywhere in the stack is ``skill_executor.dispatch``
(and only in tests that actually exercise ``run_skill_action``, which
Stage F does not).

Scenarios covered:
    * TestPolicyFixtureLoading           — fixtures reach PolicyEngine.
    * TestLowRiskAutoAllowDefault        — low risk under default.yaml.
    * TestMediumRiskAskDefault           — medium risk under default.yaml.
    * TestHighRiskDenyRestrictive        — high risk under restrictive.yaml.
    * TestBlockedToolsStripsActiveTools  — blocked_tools tool-name route.
    * TestSkillOverrideBeatsRiskDefault  — skill_policies wins over
                                            risk-level default.
"""

from __future__ import annotations

import asyncio

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.runtime import fixtures_policies_dir, runtime_context


_DEFAULT = fixtures_policies_dir() / "default.yaml"
_RESTRICTIVE = fixtures_policies_dir() / "restrictive.yaml"


class TestPolicyFixtureLoading:
    """Sanity — the YAML is really reaching ``PolicyEngine``."""

    def test_default_yaml_loads_baseline(self, tmp_path) -> None:
        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            assert rt.policy.blocked_tools == []
            assert rt.policy.skill_policies == {}
            assert rt.policy.default_risk_thresholds["low"] == "auto"
            assert rt.policy.default_risk_thresholds["medium"] == "approval"
            assert rt.policy.default_risk_thresholds["high"] == "approval"

    def test_restrictive_yaml_loads_overrides(self, tmp_path) -> None:
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            assert "mock_sensitive" in rt.policy.blocked_tools
            assert "mock_ping" in rt.policy.blocked_tools
            assert "mock_readonly" in rt.policy.skill_policies
            sp = rt.policy.skill_policies["mock_readonly"]
            assert sp.approval_required is True
            assert sp.auto_grant is False


class TestLowRiskAutoAllowDefault:
    """Low-risk skill under default.yaml auto-grants through the real
    ``PolicyEngine`` — Grant.granted_by == "auto" is observable evidence
    that ``decision.decision == "auto"`` came out of the engine."""

    def test_enable_mock_readonly_auto_granted(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            assert resp["granted"] is True
            tools = set(resp["allowed_tools"])
            assert "mock_read" in tools
            assert "mock_glob" in tools

            grants = rt.grant_manager.get_active_grants(session_id)
            assert len(grants) == 1
            assert grants[0].skill_id == "mock_readonly"
            assert grants[0].granted_by == "auto"


class TestMediumRiskAskDefault:
    """Medium-risk skill under default.yaml returns
    ``decision="approval_required"`` — no Grant created, no tools
    leaked into ``active_tools``."""

    def test_enable_mock_stageful_returns_approval_required(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_stageful"))

            assert resp["granted"] is False
            assert resp["decision"] == "approval_required"
            assert rt.grant_manager.get_active_grants(session_id) == []

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_read" not in state.active_tools
            assert "mock_edit" not in state.active_tools


class TestHighRiskDenyRestrictive:
    """High-risk skill (listed in ``blocked_tools`` as a skill-id) is
    denied unconditionally under restrictive.yaml, even with a reason."""

    def test_enable_mock_sensitive_denied(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(
                    skill_id="mock_sensitive", reason="urgent"
                )
            )

            assert resp["granted"] is False
            assert resp["decision"] == "denied"
            assert rt.grant_manager.get_active_grants(session_id) == []


class TestBlockedToolsStripsActiveTools:
    """``blocked_tools`` containing a TOOL name strips that tool from
    ``active_tools`` even after a skill that owns it is successfully
    enabled — and PreToolUse consequently denies it.

    Setup: mock_ttl (low-risk, no skill_policies override under
    restrictive.yaml) is enableable.  mock_ttl advertises tool
    ``mock_ping``.  restrictive.yaml lists ``mock_ping`` in
    ``blocked_tools``.  Therefore enable succeeds, but the tool is
    stripped by ``ToolRewriter._blocked``.
    """

    def test_mock_ping_blocked_even_after_mock_ttl_enabled(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_ttl"))

            assert resp["granted"] is True
            assert "mock_ping" not in resp["allowed_tools"]

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_ping" not in state.active_tools

            gate = hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mock_ping")
            )
            assert gate["hookSpecificOutput"]["permissionDecision"] == "deny"


class TestSkillOverrideBeatsRiskDefault:
    """``skill_policies`` takes precedence over the risk-level default.

    mock_readonly is risk_level=low (would auto-grant under the default
    threshold), but restrictive.yaml pins
    ``mock_readonly.approval_required = true`` so enable returns
    ``decision="approval_required"``.
    """

    def test_mock_readonly_needs_approval_under_restrictive(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))

            assert resp["granted"] is False
            assert resp["decision"] == "approval_required"
            assert rt.grant_manager.get_active_grants(session_id) == []
