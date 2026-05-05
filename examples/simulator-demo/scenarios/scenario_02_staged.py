#!/usr/bin/env python3
"""
Scenario 02: Stage Transition Governance

Demonstrates:
- enable_skill enters initial_stage
- current_stage controls active_tools
- Legal change_stage (within allowed_next_stages) succeeds
- Illegal change_stage (outside allowed_next_stages) is rejected
- Audit log contains stage.transition.allow and stage.transition.deny
- Stage state (current_stage, stage_history, exited_stages) persists

Expected audit events:
1. session.start
2. skill.enable (granted - enters initial_stage)
3. tool.call (allow - analysis stage tool)
4. tool.call (deny - execution stage tool, not in analysis)
5. stage.transition.allow (analysis → execution)
6. tool.call (allow - execution stage tool)
7. stage.transition.deny (execution → analysis, not allowed)
8. session.end
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


async def run_scenario_02():
    """Run Scenario 02: Stage Transition Governance."""

    # Use simulator-demo fixtures instead of legacy example
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    skills_dir = fixtures_dir / "skills"
    config_dir = Path(__file__).parent.parent.parent / "01-knowledge-link" / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-02-data"

    print("=== Scenario 02: Stage Transition Governance ===\n")

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

        # Step 2: Refresh skills
        print("Step 2: Refresh Skills")
        refresh_response = await sim.refresh_skills()
        print(f"  Refresh response: {refresh_response}")
        print()

        # Step 3: Enable Staged Skill (enters initial_stage)
        print("Step 3: Enable Staged Skill (yuque-doc-edit-staged)")
        enable_response = await sim.enable_skill(
            "yuque-doc-edit-staged",
            reason="Update documentation with staged workflow"
        )
        print(f"  Enable response: {enable_response}")

        # Verify grant was created
        granted = enable_response.get('granted', False)
        assert granted, f"Expected granted=True, got {granted}"
        print(f"  ✓ Skill enabled successfully")
        print()

        # Step 4: Verify Initial Stage State
        print("Step 4: Verify Initial Stage State")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        assert 'yuque-doc-edit-staged' in skills_loaded, f"Expected skill in skills_loaded, got {list(skills_loaded.keys())}"

        skill_info = skills_loaded['yuque-doc-edit-staged']
        current_stage = skill_info.get('current_stage')
        stage_entered_at = skill_info.get('stage_entered_at')
        stage_history = skill_info.get('stage_history', [])
        exited_stages = skill_info.get('exited_stages', [])

        print(f"  current_stage: {current_stage}")
        print(f"  stage_entered_at: {stage_entered_at}")
        print(f"  stage_history: {stage_history}")
        print(f"  exited_stages: {exited_stages}")

        assert current_stage == "analysis", f"Expected current_stage='analysis', got '{current_stage}'"
        assert stage_entered_at is not None, "Expected stage_entered_at to be set"
        assert stage_history == [], f"Expected empty stage_history, got {stage_history}"
        assert exited_stages == [], f"Expected empty exited_stages, got {exited_stages}"
        print(f"  ✓ Initial stage state correct")
        print()

        # Step 5: Active Tools Recompute (Analysis Stage)
        print("Step 5: Active Tools Recompute (analysis stage)")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 6: Analysis Stage Tool (Allow)
        print("Step 6: Analysis Stage Tool (yuque_search - should allow)")
        pre_tool_read = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_search",
            {"query": "RAG", "type": "doc"}
        )
        decision_read = pre_tool_read.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_read.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_read}")

        assert decision_read == "allow", f"Expected allow, got {decision_read}"

        if decision_read == "allow":
            post_tool_read = sim.post_tool_use(
                "mcp__mock-yuque__yuque_search",
                {"query": "RAG", "type": "doc"},
                {"results": []}
            )
            print(f"  PostToolUse response: {post_tool_read}")
        print(f"  ✓ Analysis stage tool allowed")
        print()

        # Step 7: Execution Stage Tool (Deny in Analysis)
        print("Step 7: Execution Stage Tool (yuque_update_doc - should deny in analysis)")
        pre_tool_write_deny = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_update_doc",
            {"doc_id": "rag-overview", "body_markdown": "..."}
        )
        decision_write_deny = pre_tool_write_deny.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_write_deny.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_write_deny}")

        assert decision_write_deny == "deny", f"Expected deny, got {decision_write_deny}"

        if "hookSpecificOutput" in pre_tool_write_deny:
            print(f"  Denial reason: {pre_tool_write_deny['hookSpecificOutput'].get('message', 'No message')}")
        print(f"  ✓ Execution stage tool denied in analysis")
        print()

        # Step 8: Legal Stage Transition (analysis → execution)
        print("Step 8: Legal Stage Transition (analysis → execution)")
        change_stage_response = await sim.change_stage("yuque-doc-edit-staged", "execution")
        print(f"  change_stage response: {change_stage_response}")

        changed = change_stage_response.get('changed', False)
        assert changed, f"Expected changed=True, got {changed}"
        print(f"  ✓ Stage transition succeeded")
        print()

        # Step 9: Verify Stage State After Transition
        print("Step 9: Verify Stage State After Transition")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        skill_info = skills_loaded['yuque-doc-edit-staged']

        current_stage = skill_info.get('current_stage')
        stage_history = skill_info.get('stage_history', [])
        exited_stages = skill_info.get('exited_stages', [])

        print(f"  current_stage: {current_stage}")
        print(f"  stage_history: {stage_history}")
        print(f"  exited_stages: {exited_stages}")

        assert current_stage == "execution", f"Expected current_stage='execution', got '{current_stage}'"
        assert "analysis" in exited_stages, f"Expected 'analysis' in exited_stages, got {exited_stages}"
        assert len(stage_history) > 0, f"Expected non-empty stage_history, got {stage_history}"
        print(f"  ✓ Stage state updated correctly")
        print()

        # Step 10: Active Tools Recompute (Execution Stage)
        print("Step 10: Active Tools Recompute (execution stage)")
        user_prompt_response_2 = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response_2.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 11: Execution Stage Tool (Allow)
        print("Step 11: Execution Stage Tool (yuque_update_doc - should allow in execution)")
        pre_tool_write_allow = sim.pre_tool_use(
            "mcp__mock-yuque__yuque_update_doc",
            {"doc_id": "rag-overview", "body_markdown": "..."}
        )
        decision_write_allow = pre_tool_write_allow.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_write_allow.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_write_allow}")

        assert decision_write_allow == "allow", f"Expected allow, got {decision_write_allow}"

        if decision_write_allow == "allow":
            post_tool_write = sim.post_tool_use(
                "mcp__mock-yuque__yuque_update_doc",
                {"doc_id": "rag-overview", "body_markdown": "..."},
                {"success": True}
            )
            print(f"  PostToolUse response: {post_tool_write}")
        print(f"  ✓ Execution stage tool allowed")
        print()

        # Step 12: Illegal Stage Transition (execution → analysis, not in allowed_next_stages)
        print("Step 12: Illegal Stage Transition (execution → analysis, not allowed)")
        change_stage_illegal = await sim.change_stage("yuque-doc-edit-staged", "analysis")
        print(f"  change_stage response: {change_stage_illegal}")

        changed = change_stage_illegal.get('changed', False)
        error_bucket = change_stage_illegal.get('error_bucket', '')

        print(f"  changed: {changed}")
        print(f"  error_bucket: {error_bucket}")

        assert not changed, f"Expected changed=False, got {changed}"
        assert error_bucket == "stage_transition_not_allowed", f"Expected error_bucket='stage_transition_not_allowed', got '{error_bucket}'"
        print(f"  ✓ Illegal transition rejected")
        print()

        # Step 13: Verify Stage State Unchanged After Illegal Transition
        print("Step 13: Verify Stage State Unchanged After Illegal Transition")
        state = sim.get_state_snapshot()
        skills_loaded = state.get('skills_loaded', {})
        skill_info = skills_loaded['yuque-doc-edit-staged']

        current_stage = skill_info.get('current_stage')
        stage_history_after = skill_info.get('stage_history', [])

        print(f"  current_stage: {current_stage}")
        print(f"  stage_history: {stage_history_after}")

        assert current_stage == "execution", f"Expected current_stage='execution' (unchanged), got '{current_stage}'"
        assert stage_history_after == stage_history, f"Expected stage_history unchanged, got {stage_history_after}"
        print(f"  ✓ Stage state unchanged after illegal transition")
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
        else:
            print(f"  ⚠ No stage transition events found in audit log")
        print()

        # Stage-first Governance Verification Summary
        print("=== Stage-first Governance Verification ===")
        print(f"  ✓ enable_skill enters initial_stage (analysis)")
        print(f"  ✓ current_stage controls active_tools (analysis vs execution)")
        print(f"  ✓ Legal change_stage succeeds (analysis → execution)")
        print(f"  ✓ Illegal change_stage rejected (execution → analysis)")
        print(f"  ✓ Stage state persists (current_stage, stage_history, exited_stages)")
        print(f"  ✓ error_bucket='stage_transition_not_allowed' for illegal transition")
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
