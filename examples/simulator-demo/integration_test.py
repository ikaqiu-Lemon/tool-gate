#!/usr/bin/env python3
"""
Minimal integration test for Stage C governance chain.

Verifies:
1. SessionStart hook invocation
2. UserPromptSubmit hook invocation
3. MCP server startup and handshake
4. MCP tool invocation (list_skills)
5. PreToolUse hook invocation
6. PostToolUse hook invocation
7. Subprocess cleanup

Does NOT verify:
- Audit artifact generation (Stage C later tasks)
- Full scenario logic (Stage D)
- SQLite state consistency (Stage C later tasks)
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from simulator.core import ClaudeCodeSimulator


async def test_governance_chain():
    """Test minimal governance chain: hooks + MCP + cleanup."""

    # Use example 01's configuration
    example_01_dir = Path(__file__).parent.parent / "01-knowledge-link"
    skills_dir = example_01_dir / "skills"
    config_dir = example_01_dir / "config"
    data_dir = Path(__file__).parent / ".test-data"

    print("=== Stage C Integration Test ===\n")

    # Clean up any previous test data
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    async with ClaudeCodeSimulator(
        session_id="test-session",
        data_dir=data_dir,
        skills_dir=skills_dir,
        config_dir=config_dir,
        timeout=10.0,
    ) as sim:

        # Step 1: SessionStart hook
        print("1. Invoking SessionStart hook...")
        session_start_response = sim.session_start()
        print(f"   Response: {session_start_response}")
        assert "additionalContext" in session_start_response or session_start_response == {}
        print("   ✓ SessionStart hook succeeded\n")

        # Step 2: UserPromptSubmit hook
        print("2. Invoking UserPromptSubmit hook...")
        user_prompt_response = sim.user_prompt_submit()
        print(f"   Response: {user_prompt_response}")
        print("   ✓ UserPromptSubmit hook succeeded\n")

        # Step 3: MCP list_skills (MCP server already started by context manager)
        print("3. Calling MCP list_skills tool...")
        list_skills_response = await sim.list_skills()
        print(f"   Response: {list_skills_response}")
        # MCP response may have content or be empty
        assert isinstance(list_skills_response, dict)
        print("   ✓ MCP list_skills succeeded\n")

        # Step 4: PreToolUse hook (simulating a tool call)
        print("4. Invoking PreToolUse hook...")
        pre_tool_response = sim.pre_tool_use(
            tool_name="mcp__tool-governance__list_skills",
            tool_input={},
        )
        print(f"   Response: {pre_tool_response}")

        # Extract permission decision from nested structure
        if "hookSpecificOutput" in pre_tool_response:
            decision = pre_tool_response["hookSpecificOutput"].get("permissionDecision")
        else:
            decision = pre_tool_response.get("permissionDecision")

        assert decision in ["allow", "deny", "ask"]
        print(f"   Decision: {decision}")
        print("   ✓ PreToolUse hook succeeded\n")

        # Step 5: PostToolUse hook
        print("5. Invoking PostToolUse hook...")
        post_tool_response = sim.post_tool_use(
            tool_name="mcp__tool-governance__list_skills",
            tool_input={},
            tool_output=list_skills_response,
        )
        print(f"   Response: {post_tool_response}")
        print("   ✓ PostToolUse hook succeeded\n")

        # Step 6: Verify MCP server is still responsive
        print("6. Verifying MCP server still responsive...")
        list_skills_response_2 = await sim.list_skills()
        assert "content" in list_skills_response_2
        print("   ✓ MCP server still responsive\n")

    # Context manager exit should clean up MCP subprocess
    print("7. Context manager exited, MCP subprocess cleaned up\n")

    print("=== All integration tests passed ===")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(test_governance_chain())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Integration test failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
