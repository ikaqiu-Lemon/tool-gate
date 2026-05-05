# Design: Migrate Demos to Stage-first Governance

## Context

### Background

The Stage-first Skill governance refactor has completed two phases:
1. **formalize-stage-workflow-metadata** (archived) — Established `initial_stage`, `stages`, `allowed_next_stages`, and stage-level `allowed_tools` in metadata schema
2. **enforce-stage-transition-governance** (archived) — Implemented runtime enforcement: `enable_skill` stage initialization, `change_stage` validation, terminal stage blocking, and stage state persistence

The demonstration layer is now disconnected from the runtime:
- **Legacy examples** (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`) predate Stage-first governance and do not demonstrate stage workflows
- **simulator-demo** exists but does not currently demonstrate Stage-first behaviors (no `initial_stage`, `allowed_next_stages`, terminal stages, or stage-aware `active_tools`)
- **Documentation** does not clearly distinguish legacy patterns from Stage-first canonical patterns

### Current State Analysis

**Legacy examples status:**
- `examples/01-knowledge-link/README.md` — No deprecation notice, presented as current demo
- `examples/02-doc-edit-staged/README.md` — No deprecation notice, presented as current demo
- `examples/03-lifecycle-and-risk/README.md` — No deprecation notice, presented as current demo
- All three use pre-Stage-first SKILL.md files (no `initial_stage` or `allowed_next_stages`)

**simulator-demo status:**
- `examples/simulator-demo/` exists with Stage A-D complete
- Current scenarios demonstrate: discovery, staged workflow (via `change_stage`), lifecycle
- **Gap**: Scenarios do NOT demonstrate Stage-first metadata (`initial_stage`, `allowed_next_stages`, terminal stages)
- **Gap**: SCOPE.md and SCENARIOS.md reference "staged workflow" but not Stage-first governance semantics
- **Gap**: No skills with `initial_stage` or `allowed_next_stages` metadata
- **Gap**: No demonstration of terminal stage blocking or illegal transition rejection

**Documentation status:**
- `examples/README.md` — Lists all four workspaces equally, no clear canonical demo designation
- Root `README.md` — May or may not have demo links (needs verification)
- `docs/skill_stage_authoring.md` — Defines Stage-first standard but has no real demo cross-references

### Constraints

- **No runtime core changes** unless blocking bugs are discovered
- **No deletion** of legacy examples
- **No migration** of legacy examples to Stage-first
- **No new scenarios** beyond the existing three in simulator-demo
- **Real subprocess boundaries** — must use actual `tg-hook` and `tg-mcp`, not static mocks

## Goals / Non-Goals

### Goals

1. **Mark legacy examples as deprecated** — Clear notices directing users to simulator-demo
2. **Migrate simulator-demo to Stage-first** — Update scenarios, skills, and verification to demonstrate Stage-first governance
3. **Establish canonical demo path** — Update README files to point to simulator-demo as the Stage-first acceptance target
4. **Verify through real subprocesses** — Ensure all scenarios run through actual `tg-hook` and `tg-mcp` boundaries
5. **Align documentation** — Update simulator-demo docs and add minimal cross-references in authoring guide

### Non-Goals

- Migrating legacy examples to Stage-first (they remain as historical artifacts)
- Deleting legacy examples
- Modifying core governance runtime (`src/tool_governance/core/`)
- Changing metadata schema or RuntimeContext
- Adding a fourth scenario
- Introducing Tool registry, Redis abstraction, or complex approval workflows
- Refactoring core runtime unit tests

## Decisions

### Decision 1: Deprecation Strategy for Legacy Examples

**Choice**: Add prominent deprecation notices to legacy example READMEs without modifying their content or deleting them.

**Rationale**:
- Preserves historical value and existing links
- Low-cost, low-risk approach
- Clearly signals to users and future models that these are not canonical Stage-first demos

**Implementation**:
- Add deprecation notice at the top of each legacy example README (before any other content)
- Notice format:
  ```markdown
  > **⚠️ DEPRECATED / LEGACY EXAMPLE**
  >
  > This example predates Stage-first Skill governance and does not demonstrate stage workflows, `initial_stage`, `allowed_next_stages`, or terminal stages.
  >
  > **For Stage-first governance demonstrations, see [`examples/simulator-demo`](../simulator-demo/).**
  >
  > This example is preserved for historical reference only.
  ```
- No changes to SKILL.md files, scripts, or mock servers in legacy examples

**Alternatives considered**:
- **Delete legacy examples**: Rejected — loses historical value and breaks existing links
- **Migrate legacy examples**: Rejected — high cost, low value, increases maintenance burden
- **Leave unchanged**: Rejected — perpetuates confusion about canonical patterns

---

### Decision 2: simulator-demo as Sole Canonical Stage-first Demo

**Choice**: Designate `examples/simulator-demo` as the single canonical Stage-first governance demonstration.

**Rationale**:
- Focuses validation effort on one high-quality demo
- Reduces maintenance burden (one canonical demo vs. four)
- simulator-demo already has subprocess isolation infrastructure
- Clear separation between legacy (01-03) and canonical (simulator-demo)

**Implementation**:
- Update `examples/README.md` to clearly identify simulator-demo as canonical Stage-first demo
- Update root `README.md` (if it has demo links) to point to simulator-demo
- Update `examples/simulator-demo/README.md` to state canonical status explicitly

**Alternatives considered**:
- **Migrate all four examples**: Rejected — too costly, creates maintenance burden
- **Create new fifth example**: Rejected — adds complexity, simulator-demo already exists

---

### Decision 3: Three-Scenario Coverage for Stage-first Behaviors

**Choice**: Update the existing three simulator-demo scenarios to demonstrate Stage-first governance without adding a fourth scenario.

**Rationale**:
- Existing three-scenario structure already covers discovery, transitions, and lifecycle
- Can demonstrate all Stage-first behaviors within existing scenarios
- Avoids scope creep

**Scenario mapping**:

**Scenario 01: Discovery / read_skill / no-stage fallback**
- Add: `read_skill` returns `initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools`
- Add: Demonstrate no-stage Skill fallback (enable a skill without stages)
- Keep: Existing discovery and auto-grant flow

**Scenario 02: Stage workflow transition**
- Add: `enable_skill` enters `initial_stage` (or first stage if unspecified)
- Add: Demonstrate legal `change_stage` (within `allowed_next_stages`)
- Add: Demonstrate illegal `change_stage` (rejected with `stage_transition_not_allowed`)
- Add: Audit records `stage.transition.allow` and `stage.transition.deny`
- Keep: Existing staged workflow and `blocked_tools` demonstration

**Scenario 03: Lifecycle / terminal / persistence / revoke**
- Add: Demonstrate terminal stage (one with `allowed_next_stages: []`) refusing further transitions
- Add: Demonstrate expired grant not contributing to runtime `active_tools`
- Add: Demonstrate stage state persistence and recovery
- Keep: Existing TTL expiry, revoke, and high-risk denial

**Alternatives considered**:
- **Add fourth scenario**: Rejected — increases complexity, not needed for coverage
- **Rewrite scenarios from scratch**: Rejected — existing scenarios are functional, incremental update is lower risk

---

### Decision 4: Stage-first Skill Fixtures

**Choice**: Create new staged skill fixtures with Stage-first metadata for simulator-demo, plus one no-stage skill for fallback demonstration.

**Rationale**:
- simulator-demo needs skills with `initial_stage`, `allowed_next_stages`, and terminal stages
- Must demonstrate both staged and no-stage patterns
- Should not depend on legacy example skills

**Skill fixtures needed**:

1. **Staged skill with terminal stage** (for Scenario 02 and 03):
   ```yaml
   name: "yuque-doc-edit-staged"
   description: "Edit Yuque documents with analysis → execution workflow"
   risk_level: "medium"
   initial_stage: "analysis"
   stages:
     - stage_id: "analysis"
       description: "Read and analyze document"
       allowed_tools: ["yuque_get_doc", "yuque_list_docs"]
       allowed_next_stages: ["execution"]
     - stage_id: "execution"
       description: "Modify document"
       allowed_tools: ["yuque_get_doc", "yuque_update_doc"]
       allowed_next_stages: ["complete"]
     - stage_id: "complete"
       description: "Workflow complete"
       allowed_tools: []
       allowed_next_stages: []  # Terminal stage
   ```

2. **No-stage skill** (for Scenario 01 fallback):
   ```yaml
   name: "yuque-knowledge-link"
   description: "Search and link knowledge base documents"
   risk_level: "low"
   allowed_tools: ["yuque_search", "yuque_list_docs", "yuque_get_doc"]
   # No stages field — fallback to allowed_tools
   ```

**Storage location**: `examples/simulator-demo/fixtures/skills/` (new directory)

**Alternatives considered**:
- **Reuse legacy example skills**: Rejected — they lack Stage-first metadata
- **Inline skills in scenario scripts**: Rejected — harder to maintain and verify

---

### Decision 5: Real Subprocess Verification Strategy

**Choice**: Ensure all scenarios invoke real `tg-hook` and `tg-mcp` subprocesses, with verification that artifacts come from actual execution.

**Rationale**:
- Acceptance criteria require real subprocess boundaries
- Static mocks would not validate the actual governance runtime
- simulator-demo already has subprocess infrastructure (Stage B-D complete)

**Implementation**:
- Verify `run_simulator.sh` invokes scenarios that spawn real subprocesses
- Verify generated artifacts (`events.jsonl`, `audit_summary.md`, `metrics.json`, `governance.db`) contain real subprocess outputs
- Add verification step to check that audit events include Stage-first fields (`initial_stage`, `allowed_next_stages`, `stage.transition.allow`, `stage.transition.deny`)

**Verification checklist**:
- [ ] `tg-hook` subprocess spawned for each hook event
- [ ] `tg-mcp` subprocess spawned for MCP meta-tools
- [ ] `governance.db` written by real MCP server
- [ ] Audit events include `stage.transition.allow` and `stage.transition.deny`
- [ ] No hardcoded JSON files masquerading as subprocess output

**Alternatives considered**:
- **Static mock outputs**: Rejected — does not validate runtime behavior
- **In-process simulation**: Rejected — does not demonstrate subprocess isolation

---

### Decision 6: Documentation Update Scope

**Choice**: Update demo entry points and simulator-demo docs; add minimal cross-references to authoring guide.

**Rationale**:
- Users need clear guidance on where to find Stage-first demos
- Documentation must accurately reflect runtime behavior
- Authoring guide should point to real examples

**Files to update**:

1. **examples/README.md**:
   - Add section distinguishing legacy examples from canonical Stage-first demo
   - Update simulator-demo description to emphasize Stage-first governance
   - Keep legacy examples listed but mark as "historical / pre-Stage-first"

2. **Root README.md** (if applicable):
   - Update demo links to point to simulator-demo for Stage-first patterns
   - If no demo links exist, no change needed

3. **examples/simulator-demo/README.md**:
   - Add explicit statement: "This is the canonical Stage-first governance acceptance target"
   - Update "Purpose" section to list Stage-first behaviors demonstrated
   - Update "Running the Scenarios" to reference Stage-first verification

4. **examples/simulator-demo/SCOPE.md**:
   - Update scenario descriptions to include Stage-first behaviors
   - Add Stage-first metadata fields to "What the Simulator Demonstrates"

5. **examples/simulator-demo/SCENARIOS.md**:
   - Update each scenario's "Expected Flow" to include Stage-first steps
   - Add Stage-first audit events to "Expected Audit Events"
   - Update verification criteria to include Stage-first checks

6. **docs/skill_stage_authoring.md**:
   - Add minimal cross-references to simulator-demo examples (e.g., "See `examples/simulator-demo/fixtures/skills/yuque-doc-edit-staged.md` for a complete example")
   - Do NOT rewrite core definitions or standards
   - Do NOT add implementation details

**Alternatives considered**:
- **Rewrite authoring guide**: Rejected — out of scope, guide is already complete
- **No documentation updates**: Rejected — leaves users without clear guidance

---

### Decision 7: Test and Verification Scope

**Choice**: Update simulator-demo verification scripts and acceptance tests; do not modify core runtime unit tests.

**Rationale**:
- Demo verification is in scope
- Core runtime unit tests are out of scope unless blocking bugs are found
- Verification must confirm Stage-first behaviors through real subprocess execution

**In scope**:
- Update `run_simulator.sh` to verify Stage-first behaviors
- Update scenario scripts to generate Stage-first audit events
- Update verification scripts (`verify_stage_d.py` or equivalent) to check for Stage-first fields
- Add checks for `initial_stage`, `allowed_next_stages`, `stage.transition.allow`, `stage.transition.deny`

**Out of scope**:
- Core runtime unit tests (`tests/test_*.py`)
- Functional tests (`tests/functional/`)
- Integration tests outside simulator-demo

**Bug fix policy**:
- If a runtime bug is discovered during demo verification, it must be reported first
- Only bugs that directly block demo acceptance criteria may be fixed
- All bug discoveries and fixes must be documented in OpenSpec artifacts

**Alternatives considered**:
- **Refactor core runtime tests**: Rejected — out of scope, not needed for demo migration
- **No verification updates**: Rejected — cannot confirm Stage-first behaviors without verification

## Risks / Trade-offs

### Risk 1: Legacy Examples Still Mislead Users

**Risk**: Despite deprecation notices, users or models may still reference legacy examples as current patterns.

**Mitigation**:
- Prominent deprecation notices at the top of each legacy README
- `examples/README.md` clearly distinguishes legacy from canonical
- Search engines and documentation links point to simulator-demo

**Trade-off**: Keeping legacy examples preserves historical value but requires clear signaling to prevent confusion.

---

### Risk 2: simulator-demo Diverges from Runtime Behavior

**Risk**: simulator-demo scenarios may demonstrate behaviors that don't match actual runtime enforcement.

**Mitigation**:
- All scenarios run through real `tg-hook` and `tg-mcp` subprocesses
- Verification scripts check actual audit events and state snapshots
- `/opsx:verify` confirms alignment between docs and runtime

**Trade-off**: Real subprocess execution is slower than mocks but provides accurate validation.

---

### Risk 3: Incomplete Stage-first Coverage

**Risk**: Three scenarios may not cover all Stage-first behaviors.

**Mitigation**:
- Specs define 8 requirements with 34 scenarios covering all Stage-first behaviors
- Each requirement maps to specific simulator-demo scenario steps
- Verification scripts check for all required audit events

**Trade-off**: Three scenarios are sufficient for current Stage-first behaviors but may need expansion if new stage semantics are added in the future.

---

### Risk 4: Generated Artifacts in Version Control

**Risk**: Committing generated artifacts (`events.jsonl`, `audit_summary.md`, `governance.db`) may cause merge conflicts or bloat.

**Mitigation**:
- Generated artifacts stored in `.scenario-XX-data/` directories
- Add `.scenario-*-data/` to `.gitignore` to exclude from version control
- Verification scripts regenerate artifacts on each run
- Only commit scenario scripts and fixture files, not generated outputs

**Trade-off**: Excluding artifacts from version control means users must run scenarios to see outputs, but avoids merge conflicts.

---

### Risk 5: Runtime Bug Discovery During Demo Verification

**Risk**: Demo verification may uncover bugs in the Stage-first runtime enforcement.

**Mitigation**:
- Bug fix policy: report first, fix only if blocking, document in OpenSpec artifacts
- All bug discoveries recorded in design.md, tasks.md, and closeout.md
- Scope guard: no opportunistic refactoring or feature expansion

**Trade-off**: Fixing blocking bugs is necessary for demo acceptance but must be carefully scoped to avoid scope creep.

## Migration Plan

### Phase 1: Legacy Example Deprecation

1. Add deprecation notices to legacy example READMEs
2. Update `examples/README.md` to distinguish legacy from canonical
3. Verify deprecation notices are visible and clear

**Rollback**: Remove deprecation notices, restore original README content

---

### Phase 2: simulator-demo Skill Fixtures

1. Create `examples/simulator-demo/fixtures/skills/` directory
2. Write staged skill with `initial_stage`, `allowed_next_stages`, terminal stage
3. Write no-stage skill for fallback demonstration
4. Verify skills parse correctly with `SkillIndexer`

**Rollback**: Delete fixtures directory

---

### Phase 3: simulator-demo Scenario Updates

1. Update Scenario 01 to demonstrate `read_skill` returning Stage-first metadata and no-stage fallback
2. Update Scenario 02 to demonstrate `enable_skill` entering `initial_stage`, legal/illegal `change_stage`, and audit events
3. Update Scenario 03 to demonstrate terminal stage blocking, expired grant exclusion, and stage state persistence
4. Verify scenarios run through real subprocesses and generate correct audit events

**Rollback**: Restore original scenario scripts from git history

---

### Phase 4: Documentation Updates

1. Update `examples/simulator-demo/README.md`, `SCOPE.md`, `SCENARIOS.md`
2. Update `examples/README.md` and root `README.md` (if applicable)
3. Add minimal cross-references to `docs/skill_stage_authoring.md`
4. Verify documentation accurately reflects runtime behavior

**Rollback**: Restore original documentation from git history

---

### Phase 5: Verification and Acceptance

1. Run `run_simulator.sh` to execute all three scenarios
2. Verify all Stage-first audit events are present
3. Run `/opsx:verify` to confirm alignment
4. Run `openspec validate` to confirm format compliance
5. Document any runtime bugs discovered

**Rollback**: N/A (verification phase, no changes)

## Open Questions

### Q1: Should generated artifacts be committed to version control?

**Current thinking**: No, add `.scenario-*-data/` to `.gitignore` to avoid merge conflicts and bloat.

**Resolution needed**: Confirm with user during implementation.

---

### Q2: Should simulator-demo support custom scenarios beyond the three core ones?

**Current thinking**: No, out of scope for this change. Three scenarios are sufficient for Stage-first acceptance.

**Resolution needed**: If future needs arise, address in a separate change.

---

### Q3: How should runtime bugs discovered during verification be handled?

**Current thinking**: Report first, fix only if blocking demo acceptance, document in OpenSpec artifacts.

**Resolution needed**: Establish clear bug triage process during implementation.

---

### Q4: Should legacy examples eventually be deleted?

**Current thinking**: Not in this change. Deprecation is sufficient for now. Deletion can be considered in a future cleanup change.

**Resolution needed**: Defer to future decision.
