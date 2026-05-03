"""
Claude Code Simulator - Subprocess orchestration for governance chain demonstration.

This package provides the core simulator infrastructure for demonstrating
the Claude Code governance chain with real subprocess boundaries.

Stage B: Skeleton only - subprocess orchestration without full governance logic.

Modules:
    core: ClaudeCodeSimulator orchestration class
    hook_subprocess: HookSubprocess wrapper for tg-hook invocations
    mcp_subprocess: MCPSubprocess wrapper for tg-mcp server
"""

from .core import ClaudeCodeSimulator
from .hook_subprocess import HookSubprocess
from .mcp_subprocess import MCPSubprocess

__all__ = [
    "ClaudeCodeSimulator",
    "HookSubprocess",
    "MCPSubprocess",
]
