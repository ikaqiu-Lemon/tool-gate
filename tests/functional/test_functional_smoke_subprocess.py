"""Stage G — smoke subprocess lane.

Drives the real entry points (`tg-mcp` / `tg-hook`) and the full set of
`mock_*_stdio` fixtures as subprocesses. Every test is contract-only —
"can the process start and speak its minimal protocol?" — not full E2E.
Deeper pipelines stay on the in-process lane (happy / gating / stage /
etc.) and the policy-sensitive E2E file is Stage H's job.
"""

from __future__ import annotations

import sys
from pathlib import Path

from ._support.stdio import mcp_handshake, prepare_plugin_dirs, run_hook_event

_MCP_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "mcp"

_EXPECTED_META_TOOLS: set[str] = {
    "list_skills",
    "read_skill",
    "enable_skill",
    "disable_skill",
    "grant_status",
    "run_skill_action",
    "change_stage",
    "refresh_skills",
}


class TestTgMcpSubprocessMetaTools:
    """Spawn `python -m tool_governance.mcp_server` and verify the 8
    meta-tools are advertised via `tools/list`. Proves the tg-mcp entry
    point starts, the FastMCP stdio server handshakes, and every
    ``@mcp.tool()`` declaration is reachable."""

    def test_tools_list_advertises_eight_meta_tools(self, tmp_path) -> None:
        env = prepare_plugin_dirs(tmp_path)
        tool_names = mcp_handshake(
            command=sys.executable,
            args=["-m", "tool_governance.mcp_server"],
            env=env,
        )
        assert set(tool_names) == _EXPECTED_META_TOOLS, (
            f"meta-tool set mismatch: got {sorted(tool_names)}"
        )


class TestMockSensitiveStdioHandshake:
    """Stage G's new fixture. Launching mock_sensitive_stdio and
    confirming `dangerous` is advertised proves the fixture is real —
    not just a skeleton on disk — and that its tool name matches the
    one the namespaced-MCP deny test will feed PreToolUse."""

    def test_dangerous_tool_advertised(self) -> None:
        tool_names = mcp_handshake(_MCP_FIXTURES / "mock_sensitive_stdio.py")
        assert "dangerous" in tool_names


class TestTgHookSubprocessUserPromptSubmit:
    """The existing SessionStart subprocess test lives in
    test_functional_stdio.py. This one covers the per-turn rewrite
    hook — same stdout contract, different event type, hits a
    different handler branch (``handle_user_prompt_submit``)."""

    def test_stdout_contract(self, tmp_path) -> None:
        data, _stderr = run_hook_event(
            {"event": "UserPromptSubmit", "session_id": "smoke-ups"},
            tmp_path=tmp_path,
            session_id="smoke-ups",
        )
        assert isinstance(data, dict)
        assert "additionalContext" in data
        assert isinstance(data["additionalContext"], str)


class TestTgHookSubprocessPreToolUseDeny:
    """PreToolUse deny for an unknown tool must surface the canonical
    hookSpecificOutput shape (hookEventName + permissionDecision) when
    exercised through the real subprocess JSON-on-stdin transport."""

    def test_unknown_tool_returns_deny_contract(self, tmp_path) -> None:
        data, _stderr = run_hook_event(
            {
                "event": "PreToolUse",
                "session_id": "smoke-pre",
                "tool_name": "mock_unknown",
            },
            tmp_path=tmp_path,
            session_id="smoke-pre",
        )
        assert "hookSpecificOutput" in data
        out = data["hookSpecificOutput"]
        assert out["hookEventName"] == "PreToolUse"
        assert out["permissionDecision"] == "deny"
        assert "permissionDecisionReason" in out


class TestNamespacedMcpDenyInSubprocess:
    """End-to-end proof that the active_tools gate rejects
    ``mcp__<server>__<tool>`` names even when delivered through the
    real subprocess hook. Uses the Stage G fixture's declared name
    (``mock_sensitive_stdio`` exposes ``dangerous``) so the deny path
    is grounded in a real advertised tool name."""

    def test_mcp_namespaced_tool_denied(self, tmp_path) -> None:
        data, _stderr = run_hook_event(
            {
                "event": "PreToolUse",
                "session_id": "smoke-ns",
                "tool_name": "mcp__mock_sensitive__dangerous",
            },
            tmp_path=tmp_path,
            session_id="smoke-ns",
        )
        out = data["hookSpecificOutput"]
        assert out["permissionDecision"] == "deny"
        assert "enable_skill" in out["additionalContext"]
