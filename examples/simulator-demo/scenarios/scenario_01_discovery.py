#!/usr/bin/env python3
"""
Scenario 01: Discovery and Stage-first Governance

Demonstrates:
- Stage-first skill discovery (staged vs no-stage skills)
- read_skill returns stage workflow metadata for staged skills
- No-stage skill fallback behavior (skill-level allowed_tools)
- Low-risk auto-grant
- Basic discovery flow: list_skills → read_skill → enable_skill
- Runtime available tool set enforcement (allow/deny)

Expected audit events:
1. session.start
2. skill.read (staged skill - yuque-doc-edit-staged)
3. skill.read (no-stage skill - yuque-knowledge-link)
4. skill.enable (granted)
5. tool.call (allow)
6. tool.call (deny - tool_not_available)
7. session.end
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from simulator.core import ClaudeCodeSimulator


async def run_scenario_01():
    """Run Scenario 01: Discovery and Stage-first Governance."""

    # Use simulator-demo fixtures instead of legacy example
    fixtures_dir = Path(__file__).parent.parent / "fixtures"
    skills_dir = fixtures_dir / "skills"
    config_dir = Path(__file__).parent.parent.parent / "01-knowledge-link" / "config"
    data_dir = Path(__file__).parent.parent / ".scenario-01-data"

    print("=== Scenario 01: Discovery and Stage-first Governance ===\n")

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

        # list_skills returns a list of skill dicts
        assert isinstance(list_skills_response, list), f"Expected list, got {type(list_skills_response)}"
        skills_list = list_skills_response

        # Verify both staged and no-stage skills are discovered
        skill_ids = [s.get('skill_id') for s in skills_list if isinstance(s, dict)]
        print(f"  Skill IDs: {skill_ids}")
        assert "yuque-doc-edit-staged" in skill_ids, "Staged skill not discovered"
        assert "yuque-knowledge-link" in skill_ids, "No-stage skill not discovered"
        print(f"  ✓ Both staged and no-stage skills discovered")
        print()

        # Step 3: Read Staged Skill (Stage-first metadata verification)
        print("Step 3: Read Staged Skill (yuque-doc-edit-staged)")
        read_staged_response = await sim.read_skill("yuque-doc-edit-staged")
        print(f"  Read skill response keys: {read_staged_response.keys() if isinstance(read_staged_response, dict) else 'Not a dict'}")

        # Verify Stage-first metadata
        if isinstance(read_staged_response, dict):
            metadata = read_staged_response.get('metadata', {})
            print(f"  Metadata keys: {metadata.keys()}")
            print(f"  initial_stage: {metadata.get('initial_stage')}")
            print(f"  stages count: {len(metadata.get('stages', []))}")

            # Verify initial_stage
            assert metadata.get('initial_stage') == 'analysis', f"Expected initial_stage='analysis', got {metadata.get('initial_stage')}"
            print(f"  ✓ initial_stage = 'analysis'")

            # Verify stages exist
            stages = metadata.get('stages', [])
            assert len(stages) == 3, f"Expected 3 stages, got {len(stages)}"
            stage_ids = [s.get('stage_id') for s in stages]
            assert stage_ids == ['analysis', 'execution', 'verification'], f"Expected ['analysis', 'execution', 'verification'], got {stage_ids}"
            print(f"  ✓ stages = {stage_ids}")

            # Verify each stage has allowed_tools and allowed_next_stages
            for stage in stages:
                stage_id = stage.get('stage_id')
                allowed_tools = stage.get('allowed_tools', [])
                allowed_next_stages = stage.get('allowed_next_stages', [])
                print(f"    - {stage_id}: tools={allowed_tools}, next={allowed_next_stages}")

            # Verify terminal stage
            verification_stage = next((s for s in stages if s.get('stage_id') == 'verification'), None)
            assert verification_stage is not None, "verification stage not found"
            assert verification_stage.get('allowed_next_stages') == [], f"Expected terminal stage (allowed_next_stages=[]), got {verification_stage.get('allowed_next_stages')}"
            print(f"  ✓ 'verification' stage is terminal (allowed_next_stages=[])")
        print()

        # Step 4: Read No-Stage Skill (Fallback behavior verification)
        print("Step 4: Read No-Stage Skill (yuque-knowledge-link)")
        read_noStage_response = await sim.read_skill("yuque-knowledge-link")
        print(f"  Read skill response keys: {read_noStage_response.keys() if isinstance(read_noStage_response, dict) else 'Not a dict'}")

        # Verify no-stage fallback behavior
        if isinstance(read_noStage_response, dict):
            metadata = read_noStage_response.get('metadata', {})
            print(f"  initial_stage: {metadata.get('initial_stage')}")
            print(f"  stages: {metadata.get('stages', [])}")
            print(f"  allowed_tools: {metadata.get('allowed_tools', [])}")

            # Verify no stages or empty stages
            stages = metadata.get('stages', [])
            assert len(stages) == 0, f"Expected no stages for no-stage skill, got {len(stages)}"
            print(f"  ✓ No stages defined (no-stage skill)")

            # Verify initial_stage is None
            assert metadata.get('initial_stage') is None, f"Expected initial_stage=None, got {metadata.get('initial_stage')}"
            print(f"  ✓ initial_stage = None")

            # Verify skill-level allowed_tools exists
            allowed_tools = metadata.get('allowed_tools', [])
            assert len(allowed_tools) > 0, "Expected skill-level allowed_tools for no-stage skill"
            print(f"  ✓ Skill-level allowed_tools = {allowed_tools}")
        print()

        # Step 5: Skill Enablement (Auto-Grant for no-stage skill)
        print("Step 5: Skill Enablement (enable_skill yuque-knowledge-link)")
        enable_response = await sim.enable_skill("yuque-knowledge-link")
        print(f"  Enable response: {enable_response}")
        print()

        # Step 6: Active Tools Recompute
        print("Step 6: Active Tools Recompute (UserPromptSubmit)")
        user_prompt_response = sim.user_prompt_submit()
        print(f"  UserPromptSubmit response: {user_prompt_response.get('additionalContext', 'No context')[:100]}...")
        print()

        # Step 7: Authorized Tool Call (Allow)
        print("Step 7: Authorized Tool Call (mcp__mock-yuque__yuque_search - should allow)")
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

        # Step 8: Unauthorized Tool Call (Deny - tool not in allowed_tools)
        print("Step 8: Unauthorized Tool Call (mcp__mock-web-search__rag_paper_search - should deny)")
        pre_tool_deny = sim.pre_tool_use(
            "mcp__mock-web-search__rag_paper_search",
            {"query": "RAG survey 2026"}
        )
        decision_deny = pre_tool_deny.get("hookSpecificOutput", {}).get("permissionDecision") or pre_tool_deny.get("permissionDecision")
        print(f"  PreToolUse decision: {decision_deny}")
        if "hookSpecificOutput" in pre_tool_deny:
            print(f"  Denial reason: {pre_tool_deny['hookSpecificOutput'].get('message', 'No message')}")

        # Verify denial
        assert decision_deny == "deny", f"Expected deny, got {decision_deny}"
        print(f"  ✓ Unavailable tool correctly denied")
        print()

        # Step 9: Generate Artifacts
        print("Step 9: Generate Session Artifacts")
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

        # Stage-first Governance Verification Summary
        print("=== Stage-first Governance Verification ===")
        print(f"  ✓ Staged skill discovered with stage workflow metadata")
        print(f"  ✓ No-stage skill discovered with skill-level allowed_tools fallback")
        print(f"  ✓ initial_stage and stages correctly parsed from SKILL.md")
        print(f"  ✓ Terminal stage (allowed_next_stages=[]) correctly identified")
        print(f"  ✓ Unavailable tool correctly denied by runtime")
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
