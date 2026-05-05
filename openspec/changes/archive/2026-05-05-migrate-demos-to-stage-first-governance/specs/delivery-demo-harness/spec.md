# delivery-demo-harness Specification Delta

## ADDED Requirements

### Requirement: Legacy Examples MUST Be Marked As Deprecated

Legacy demo workspaces (`examples/01-knowledge-link`, `examples/02-doc-edit-staged`, `examples/03-lifecycle-and-risk`) MUST be clearly marked as deprecated and historical artifacts. These examples SHALL remain in place for reference but SHALL NOT be migrated to Stage-first governance or maintained as canonical demonstrations.

#### Scenario: Deprecation notice in legacy example READMEs

- **WHEN** a user opens `examples/01-knowledge-link/README.md`, `examples/02-doc-edit-staged/README.md`, or `examples/03-lifecycle-and-risk/README.md`
- **THEN** the README MUST contain a prominent deprecation notice at the top stating that this example is a legacy/historical artifact
- **AND** the notice MUST direct users to `examples/simulator-demo` as the canonical Stage-first governance demonstration

#### Scenario: Legacy examples not deleted

- **WHEN** the change is complete
- **THEN** all three legacy example directories (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`) MUST still exist
- **AND** their SKILL.md files, scripts, and mock servers MUST remain unchanged (no Stage-first migration)

#### Scenario: Legacy examples excluded from canonical guidance

- **WHEN** documentation references demo workspaces
- **THEN** legacy examples MUST NOT be presented as canonical Stage-first governance demonstrations
- **AND** users MUST be directed to `simulator-demo` for Stage-first patterns

### Requirement: simulator-demo MUST Be The Canonical Stage-first Demo

The `examples/simulator-demo` workspace MUST be established as the canonical demonstration and acceptance target for Stage-first Skill governance. All demo entry points MUST direct users to `simulator-demo` for Stage-first governance patterns.

#### Scenario: Examples README points to simulator-demo

- **WHEN** a user opens `examples/README.md`
- **THEN** it MUST clearly identify `examples/simulator-demo` as the canonical Stage-first governance demonstration
- **AND** it MUST distinguish `simulator-demo` from legacy examples

#### Scenario: Root README demo navigation

- **WHEN** the root `README.md` contains demo-related links
- **THEN** it MUST point to `examples/simulator-demo` as the primary Stage-first demo
- **AND** it MUST NOT default to legacy examples for Stage-first guidance

#### Scenario: simulator-demo README declares canonical status

- **WHEN** a user opens `examples/simulator-demo/README.md`
- **THEN** it MUST explicitly state that this is the canonical Stage-first governance acceptance target
- **AND** it MUST explain that it demonstrates Stage-first governance through real subprocess boundaries

### Requirement: simulator-demo SHALL Prove Stage Workflow Discovery And No-Stage Fallback

The `simulator-demo` workspace SHALL demonstrate that the governance system correctly exposes stage workflow metadata through `read_skill` and maintains backward compatibility with no-stage Skills.

#### Scenario: read_skill returns stage workflow metadata

- **WHEN** the simulator-demo runs a scenario that calls `read_skill` on a staged Skill
- **THEN** the returned `SkillContent` MUST include `initial_stage`, `stages`, `allowed_next_stages`, and `stage.allowed_tools` fields
- **AND** the demo verification MUST confirm these fields are present and correctly structured

#### Scenario: list_skills and read_skill discovery flow

- **WHEN** the simulator-demo runs its discovery scenario
- **THEN** it MUST demonstrate `list_skills` returning available skills
- **AND** it MUST demonstrate `read_skill` returning complete stage workflow metadata for at least one staged Skill

#### Scenario: no-stage Skill fallback remains valid

- **WHEN** the simulator-demo includes a Skill without stage definitions
- **THEN** the governance system MUST accept and enable the no-stage Skill
- **AND** the Skill's `allowed_tools` MUST be used directly without stage-level filtering

#### Scenario: unauthorized tool rejection

- **WHEN** the simulator-demo attempts to call a tool not in any enabled Skill's `allowed_tools`
- **THEN** the system MUST reject the call with `tool_not_available` or equivalent error
- **AND** the audit log MUST record the denial

### Requirement: simulator-demo SHALL Prove Stage Transition Governance

The `simulator-demo` workspace SHALL demonstrate that stage transitions are correctly governed by `initial_stage`, `allowed_next_stages`, and `current_stage` enforcement, and that `active_tools` updates correctly with stage changes.

#### Scenario: enable_skill enters initial_stage

- **WHEN** the simulator-demo calls `enable_skill` on a staged Skill
- **THEN** the Skill's `current_stage` MUST be set to `initial_stage` (or the first stage if `initial_stage` is not specified)
- **AND** `active_tools` MUST reflect only the tools allowed in that stage

#### Scenario: analysis stage exposes read-only tools

- **WHEN** the simulator-demo demonstrates an analysis stage
- **THEN** the stage's `allowed_tools` MUST contain only read-oriented tools (e.g., query, search, list)
- **AND** write-oriented tools (e.g., update, delete, create) MUST NOT be in `active_tools` during this stage

#### Scenario: execution stage exposes write tools

- **WHEN** the simulator-demo transitions to an execution stage
- **THEN** the stage's `allowed_tools` MUST include write-oriented tools
- **AND** `active_tools` MUST update to reflect the execution stage's tool set

#### Scenario: legal change_stage succeeds

- **WHEN** the simulator-demo calls `change_stage` with a `stage_id` that is in the current stage's `allowed_next_stages`
- **THEN** the transition MUST succeed
- **AND** `current_stage` MUST update to the new stage
- **AND** `active_tools` MUST update to reflect the new stage's `allowed_tools`

#### Scenario: illegal change_stage rejected

- **WHEN** the simulator-demo calls `change_stage` with a `stage_id` that is NOT in the current stage's `allowed_next_stages`
- **THEN** the transition MUST be rejected with `stage_transition_not_allowed` error
- **AND** `current_stage` MUST remain unchanged
- **AND** `active_tools` MUST remain unchanged

#### Scenario: audit records stage transitions

- **WHEN** the simulator-demo performs both legal and illegal stage transitions
- **THEN** the audit log MUST contain `stage.transition.allow` events for successful transitions
- **AND** the audit log MUST contain `stage.transition.deny` events for rejected transitions
- **AND** each event MUST include `skill_id`, `from_stage`, `to_stage`, and `decision` fields

### Requirement: simulator-demo SHALL Prove Lifecycle, Terminal, Persistence, And Revoke Behavior

The `simulator-demo` workspace SHALL demonstrate that terminal stages prevent further transitions, expired grants do not contribute tools, stage state persists across sessions, and revocation removes tools correctly.

#### Scenario: terminal stage refuses further transitions

- **WHEN** the simulator-demo reaches a terminal stage (one with `allowed_next_stages: []`)
- **THEN** any subsequent `change_stage` call MUST be rejected
- **AND** the rejection reason MUST indicate that the stage is terminal

#### Scenario: expired grants do not contribute tools

- **WHEN** the simulator-demo includes a grant that has passed its TTL expiry time
- **THEN** the expired grant MUST NOT contribute tools to the runtime `active_tools` view
- **AND** the grant status MUST be marked as expired in the audit log

#### Scenario: stage state persists and recovers

- **WHEN** the simulator-demo enables a staged Skill and transitions to a non-initial stage
- **THEN** the `current_stage` value MUST be persisted to the session state
- **AND** when the session is restored, the Skill MUST resume at the persisted `current_stage`
- **AND** `active_tools` MUST reflect the restored stage's tool set

#### Scenario: disable_skill removes tools

- **WHEN** the simulator-demo calls `disable_skill` on an enabled staged Skill
- **THEN** the Skill MUST be removed from `skills_loaded`
- **AND** the Skill's tools MUST be removed from `active_tools`
- **AND** the grant MUST be revoked

#### Scenario: risk and approval behavior preserved

- **WHEN** the simulator-demo includes risk-level or approval-required scenarios
- **THEN** existing risk/approval logic MUST continue to function
- **AND** no new complex approval workflows SHALL be introduced by this change

### Requirement: simulator-demo MUST Run Through Real Subprocess Boundaries

The `simulator-demo` workspace MUST execute all scenarios through real `tg-hook` and `tg-mcp` subprocess boundaries. Static mock outputs or hardcoded responses SHALL NOT be used to simulate governance behavior.

#### Scenario: real tg-hook subprocess invocation

- **WHEN** the simulator-demo runs any scenario
- **THEN** hook events (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse) MUST be processed by actual `tg-hook` subprocess invocations
- **AND** hook outputs MUST be generated by the real governance runtime, not static files

#### Scenario: real tg-mcp subprocess invocation

- **WHEN** the simulator-demo calls any MCP meta-tool (list_skills, read_skill, enable_skill, change_stage, etc.)
- **THEN** the tool call MUST be handled by an actual `tg-mcp` subprocess
- **AND** responses MUST be generated by the real MCP server, not static mock data

#### Scenario: run_simulator.sh executes all scenarios

- **WHEN** a user runs `examples/simulator-demo/run_simulator.sh` (or equivalent command)
- **THEN** all simulator-demo scenarios MUST execute end-to-end
- **AND** the script MUST exit with status 0 if all scenarios pass
- **AND** the script MUST exit with non-zero status if any scenario fails

#### Scenario: verification artifacts generated

- **WHEN** the simulator-demo completes execution
- **THEN** it MUST generate verification artifacts such as `events.jsonl`, `audit_summary.md`, or `metrics.json`
- **AND** these artifacts MUST contain evidence of real subprocess execution (timestamps, process IDs, actual audit events)

### Requirement: Documentation SHALL Align Users With Stage-first Governance

Documentation updates MUST guide users toward Stage-first governance patterns and ensure that documentation accurately reflects runtime behavior. Documentation SHALL NOT hide runtime inconsistencies through wording changes alone.

#### Scenario: simulator-demo README updated

- **WHEN** a user opens `examples/simulator-demo/README.md`
- **THEN** it MUST describe Stage-first governance scenarios (discovery, stage transitions, terminal stages, persistence)
- **AND** it MUST reference the Stage-first metadata fields (`initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools`)

#### Scenario: simulator-demo SCOPE and SCENARIOS updated

- **WHEN** a user opens `examples/simulator-demo/SCOPE.md` or `examples/simulator-demo/SCENARIOS.md`
- **THEN** these documents MUST reflect Stage-first governance scope and scenarios
- **AND** they MUST NOT reference pre-Stage-first patterns as current behavior

#### Scenario: examples README updated

- **WHEN** a user opens `examples/README.md`
- **THEN** it MUST direct users to `simulator-demo` for Stage-first governance demonstrations
- **AND** it MUST clearly distinguish legacy examples from the canonical Stage-first demo

#### Scenario: skill_stage_authoring.md references real demos

- **WHEN** `docs/skill_stage_authoring.md` is updated
- **THEN** it MAY add minimal cross-references to real `simulator-demo` examples
- **AND** it MUST NOT rewrite the core Stage-first authoring standard
- **AND** it MUST NOT redefine Skill, Stage, or Tool concepts

#### Scenario: documentation does not hide runtime behavior

- **WHEN** documentation is updated
- **THEN** it MUST accurately reflect actual runtime behavior
- **AND** it MUST NOT use wording changes to hide runtime inconsistencies or bugs
- **AND** any discovered runtime bugs MUST be reported and documented in OpenSpec artifacts

### Requirement: Demo Acceptance Tests SHALL Be Limited To Demo Verification Scope

Demo acceptance tests and verification scripts MAY be updated to validate Stage-first governance behaviors, but core runtime unit tests MUST remain unchanged unless blocking bugs are discovered. This change SHALL NOT become a runtime unit test refactor.

#### Scenario: simulator-demo verification tests updated

- **WHEN** the change includes test updates
- **THEN** updates MUST be limited to `examples/simulator-demo` verification tests and scripts
- **AND** updates MAY include demo acceptance tests that validate end-to-end scenarios

#### Scenario: core runtime unit tests unchanged

- **WHEN** the change is complete
- **THEN** core runtime unit tests (under `tests/`) MUST remain unchanged
- **AND** no core runtime test expectations MUST be modified unless a blocking bug is discovered and documented

#### Scenario: run_simulator.sh and verification scripts updated

- **WHEN** the change updates `run_simulator.sh` or equivalent verification scripts
- **THEN** these updates MUST be within the demo verification scope
- **AND** they MUST validate Stage-first governance behaviors through real subprocess boundaries

#### Scenario: runtime bug discovery and reporting

- **WHEN** a runtime bug is discovered during demo verification
- **THEN** the bug MUST be reported first before any fix is attempted
- **AND** the bug and its fix MUST be documented in OpenSpec artifacts
- **AND** only bugs that directly block demo acceptance criteria MAY be fixed within this change
- **AND** opportunistic scope expansion (e.g., "while we're here, let's also refactor X") is prohibited

## Out of Scope

The following items are explicitly OUT OF SCOPE for this change and MUST NOT be included:

- Modifying core metadata schema (`models/skill.py`)
- Modifying `RuntimeContext` primary logic
- Modifying `enable_skill` or `change_stage` runtime enforcement (unless a blocking bug is discovered and documented)
- Re-discussing or redesigning `initial_stage` or `allowed_next_stages` semantics
- Deleting legacy examples (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`)
- Migrating legacy examples to Stage-first governance
- Adding a fourth simulator scenario (without explicit approval)
- Introducing Tool registry abstraction
- Renaming `active_tools` or `allowed_tools`
- Redis, StateStore, or CacheStore abstraction
- Observability taxonomy redesign
- Cache layer refactor
- Complex human approval workflow implementation
- General workflow engine implementation

### Bug Fix Policy

If runtime bugs are discovered during demo verification:

1. The bug MUST be reported first
2. Only bugs that directly block this change's acceptance criteria MAY be fixed
3. All bug discoveries and fixes MUST be documented in OpenSpec artifacts
4. Opportunistic scope expansion is prohibited
