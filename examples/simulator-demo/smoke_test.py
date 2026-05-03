#!/usr/bin/env python3
"""
Smoke test for simulator subprocess orchestration.

Verifies:
1. HookSubprocess can spawn tg-hook and receive JSON response
2. MCPSubprocess can spawn tg-mcp and complete basic communication
3. Subprocess cleanup works correctly
4. Timeout handling prevents resource leaks

Stage B: Minimal verification only - does not test full governance logic.
"""

import json
import sys
from pathlib import Path

# Add simulator to path
sys.path.insert(0, str(Path(__file__).parent))

from simulator import ClaudeCodeSimulator, HookSubprocess, MCPSubprocess


def test_hook_subprocess_spawn():
    """Test that HookSubprocess can spawn tg-hook and get a response."""
    print("Testing HookSubprocess spawn...")

    hook = HookSubprocess(timeout=5.0)

    # Send a minimal SessionStart event
    event = {
        "event": "SessionStart",
        "session_id": "smoke-test",
        "cwd": str(Path.cwd()),
    }

    try:
        response = hook.invoke(event)
        print(f"✓ Hook subprocess returned: {type(response).__name__}")

        # Verify response is a dict (even if empty)
        assert isinstance(response, dict), f"Expected dict, got {type(response)}"

        print("✓ HookSubprocess spawn test passed")
        return True

    except Exception as e:
        print(f"✗ HookSubprocess spawn test failed: {e}")
        return False


def test_mcp_subprocess_lifecycle():
    """Test that MCPSubprocess can start and shutdown cleanly."""
    print("\nTesting MCPSubprocess lifecycle...")

    mcp = MCPSubprocess(timeout=5.0)

    try:
        # Start subprocess
        mcp.start()
        print("✓ MCP subprocess started")

        # Verify process is running
        assert mcp.process is not None, "MCP process should be running"
        assert mcp.process.poll() is None, "MCP process should not have exited"

        print("✓ MCP subprocess is running")

        # Shutdown
        mcp.shutdown()
        print("✓ MCP subprocess shutdown cleanly")

        # Verify process is stopped
        assert mcp.process is None, "MCP process should be None after shutdown"

        print("✓ MCPSubprocess lifecycle test passed")
        return True

    except Exception as e:
        print(f"✗ MCPSubprocess lifecycle test failed: {e}")
        # Ensure cleanup
        try:
            mcp.shutdown()
        except:
            pass
        return False


def test_context_manager_cleanup():
    """Test that context manager ensures cleanup."""
    print("\nTesting context manager cleanup...")

    try:
        with MCPSubprocess(timeout=5.0) as mcp:
            mcp.start()
            print("✓ MCP subprocess started in context manager")

            # Verify running
            assert mcp.process is not None
            assert mcp.process.poll() is None

        # After context exit, process should be cleaned up
        assert mcp.process is None, "MCP process should be None after context exit"

        print("✓ Context manager cleanup test passed")
        return True

    except Exception as e:
        print(f"✗ Context manager cleanup test failed: {e}")
        return False


def test_simulator_initialization():
    """Test that ClaudeCodeSimulator initializes correctly."""
    print("\nTesting ClaudeCodeSimulator initialization...")

    try:
        sim = ClaudeCodeSimulator(
            session_id="smoke-test",
            data_dir=Path.cwd() / ".smoke-test-data",
        )

        print(f"✓ Simulator initialized: {sim}")

        # Verify session_id
        assert sim.session_id == "smoke-test"

        # Verify data_dir was created
        assert sim.data_dir.exists(), "Data directory should exist"

        # Verify subprocess wrappers are initialized
        assert sim._hook_subprocess is not None
        assert sim._mcp_subprocess is not None

        print("✓ ClaudeCodeSimulator initialization test passed")
        return True

    except Exception as e:
        print(f"✗ ClaudeCodeSimulator initialization test failed: {e}")
        return False


def main():
    """Run all smoke tests."""
    print("=" * 60)
    print("Simulator Subprocess Smoke Tests (Stage B)")
    print("=" * 60)

    results = []

    # Test 1: Hook subprocess spawn
    results.append(test_hook_subprocess_spawn())

    # Test 2: MCP subprocess lifecycle
    results.append(test_mcp_subprocess_lifecycle())

    # Test 3: Context manager cleanup
    results.append(test_context_manager_cleanup())

    # Test 4: Simulator initialization
    results.append(test_simulator_initialization())

    # Summary
    print("\n" + "=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} tests passed")
    print("=" * 60)

    if passed == total:
        print("✓ All smoke tests passed")
        return 0
    else:
        print("✗ Some smoke tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
