#!/usr/bin/env python3
"""
Scenario 01: Discovery

Demonstrates:
- Low-risk auto-grant
- Basic discovery flow: list_skills → read_skill → enable_skill
- Whitelist enforcement (allow/deny)
- Mixed MCP environment

Expected audit events:
1. session.start
2. skill.read
3. skill.enable (granted)
4. tool.call (allow)
5. tool.call (deny - whitelist violation)
6. session.end
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


async def run_scenario_01():
    """Run Scenario 01: Discovery."""

    example_01_dir = Path(__file__).parent.parent.parent / "01-knowledge-link"
    skills_dir = example_01_dir / "skills"
    config_dir = example_01_dir / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-01-data"

    print("=== Scenario 01: Discovery ===\n")

    # Clean up previous run
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    async with ClaudeCodeSimulator(
        session_id="scenario-01",
        data_dir=data_dir,
        skills_dir=skills_dir,
        config_dir=config_dir,
        timeout=10.0,
    ) as sim:

        # Step 1: Session Initialization
        print("Step 1: Session Initialization")
        session_start_response = sim.session_start()
        print(f"  SessionStart response: {session_start_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 2: Skill Discovery (refresh and list)
        print("Step 2: Skill Discovery (refresh_skills + list_skills)")
        refresh_response = await sim.refresh_skills()
        print(f"  Refresh response: {refresh_response}")
        list_skills_response = await sim.list_skills()
        print(f"  Found skills: {list_skills_response}")
        print()

        # Step 3: Skill Understanding
        print("Step 3: Skill Understanding (read_skill)")
        read_skill_response = await sim.read_skill("yuque-knowledge-link")
        print(f"  Read skill response: {read_skill_response}")
        print()

        # Step 4: Skill Enablement (Auto-Grant)
        print("Step 4: Skill Enablement (enable_skill)")
        enable_response = await sim.enable_skill("yuque-knowledge-link")
        print(f"  Enable response: {enable_response}")
        print()

        # Step 5: Active Tools Recompute
        print("Step 5: Active Tools Recompute (UserPromptSubmit)")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 6: Authorized Tool Call (Allow)
        print("Step 6: Authorized Tool Call (mcp__mock-yuque__yuque_search - should allow)")
        pre_tool_allow = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_search",
            {"query": "RAG", "type": "doc"}
        )
        decision_allow = pre_tool_allow.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_allow.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_allow}")

        if decision_allow == "allow":
            post_tool_allow = sim.post_tool_use(
                "mcp__mock-yuque__yuque_search",
                {"query": "RAG", "type": "doc"},
                {"results": []}
            )
            print(f"  PostToolUse response: {post_tool_allow}")
        print()

        # Step 7: Unauthorized Tool Call (Deny)
        print("Step 7: Unauthorized Tool Call (mcp__mock-web-search__rag_paper_search - should deny)")
        pre_tool_deny = sim.pre_tool_use(
            "mcp__mock-web-search__rag_paper_search",
            {"query": "RAG survey 2026"}
        )
        decision_deny = pre_tool_deny.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_deny.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_deny}")
        if "hookSpecificOutput" in pre_tool_deny:
            print(f"  Denial reason: {pre_tool_deny['hookSpecificOutput'].get('message', 'No message')}")
        print()

        # Step 8: Generate Artifacts
        print("Step 8: Generate Session Artifacts")
        artifacts = sim.generate_artifacts()
        print(f"  Generated artifacts:")
        for name, path in artifacts.items():
            print(f"    - {name}: {path}")
        print()

        # Verification
        print("=== Verification ===\n")

        # Check state snapshot
        state = sim.get_state_snapshot()
        print(f"State Snapshot:")
        print(f"  Sessions: {len(state['sessions'])}")
        print(f"  Grants: {len(state['grants'])}")
        print(f"  Audit log entries: {len(state['audit_log'])}")
        print()

        # Check audit completeness
        completeness = sim.verify_audit_completeness()
        print(f"Audit Completeness:")
        print(f"  Complete: {completeness['complete']}")
        print(f"  Event types: {completeness['event_types_found']}")
        print()

        # Check state consistency
        consistency = sim.verify_state_consistency()
        print(f"State Consistency:")
        print(f"  Consistent: {consistency['consistent']}")
        print(f"  Session exists: {consistency['session_exists']}")
        print(f"  Audit entries: {consistency['audit_log_count']}")
        print()

        # Check expected audit events in SQLite
        print("Expected Audit Events in SQLite:")
        expected_events = [
            "session.start",
            "skill.read",
            "skill.enable",
            "tool.call",
        ]

        audit_event_types = set()
        for entry in state['audit_log']:
            event_type = entry.get('event_type')
            if event_type:
                audit_event_types.add(event_type)

        print(f"  Found event types: {sorted(audit_event_types)}")

        missing = set(expected_events) - audit_event_types
        if missing:
            print(f"  ⚠ Missing expected events: {sorted(missing)}")
        else:
            print(f"  ✓ All expected event types present")
        print()

    print("=== Scenario 01 Complete ===")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(run_scenario_01())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Scenario 01 failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
