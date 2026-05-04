"""Stage H — Mock E2E lane (lifecycle re-verification, E7–E9).

Split from ``test_functional_policy_e2e.py`` to stay under the Stage H
LOC budget.  Every test here proves that the existing lifecycle flows —
``change_stage``, TTL expiry, explicit revoke — continue to work when
policy is loaded from real YAML via ``bootstrap.load_policy`` instead
of the inline ``DEFAULT_POLICY_YAML`` used by the Stage C tests.

Same honesty contract as the sibling file: no monkeypatch on
``PolicyEngine.evaluate``.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

import yaml

from tool_governance import hook_handler, mcp_server

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


# ---------------------------------------------------------------- E7
class TestE7ChangeStageUnderPolicy:
    """E2E-5b — ``change_stage`` still swaps active_tools and emits
    ``stage.transition.allow`` audit when policy comes from an inline derivative
    of ``restrictive.yaml`` (``mock_stageful.auto_grant=true``,
    ``require_reason=true``).  Enabling with a reason auto-grants via
    the skill-specific route; default stage = analysis, switching to
    execution swaps the tool set.

    Why a derivative: canonical ``restrictive.yaml`` sets
    ``mock_stageful.auto_grant=false`` with medium threshold
    ``approval``, which — per the documented PolicyEngine silence at
    policy_engine.py:86 — falls through to the default even when a
    reason is given.  Flipping ``auto_grant=true`` isolates the
    skill-specific reason-then-grant path for this test.
    """

    def test_change_stage_swaps_tools_and_emits_audit(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        def mutate(d: dict) -> None:
            d["skill_policies"]["mock_stageful"]["auto_grant"] = True

        policy = _policy_variant(tmp_path, _RESTRICTIVE, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            enable = asyncio.run(
                mcp_server.enable_skill(
                    skill_id="mock_stageful", reason="staging e2e"
                )
            )
            assert enable["granted"] is True

            state = rt.state_manager.load_or_init(session_id)
            # Stage C3 excluded ``active_tools`` from the persisted
            # payload; recompute before asserting tool membership.
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            assert "mock_read" in state.active_tools
            assert "mock_write" not in state.active_tools

            change = asyncio.run(
                mcp_server.change_stage(
                    skill_id="mock_stageful", stage_id="execution"
                )
            )
            assert change["changed"] is True
            new_tools = set(change["new_active_tools"])
            assert {"mock_edit", "mock_write"}.issubset(new_tools)
            assert "mock_read" not in new_tools
            assert "mock_glob" not in new_tools

            audits = events_of_type(rt, session_id, "stage.transition.allow")
            assert len(audits) == 1
            assert audits[0]["skill_id"] == "mock_stageful"
            detail = decoded_detail(audits[0])
            assert detail["from_stage"] == "analysis"
            assert detail["to_stage"] == "execution"


# ---------------------------------------------------------------- E8
class TestE8TTLExpiryUnderPolicy:
    """E2E-5c — TTL reclamation sweep still fires under real YAML policy.

    ``default.yaml`` auto-grants ``mock_readonly``, but we bypass
    ``enable_skill`` to create a grant with ``ttl=0`` directly (same
    pattern as ``test_functional_ttl.py``).  After a tick,
    ``UserPromptSubmit`` must drop the skill from ``skills_loaded`` and
    emit ``grant.expire`` (NOT ``grant.revoke`` — expiry and revoke are
    distinct audit buckets).
    """

    def test_expiry_sweep_emits_expire_not_revoke(
        self, tmp_path, session_id
    ) -> None:
        with runtime_context(tmp_path, policy_file=_DEFAULT) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            state = rt.state_manager.load_or_init(session_id)
            # Stage D: read from indexer instead of persisted state.
            meta = rt.indexer.current_index()["mock_readonly"]
            grant = rt.grant_manager.create_grant(
                session_id, "mock_readonly", meta.allowed_ops, ttl=0
            )
            rt.state_manager.add_to_skills_loaded(state, "mock_readonly")
            state.active_grants["mock_readonly"] = grant
            rt.tool_rewriter.recompute_active_tools(state, rt.indexer)
            rt.state_manager.save(state)

            time.sleep(0.1)
            hook_handler.handle_user_prompt_submit(
                events.user_prompt_submit(session_id)
            )

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" not in state.skills_loaded

            expires = events_of_type(rt, session_id, "grant.expire")
            revokes = events_of_type(rt, session_id, "grant.revoke")
            assert any(r["skill_id"] == "mock_readonly" for r in expires)
            assert revokes == []


# ---------------------------------------------------------------- E9
class TestE9RevokeUnderPolicy:
    """E2E-5d — ``disable_skill`` still emits audit order
    ``grant.revoke`` → ``skill.disable`` under real YAML policy.

    Uses an inline derivative of ``restrictive.yaml`` with the
    ``mock_readonly`` approval override dropped so enable auto-grants
    and the revoke path can be isolated from approval flow.
    """

    def test_audit_order_revoke_then_disable_with_reason(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        def mutate(d: dict) -> None:
            d["skill_policies"] = {}
            d["blocked_tools"] = []

        policy = _policy_variant(tmp_path, _RESTRICTIVE, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            enable = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            assert enable["granted"] is True

            disable = asyncio.run(mcp_server.disable_skill(skill_id="mock_readonly"))
            assert disable["disabled"] is True

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" not in state.skills_loaded
            assert "mock_read" not in state.active_tools
            assert "mock_glob" not in state.active_tools

            all_events = rt.store.query_audit(session_id=session_id)
            relevant = [
                e
                for e in all_events
                if e["event_type"] in ("grant.revoke", "skill.disable")
            ]
            assert [e["event_type"] for e in relevant] == [
                "grant.revoke",
                "skill.disable",
            ]
            assert decoded_detail(relevant[0]).get("reason") == "explicit"
            assert relevant[0]["skill_id"] == relevant[1]["skill_id"] == "mock_readonly"
