# Implementation Tasks: formalize-stage-workflow-metadata

## Stage A: Schema Extension and Parsing Validation

**Goal**: Extend metadata schema to support Stage workflow (initial_stage, allowed_next_stages) without breaking existing skills.

**Files to modify**:
- `src/tool_governance/models/skill.py`

**Files NOT to modify**:
- `src/tool_governance/core/tool_rewriter.py` (active_tools logic unchanged)
- `src/tool_governance/core/runtime_context.py` (no runtime enforcement)
- `src/tool_governance/hook_handler.py` (no runtime enforcement)
- `src/tool_governance/mcp_server.py` (no change_stage validation)

**Tasks**:

- [x] A.1 Add `allowed_next_stages: list[str] = Field(default_factory=list)` to `StageDefinition` in `src/tool_governance/models/skill.py`
- [x] A.2 Add `initial_stage: str | None = None` to `SkillMetadata` in `src/tool_governance/models/skill.py`
- [x] A.3 Verify all existing fields remain unchanged (allowed_tools, stages, stage_id, description)
- [x] A.4 Add test in `tests/test_models.py`: `SkillMetadata` can be instantiated with `initial_stage`
- [x] A.5 Add test in `tests/test_models.py`: `StageDefinition` can be instantiated with `allowed_next_stages`
- [x] A.6 Add test in `tests/test_models.py`: `allowed_next_stages` defaults to empty list
- [x] A.7 Add test in `tests/test_models.py`: `initial_stage` defaults to None
- [x] A.8 Add test in `tests/test_skill_indexer.py`: Parse SKILL.md with `initial_stage` in frontmatter
- [x] A.9 Add test in `tests/test_skill_indexer.py`: Parse SKILL.md with `allowed_next_stages` in stage definitions
- [x] A.10 Add test in `tests/test_skill_indexer.py`: `allowed_next_stages: []` preserved as empty list (terminal stage)
- [x] A.11 Add test in `tests/test_skill_indexer.py`: Skills without stages remain valid
- [x] A.12 Add test in `tests/test_skill_indexer.py`: Skills with stages but no `initial_stage` are valid
- [ ] A.13 (Optional) Add validation warning in `skill_indexer.py` when `initial_stage` references non-existent stage
- [ ] A.14 (Optional) Add validation warning in `skill_indexer.py` when `allowed_next_stages` references non-existent stage
- [ ] A.15 (Optional) Add validation warning in `skill_indexer.py` when `initial_stage` present but no stages defined

**Verification**:
```bash
python -m pytest tests/test_models.py -v -k "initial_stage or allowed_next_stages"
python -m pytest tests/test_skill_indexer.py -v -k "stage"
```

**Completion criteria**:
- All new tests pass
- Existing tests remain passing
- No changes to active_tools computation logic
- Skills without stages still work

**Rollback**:
- Remove `initial_stage` field from `SkillMetadata`
- Remove `allowed_next_stages` field from `StageDefinition`
- Remove new tests

---

## Stage B: SkillContent / read_skill Exposure Validation

**Goal**: Verify `read_skill` exposes complete stage workflow information to the model.

**Files to check** (likely no modification needed):
- `src/tool_governance/core/skill_indexer.py` (read_skill method)
- `src/tool_governance/models/skill.py` (SkillContent)

**Files NOT to modify**:
- `src/tool_governance/models/state.py` (no runtime state in read_skill)
- `src/tool_governance/core/runtime_context.py` (read_skill is metadata-only)

**Tasks**:

- [x] B.1 Verify `SkillContent.metadata` automatically includes new `initial_stage` field (Pydantic auto-serialization)
- [x] B.2 Verify `SkillContent.metadata.stages` automatically includes new `allowed_next_stages` field per stage
- [x] B.3 Confirm `read_skill()` requires no code changes (metadata extension is sufficient)
- [x] B.4 Add test in `tests/test_skill_indexer.py`: `read_skill` on staged skill returns `initial_stage`
- [x] B.5 Add test in `tests/test_skill_indexer.py`: `read_skill` on staged skill returns each stage's `allowed_next_stages`
- [x] B.6 Add test in `tests/test_skill_indexer.py`: `read_skill` on terminal stage returns `allowed_next_stages: []`
- [x] B.7 Add test in `tests/test_skill_indexer.py`: `read_skill` on non-staged skill returns skill-level `allowed_tools`
- [x] B.8 Add test in `tests/test_skill_indexer.py`: `read_skill` on non-staged skill has empty `stages` list
- [ ] B.9 Add integration test in `tests/test_integration.py`: Full workflow - parse staged skill, read_skill, verify complete workflow info returned
- [ ] B.10 Add integration test in `tests/test_integration.py`: Full workflow - parse non-staged skill, read_skill, verify skill-level allowed_tools returned
- [x] B.11 Verify `read_skill` does NOT expose runtime state (current_stage, exited_stages, etc.)

**Verification**:
```bash
python -m pytest tests/test_skill_indexer.py::test_read_skill -v
python -m pytest tests/test_integration.py -v -k "read_skill"
```

**Completion criteria**:
- `read_skill` returns complete stage workflow metadata
- Terminal stages correctly expose `allowed_next_stages: []`
- Non-staged skills correctly expose skill-level `allowed_tools`
- No runtime state leaks into `read_skill` output

**Rollback**:
- Remove new tests
- No code rollback needed (Stage A rollback is sufficient)

---

## Stage C: Skill Stage Authoring Standard Documentation

**Goal**: Create `docs/skill_stage_authoring.md` defining when/how to decompose Skills into Stages.

**Files to create**:
- `docs/skill_stage_authoring.md`

**Files NOT to modify**:
- `docs/requirements.md` (defer to later sync)
- `docs/technical_design.md` (defer to later sync)
- `docs/dev_plan.md` (defer to later sync)

**Tasks**:

- [x] C.1 Create `docs/skill_stage_authoring.md` with section: Core Definitions (Skill/Stage/Tool semantics)
- [x] C.2 Add section: Skill = business capability / SOP / workflow (NOT tool grouping)
- [x] C.3 Add section: Stage = phase within Skill's workflow
- [x] C.4 Add section: Tool = external capability callable within a stage
- [x] C.5 Add section: SOP lives in SKILL.md body, metadata defines governance boundaries
- [x] C.6 Add section: When to Create a Skill (different business goals, authorization semantics, risk boundaries, SOPs)
- [x] C.7 Add section: When to Decompose into Stages (different tool requirements per phase, risk profiles, progressive disclosure)
- [x] C.8 Add section: When NOT to Use Stages (simple/low-risk/single-phase, uniform tool requirements)
- [x] C.9 Add section: Choosing initial_stage (safest entry point, typically read-only, must be valid stage_id, defaults to first stage if omitted)
- [x] C.10 Add section: Designing allowed_next_stages (list valid successors, empty list = terminal stage, circular/backward allowed for retry patterns)
- [x] C.11 Add section: Terminal Stage Expression (`allowed_next_stages: []` means no further transitions)
- [x] C.12 Add section: Anti-Patterns (❌ splitting by tool type like "read-stage"/"write-stage", ❌ separate skills for "read-ops"/"write-ops")
- [x] C.13 Add section: Best Practices (✅ split by workflow phase like "diagnose"/"analyze"/"remediate")
- [x] C.14 Add example: Simple Skill without stages (e.g., "list-files" with uniform read-only tools)
- [x] C.15 Add example: Staged Skill (e.g., "document-editing" with stages: "review" → "edit" → "publish")
- [x] C.16 Add note: Runtime enforcement (auto-enter initial_stage, validate transitions) is future work
- [x] C.17 Verify document covers all requirements from `specs/skill-stage-authoring-standard/spec.md`

**Verification**:
```bash
# Manual review
cat docs/skill_stage_authoring.md

# Verify examples parse correctly (optional)
# Create test SKILL.md files based on examples and verify they parse
```

**Completion criteria**:
- Document exists at `docs/skill_stage_authoring.md`
- All required sections present
- Two examples included (simple + staged)
- Anti-patterns clearly marked
- Runtime enforcement explicitly noted as future work

**Rollback**:
- Delete `docs/skill_stage_authoring.md`

---

## Stage D: Verification, Closeout, and Boundary Confirmation

**Goal**: Run tests, confirm no runtime enforcement implemented, prepare for archive.

**Files to verify** (no modifications):
- All test files
- All source files

**Tasks**:

- [x] D.1 Run metadata/schema tests: `python -m pytest tests/test_models.py -v`
- [x] D.2 Run skill_indexer tests: `python -m pytest tests/test_skill_indexer.py -v`
- [x] D.3 Run integration tests: `python -m pytest tests/test_integration.py -v`
- [x] D.4 Run full test suite: `python -m pytest tests/ -v`
- [x] D.5 Verify NO implementation of: enable_skill auto-entry to initial_stage
- [x] D.6 Verify NO implementation of: change_stage validation of allowed_next_stages
- [x] D.7 Verify NO implementation of: exited_stages state tracking
- [x] D.8 Verify NO implementation of: stage_history state tracking
- [x] D.9 Verify NO implementation of: stage_entered_at state tracking
- [x] D.10 Verify NO implementation of: simulator-demo migration
- [x] D.11 Verify NO implementation of: old examples deprecated marking
- [x] D.12 Verify existing skills without stages still work (run test or manual check)
- [x] D.13 Verify active_tools computation logic unchanged (check ToolRewriter.get_stage_tools behavior)
- [x] D.14 Create closeout summary documenting: what was completed, what is deferred to future changes
- [x] D.15 Document next recommended change: `enforce-stage-transition-governance`

**Verification**:
```bash
# Full test suite
python -m pytest tests/ -v

# Verify no runtime enforcement
grep -r "initial_stage" src/tool_governance/hook_handler.py  # Should find nothing
grep -r "allowed_next_stages" src/tool_governance/mcp_server.py  # Should find nothing in change_stage validation

# Verify backward compatibility
python -m pytest tests/test_skill_indexer.py -v -k "without_stages"
```

**Completion criteria**:
- All tests pass
- No runtime enforcement implemented
- Existing skills without stages work
- active_tools logic unchanged
- Closeout summary written

**Rollback**:
- Execute Stage A, B, C rollback steps
- Remove all new tests
- Restore original state

---

## Out of Scope (Explicitly NOT in This Change)

The following are **NOT** implemented in this change and are reserved for future changes:

### Runtime Enforcement (future: `enforce-stage-transition-governance`)
- enable_skill auto-entry to initial_stage
- change_stage validation of allowed_next_stages
- Deny change_stage on skills without stages (error_bucket: skill_has_no_stages)
- exited_stages / exited_stage_ids state tracking
- stage_history state tracking
- stage_entered_at timestamp tracking
- Audit events: stage.enter, stage.exit, stage.transition.deny

### Demo Migration (future: `migrate-simulator-demo-to-stage-first-governance`)
- Migrate simulator-demo to Stage-first governance
- Mark old examples (01-knowledge-link, 02-doc-edit-staged, 03-lifecycle-and-risk) as deprecated
- Update runbooks and verification procedures

### Other Out of Scope
- Modify active_tools computation logic
- Modify RuntimeContext
- Modify hook handlers for stage enforcement
- Deprecate skills without stages

---

## Documentation Sync (Post-Implementation)

After all stages complete, sync the following into canonical docs:

- [ ] Sync metadata schema changes into `docs/technical_design.md` §3.1 (Data Models)
- [ ] Sync authoring standard reference into `docs/requirements.md` (if applicable)
- [ ] Update `docs/dev_plan.md` progress tracking
