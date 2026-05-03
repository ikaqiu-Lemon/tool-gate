"""
Claude Code Simulator - Core orchestration for governance chain demonstration.

This module provides the main ClaudeCodeSimulator class that orchestrates
hook and MCP subprocess invocations to demonstrate the governance chain.

Stage C: Governance chain integration with real subprocess communication.
"""

import asyncio
import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .hook_subprocess import HookSubprocess
from .mcp_subprocess import MCPSubprocess


class ClaudeCodeSimulator:
    """
    Orchestrates the Claude Code governance chain demonstration.

    Responsibilities:
    - Manage session lifecycle (session_id, data_dir, environment variables)
    - Coordinate hook and MCP subprocess invocations
    - Capture responses from subprocesses
    - Provide minimal governance chain methods

    Does NOT:
    - Implement policy evaluation logic (delegated to tg-hook and tg-mcp)
    - Implement scenario logic (Stage D)
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        data_dir: Optional[Path] = None,
        skills_dir: Optional[Path] = None,
        config_dir: Optional[Path] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize the simulator.

        Args:
            session_id: Unique session identifier (generated if not provided)
            data_dir: Directory for governance.db and session state
            skills_dir: Directory containing skill definitions
            config_dir: Directory containing policy configuration
            timeout: Default timeout for subprocess invocations (seconds)
        """
        self.session_id = session_id or f"sim-{uuid.uuid4().hex[:8]}"
        self.timeout = timeout

        # Set up directories
        self.data_dir = data_dir or Path.cwd() / ".simulator-data"
        self.skills_dir = skills_dir
        self.config_dir = config_dir

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variables for governance runtime
        self._setup_environment()

        # Subprocess wrappers
        self._hook_subprocess = HookSubprocess(timeout=timeout)
        self._mcp_subprocess = MCPSubprocess(timeout=timeout)
        self._mcp_started = False

        # Event tracking for artifacts
        self._events: List[Dict[str, Any]] = []

    @property
    def db_path(self) -> Path:
        """Return path to governance.db."""
        return self.data_dir / "governance.db"

    def _setup_environment(self) -> None:
        """Set up environment variables for tg-hook and tg-mcp."""
        os.environ["GOVERNANCE_DATA_DIR"] = str(self.data_dir)
        os.environ["CLAUDE_SESSION_ID"] = self.session_id

        if self.skills_dir:
            os.environ["GOVERNANCE_SKILLS_DIR"] = str(self.skills_dir)

        if self.config_dir:
            os.environ["GOVERNANCE_CONFIG_DIR"] = str(self.config_dir)

    async def start_mcp(self) -> None:
        """Start the MCP server subprocess and complete handshake."""
        if not self._mcp_started:
            await self._mcp_subprocess.start()
            self._mcp_started = True

    async def stop_mcp(self) -> None:
        """Stop the MCP server subprocess."""
        if self._mcp_started:
            await self._mcp_subprocess.stop()
            self._mcp_started = False

    def session_start(self) -> Dict[str, Any]:
        """Invoke SessionStart hook.

        Returns:
            Hook response containing additionalContext
        """
        event = {
            "event": "SessionStart",
            "session_id": self.session_id,
            "cwd": str(Path.cwd()),
        }
        result = self._hook_subprocess.invoke(event)
        self._events.append({
            "type": "hook.session_start",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
        })
        return result

    def user_prompt_submit(self) -> Dict[str, Any]:
        """Invoke UserPromptSubmit hook.

        Returns:
            Hook response containing updated active_tools
        """
        event = {
            "event": "UserPromptSubmit",
            "session_id": self.session_id,
        }
        result = self._hook_subprocess.invoke(event)
        self._events.append({
            "type": "hook.user_prompt_submit",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.session_id,
        })
        return result

    def pre_tool_use(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke PreToolUse hook.

        Args:
            tool_name: Name of the tool being called
            tool_input: Tool arguments

        Returns:
            Hook response containing permissionDecision (allow/deny)
        """
        event = {
            "event": "PreToolUse",
            "session_id": self.session_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
        }
        result = self._hook_subprocess.invoke(event)
        self._events.append({
            "type": "hook.pre_tool_use",
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
            "decision": result.get("permissionDecision", "unknown"),
        })
        return result

    def post_tool_use(self, tool_name: str, tool_input: Dict[str, Any], tool_output: Any) -> Dict[str, Any]:
        """Invoke PostToolUse hook.

        Args:
            tool_name: Name of the tool that was called
            tool_input: Tool arguments
            tool_output: Tool result

        Returns:
            Hook response (typically empty)
        """
        event = {
            "event": "PostToolUse",
            "session_id": self.session_id,
            "tool_name": tool_name,
            "tool_input": tool_input,
            "tool_output": tool_output,
        }
        result = self._hook_subprocess.invoke(event)
        self._events.append({
            "type": "hook.post_tool_use",
            "timestamp": datetime.utcnow().isoformat(),
            "tool_name": tool_name,
        })
        return result

    async def enable_skill(self, skill_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Call enable_skill MCP tool.

        Args:
            skill_id: Skill to enable
            reason: Optional reason for enablement

        Returns:
            MCP tool result
        """
        if not self._mcp_started:
            await self.start_mcp()

        arguments = {"skill_id": skill_id}
        if reason:
            arguments["reason"] = reason

        result = await self._mcp_subprocess.call_tool("enable_skill", arguments)
        self._events.append({
            "type": "mcp.enable_skill",
            "timestamp": datetime.utcnow().isoformat(),
            "skill_id": skill_id,
            "reason": reason,
        })
        return result

    async def disable_skill(self, skill_id: str) -> Dict[str, Any]:
        """Call disable_skill MCP tool.

        Args:
            skill_id: Skill to disable

        Returns:
            MCP tool result
        """
        if not self._mcp_started:
            await self.start_mcp()

        result = await self._mcp_subprocess.call_tool("disable_skill", {"skill_id": skill_id})
        self._events.append({
            "type": "mcp.disable_skill",
            "timestamp": datetime.utcnow().isoformat(),
            "skill_id": skill_id,
        })
        return result

    async def change_stage(self, skill_id: str, stage_id: str) -> Dict[str, Any]:
        """Call change_stage MCP tool.

        Args:
            skill_id: Skill to change stage for
            stage_id: Target stage

        Returns:
            MCP tool result
        """
        if not self._mcp_started:
            await self.start_mcp()

        result = await self._mcp_subprocess.call_tool(
            "change_stage",
            {"skill_id": skill_id, "stage_id": stage_id}
        )
        self._events.append({
            "type": "mcp.change_stage",
            "timestamp": datetime.utcnow().isoformat(),
            "skill_id": skill_id,
            "stage_id": stage_id,
        })
        return result

    async def list_skills(self) -> Dict[str, Any]:
        """Call list_skills MCP tool.

        Returns:
            MCP tool result with list of skills
        """
        if not self._mcp_started:
            await self.start_mcp()

        return await self._mcp_subprocess.call_tool("list_skills", {})

    async def read_skill(self, skill_id: str) -> Dict[str, Any]:
        """Call read_skill MCP tool.

        Args:
            skill_id: Skill to read

        Returns:
            MCP tool result with skill details
        """
        if not self._mcp_started:
            await self.start_mcp()

        return await self._mcp_subprocess.call_tool("read_skill", {"skill_id": skill_id})

    async def refresh_skills(self) -> Dict[str, Any]:
        """Call refresh_skills MCP tool to rebuild skill index.

        Returns:
            MCP tool result
        """
        if not self._mcp_started:
            await self.start_mcp()

        return await self._mcp_subprocess.call_tool("refresh_skills", {})

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Read current state from SQLite governance.db.

        Returns:
            Dict containing sessions, grants, and audit_log entries
        """
        if not self.db_path.exists():
            return {"sessions": [], "grants": [], "audit_log": []}

        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Read sessions
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (self.session_id,))
            sessions = [dict(row) for row in cursor.fetchall()]

            # Read grants
            cursor.execute("SELECT * FROM grants WHERE session_id = ?", (self.session_id,))
            grants = [dict(row) for row in cursor.fetchall()]

            # Read audit_log
            cursor.execute("SELECT * FROM audit_log WHERE session_id = ?", (self.session_id,))
            audit_log = [dict(row) for row in cursor.fetchall()]

            return {
                "sessions": sessions,
                "grants": grants,
                "audit_log": audit_log,
            }
        finally:
            conn.close()

    def generate_artifacts(self, output_dir: Optional[Path] = None) -> Dict[str, Path]:
        """Generate audit artifacts from collected events.

        Args:
            output_dir: Directory to write artifacts (defaults to data_dir)

        Returns:
            Dict mapping artifact name to file path
        """
        output_dir = output_dir or self.data_dir
        output_dir.mkdir(parents=True, exist_ok=True)

        artifacts = {}

        # Generate events.jsonl
        events_path = output_dir / "events.jsonl"
        with open(events_path, "w") as f:
            for event in self._events:
                f.write(json.dumps(event) + "\n")
        artifacts["events"] = events_path

        # Generate audit_summary.md
        summary_path = output_dir / "audit_summary.md"
        with open(summary_path, "w") as f:
            f.write(f"# Audit Summary\n\n")
            f.write(f"**Session ID**: {self.session_id}\n\n")
            f.write(f"**Total Events**: {len(self._events)}\n\n")
            f.write(f"## Event Breakdown\n\n")

            event_counts = {}
            for event in self._events:
                event_type = event.get("type", "unknown")
                event_counts[event_type] = event_counts.get(event_type, 0) + 1

            for event_type, count in sorted(event_counts.items()):
                f.write(f"- {event_type}: {count}\n")
        artifacts["summary"] = summary_path

        # Generate metrics.json
        metrics_path = output_dir / "metrics.json"
        state = self.get_state_snapshot()
        metrics = {
            "session_id": self.session_id,
            "total_events": len(self._events),
            "event_types": {k: v for k, v in sorted(event_counts.items())},
            "grants_count": len(state["grants"]),
            "audit_log_count": len(state["audit_log"]),
        }
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)
        artifacts["metrics"] = metrics_path

        return artifacts

    def verify_audit_completeness(self) -> Dict[str, Any]:
        """Verify that audit trail contains expected event types.

        Returns:
            Dict with verification results
        """
        event_types = {event.get("type") for event in self._events}

        # Expected event types for a minimal governance chain
        expected = {
            "hook.session_start",
            "hook.user_prompt_submit",
            "hook.pre_tool_use",
            "hook.post_tool_use",
        }

        missing = expected - event_types
        extra = event_types - expected - {
            "mcp.enable_skill",
            "mcp.disable_skill",
            "mcp.change_stage",
        }

        return {
            "complete": len(missing) == 0,
            "event_types_found": sorted(event_types),
            "missing_types": sorted(missing),
            "extra_types": sorted(extra),
        }

    def verify_state_consistency(self) -> Dict[str, Any]:
        """Verify that SQLite state is consistent with session.

        Returns:
            Dict with verification results
        """
        state = self.get_state_snapshot()

        # Check that session exists in database
        session_exists = len(state["sessions"]) > 0

        # Check that audit_log has entries
        has_audit_entries = len(state["audit_log"]) > 0

        return {
            "consistent": session_exists and has_audit_entries,
            "session_exists": session_exists,
            "has_audit_entries": has_audit_entries,
            "grants_count": len(state["grants"]),
            "audit_log_count": len(state["audit_log"]),
        }

    def __repr__(self) -> str:
        return (
            f"ClaudeCodeSimulator(session_id={self.session_id!r}, "
            f"data_dir={self.data_dir})"
        )

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start_mcp()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensures MCP subprocess cleanup."""
        await self.stop_mcp()
        return False
