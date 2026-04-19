"""Canonical hook event JSON builders for functional tests."""

from __future__ import annotations

from typing import Any


def session_start(session_id: str) -> dict[str, Any]:
    return {"event": "SessionStart", "session_id": session_id}


def user_prompt_submit(session_id: str) -> dict[str, Any]:
    return {"event": "UserPromptSubmit", "session_id": session_id}


def pre_tool_use(session_id: str, tool_name: str) -> dict[str, Any]:
    return {"event": "PreToolUse", "session_id": session_id, "tool_name": tool_name}


def post_tool_use(session_id: str, tool_name: str) -> dict[str, Any]:
    return {"event": "PostToolUse", "session_id": session_id, "tool_name": tool_name}
