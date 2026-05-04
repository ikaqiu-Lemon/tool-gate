# stage-transition-validation Specification

## Purpose

Runtime validation of stage transitions against `allowed_next_stages` metadata, including terminal stage enforcement and stage-specific error taxonomy.

## ADDED Requirements

### Requirement: change_stage MUST enforce allowed_next_stages

The `change_stage` MCP tool SHALL validate all stage transition requests against the current stage's `allowed_next_stages` list. Valid transitions SHALL update `current_stage`, `stage_entered_at`, append to `stage_history`, add the previous stage to `exited_stages`, recompute `active_tools`, and return success. Invalid transitions SHALL be denied with a specific error bucket and SHALL NOT modify stage state.

#### Scenario: Valid stage transition

- **WHEN** a skill is in stage "analysis" with `allowed_next_stages: ["execution"]` and the model calls `change_stage(skill_id, "execution")`
- **THEN** the system updates `current_stage` to "execution", records the transition in `stage_history`, adds "analysis" to `exited_stages`, updates `stage_entered_at`, recomputes `active_tools` to reflect execution stage tools, and returns `{changed: true, new_active_tools: [...]}`

#### Scenario: Target stage not in allowed_next_stages

- **WHEN** a skill is in stage "analysis" with `allowed_next_stages: ["execution"]` and the model calls `change_stage(skill_id, "deployment")`
- **THEN** the system denies the transition, returns `{changed: false, error: "stage_transition_not_allowed"}`, and does NOT modify `current_stage`, `stage_history`, or `exited_stages`

#### Scenario: Target stage does not exist

- **WHEN** the model calls `change_stage(skill_id, "nonexistent-stage")`
- **THEN** the system returns `{changed: false, error: "stage_not_found"}` and does NOT modify stage state

#### Scenario: Current stage not initialized

- **WHEN** a skill's `current_stage` is None and the model calls `change_stage(skill_id, "execution")`
- **THEN** the system returns `{changed: false, error: "stage_not_initialized"}` and does NOT modify stage state

### Requirement: Terminal stages MUST block further transitions

Stages with `allowed_next_stages: []` SHALL be treated as terminal stages. Any `change_stage` call from a terminal stage MUST be denied with error bucket `stage_transition_not_allowed`.

#### Scenario: Transition from terminal stage denied

- **WHEN** a skill is in stage "complete" with `allowed_next_stages: []` and the model calls `change_stage(skill_id, "analysis")`
- **THEN** the system returns `{changed: false, error: "stage_transition_not_allowed"}` and does NOT modify stage state

#### Scenario: Terminal stage reached successfully

- **WHEN** a skill transitions to stage "complete" with `allowed_next_stages: []`
- **THEN** the system updates `current_stage` to "complete", records the transition, and subsequent `change_stage` calls are denied

### Requirement: No-stage skills MUST preserve compatibility

Skills without stage definitions SHALL continue using skill-level `allowed_tools`. Calling `change_stage` on a no-stage skill MUST return error bucket `skill_has_no_stages` and SHALL NOT modify `current_stage` or `active_tools`.

#### Scenario: change_stage on no-stage skill denied

- **WHEN** a skill has no `stages` field and the model calls `change_stage(skill_id, "any-stage")`
- **THEN** the system returns `{changed: false, error: "skill_has_no_stages"}` and does NOT modify state

#### Scenario: No-stage skill active_tools unchanged

- **WHEN** a no-stage skill is enabled and `change_stage` is called
- **THEN** `active_tools` continues to reflect the skill's top-level `allowed_tools` and is NOT affected by the denied transition

### Requirement: Stage transition attempts MUST be auditable

All `change_stage` calls SHALL be recorded in the audit log with event type `stage.transition.allow` (for successful transitions) or `stage.transition.deny` (for denied transitions). Each audit record MUST include: `session_id`, `skill_id`, `from_stage`, `to_stage`, `decision` (allow/deny), `error_bucket` (for denied transitions), and `timestamp`.

#### Scenario: Successful transition audited

- **WHEN** a valid stage transition succeeds
- **THEN** the audit log contains a `stage.transition.allow` record with `from_stage`, `to_stage`, and `decision: "allow"`

#### Scenario: Denied transition audited

- **WHEN** a stage transition is denied due to `allowed_next_stages` violation
- **THEN** the audit log contains a `stage.transition.deny` record with `from_stage`, `to_stage`, `decision: "deny"`, and `error_bucket: "stage_transition_not_allowed"`

#### Scenario: Denied transitions excluded from stage_history

- **WHEN** a stage transition is denied
- **THEN** the denied transition does NOT appear in `stage_history` and the previous stage is NOT added to `exited_stages`

### Requirement: Stage-specific errors MUST be distinguishable

Stage transition errors SHALL use specific error buckets that distinguish between different failure modes. The system MUST NOT hide stage errors as generic tool availability errors.

#### Scenario: Error buckets distinguish failure modes

- **WHEN** stage transition failures occur
- **THEN** the system returns distinct error buckets: `stage_transition_not_allowed` (not in allowlist or terminal stage), `stage_not_found` (target doesn't exist), `skill_has_no_stages` (no-stage skill), `stage_not_initialized` (current_stage is None), `invalid_initial_stage` (enable_skill with bad initial_stage)

#### Scenario: Stage errors not masked as tool errors

- **WHEN** a stage transition is denied
- **THEN** the error response uses a stage-specific error bucket and does NOT return a generic `tool_not_available` or similar error
