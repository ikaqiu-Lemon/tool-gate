"""mock_sensitive_stdio — FastMCP stdio fixture pairing with mock_sensitive.

Stage G addition. Advertises a single high-risk tool ``dangerous`` so
Stage G's namespaced-MCP deny test (``mcp__mock_sensitive__dangerous``)
has a real server whose declared tool name matches what the
subprocess PreToolUse gate receives.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock_sensitive")


@mcp.tool()
async def dangerous(target: str) -> dict[str, str]:
    """High-risk placeholder operation."""
    return {"danger": target}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
