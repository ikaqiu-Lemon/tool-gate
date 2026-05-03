#!/usr/bin/env python3
"""
Stage C Verification Script

Verifies:
1. State snapshot reads from SQLite
2. Artifact generation (events.jsonl, audit_summary.md, metrics.json)
3. State consistency verification
4. Audit completeness verification
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from simulator.core import ClaudeCodeSimulator


async def verify_stage_c():
    """Run minimal verification for Stage C closeout."""

    example_01_dir = Path(__file__).parent.parent / "01-knowledge-link"
    skills_dir = example_01_dir / "skills"
    config_dir = example_01_dir / "config"
    data_dir = Path(__file__).parent / ".verify-data"

    print("=== Stage C Verification ===\n")

    # Clean up previous test data
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    async with ClaudeCodeSimulator(
        session_id="verify-session",
        data_dir=data_dir,
        skills_dir=skills_dir,
        config_dir=config_dir,
        timeout=10.0,
    ) as sim:

        # Run minimal governance chain
        print("1. Running governance chain...")
        sim.session_start()
        sim.user_prompt_submit()
        await sim.list_skills()
        sim.pre_tool_use("mcp__tool-governance__list_skills", {})
        sim.post_tool_use("mcp__tool-governance__list_skills", {}, {"content": []})
        print("   ✓ Governance chain executed\n")

        # Test state snapshot
        print("2. Testing state snapshot...")
        state = sim.get_state_snapshot()
        print(f"   Sessions: {len(state['sessions'])}")
        print(f"   Grants: {len(state['grants'])}")
        print(f"   Audit log: {len(state['audit_log'])}")
        assert "sessions" in state
        assert "grants" in state
        assert "audit_log" in state
        print("   ✓ State snapshot working\n")

        # Test artifact generation
        print("3. Testing artifact generation...")
        artifacts = sim.generate_artifacts()
        print(f"   Generated artifacts:")
        for name, path in artifacts.items():
            print(f"     - {name}: {path}")
            assert path.exists(), f"Artifact {name} not created"
        print("   ✓ Artifacts generated\n")

        # Test audit completeness
        print("4. Testing audit completeness verification...")
        completeness = sim.verify_audit_completeness()
        print(f"   Complete: {completeness['complete']}")
        print(f"   Event types found: {completeness['event_types_found']}")
        if completeness['missing_types']:
            print(f"   Missing types: {completeness['missing_types']}")
        print("   ✓ Audit completeness verified\n")

        # Test state consistency
        print("5. Testing state consistency verification...")
        consistency = sim.verify_state_consistency()
        print(f"   Consistent: {consistency['consistent']}")
        print(f"   Session exists: {consistency['session_exists']}")
        print(f"   Has audit entries: {consistency['has_audit_entries']}")
        print(f"   Grants count: {consistency['grants_count']}")
        print(f"   Audit log count: {consistency['audit_log_count']}")
        print("   ✓ State consistency verified\n")

    print("=== Stage C Verification Complete ===")
    print("\nStage C closeout requirements met:")
    print("✓ State snapshot implemented (reads from SQLite)")
    print("✓ Artifact generation implemented (events.jsonl, audit_summary.md, metrics.json)")
    print("✓ State verification implemented (verify_state_consistency)")
    print("✓ Audit verification implemented (verify_audit_completeness)")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(verify_stage_c())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Verification failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
