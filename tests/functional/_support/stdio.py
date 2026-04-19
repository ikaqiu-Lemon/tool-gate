"""Subprocess lifecycle helpers for stdio functional tests.

Two distinct transports are covered:

* ``tg-hook`` one-shot — read event JSON from stdin, write a single JSON
  object to stdout, exit. :func:`run_hook_event` drives this via
  ``subprocess.Popen.communicate``.
* MCP stdio server (``mock_*_stdio``) — long-lived process speaking the
  Model Context Protocol over stdio. :func:`mcp_handshake` wraps the
  official ``mcp`` client SDK so the test body stays short.

Both helpers guarantee the child process is terminated (terminate →
wait(2) → kill) so leaked subprocesses cannot outlive a test.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from .runtime import DEFAULT_POLICY_YAML


@contextlib.contextmanager
def spawn(
    script: str | Path,
    env: dict[str, str] | None = None,
):
    """Generic subprocess context manager (kept for future phases).

    Launches ``python <script>`` with piped stdin/stdout/stderr. Teardown
    chain: ``terminate() → wait(2) → kill()``.
    """
    argv = [sys.executable, str(script)]
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=full_env,
    )
    try:
        yield proc
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)


def prepare_plugin_dirs(tmp_path: Path) -> dict[str, str]:
    """Create data/config dirs + default policy; return the env-var dict
    the subprocess will consume."""
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "default_policy.yaml").write_text(
        DEFAULT_POLICY_YAML, encoding="utf-8"
    )

    skills_dir = (
        Path(__file__).resolve().parents[2] / "fixtures" / "skills"
    )
    return {
        "GOVERNANCE_DATA_DIR": str(data_dir),
        "GOVERNANCE_CONFIG_DIR": str(config_dir),
        "GOVERNANCE_SKILLS_DIR": str(skills_dir),
    }


def run_hook_event(
    event: dict[str, Any],
    *,
    tmp_path: Path,
    session_id: str,
    timeout: float = 5.0,
) -> tuple[dict[str, Any], str]:
    """Run ``python -m tool_governance.hook_handler`` one-shot.

    Writes ``event`` (as JSON) to the child's stdin and returns a tuple
    ``(parsed_stdout_json, stderr_str)``. Raises ``RuntimeError`` if the
    child exits non-zero or stdout is not a single JSON object.
    """
    env = {
        **os.environ,
        **prepare_plugin_dirs(tmp_path),
        "CLAUDE_SESSION_ID": session_id,
    }
    proc = subprocess.Popen(
        [sys.executable, "-m", "tool_governance.hook_handler"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        stdout_bytes, stderr_bytes = proc.communicate(
            input=json.dumps(event).encode("utf-8"), timeout=timeout
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)
        raise

    stderr = stderr_bytes.decode("utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(
            f"tg-hook exited {proc.returncode}\nstderr:\n{stderr}"
        )
    text = stdout_bytes.decode("utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"tg-hook stdout is not a single JSON object:\n{text!r}\n{e}"
        )
    if not isinstance(data, dict):
        raise RuntimeError(
            f"tg-hook stdout JSON is not an object: {type(data).__name__}"
        )
    return data, stderr


def mcp_handshake(
    script_path: Path | None = None,
    *,
    command: str | None = None,
    args: list[str] | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 10.0,
) -> list[str]:
    """Launch an MCP stdio server and return the tool names it advertises.

    Two launch modes:
        * ``mcp_handshake(<path>)`` runs ``python <path>``.
        * ``mcp_handshake(command=<bin>, args=[...])`` invokes an
          explicit command, e.g.
          ``mcp_handshake(command=sys.executable,
                          args=["-m", "tool_governance.mcp_server"])``.

    ``env`` is passed straight into ``StdioServerParameters``. When
    ``None``, the child inherits the parent's environment. Callers that
    need governance env vars (``GOVERNANCE_*``, ``CLAUDE_SESSION_ID``)
    should merge them with ``os.environ`` themselves or use
    :func:`prepare_plugin_dirs` to build the dict.

    Runs the minimum viable handshake: ``initialize`` → ``tools/list``.
    Uses the official ``mcp`` client SDK to avoid hand-rolling JSON-RPC.
    """
    if script_path is not None and command is not None:
        raise ValueError("pass either script_path or command, not both")
    if script_path is not None:
        resolved_command = sys.executable
        resolved_args = [str(script_path)]
    elif command is not None:
        resolved_command = command
        resolved_args = list(args or [])
    else:
        raise ValueError("mcp_handshake requires script_path or command")

    async def _run() -> list[str]:
        params = StdioServerParameters(
            command=resolved_command,
            args=resolved_args,
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                return [t.name for t in tools_result.tools]

    return asyncio.run(asyncio.wait_for(_run(), timeout=timeout))
