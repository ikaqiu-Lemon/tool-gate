#!/usr/bin/env python3
"""
Scenario 02: Staged Workflow

Demonstrates:
- require_reason enforcement
- Deny without reason / grant with reason
- Analysis → execution two-stage flow
- Stage-aware tool filtering
- blocked_tools global red line

Expected audit events:
1. session.start
2. skill.enable (denied - reason_missing)
3. skill.enable (granted - with reason)
4. tool.call (allow - analysis stage)
5. tool.call (deny - analysis stage, write tool)
6. stage.change (analysis → execution)
7. tool.call (allow - execution stage, write tool)
8. tool.call (deny - blocked_tools)
9. session.end
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


async def run_scenario_02():
    """Run Scenario 02: Staged Workflow."""

    # Use example 02's configuration
    example_02_dir = Path(__file__).parent.parent.parent / "02-doc-edit-staged"
    skills_dir = example_02_dir / "skills"
    config_dir = example_02_dir / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-02-data"

    print("=== Scenario 02: Staged Workflow ===\n")

    # Clean up previous run
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    async with ClaudeCodeSimulator(
        session_id="scenario-02",
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

        # Step 1.5: Refresh skills to ensure MCP server has indexed them
        print("Step 1.5: Refresh Skills")
        refresh_response = await sim.refresh_skills()
        print(f"  Refresh response: {refresh_response}")
        print()

        # Step 2: Skill Enablement Without Reason (Deny)
        print("Step 2: Skill Enablement Without Reason (should deny)")
        enable_no_reason = await sim.enable_skill("yuque-doc-edit")
        print(f"  Enable response (no reason): {enable_no_reason}")
        print()

        # Step 3: Skill Enablement With Reason (Grant)
        print("Step 3: Skill Enablement With Reason (should grant)")
        enable_with_reason = await sim.enable_skill(
            "yuque-doc-edit",
            reason="Update related docs section"
        )
        print(f"  Enable response (with reason): {enable_with_reason}")
        print()

        # Step 4: Active Tools Recompute (Analysis Stage)
        print("Step 4: Active Tools Recompute (analysis stage)")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 5: Read Tool Call (Allow in Analysis Stage)
        print("Step 5: Read Tool Call (yuque_get_doc - should allow in analysis)")
        pre_tool_read = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_get_doc",
            {"doc_id": "rag-overview-v2"}
        )
        decision_read = pre_tool_read.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_read.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_read}")

        if decision_read == "allow":
            post_tool_read = sim.post_tool_use(
                "mcp__mock-yuque__yuque_get_doc",
                {"doc_id": "rag-overview-v2"},
                {"content": "..."}
            )
            print(f"  PostToolUse response: {post_tool_read}")
        print()

        # Step 6: Write Tool Call (Deny in Analysis Stage)
        print("Step 6: Write Tool Call (yuque_update_doc - should deny in analysis)")
        pre_tool_write_deny = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_update_doc",
            {"doc_id": "rag-overview-v2", "body_markdown": "..."}
        )
        decision_write_deny = pre_tool_write_deny.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_write_deny.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_write_deny}")
        if "hookSpecificOutput" in pre_tool_write_deny:
            print(f"  Denial reason: {pre_tool_write_deny['hookSpecificOutput'].get('message', 'No message')[:100]}...")
        print()

        # Step 7: Stage Transition
        print("Step 7: Stage Transition (analysis → execution)")
        change_stage_response = await sim.change_stage("yuque-doc-edit", "execution")
        print(f"  change_stage response: {change_stage_response}")
        print()

        # Step 8: Active Tools Recompute (Execution Stage)
        print("Step 8: Active Tools Recompute (execution stage)")
        user_prompt_response_2 = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response_2.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 9: Write Tool Call (Allow in Execution Stage)
        print("Step 9: Write Tool Call (yuque_update_doc - should allow in execution)")
        pre_tool_write_allow = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_update_doc",
            {"doc_id": "rag-overview-v2", "body_markdown": "..."}
        )
        decision_write_allow = pre_tool_write_allow.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_write_allow.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_write_allow}")

        if decision_write_allow == "allow":
            post_tool_write = sim.post_tool_use(
                "mcp__mock-yuque__yuque_update_doc",
                {"doc_id": "rag-overview-v2", "body_markdown": "..."},
                {"success": True}
            )
            print(f"  PostToolUse response: {post_tool_write}")
        print()

        # Step 10: Blocked Tool Call (Deny via Global Red Line)
        print("Step 10: Blocked Tool Call (Bash - should deny via blocked_tools)")
        pre_tool_blocked = sim.pre_tool_use(
            "Bash",
            {"command": "df -h"}
        )
        decision_blocked = pre_tool_blocked.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_blocked.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_blocked}")
        if "hookSpecificOutput" in pre_tool_blocked:
            print(f"  Denial reason: {pre_tool_blocked['hookSpecificOutput'].get('message', 'No message')[:100]}...")
        print()

        # Step 11: Generate Artifacts
        print("Step 11: Generate Session Artifacts")
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

        # Check expected audit events in SQLite
        print("Expected Audit Events in SQLite:")
        expected_events = [
            "session.start",
            "skill.enable",
            "stage.change",
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

    print("=== Scenario 02 Complete ===")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(run_scenario_02())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Scenario 02 failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
