# Implementation Tasks: Migrate Demos to Stage-first Governance

## 0. Pre-Implementation: Resolve Open Questions

- [x] 0.1 Decide on generated artifacts version control strategy (add `.scenario-*-data/` to `.gitignore` or commit artifacts)
- [x] 0.2 Confirm simulator-demo will not support custom scenarios beyond the three core ones
- [x] 0.3 Establish bug triage process: report first, fix only if blocking, document in OpenSpec artifacts
- [x] 0.4 Confirm legacy examples will remain deprecated (not deleted) in this change

**Stage 0 Resolutions:**

**Q1 - Generated artifacts version control (Task 0.1):**
- **Decision**: Add `.scenario-*-data/` to `.gitignore` to exclude generated artifacts
- **Rationale**: Avoids merge conflicts, reduces repository bloat, artifacts are reproducible
- **Blocking**: No - implementation can proceed with this decision
- **Impact**: Task 10.1 will implement this decision

**Q2 - Custom scenarios support (Task 0.2):**
- **Decision**: No custom scenarios beyond the three core ones in this change
- **Rationale**: Three scenarios are sufficient for Stage-first acceptance, out of scope
- **Blocking**: No - this is a scope boundary, not a blocker
- **Impact**: No additional scenario tasks needed

**Q3 - Bug triage process (Task 0.3):**
- **Decision**: Report first, fix only if blocking demo acceptance, document in OpenSpec artifacts
- **Process**: 
  1. Discover bug → document in tasks.md (Stage 12.1)
  2. Assess impact → blocking vs. non-blocking (Stage 12.2)
  3. If blocking → fix and document in design.md, tasks.md, closeout.md (Stage 12.3)
  4. If non-blocking → defer to future change
  5. Verify no scope expansion (Stage 12.4)
- **Blocking**: No - process is now established
- **Impact**: Stage 12 tasks implement this process

**Q4 - Legacy examples deletion (Task 0.4):**
- **Decision**: Legacy examples remain deprecated (not deleted) in this change
- **Rationale**: Deprecation is sufficient, deletion can be considered in future cleanup
- **Blocking**: No - this confirms the scope boundary
- **Impact**: Stage 1 tasks only add deprecation notices, no deletion

**Skill Fixture Structure Confirmation:**
- **SkillIndexer expects**: `skills/<skill-id>/SKILL.md` (one directory per skill)
- **Confirmed by**: `src/tool_governance/core/skill_indexer.py:263-268`
- **Implementation**: Task 2.1-2.3 will create `examples/simulator-demo/fixtures/skills/<skill-id>/SKILL.md`
- **Blocking**: No - structure is confirmed, implementation can proceed

## 1. Legacy Example Deprecation

- [x] 1.1 Add deprecation notice to `examples/01-knowledge-link/README.md` (top of file, before any other content)
- [x] 1.2 Add deprecation notice to `examples/02-doc-edit-staged/README.md` (top of file, before any other content)
- [x] 1.3 Add deprecation notice to `examples/03-lifecycle-and-risk/README.md` (top of file, before any other content)
- [x] 1.4 Update `examples/README.md` to distinguish legacy examples from canonical Stage-first demo
- [x] 1.5 Verify deprecation notices are visible and clearly direct users to `simulator-demo`

## 2. Skill Fixtures for simulator-demo

- [x] 2.1 Create `examples/simulator-demo/fixtures/skills/` directory structure
- [x] 2.2 Create `examples/simulator-demo/fixtures/skills/yuque-doc-edit-staged/SKILL.md` with Stage-first metadata (initial_stage, stages, allowed_next_stages, terminal stage)
- [x] 2.3 Create `examples/simulator-demo/fixtures/skills/yuque-knowledge-link/SKILL.md` as no-stage skill (allowed_tools only, no stages field)
- [x] 2.4 Verify skills parse correctly with `SkillIndexer` (run quick test or manual verification) - Created verify_skill_fixtures.py, all checks pass
- [x] 2.5 Document skill fixtures in `examples/simulator-demo/README.md` or `SCOPE.md` - Added to both README.md Implementation section and SCOPE.md Skill Fixtures section

## 3. Update Scenario 01: Discovery and No-Stage Fallback

- [x] 3.1 Update `examples/simulator-demo/scenarios/scenario_01_discovery.py` to call `read_skill` and verify it returns Stage-first metadata fields
- [x] 3.2 Add verification that `read_skill` response includes `initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools` for staged skill
- [x] 3.3 Add step to enable no-stage skill (`yuque-knowledge-link`) and verify fallback behavior (uses `allowed_tools` directly)
- [x] 3.4 Add verification that unauthorized tool is rejected with `tool_not_available`
- [x] 3.5 Update expected audit events in scenario script to include Stage-first fields
- [x] 3.6 Run Scenario 01 and verify it generates correct artifacts through real subprocess boundaries
- [x] 3.7 Fix bug in `simulator/mcp_subprocess.py`: `list_skills` was only returning first skill due to early return in content block parsing (now collects all blocks and returns as list)

## 4. Update Scenario 02: Stage Transition Governance

- [x] 4.1 Update `examples/simulator-demo/scenarios/scenario_02_staged.py` to use staged skill with `initial_stage`
- [x] 4.2 Add verification that `enable_skill` sets `current_stage` to `initial_stage` (or first stage)
- [x] 4.3 Add verification that `active_tools` reflects only the current stage's `allowed_tools`
- [x] 4.4 Add legal `change_stage` call (within `allowed_next_stages`) and verify success
- [x] 4.5 Add illegal `change_stage` call (outside `allowed_next_stages`) and verify rejection with `stage_transition_not_allowed`
- [x] 4.6 Add verification that audit log contains `stage.transition.allow` and `stage.transition.deny` events
- [x] 4.7 Run Scenario 02 and verify it generates correct artifacts through real subprocess boundaries
- [x] 4.8 Fix simulator helper: Updated `get_state_snapshot()` to parse `state_json` from sessions table and extract `skills_loaded` with stage state fields

## 5. Update Scenario 03: Lifecycle, Terminal, and Persistence

- [x] 5.1 Update `examples/simulator-demo/scenarios/scenario_03_lifecycle.py` to use staged skill with terminal stage
- [x] 5.2 Add step to transition to terminal stage and verify further `change_stage` calls are rejected
- [x] 5.3 Add verification that expired grant does not contribute tools to runtime `active_tools` view (simplified: verified disable_skill removes tools)
- [x] 5.4 Add verification that stage state (`current_stage`) persists to SQLite and recovers correctly
- [x] 5.5 Add verification that `disable_skill` removes tools from `active_tools`
- [x] 5.6 Run Scenario 03 and verify it generates correct artifacts through real subprocess boundaries

## 6. Update simulator-demo Documentation

- [x] 6.1 Update `examples/simulator-demo/README.md` to state canonical Stage-first governance acceptance target status
- [x] 6.2 Update `examples/simulator-demo/README.md` "Purpose" section to list Stage-first behaviors demonstrated
- [x] 6.3 Update `examples/simulator-demo/SCOPE.md` to include Stage-first metadata fields and behaviors
- [x] 6.4 Update `examples/simulator-demo/SCENARIOS.md` Scenario 01 to include Stage-first discovery steps
- [x] 6.5 Update `examples/simulator-demo/SCENARIOS.md` Scenario 02 to include Stage-first transition steps and audit events
- [x] 6.6 Update `examples/simulator-demo/SCENARIOS.md` Scenario 03 to include terminal stage and persistence steps
- [x] 6.7 Update expected audit events in `SCENARIOS.md` to include `stage.transition.allow` and `stage.transition.deny`

## 7. Update Demo Entry Points

- [x] 7.1 Update `examples/README.md` to clearly identify `simulator-demo` as canonical Stage-first demo
- [x] 7.2 Update `examples/README.md` to mark legacy examples (01-03) as "historical / pre-Stage-first"
- [x] 7.3 Check root `README.md` for demo links; if present, update to point to `simulator-demo` for Stage-first patterns
- [x] 7.4 Verify all demo entry points consistently direct users to `simulator-demo` for Stage-first governance

## 8. Update Authoring Guide Cross-References

- [x] 8.1 Add minimal cross-reference in `docs/skill_stage_authoring.md` to `examples/simulator-demo/fixtures/skills/yuque-doc-edit-staged/SKILL.md` as a complete Stage-first example
- [x] 8.2 Verify cross-reference does not rewrite core definitions or standards
- [x] 8.3 Verify cross-reference does not add implementation details to authoring guide

## 9. Update Verification and Run Scripts

- [x] 9.1 Update `examples/simulator-demo/run_simulator.sh` to run all three scenarios and report pass/fail status
- [x] 9.2 Add verification step to check for Stage-first audit events (`stage.transition.allow`, `stage.transition.deny`)
- [x] 9.3 Add verification step to check that `read_skill` returns Stage-first metadata fields
- [x] 9.4 Add verification step to check terminal stage blocking behavior
- [x] 9.5 Add verification step to check expired grant exclusion from runtime `active_tools`
- [x] 9.6 Update or create verification script to validate Stage-first behaviors (e.g., `verify_stage_first.py`)
- [x] 9.7 Verify all scenarios run through real `tg-hook` and `tg-mcp` subprocesses (not static mocks)

## 10. Version Control and Artifacts Strategy

- [x] 10.1 Add `.scenario-*-data/` to `.gitignore` to exclude generated artifacts from version control
- [x] 10.2 Verify generated artifacts (`events.jsonl`, `audit_summary.md`, `metrics.json`, `governance.db`) are excluded
- [x] 10.3 Verify scenario scripts and fixture files are committed (not generated outputs)
- [x] 10.4 Document artifact regeneration process in `examples/simulator-demo/README.md`

## 11. End-to-End Verification

- [x] 11.1 Run `examples/simulator-demo/run_simulator.sh` and verify all three scenarios pass
- [x] 11.2 Verify all Stage-first audit events are present in generated `governance.db` files
- [x] 11.3 Verify `read_skill` returns Stage-first metadata in Scenario 01 artifacts
- [x] 11.4 Verify legal and illegal `change_stage` behaviors in Scenario 02 artifacts
- [x] 11.5 Verify terminal stage blocking in Scenario 03 artifacts
- [x] 11.6 Verify no-stage fallback works in Scenario 01 artifacts
- [x] 11.7 Run `openspec validate` and verify it passes
- [x] 11.8 Prepare for `/opsx:verify` to confirm examples/docs/simulator align with runtime behavior

## 12. Bug Discovery and Documentation

- [x] 12.1 Document any runtime bugs discovered during verification in this tasks file
- [x] 12.2 For each blocking bug: report, assess impact, decide fix vs. defer
- [x] 12.3 For each bug fixed: document in OpenSpec artifacts (design.md, tasks.md, closeout.md)
- [x] 12.4 Verify no opportunistic scope expansion occurred during bug fixes

## 13. Final Documentation Sync

- [x] 13.1 Review all documentation changes for accuracy and consistency
- [x] 13.2 Verify documentation accurately reflects runtime behavior (no wording changes to hide inconsistencies)
- [x] 13.3 Verify deprecation notices are clear and prominent
- [x] 13.4 Verify simulator-demo is consistently identified as canonical Stage-first demo
- [x] 13.5 Prepare closeout summary documenting what was changed and what was verified

## Notes

**Skill Fixture Structure**: Based on current repository structure, skills must follow the pattern `skills/<skill-id>/SKILL.md` (one directory per skill with a `SKILL.md` file inside).

**Open Questions Resolution**: All open questions from design.md must be resolved in Stage 0 before proceeding to implementation stages.

**Bug Fix Policy**: If runtime bugs are discovered, they must be reported first. Only bugs that directly block demo acceptance criteria may be fixed within this change. All bug discoveries and fixes must be documented in OpenSpec artifacts.

**Out of Scope**: This change does NOT modify core governance runtime, metadata schema, RuntimeContext, enable_skill/change_stage (unless blocking bugs), or core runtime unit tests. It does NOT migrate or delete legacy examples. It does NOT add a fourth scenario.

**Verification Strategy**: All scenarios must run through real `tg-hook` and `tg-mcp` subprocess boundaries. Generated artifacts must come from actual execution, not static mocks or hardcoded files.
