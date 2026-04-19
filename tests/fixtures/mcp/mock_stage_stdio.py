"""mock_stage_stdio — FastMCP stdio fixture matching mock_stageful tools.

Stage A skeleton. Exposes tool names that line up with
``mock_stageful``'s stage ``allowed_tools`` so PreToolUse name-matching
(``mcp__mock_stage__<tool>``) can be exercised over real stdio without
depending on any third-party MCP server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock_stage")


@mcp.tool()
async def mock_read(path: str) -> dict[str, str]:
    """Analysis-stage read placeholder."""
    return {"read": path}


@mcp.tool()
async def mock_glob(pattern: str) -> dict[str, list[str]]:
    """Analysis-stage glob placeholder."""
    return {"matches": []}


@mcp.tool()
async def mock_edit(path: str, content: str) -> dict[str, str]:
    """Execution-stage edit placeholder."""
    return {"edited": path}


@mcp.tool()
async def mock_write(path: str, content: str) -> dict[str, str]:
    """Execution-stage write placeholder."""
    return {"written": path}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
