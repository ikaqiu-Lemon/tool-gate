"""mock_echo_stdio — minimal FastMCP stdio server fixture.

Stage A skeleton. Exposes one tool ``echo(text)`` returning
``{"echo": text}``. Used by functional tests to verify the baseline MCP
stdio handshake (``tools/list``) and one ``tools/call`` round-trip. Not a
governance dependency — purely a stand-in for a third-party MCP server.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("mock_echo")


@mcp.tool()
async def echo(text: str) -> dict[str, str]:
    """Return the input text under the ``echo`` key."""
    return {"echo": text}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
