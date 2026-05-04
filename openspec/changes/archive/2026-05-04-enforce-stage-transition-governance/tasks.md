# Implementation Tasks: enforce-stage-transition-governance

## Stage A: State Model Extension

**Goal:** Extend `LoadedSkillInfo` with stage lifecycle fields and ensure serialization, restoration, and backward compatibility.

**Files to modify:**
- `src/tool_governance/models/state.py`

**Files NOT to modify:**
- `src/tool_governance/mcp_server.py`
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`

**Tasks:**

- [x] A.1 Add `StageTransitionRecord` model to `models/state.py` with fields: `from_stage: str`, `to_stage: str`, `transitioned_at: datetime`
- [x] A.2 Add `stage_entered_at: datetime | None = None` to `LoadedSkillInfo`
- [x] A.3 Add `stage_history: list[StageTransitionRecord] = Field(default_factory=list)` to `LoadedSkillInfo`
- [x] A.4 Add `exited_stages: list[str] = Field(default_factory=list)` to `LoadedSkillInfo`
- [x] A.5 Add docstring clarifying `exited_stages` means "stages that were left", not "completed stages"
- [x] A.6 Add docstring clarifying `stage_history` only records successful transitions (denied attempts go to audit only)
- [x] A.7 Write test: `test_stage_transition_record_serialization` — verify `StageTransitionRecord` can serialize/deserialize
- [x] A.8 Write test: `test_loaded_skill_info_new_fields_defaults` — verify new fields have correct default values
- [x] A.9 Write test: `test_loaded_skill_info_stage_fields_serialization` — verify new fields serialize to JSON
- [x] A.10 Write test: `test_loaded_skill_info_stage_fields_deserialization` — verify new fields restore from JSON
- [x] A.11 Write test: `test_loaded_skill_info_backward_compatibility` — verify old state JSON (missing new fields) still loads
- [x] A.12 Write test: `test_stage_history_default_not_shared` — verify empty list defaults are not shared between instances
- [x] A.13 Write test: `test_exited_stages_default_not_shared` — verify empty list defaults are not shared between instances

**Verification:**
```bash
python -m pytest tests/test_models.py::TestLoadedSkillInfo -v
```

**Completion criteria:**
- All new fields added to `LoadedSkillInfo`
- `StageTransitionRecord` model defined
- All 7 tests pass
- No changes to enable_skill or change_stage behavior

**Rollback:**
```bash
git checkout src/tool_governance/models/state.py
git checkout tests/test_models.py
```

---

## Stage B: enable_skill Stage Initialization

**Goal:** Initialize stage state when enabling staged skills, fail safely for invalid `initial_stage`, preserve no-stage skill compatibility.

**Files to modify:**
- `src/tool_governance/mcp_server.py` (enable_skill function)
- `src/tool_governance/tools/langchain_tools.py` (enable_skill_tool wrapper)

**Files NOT to modify:**
- `src/tool_governance/mcp_server.py` (change_stage function)
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`

**Tasks:**

- [x] B.1 In `mcp_server.enable_skill`, after policy evaluation succeeds, add stage initialization logic
- [x] B.2 If skill has stages and `initial_stage` is configured, validate it exists in `stages` list
- [x] B.3 If `initial_stage` is invalid, return `{"granted": False, "error": "invalid_initial_stage"}` without creating grant
- [x] B.4 If `initial_stage` is invalid, record `skill.enable` audit with `decision="deny"` and `detail={"error_bucket": "invalid_initial_stage"}`
- [x] B.5 If `initial_stage` is valid, set `current_stage` to `initial_stage`
- [x] B.6 If `initial_stage` is None/empty and skill has stages, set `current_stage` to first stage's `stage_id`
- [x] B.7 When entering a stage, initialize `stage_entered_at` to current UTC timestamp
- [x] B.8 When entering a stage, initialize `stage_history = []` and `exited_stages = []`
- [x] B.9 If skill has no stages, set `current_stage = None` and do NOT initialize stage_entered_at/stage_history/exited_stages
- [x] B.10 Mirror changes in `langchain_tools.enable_skill_tool` to maintain entry-point parity
- [x] B.11 Write test: `test_enable_skill_with_valid_initial_stage` — enters configured initial_stage
- [x] B.12 Write test: `test_enable_skill_without_initial_stage` — enters first stage
- [x] B.13 Write test: `test_enable_skill_invalid_initial_stage_fails_safely` — returns `invalid_initial_stage`, no grant created
- [x] B.14 Write test: `test_enable_skill_invalid_initial_stage_no_skills_loaded` — verify skill NOT added to skills_loaded
- [x] B.15 Write test: `test_enable_skill_invalid_initial_stage_no_tools_exposed` — verify active_tools unchanged
- [x] B.16 Write test: `test_enable_skill_invalid_initial_stage_audit` — verify audit record with error_bucket
- [x] B.17 Write test: `test_enable_skill_no_stage_skill_compatibility` — current_stage=None, uses skill.allowed_tools
- [x] B.18 Write test: `test_enable_skill_initializes_stage_entered_at` — timestamp set correctly
- [x] B.19 Write test: `test_enable_skill_initializes_empty_stage_history` — stage_history=[]
- [x] B.20 Write test: `test_enable_skill_initializes_empty_exited_stages` — exited_stages=[]
- [x] B.21 Write test: `test_enable_skill_active_tools_reflects_initial_stage` — active_tools from initial stage's allowed_tools

**Verification:**
```bash
python -m pytest tests/test_mcp_server.py::TestEnableSkillStageInit -v
python -m pytest tests/test_integration.py::TestEnableSkillStageInit -v
```

**Completion criteria:**
- enable_skill initializes stage state for staged skills
- Invalid initial_stage fails safely with correct error_bucket
- No-stage skills remain compatible
- All 11 tests pass

**Rollback:**
```bash
git checkout src/tool_governance/mcp_server.py
git checkout src/tool_governance/tools/langchain_tools.py
git checkout tests/test_mcp_server.py
git checkout tests/test_integration.py
```

---

## Stage C: change_stage Transition Enforcement

**Goal:** Validate stage transitions against `allowed_next_stages`, enforce terminal stages, update stage state on success, deny with specific error_buckets on failure.

**Files to modify:**
- `src/tool_governance/mcp_server.py` (change_stage function)

**Files NOT to modify:**
- `src/tool_governance/mcp_server.py` (enable_skill function)
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`

**Tasks:**

- [x] C.1 In `mcp_server.change_stage`, implement fail-fast validation sequence
- [x] C.2 Check skill is enabled (skill_id in skills_loaded), else return error
- [x] C.3 Check metadata exists (skill_meta is not None), else return error
- [x] C.4 Check skill has stages (skill_meta.stages is not empty), else return `{"changed": False, "error": "skill_has_no_stages"}`
- [x] C.5 Check target stage exists in stages list, else return `{"changed": False, "error": "stage_not_found"}`
- [x] C.6 Check current_stage is not None, else return `{"changed": False, "error": "stage_not_initialized"}`
- [x] C.7 Find current stage definition in skill_meta.stages
- [x] C.8 Check if current_stage.allowed_next_stages is empty list (terminal stage), deny with `stage_transition_not_allowed`
- [x] C.9 Check if target_stage in current_stage.allowed_next_stages, else deny with `stage_transition_not_allowed`
- [x] C.10 On allow: append previous stage to `exited_stages`
- [x] C.11 On allow: append `StageTransitionRecord(from_stage, to_stage, now())` to `stage_history`
- [x] C.12 On allow: update `current_stage` to target_stage
- [x] C.13 On allow: update `stage_entered_at` to current UTC timestamp
- [x] C.14 On allow: rebuild RuntimeContext to recompute active_tools
- [x] C.15 On allow: save state via state_manager
- [x] C.16 On allow: record `stage.transition.allow` audit with detail={from_stage, to_stage}
- [x] C.17 On deny: do NOT modify current_stage, exited_stages, stage_history, stage_entered_at, or active_tools
- [x] C.18 On deny: record `stage.transition.deny` audit with detail={from_stage, to_stage, error_bucket}
- [x] C.19 Write test: `test_change_stage_legal_transition_succeeds` — valid transition updates state
- [x] C.20 Write test: `test_change_stage_target_not_found` — returns stage_not_found
- [x] C.21 Write test: `test_change_stage_terminal_stage_denies` — allowed_next_stages=[] blocks transition
- [x] C.22 Write test: `test_change_stage_target_not_in_allowlist` — returns stage_transition_not_allowed
- [x] C.23 Write test: `test_change_stage_no_stage_skill_denies` — returns skill_has_no_stages
- [x] C.24 Write test: `test_change_stage_current_stage_missing` — returns stage_not_initialized
- [x] C.25 Write test: `test_change_stage_denied_no_state_mutation` — denied transition leaves all state unchanged
- [x] C.26 Write test: `test_change_stage_stage_history_only_successful` — denied transition NOT in stage_history
- [x] C.27 Write test: `test_change_stage_exited_stages_only_on_success` — exited_stages only updated on allow
- [x] C.28 Write test: `test_change_stage_allow_audit_exists` — stage.transition.allow audit record created
- [x] C.29 Write test: `test_change_stage_deny_audit_exists` — stage.transition.deny audit record created with error_bucket

**Verification:**
```bash
python -m pytest tests/test_mcp_server.py::TestChangeStageEnforcement -v
python -m pytest tests/test_integration.py::TestChangeStageEnforcement -v
```

**Completion criteria:**
- change_stage validates all transitions against allowed_next_stages
- Terminal stages block further transitions
- Denied transitions do not mutate state
- Audit records use correct event types and error_bucket field
- All 11 tests pass

**Rollback:**
```bash
git checkout src/tool_governance/mcp_server.py
git checkout tests/test_mcp_server.py
git checkout tests/test_integration.py
```

---

## Stage D: Integration Testing (active_tools, audit, persistence)

**Goal:** Verify stage state integrates correctly with RuntimeContext, active_tools computation, audit system, and persistence layer.

**Files to modify:**
- `tests/test_integration.py` (new test classes)
- `tests/test_stage_governance_integration.py` (new file)

**Files NOT to modify:**
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`
- `src/tool_governance/storage/sqlite_store.py`

**Tasks:**

- [x] D.1 Write test: `test_active_tools_reflects_analysis_stage` — analysis stage exposes read tools only
- [x] D.2 Write test: `test_active_tools_reflects_execution_stage` — execution stage exposes write tools only
- [x] D.3 Write test: `test_active_tools_updates_after_change_stage` — tools change when stage changes
- [x] D.4 Write test: `test_blocked_tools_still_filtered_from_stage_tools` — global blocked_tools applied to stage tools
- [x] D.5 Write test: `test_expired_grant_does_not_contribute_stage_tools` — expired grant filtered by build_runtime_context
- [x] D.6 Write test: `test_no_stage_skill_uses_top_level_allowed_tools` — no-stage fallback still works
- [x] D.7 Write test: `test_current_stage_persists_and_restores` — current_stage survives save/load cycle
- [x] D.8 Write test: `test_stage_entered_at_persists_and_restores` — stage_entered_at survives save/load cycle
- [x] D.9 Write test: `test_stage_history_persists_and_restores` — stage_history survives save/load cycle
- [x] D.10 Write test: `test_exited_stages_persists_and_restores` — exited_stages survives save/load cycle
- [x] D.11 Write test: `test_active_tools_after_session_restore` — active_tools recomputed from restored current_stage
- [x] D.12 Write test: `test_stage_transition_allow_audit_format` — verify stage.transition.allow event structure
- [x] D.13 Write test: `test_stage_transition_deny_audit_format` — verify stage.transition.deny event structure with error_bucket
- [x] D.14 Write test: `test_denied_transition_not_in_stage_history` — denied attempt only in audit, not stage_history
- [x] D.15 Write test: `test_invalid_initial_stage_audit_clear` — skill.enable deny audit includes error_bucket
- [x] D.16 Write test: `test_staged_skill_without_allowed_next_stages_is_terminal` — default [] makes stage terminal
- [x] D.17 Write test: `test_staged_skill_without_initial_stage_enters_first` — fallback to first stage works
- [x] D.18 Write test: `test_no_stage_skill_unchanged_by_governance` — no-stage skills unaffected
- [x] D.19 Write test: `test_old_persisted_state_missing_stage_fields_loads` — backward compatibility with old state

**Verification:**
```bash
python -m pytest tests/test_stage_governance_integration.py -v
python -m pytest tests/test_integration.py::TestStageGovernanceIntegration -v
```

**Completion criteria:**
- All 19 integration tests pass
- active_tools correctly reflects current_stage
- Stage state persists and restores correctly
- Audit events use correct format (stage.transition.allow/deny, error_bucket)
- Expired grants do not contribute tools (no new cleanup scope)
- Backward compatibility verified

**Rollback:**
```bash
git checkout tests/test_integration.py
rm tests/test_stage_governance_integration.py
```

---

## Stage E: Verification and Closeout

**Goal:** Final verification that runtime enforcement is complete, scope boundaries are respected, and the change is ready for archive.

**Files to modify:**
- `openspec/changes/enforce-stage-transition-governance/closeout.md` (new file)

**Files NOT to modify:**
- `examples/` (no demo migration)
- `docs/` (sync deferred to after archive)

**Tasks:**

- [x] E.1 Run all new stage governance tests: `python -m pytest tests/test_stage_governance_integration.py -v`
- [x] E.2 Run mcp_server tests: `python -m pytest tests/test_mcp_server.py -v`
- [x] E.3 Run state_manager tests: `python -m pytest tests/test_state_manager.py -v`
- [x] E.4 Run runtime_context tests: `python -m pytest tests/test_runtime_context.py -v`
- [x] E.5 Run full test suite: `python -m pytest tests/ -v` (or project-recommended command)
- [x] E.6 Run OpenSpec validation: `openspec validate enforce-stage-transition-governance`
- [x] E.7 Verify NO changes to: `examples/simulator-demo/`, `examples/01-knowledge-link/`, `examples/02-doc-edit-staged/`, `examples/03-lifecycle-and-risk/`
- [x] E.8 Verify NO changes to: `docs/skill_stage_authoring.md` (beyond minimal necessary updates)
- [x] E.9 Verify NO introduction of: Tool registry, active_tools rename, allowed_tools rename, Redis, StateStore, CacheStore
- [x] E.10 Verify NO changes to: observability taxonomy, cache layer architecture
- [x] E.11 Create closeout summary documenting: what was completed, files modified, new state fields, new error buckets, new audit events
- [x] E.12 Document in closeout: what is deferred to `migrate-demos-to-stage-first-governance` (demo migration, examples deprecated, runbook updates)
- [x] E.13 Update all task checkboxes in this file to [x] for completed tasks
- [x] E.14 Prepare for `openspec verify enforce-stage-transition-governance`
- [x] E.15 Prepare for `openspec archive enforce-stage-transition-governance`

**Verification:**
```bash
openspec validate enforce-stage-transition-governance
python -m pytest tests/ -v
```

**Completion criteria:**
- All tests pass (target: 238+ tests, including ~50 new stage governance tests)
- OpenSpec validation passes
- No scope creep into demo migration, tool registry, or observability redesign
- Closeout summary documents all changes and deferred work
- Ready for archive

**Rollback:**
```bash
# Full rollback of all stages
git checkout src/tool_governance/models/state.py
git checkout src/tool_governance/mcp_server.py
git checkout src/tool_governance/tools/langchain_tools.py
git checkout tests/
rm tests/test_stage_governance_integration.py
rm openspec/changes/enforce-stage-transition-governance/closeout.md
```

---

## Summary

**Total tasks:** 78 tasks across 5 stages

**Modified files:**
- `src/tool_governance/models/state.py` (Stage A)
- `src/tool_governance/mcp_server.py` (Stages B, C)
- `src/tool_governance/tools/langchain_tools.py` (Stage B)
- `tests/test_models.py` (Stage A)
- `tests/test_mcp_server.py` (Stages B, C)
- `tests/test_integration.py` (Stages B, C, D)
- `tests/test_stage_governance_integration.py` (Stage D, new file)
- `openspec/changes/enforce-stage-transition-governance/closeout.md` (Stage E, new file)

**NOT modified:**
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`
- `src/tool_governance/storage/sqlite_store.py`
- `examples/` (all demo workspaces)
- `docs/` (sync deferred to post-archive)

**New capabilities:**
- Stage state initialization on enable_skill
- Stage transition validation in change_stage
- Terminal stage enforcement
- Stage-specific error buckets (5 new)
- Stage transition audit (2 new event types)
- Stage state persistence and restoration

**Deferred to `migrate-demos-to-stage-first-governance`:**
- Migrate simulator-demo to use stage governance
- Mark old examples as deprecated
- Update demo runbooks and READMEs
- Verify stage governance with real hook/MCP subprocesses
