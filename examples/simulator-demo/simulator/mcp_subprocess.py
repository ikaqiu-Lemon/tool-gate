"""MCP server subprocess wrapper.

Manages the lifecycle of a tg-mcp server process, including:
- Startup and handshake via mcp SDK
- JSON-RPC request/response over stdin/stdout
- Graceful shutdown
"""

import asyncio
import subprocess
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPSubprocess:
    """Wrapper for tg-mcp server subprocess.

    Uses the mcp SDK to perform real JSON-RPC handshake and tool invocation.
    """

    def __init__(self, timeout: float = 10.0):
        """Initialize MCP subprocess wrapper.

        Args:
            timeout: Default timeout for operations in seconds
        """
        self.timeout = timeout
        self.session: ClientSession | None = None
        self._available_tools: list[str] = []
        self._stdio_context = None
        self._session_context = None

    async def start(self) -> None:
        """Start the MCP server process and complete handshake.

        Raises:
            RuntimeError: If server already started, process fails to start,
                         handshake fails, or no tools are available
            subprocess.TimeoutExpired: If handshake exceeds timeout
        """
        if self.session is not None:
            raise RuntimeError("MCP server already started")

        # Collect environment variables to pass to subprocess
        import os
        # Start with parent environment to preserve PATH, HOME, etc.
        env = os.environ.copy()
        # Override with governance-specific variables
        env["GOVERNANCE_DATA_DIR"] = os.environ.get("GOVERNANCE_DATA_DIR", "")
        env["CLAUDE_SESSION_ID"] = os.environ.get("CLAUDE_SESSION_ID", "")
        if "GOVERNANCE_SKILLS_DIR" in os.environ:
            env["GOVERNANCE_SKILLS_DIR"] = os.environ["GOVERNANCE_SKILLS_DIR"]
        if "GOVERNANCE_CONFIG_DIR" in os.environ:
            env["GOVERNANCE_CONFIG_DIR"] = os.environ["GOVERNANCE_CONFIG_DIR"]

        # Start tg-mcp server via entry point
        server_params = StdioServerParameters(
            command="tg-mcp",
            args=[],
            env=env,
        )

        try:
            # Establish stdio connection - keep context alive
            self._stdio_context = stdio_client(server_params)
            read_stream, write_stream = await self._stdio_context.__aenter__()

            # Create session - keep context alive
            self._session_context = ClientSession(read_stream, write_stream)
            session = await self._session_context.__aenter__()

            # Initialize protocol
            await asyncio.wait_for(
                session.initialize(),
                timeout=self.timeout,
            )

            # List tools to verify server is functional
            tools_result = await asyncio.wait_for(
                session.list_tools(),
                timeout=self.timeout,
            )

            self._available_tools = [tool.name for tool in tools_result.tools]

            if not self._available_tools:
                raise RuntimeError("MCP server handshake succeeded but no tools available")

            # Store session for later tool calls
            self.session = session

        except asyncio.TimeoutError as e:
            await self._cleanup_on_error()
            raise subprocess.TimeoutExpired(
                cmd="tg-mcp",
                timeout=self.timeout,
            ) from e
        except Exception as e:
            await self._cleanup_on_error()
            raise RuntimeError(f"MCP handshake failed: {e}") from e

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Call an MCP tool.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            Tool result as dict

        Raises:
            RuntimeError: If server not started or tool call fails
            asyncio.TimeoutError: If tool call exceeds timeout
        """
        if self.session is None:
            raise RuntimeError("MCP server not started or handshake incomplete")

        if tool_name not in self._available_tools:
            raise RuntimeError(
                f"Tool '{tool_name}' not available. Available: {self._available_tools}"
            )

        try:
            result = await asyncio.wait_for(
                self.session.call_tool(tool_name, arguments),
                timeout=self.timeout,
            )

            # Extract content from MCP response
            import json

            if result.content:
                # MCP returns list of content blocks
                # For list_skills, each block is a separate skill dict
                # For other tools, typically one block with the full result
                text_blocks = []
                for block in result.content:
                    if hasattr(block, 'text'):
                        text_blocks.append(block.text)

                # If only one block, parse and return it directly
                if len(text_blocks) == 1:
                    return json.loads(text_blocks[0])

                # If multiple blocks, parse each and return as list
                if len(text_blocks) > 1:
                    return [json.loads(text) for text in text_blocks]

            # If no text content, return the raw result structure
            return {
                "isError": getattr(result, 'isError', False),
                "content": [
                    {"type": getattr(block, 'type', 'unknown'), "text": getattr(block, 'text', str(block))}
                    for block in (result.content or [])
                ]
            }

        except asyncio.TimeoutError:
            raise
        except Exception as e:
            raise RuntimeError(f"MCP tool call failed: {e}") from e

    async def stop(self) -> None:
        """Stop the MCP server process gracefully."""
        # Exit session context
        if self._session_context is not None:
            try:
                await self._session_context.__aexit__(None, None, None)
            except Exception:
                pass  # Best-effort cleanup
            finally:
                self._session_context = None
                self.session = None

        # Exit stdio context
        if self._stdio_context is not None:
            try:
                await self._stdio_context.__aexit__(None, None, None)
            except Exception:
                pass  # Best-effort cleanup
            finally:
                self._stdio_context = None

    async def _cleanup_on_error(self) -> None:
        """Clean up resources after an error during startup."""
        await self.stop()

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
        return False

    @property
    def available_tools(self) -> list[str]:
        """Return list of available tool names after handshake."""
        return self._available_tools.copy()
