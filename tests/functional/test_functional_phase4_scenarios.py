"""Phase 4 E2E + boundary scenarios.

Gap-fills the Phase 4 §4.5/§4.6 items that the earlier functional
harness did not explicitly cover:

- Multiple skills enabled concurrently — ``active_tools`` must be the
  union of their allowed_tools and both grants must stay valid.
- ``max_ttl`` enforcement — an explicit request for a TTL larger than
  the configured cap must be capped at grant creation time.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from tool_governance import hook_handler, mcp_server

from ._support import events
from ._support.runtime import fixtures_policies_dir, runtime_context


_DEFAULT = fixtures_policies_dir() / "default.yaml"


def _policy_variant(tmp_path: Path, base: Path, mutate) -> Path:
    data = yaml.safe_load(base.read_text(encoding="utf-8"))
    mutate(data)
    out = tmp_path / "policy_variant.yaml"
    out.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return out


class TestMultiSkillConcurrentEnable:
    """Two low-risk skills enabled in the same session must both remain
    active; ``active_tools`` must be the set-union of their
    ``allowed_tools``; both grants must be retrievable."""

    def test_two_skills_active_simultaneously(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))

            r1 = asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            r2 = asyncio.run(mcp_server.enable_skill(skill_id="mock_ttl"))

            assert r1["granted"] is True
            assert r2["granted"] is True

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" in state.skills_loaded
            assert "mock_ttl" in state.skills_loaded

            grants = rt.grant_manager.get_active_grants(session_id)
            skill_ids = {g.skill_id for g in grants}
            assert {"mock_readonly", "mock_ttl"} <= skill_ids

            assert {"mock_read", "mock_glob", "mock_ping"} <= set(
                state.active_tools
            )

    def test_disabling_one_leaves_the_other_intact(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)
        with runtime_context(tmp_path) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_readonly"))
            asyncio.run(mcp_server.enable_skill(skill_id="mock_ttl"))

            asyncio.run(mcp_server.disable_skill(skill_id="mock_readonly"))

            state = rt.state_manager.load_or_init(session_id)
            assert "mock_readonly" not in state.skills_loaded
            assert "mock_ttl" in state.skills_loaded

            tools = set(state.active_tools)
            assert "mock_ping" in tools
            assert "mock_read" not in tools
            assert "mock_glob" not in tools


class TestMaxTTLCapping:
    """A grant request with ``ttl`` exceeding the skill's ``max_ttl``
    must be capped at grant creation — the stored ``ttl_seconds`` and
    derived ``expires_at`` must reflect the cap, not the request."""

    def test_requested_ttl_above_cap_is_capped(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        def mutate(d: dict) -> None:
            d.setdefault("skill_policies", {})
            d["skill_policies"]["mock_readonly"] = {
                "skill_id": "mock_readonly",
                "auto_grant": True,
                "require_reason": False,
                "approval_required": False,
                "max_ttl": 120,
            }

        policy = _policy_variant(tmp_path, _DEFAULT, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(skill_id="mock_readonly", ttl=9999)
            )
            assert resp["granted"] is True

            grants = rt.grant_manager.get_active_grants(session_id)
            readonly = [g for g in grants if g.skill_id == "mock_readonly"]
            assert len(readonly) == 1
            assert readonly[0].ttl_seconds == 120

    def test_requested_ttl_below_cap_is_honoured(
        self, tmp_path, session_id, monkeypatch
    ) -> None:
        monkeypatch.setenv("CLAUDE_SESSION_ID", session_id)

        def mutate(d: dict) -> None:
            d.setdefault("skill_policies", {})
            d["skill_policies"]["mock_readonly"] = {
                "skill_id": "mock_readonly",
                "auto_grant": True,
                "require_reason": False,
                "approval_required": False,
                "max_ttl": 600,
            }

        policy = _policy_variant(tmp_path, _DEFAULT, mutate)
        with runtime_context(tmp_path, policy_file=policy) as rt:
            hook_handler.handle_session_start(events.session_start(session_id))
            resp = asyncio.run(
                mcp_server.enable_skill(skill_id="mock_readonly", ttl=60)
            )
            assert resp["granted"] is True

            grants = rt.grant_manager.get_active_grants(session_id)
            readonly = [g for g in grants if g.skill_id == "mock_readonly"]
            assert len(readonly) == 1
            assert readonly[0].ttl_seconds == 60
