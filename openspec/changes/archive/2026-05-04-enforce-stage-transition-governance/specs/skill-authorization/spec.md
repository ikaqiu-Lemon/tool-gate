# skill-authorization Specification Delta

## ADDED Requirements

### Requirement: enable_skill MUST initialize stage state for staged skills

When `enable_skill` is called for a skill with stage definitions, the system SHALL initialize stage state. If the skill has `initial_stage` configured, the system SHALL enter that stage. If `initial_stage` is not configured, the system SHALL enter the first stage in the `stages` list. For skills without stage definitions, `current_stage` SHALL remain None and the skill SHALL use top-level `allowed_tools`.

#### Scenario: Enable staged skill with initial_stage

- **WHEN** a skill has `initial_stage: "analysis"` and stages defined, and the model calls `enable_skill(skill_id)`
- **THEN** the system creates a Grant, adds the skill to `skills_loaded` with `current_stage: "analysis"`, initializes `stage_entered_at` to current timestamp, initializes empty `stage_history` and `exited_stages`, recomputes `active_tools` to reflect analysis stage tools, and returns `{granted: true, allowed_tools: [...]}`

#### Scenario: Enable staged skill without initial_stage

- **WHEN** a skill has stages defined but no `initial_stage` field, and the model calls `enable_skill(skill_id)`
- **THEN** the system enters the first stage in the `stages` list, initializes `current_stage` to the first stage's `stage_id`, and initializes stage state fields

#### Scenario: Enable no-stage skill preserves compatibility

- **WHEN** a skill has no `stages` field and the model calls `enable_skill(skill_id)`
- **THEN** the system creates a Grant with `current_stage: None`, does NOT initialize `stage_history` or `exited_stages`, and `active_tools` reflects the skill's top-level `allowed_tools`

#### Scenario: Stage state persisted and restored

- **WHEN** a staged skill is enabled, then the session is saved and later restored
- **THEN** the restored session contains the skill's `current_stage`, `stage_entered_at`, `stage_history`, and `exited_stages`, and `active_tools` is recomputed based on the restored `current_stage`

### Requirement: enable_skill MUST fail safely for invalid initial_stage

If a skill's `initial_stage` references a stage that does not exist in the `stages` list, `enable_skill` MUST fail safely. The system SHALL return error bucket `invalid_initial_stage`, SHALL NOT create a Grant, SHALL NOT add the skill to `skills_loaded`, and SHALL NOT expose any tools.

#### Scenario: Invalid initial_stage denied

- **WHEN** a skill has `initial_stage: "nonexistent"` but "nonexistent" is not in the `stages` list, and the model calls `enable_skill(skill_id)`
- **THEN** the system returns `{granted: false, error: "invalid_initial_stage"}`, does NOT create a Grant, does NOT add to `skills_loaded`, and does NOT modify `active_tools`

#### Scenario: Valid initial_stage succeeds

- **WHEN** a skill has `initial_stage: "analysis"` and "analysis" exists in the `stages` list
- **THEN** `enable_skill` succeeds and enters the "analysis" stage

### Requirement: Runtime tool exposure MUST follow current_stage

For staged skills, `active_tools` SHALL be computed from the `current_stage`'s `allowed_tools`. When `current_stage` changes via `change_stage`, `active_tools` MUST be recomputed to reflect the new stage's tools. Expired grants SHALL NOT contribute tools. Global `blocked_tools` SHALL still be filtered from `active_tools`. No-stage skills SHALL continue using top-level `allowed_tools`.

#### Scenario: active_tools reflects current_stage

- **WHEN** a staged skill is in "analysis" stage with `allowed_tools: ["Read", "Grep"]`
- **THEN** `active_tools` includes Read and Grep (minus any blocked_tools)

#### Scenario: active_tools updates after change_stage

- **WHEN** a skill transitions from "analysis" (tools: ["Read", "Grep"]) to "execution" (tools: ["Edit", "Write"])
- **THEN** `active_tools` is recomputed and now includes Edit and Write instead of Read and Grep

#### Scenario: Expired grant does not contribute tools

- **WHEN** a staged skill's grant expires
- **THEN** the skill is removed from `skills_loaded` and its stage tools are removed from `active_tools`

#### Scenario: blocked_tools filtered from stage tools

- **WHEN** a stage's `allowed_tools` includes "Bash" but "Bash" is in global `blocked_tools`
- **THEN** "Bash" does NOT appear in `active_tools`

#### Scenario: No-stage skill uses top-level allowed_tools

- **WHEN** a no-stage skill is enabled with `allowed_tools: ["Read", "Write"]`
- **THEN** `active_tools` includes Read and Write, and does NOT depend on any stage
