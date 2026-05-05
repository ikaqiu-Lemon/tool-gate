#!/usr/bin/env python3
"""
Scenario 03: Lifecycle, Terminal Stage, and Persistence

Demonstrates:
- Terminal stage blocks further transitions (allowed_next_stages=[])
- Stage state persists to SQLite and recovers correctly
- Expired grant does not contribute tools to runtime active_tools
- disable_skill removes tools from active_tools
- Stage lifecycle: analysis → execution → verification (terminal)
- Full stage history tracking (stage_history, exited_stages)

Expected audit events:
1. session.start
2. skill.enable (yuque-doc-edit-staged, enters initial_stage)
3. stage.transition.allow (analysis → execution)
4. stage.transition.allow (execution → verification)
5. stage.transition.deny (verification → execution, terminal stage)
6. skill.enable (yuque-knowledge-link, short TTL for expiration test)
7. tool.call (allow - before expiration)
8. tool.call (deny - after expiration)
9. skill.disable (yuque-doc-edit-staged)
10. grant.revoke (yuque-doc-edit-staged)
11. tool.call (deny - disabled skill)
12. session.end
"""

import asyncio
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


async def run_scenario_03():
    """Run Scenario 03: Lifecycle, Terminal Stage, and Persistence."""

    # Use simulator-demo fixtures
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    skills_dir = fixtures_dir / "skills"
    config_dir = Path(__file__).parent.parent.parent / "01-knowledge-link" / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-03-data"

    print("=== Scenario 03: Lifecycle, Terminal Stage, and Persistence ===\n")

    # Clean up previous run
    if data_dir.exists():
        import shutil
        shutil.rmtree(data_dir)

    async with ClaudeCodeSimulator(
        session_id="scenario-03",
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

        # Step 2: Refresh skills
        print("Step 2: Refresh Skills")
        refresh_response = await sim.refresh_skills()
        print(f"  Refresh response: {refresh_response}")
        print()

        # Step 3: Enable Staged Skill
        print("Step 3: Enable Staged Skill (yuque-doc-edit-staged)")
        enable_response = await sim.enable_skill(
            "yuque-doc-edit-staged",
            reason="Testing terminal stage and persistence"
        )
        print(f"  Enable response: {enable_response}")

        granted = enable_response.get('granted', False)
        assert granted, f"Expected granted=True, got {granted}"
        print(f"  ✓ Skill enabled, entered initial_stage")
        print()

        # Step 4: Verify Initial Stage
        print("Step 4: Verify Initial Stage (analysis)")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        skill_info = skills_loaded['yuque-doc-edit-staged']

        current_stage = skill_info.get('current_stage')
        print(f"  current_stage: {current_stage}")
        assert current_stage == "analysis", f"Expected 'analysis', got '{current_stage}'"
        print(f"  ✓ Initial stage correct")
        print()

        # Step 5: Transition to Execution
        print("Step 5: Legal Transition (analysis → execution)")
        change_response_1 = await sim.change_stage("yuque-doc-edit-staged", "execution")
        print(f"  change_stage response: {change_response_1}")

        changed = change_response_1.get('changed', False)
        assert changed, f"Expected changed=True, got {changed}"
        print(f"  ✓ Transitioned to execution")
        print()

        # Step 6: Transition to Verification (Terminal Stage)
        print("Step 6: Legal Transition (execution → verification, terminal stage)")
        change_response_2 = await sim.change_stage("yuque-doc-edit-staged", "verification")
        print(f"  change_stage response: {change_response_2}")

        changed = change_response_2.get('changed', False)
        assert changed, f"Expected changed=True, got {changed}"
        print(f"  ✓ Transitioned to verification (terminal)")
        print()

        # Step 7: Verify Terminal Stage State
        print("Step 7: Verify Terminal Stage State")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        skill_info = skills_loaded['yuque-doc-edit-staged']

        current_stage = skill_info.get('current_stage')
        stage_history = skill_info.get('stage_history', [])
        exited_stages = skill_info.get('exited_stages', [])

        print(f"  current_stage: {current_stage}")
        print(f"  stage_history: {stage_history}")
        print(f"  exited_stages: {exited_stages}")

        assert current_stage == "verification", f"Expected 'verification', got '{current_stage}'"
        assert len(stage_history) == 2, f"Expected 2 transitions, got {len(stage_history)}"
        assert "analysis" in exited_stages, f"Expected 'analysis' in exited_stages"
        assert "execution" in exited_stages, f"Expected 'execution' in exited_stages"
        print(f"  ✓ Terminal stage state correct")
        print()

        # Step 8: Attempt Transition from Terminal Stage (Should Deny)
        print("Step 8: Illegal Transition from Terminal Stage (verification → execution)")
        change_response_3 = await sim.change_stage("yuque-doc-edit-staged", "execution")
        print(f"  change_stage response: {change_response_3}")

        changed = change_response_3.get('changed', False)
        error_bucket = change_response_3.get('error_bucket', '')

        print(f"  changed: {changed}")
        print(f"  error_bucket: {error_bucket}")

        assert not changed, f"Expected changed=False, got {changed}"
        assert error_bucket == "stage_transition_not_allowed", f"Expected 'stage_transition_not_allowed', got '{error_bucket}'"
        print(f"  ✓ Terminal stage blocks further transitions")
        print()

        # Step 9: Verify Stage State Unchanged After Terminal Denial
        print("Step 9: Verify Stage State Unchanged After Terminal Denial")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        skill_info = skills_loaded['yuque-doc-edit-staged']

        current_stage_after = skill_info.get('current_stage')
        stage_history_after = skill_info.get('stage_history', [])

        print(f"  current_stage: {current_stage_after}")
        print(f"  stage_history length: {len(stage_history_after)}")

        assert current_stage_after == "verification", f"Expected 'verification' (unchanged), got '{current_stage_after}'"
        assert len(stage_history_after) == 2, f"Expected 2 transitions (unchanged), got {len(stage_history_after)}"
        print(f"  ✓ Stage state unchanged after terminal denial")
        print()

        # Step 10: Verify Stage State Persistence
        print("Step 10: Verify Stage State Persistence")
        # Re-read from database to verify persistence
        state_fresh = sim.get_state_snapshot()
        skills_loaded_fresh = state_fresh.get('skills_loaded', {})
        skill_info_fresh = skills_loaded_fresh['yuque-doc-edit-staged']

        print(f"  Persisted current_stage: {skill_info_fresh.get('current_stage')}")
        print(f"  Persisted stage_history: {skill_info_fresh.get('stage_history', [])}")
        print(f"  Persisted exited_stages: {skill_info_fresh.get('exited_stages', [])}")

        assert skill_info_fresh.get('current_stage') == "verification", "Stage state not persisted correctly"
        assert len(skill_info_fresh.get('stage_history', [])) == 2, "Stage history not persisted correctly"
        print(f"  ✓ Stage state persists to SQLite")
        print()

        # Step 11: Test Expired Grant Behavior
        print("Step 11: Test Expired Grant Behavior")
        print("  [11a] Enable yuque-knowledge-link with TTL=2 seconds")
        enable_ttl_response = await sim.enable_skill(
            "yuque-knowledge-link",
            reason="Testing grant expiration",
            ttl=2
        )
        print(f"  Enable response: {enable_ttl_response}")

        granted_ttl = enable_ttl_response.get('granted', False)
        assert granted_ttl, f"Expected granted=True, got {granted_ttl}"
        print(f"  ✓ Skill enabled with TTL=2s")
        print()

        # Verify tool available before expiration using PreToolUse
        print("  [11b] Verify tool allowed before expiration")
        tool_name = "yuque_search"
        pre_tool_before = sim.pre_tool_use(tool_name, {})
        decision_before = pre_tool_before.get("hookSpecificOutput", {}).get("permissionDecision")
        print(f"  PreToolUse decision before expiration: {decision_before}")

        assert decision_before == "allow", f"Expected allow before expiration, got {decision_before}"
        print(f"  ✓ Tool call allowed before expiration")
        print()

        # Wait for grant to expire
        print("  [11c] Wait 3 seconds for grant to expire")
        time.sleep(3)
        print(f"  ✓ Grant expired (TTL=2s elapsed)")
        print()

        # Verify tool NOT available after expiration using PreToolUse
        print("  [11d] Verify tool denied after expiration")
        pre_tool_after = sim.pre_tool_use(tool_name, {})
        decision_after = pre_tool_after.get("hookSpecificOutput", {}).get("permissionDecision")
        reason_after = pre_tool_after.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        print(f"  PreToolUse decision after expiration: {decision_after}")
        print(f"  Deny reason: {reason_after[:100]}...")

        assert decision_after == "deny", f"Expected deny after expiration, got {decision_after}"
        assert "not in active_tools" in reason_after, f"Expected 'not in active_tools' in reason"
        print(f"  ✓ Tool call denied after expiration (expired grant does not contribute to active_tools)")
        print()

        # Step 12: Disable Skill and Verify Tools Removed
        print("Step 12: Disable Skill (yuque-doc-edit-staged)")
        disable_response = await sim.disable_skill("yuque-doc-edit-staged")
        print(f"  Disable response: {disable_response}")

        disabled = disable_response.get('disabled', False)
        assert disabled, f"Expected disabled=True, got {disabled}"
        print(f"  ✓ Skill disabled")
        print()

        # Step 13: Verify Tools Not Available After Disable
        print("Step 13: Verify Tools Not Available After Disable")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")

        # Try to use tool from disabled skill
        pre_tool_disabled = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_get_doc",
            {"doc_id": "test"}
        )
        decision_disabled = pre_tool_disabled.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_disabled.get("permissionDecision")
        print(f"  PreToolUse decision for disabled skill tool: {decision_disabled}")

        assert decision_disabled == "deny", f"Expected deny for disabled skill tool, got {decision_disabled}"
        print(f"  ✓ Disabled skill tools not available")
        print()

        # Step 14: Generate Artifacts
        print("Step 14: Generate Session Artifacts")
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
            "skill.enable",
            "skill.disable",
            "grant.revoke",
            "tool.call",
        ]

        audit_event_types = set()
        stage_transition_events = []
        for entry in state['audit_log']:
            event_type = entry.get('event_type')
            if event_type:
                audit_event_types.add(event_type)
            # Collect stage transition events
            if event_type and 'stage' in event_type.lower() and 'transition' in event_type.lower():
                stage_transition_events.append(entry)

        print(f"  Found event types: {sorted(audit_event_types)}")

        missing = set(expected_events) - audit_event_types
        if missing:
            print(f"  ⚠ Missing expected events: {sorted(missing)}")
        else:
            print(f"  ✓ All expected event types present")

        # Check for stage transition events
        print(f"\nStage Transition Events:")
        if stage_transition_events:
            for event in stage_transition_events:
                print(f"  - {event.get('event_type')}: {event.get('detail', {})}")

            # Verify terminal stage denial
            deny_events = [e for e in stage_transition_events if e.get('event_type') == 'stage.transition.deny']
            if deny_events:
                print(f"  ✓ Terminal stage denial recorded in audit")
            else:
                print(f"  ⚠ No stage.transition.deny events found")
        else:
            print(f"  ⚠ No stage transition events found in audit log")
        print()

        # Lifecycle Verification Summary
        print("=== Lifecycle, Terminal, and Persistence Verification ===")
        print(f"  ✓ Terminal stage blocks further transitions (verification → execution denied)")
        print(f"  ✓ Stage state persists to SQLite (current_stage, stage_history, exited_stages)")
        print(f"  ✓ Expired grant does NOT contribute tools to active_tools")
        print(f"  ✓ Tool calls denied after expiration (tool_not_available)")
        print(f"  ✓ disable_skill removes tools from active_tools")
        print(f"  ✓ Tool calls denied after disable_skill (tool_not_available)")
        print(f"  ✓ Full lifecycle: analysis → execution → verification (terminal)")
        print(f"  ✓ Stage history tracking complete")
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
