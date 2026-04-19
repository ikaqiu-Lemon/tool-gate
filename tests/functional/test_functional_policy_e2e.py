"""Stage H — Mock E2E lane (policy-sensitive core, E1–E6).

Every test here drives the runtime through a real YAML fixture
(``tests/fixtures/policies/{default,restrictive}.yaml``) or an inline
derivative written to ``tmp_path``. **No test monkey-patches
``PolicyEngine.evaluate``** — the only patched symbol is
``skill_executor.dispatch`` (outside the governance decision path).
This keeps the assertion chain honest: if these tests pass, policy is
really running.

Lifecycle re-verification (change_stage / TTL / revoke under real
policy) lives in the sibling file ``test_functional_policy_e2e_lifecycle.py``.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from tool_governance import hook_handler, mcp_server
from tool_governance.core import skill_executor as skill_executor_mod

from ._support import events
from ._support.audit import decoded_detail, events_of_type
from ._support.runtime import fixtures_policies_dir, runtime_context


_DEFAULT = fixtures_policies_dir() / "default.yaml"
_RESTRICTIVE = fixtures_policies_dir() / "restrictive.yaml"


def _policy_variant(tmp_path: Path, base: Path, mutate) -> Path:
    """Load ``base`` YAML, apply ``mutate(dict)``, write under tmp_path."""
    data = yaml.safe_load(base.read_text(encoding="utf-8"))
    mutate(data)
    out = tmp_path / "policy_variant.yaml"
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return out


# ---------------------------------------------------------------- E1
class TestE1LowRiskAutoAllowFullChain:
    """E2E-1 — low-risk happy path, full chain.

    Proves: SessionStart indexes fixtures → list_skills/read_skill expose
    mock_readonly → enable_skill under default.yaml auto-grants (policy
    really ran: Grant.granted_by=="auto") → UserPromptSubmit rewrites
    context with active tools → run_skill_action dispatches (stubbed) →
    PostToolUse stamps last_used_at and writes tool.call audit.
    """

    def test_full_low_risk_chain(self, tmp_path, session_id, monkeypatch) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        captured: list[tuple[str, str, dict]] = []

        def stub_dispatch(skill_id: str, op: str, args: dict) -> dict:
            captured.append((skill_id, op, dict(args)))
            return {"info": f"{skill_id}:{op}"}

        monkeypatch.setattr(skill_executor_mod, "dispatch", stub_dispatch)

        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            ss = hook_handler.handle_session_start(events.session_start(session_id))
            assert "Mock Readonly" in ss["additionalContext"]

            listed = asyncio.run(mcp_server.list_skills())
            assert "mock_readonly" in {e["skill_id"] for e in listed}

            sop = asyncio.run(mcp_server.read_skill("mock_readonly"))
            assert sop["metadata"]["skill_id"] == "mock_readonly"

            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            assert resp["granted"] is True
            grants = rt.grant_manager.get_active_grants(session_id)
            assert len(grants) == 1
            assert grants[0].granted_by == "auto"  # proves policy fired

            ups = hook_handler.handle_user_prompt_submit(
                events.user_prompt_submit(session_id)
            )
            assert "mock_read" in ups["additionalContext"]
            state = rt.state_manager.load_or_init(session_id)
            assert {"mock_read", "mock_glob"}.issubset(state.active_tools)

            act = asyncio.run(
                mcp_server.run_skill_action("mock_readonly", "search", {"q": "x"})
            )
            assert act == {"result": {"info": "mock_readonly:search"}}
            assert captured == [("mock_readonly", "search", {"q": "x"})]

            hook_handler.handle_post_tool_use(
                events.post_tool_use(session_id, "mock_read")
            )
            state = rt.state_manager.load_or_init(session_id)
            assert state.skills_loaded["mock_readonly"].last_used_at is not None

            tool_calls = events_of_type(rt, session_id, "tool.call")
            assert any(r.get("tool_name") == "mock_read" for r in tool_calls)
            enables = events_of_type(rt, session_id, "skill.enable")
            assert any(e.get("decision") == "granted" for e in enables)


# ---------------------------------------------------------------- E2
class TestE2MediumRiskAskNoGrant:
    """E2E-2 — medium-risk ``ask`` path.

    Under default.yaml (medium → approval), ``enable_skill(mock_stageful)``
    without reason returns ``decision="approval_required"``.  No Grant is
    created, no tools leak into ``active_tools``, and a follow-up
    ``run_skill_action`` is rejected because the skill is not loaded.
    """

    def test_ask_no_grant_no_tools_no_execution(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_stageful"))
            assert resp["granted"] is False
            assert resp["decision"] == "approval_required"

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_stageful" not in state.skills_loaded
            assert "mock_read" not in state.active_tools
            assert rt.grant_manager.get_active_grants(session_id) == []

            act = asyncio.run(
                mcp_server.run_skill_action("mock_stageful", "analyze", {})
            )
            assert "error" in act
            assert "not enabled" in act["error"].lower()


# ---------------------------------------------------------------- E3
class TestE3HighRiskDenyUnderRestrictive:
    """E2E-3 — high-risk deny.

    Canonical ``restrictive.yaml`` already lists ``mock_sensitive`` in
    ``blocked_tools`` (skill-id denylist route inside ``PolicyEngine``),
    so an inline derivative is unnecessary — the fixture is already the
    derivative the Stage H plan describes. ``enable_skill`` returns
    ``decision="denied"`` even with a reason; no Grant row is created.
    """

    def test_sensitive_denied_via_blocked_skill_id(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(skill_id="mock_sensitive", reason="urgent")
            )
            assert resp["granted"] is False
            assert resp["decision"] == "denied"
            assert rt.grant_manager.get_active_grants(session_id) == []

            enables = events_of_type(rt, session_id, "skill.enable")
            assert enables and enables[-1]["decision"] == "denied"


# ---------------------------------------------------------------- E4
class TestE4BlockedToolStripsAndDenies:
    """E2E-4 — ``blocked_tools`` (tool-name route) strips the tool from
    ``active_tools`` even after a successful enable, and PreToolUse
    denies it with ``error_bucket="whitelist_violation"``.

    Uses an inline derivative that keeps ``blocked_tools: [mock_read]``
    but drops the ``mock_readonly`` approval override so enable succeeds
    and we can isolate the ``ToolRewriter`` deny path.
    """

    def test_blocked_tool_stripped_and_denied_at_pretooluse(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        def mutate(d: dict) -> None:
            d["blocked_tools"] = ["mock_read"]
            d["skill_policies"] = {}

        policy = _policy_variant(tmp_path, _RESTRICTIVE, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            assert resp["granted"] is True
            assert "mock_read" not in resp["allowed_tools"]
            assert "mock_glob" in resp["allowed_tools"]

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_read" not in state.active_tools

            gate = hook_handler.handle_pre_tool_use(
                events.pre_tool_use(session_id, "mock_read")
            )
            assert gate["hookSpecificOutput"]["permissionDecision"] == "deny"

            denies = [
                r
                for r in events_of_type(rt, session_id, "tool.call")
                if r.get("decision") == "deny"
            ]
            assert denies
            assert decoded_detail(denies[-1]).get("error_bucket") == "whitelist_violation"


# ---------------------------------------------------------------- E5
class TestE5SkillOverrideBeatsRiskDefault:
    """E2E-5a — skill-specific override wins.

    ``mock_readonly`` is low-risk (would auto-grant under
    ``low: auto``), but canonical ``restrictive.yaml`` pins
    ``skill_policies.mock_readonly.approval_required = true``.
    ``enable_skill`` must therefore return ``approval_required``.
    """

    def test_low_risk_skill_needs_approval_under_override(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            assert resp["granted"] is False
            assert resp["decision"] == "approval_required"
            assert rt.grant_manager.get_active_grants(session_id) == []


# ---------------------------------------------------------------- E6
class TestE6RequireReasonOverrideBothBranches:
    """E2E-5 support — ``require_reason`` override, both sub-cases.

    Canonical ``restrictive.yaml`` sets
    ``skill_policies.mock_stageful.require_reason = true``.  Without a
    reason ``PolicyEngine`` returns ``reason_required``; with a reason
    it returns ``auto`` with the reason attached.
    """

    def test_without_reason_returns_reason_required(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path, policy_file=_RESTRICTIVE) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(mcp_server.enable_skill(skill_id="mock_stageful"))
            assert resp["granted"] is False
            assert resp["decision"] == "reason_required"
            assert rt.grant_manager.get_active_grants(session_id) == []

    def test_with_reason_grants_auto_and_records_reason(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        # Canonical restrictive.yaml has mock_stageful.auto_grant=false,
        # which causes the skill-specific step to fall through to the
        # medium=approval default even when a reason is given (documented
        # silence at policy_engine.py:86).  To prove the reason-grant
        # branch end-to-end we set auto_grant=true on the override — now
        # with reason the engine returns decision="auto" via step 2.
        def mutate(d: dict) -> None:
            d["skill_policies"]["mock_stageful"]["auto_grant"] = True

        policy = _policy_variant(tmp_path, _RESTRICTIVE, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(
                    skill_id="mock_stageful", reason="ticket PROJ-42"
                )
            )
            assert resp["granted"] is True
            grants = rt.grant_manager.get_active_grants(session_id)
            assert len(grants) == 1
            assert grants[0].reason == "ticket PROJ-42"
            # PolicyEngine decision == "auto" → granted_by == "auto".
            assert grants[0].granted_by == "auto"
