#!/usr/bin/env python3
"""
Scenario 03: Lifecycle and Risk

Demonstrates:
- TTL expiration
- Automatic cleanup / re-authorization
- disable_skill with strict ordering
- approval_required / high-risk denial

Expected audit events:
1. session.start
2. grant.expire (TTL expiration)
3. tool.call (deny - expired grant)
4. skill.enable (re-authorization)
5. grant.revoke
6. skill.disable (strict ordering: after revoke)
7. skill.enable (denied - approval_required)
8. session.end
"""

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


def setup_expired_grant(db_path: Path, session_id: str):
    """Pre-create an expired grant for testing TTL expiration.

    Note: Must be called after session_start() to ensure database and session exist.
    """
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Create expired grant (session already exists from session_start)
    expired_time = (datetime.utcnow() - timedelta(hours=2)).isoformat()
    cursor.execute("""
        INSERT INTO grants (
            grant_id, session_id, skill_id, allowed_ops, scope, ttl_seconds,
            status, granted_by, reason, created_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        "expired-grant-001",
        session_id,
        "yuque-knowledge-link",
        json.dumps(["yuque_search", "yuque_list_docs", "yuque_get_doc"]),
        "session",
        3600,
        "active",
        "auto",
        None,
        expired_time,
        expired_time,
    ))

    conn.commit()
    conn.close()


async def run_scenario_03():
    """Run Scenario 03: Lifecycle and Risk."""

    # Use example 01's configuration (has low-risk and high-risk skills)
    example_01_dir = Path(__file__).parent.parent.parent / "01-knowledge-link"
    skills_dir = example_01_dir / "skills"
    config_dir = example_01_dir / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-03-data"

    print("=== Scenario 03: Lifecycle and Risk ===\n")

    # Clean up previous run
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    # Create simulator instance
    sim = ClaudeCodeSimulator(
        session_id="scenario-03",
        data_dir=data_dir,
        skills_dir=skills_dir,
        config_dir=config_dir,
        timeout=10.0,
    )

    # Now start the actual scenario
    async with sim:

        # Step 1: Session Initialization (initializes database)
        print("Step 1: Session Initialization")
        session_start_response = sim.session_start()
        print(f"  SessionStart response: {session_start_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Setup: Pre-create expired grant (after database is initialized)
        print("Setup: Creating expired grant")
        setup_expired_grant(sim.db_path, sim.session_id)
        print(f"  Created expired grant for yuque-knowledge-link")
        print()

        # Step 1.5: Refresh skills to ensure MCP server has indexed them
        print("Step 1.5: Refresh Skills")
        refresh_response = await sim.refresh_skills()
        print(f"  Refresh response: {refresh_response}")
        print()

        # Step 2: Active Tools Recompute (Expired Grant Cleanup)
        print("Step 2: Active Tools Recompute (expired grant cleanup)")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 3: Expired Tool Call (Deny)
        print("Step 3: Expired Tool Call (yuque_search - should deny, grant expired)")
        pre_tool_expired = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_search",
            {"query": "RAG"}
        )
        decision_expired = pre_tool_expired.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_expired.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_expired}")
        if "hookSpecificOutput" in pre_tool_expired:
            print(f"  Denial reason: {pre_tool_expired['hookSpecificOutput'].get('message', 'No message')[:100]}...")
        print()

        # Step 4: Re-Authorization
        print("Step 4: Re-Authorization (enable_skill)")
        enable_response = await sim.enable_skill("yuque-knowledge-link")
        print(f"  Enable response: {enable_response}")
        print()

        # Step 5: Active Tools Recompute (Re-Authorized)
        print("Step 5: Active Tools Recompute (re-authorized)")
        user_prompt_response_2 = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response_2.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 6: Grant Revocation (Strict Ordering)
        print("Step 6: Grant Revocation (disable_skill)")
        disable_response = await sim.disable_skill("yuque-knowledge-link")
        print(f"  Disable response: {disable_response}")
        print()

        # Step 7: High-Risk Skill Enablement (Deny)
        print("Step 7: High-Risk Skill Enablement (yuque-comment-sync - should deny)")
        # Note: yuque-comment-sync is configured as approval_required in example 01
        enable_high_risk = await sim.enable_skill(
            "yuque-comment-sync",
            reason="Need to sync comments for analysis"
        )
        print(f"  Enable response (high-risk): {enable_high_risk}")
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

        # Check for strict ordering: grant.revoke before skill.disable
        print("Strict Ordering Check (grant.revoke before skill.disable):")
        revoke_events = [e for e in state['audit_log'] if e.get('event_type') == 'grant.revoke']
        disable_events = [e for e in state['audit_log'] if e.get('event_type') == 'skill.disable']

        if revoke_events and disable_events:
            revoke_time = revoke_events[0].get('timestamp')
            disable_time = disable_events[0].get('timestamp')
            if revoke_time and disable_time:
                ordering_correct = revoke_time < disable_time
                print(f"  Revoke timestamp: {revoke_time}")
                print(f"  Disable timestamp: {disable_time}")
                print(f"  Ordering correct: {ordering_correct}")
        else:
            print(f"  ⚠ Missing revoke or disable events")
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
            "grant.expire",
            "skill.enable",
            "skill.disable",
            "grant.revoke",
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

    print("=== Scenario 03 Complete ===")
    return True


if __name__ == "__main__":
    try:
        result = asyncio.run(run_scenario_03())
        sys.exit(0 if result else 1)
    except Exception as e:
        print(f"\n❌ Scenario 03 failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
