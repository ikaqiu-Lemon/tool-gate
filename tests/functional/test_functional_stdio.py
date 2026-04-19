"""Functional stdio-lane tests (Stage F).

Two narrow smoke tests that close out verify Critical 2 by proving the
``mock_*_stdio`` fixtures and the ``tg-hook`` entry point actually run
as subprocesses and speak their respective protocols. Intentionally
minimal — deeper pipelines stay on the in-process lane.
"""

from __future__ import annotations

from pathlib import Path

from ._support.stdio import mcp_handshake, run_hook_event

_MCP_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "mcp"


class TestMockEchoStdioHandshake:
    """Spawn ``mock_echo_stdio.py`` and complete an MCP ``tools/list``
    round-trip. Proves the skeleton server is launchable and protocol-
    compliant, not just a file on disk."""

    def test_tools_list_includes_echo(self) -> None:
        tool_names = mcp_handshake(_MCP_FIXTURES / "mock_echo_stdio.py")
        assert "echo" in tool_names


class TestHookSubprocessStdoutContract:
    """Drive ``python -m tool_governance.hook_handler`` as a subprocess
    with a SessionStart event on stdin and assert the stdout contract
    shape: exactly one JSON object containing ``additionalContext``.
    """

    def test_session_start_stdout_is_single_json_object(
        self, tmp_path
    ) -> None:
        data, _stderr = run_hook_event(
            {"event": "SessionStart", "session_id": "stdio-hook-smoke"},
            tmp_path=tmp_path,
            session_id="stdio-hook-smoke",
        )
        assert isinstance(data, dict)
        assert "additionalContext" in data
        assert isinstance(data["additionalContext"], str)
