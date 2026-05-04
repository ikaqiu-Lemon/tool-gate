# skill-authorization Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
### Requirement: Enable skill with policy evaluation

The `enable_skill` MCP tool SHALL accept `skill_id`, optional `reason`, optional `scope` (default "session"), and optional `ttl` (seconds). The system MUST evaluate the request against the policy engine before granting. On success, the system SHALL create a Grant record, add the skill to `skills_loaded`, recompute `active_tools`, and return the granted status with the list of allowed tools.

#### Scenario: Auto-grant for low-risk skill

- **WHEN** the model calls `enable_skill("repo-read")` and "repo-read" has `risk_level: "low"`
- **THEN** the system auto-grants without requiring a reason, creates a Grant with `granted_by: "auto"`, and returns `{granted: true, allowed_tools: ["Read", "Glob", "Grep"]}`

#### Scenario: Reason required for medium-risk skill

- **WHEN** the model calls `enable_skill("code-edit")` without a reason and "code-edit" has `risk_level: "medium"`
- **THEN** the system returns `{granted: false, decision: "reason_required"}` indicating a reason must be provided

#### Scenario: Medium-risk skill with reason

- **WHEN** the model calls `enable_skill("code-edit", reason="Need to fix bug in auth module")`
- **THEN** the system grants the skill and returns `{granted: true, allowed_tools: [...]}`

#### Scenario: High-risk skill requires user approval

- **WHEN** the model calls `enable_skill("deploy-prod")` and "deploy-prod" has `risk_level: "high"`
- **THEN** the system returns a decision requiring user confirmation via Claude Code's permission prompt

#### Scenario: Enable already-enabled skill

- **WHEN** the model calls `enable_skill("repo-read")` when "repo-read" is already in `skills_loaded`
- **THEN** the system returns the current grant status without creating a duplicate Grant

### Requirement: Disable skill and revoke grant

The `disable_skill` MCP tool SHALL accept a `skill_id`, revoke its corresponding Grant, remove the skill from `skills_loaded`, and recompute `active_tools`.

#### Scenario: Disable an enabled skill

- **WHEN** "repo-read" is enabled and the model calls `disable_skill("repo-read")`
- **THEN** the Grant status becomes "revoked", "repo-read" is removed from `skills_loaded`, `active_tools` no longer contains Read/Glob/Grep (unless another enabled skill also allows them), and the system returns `{disabled: true}`

#### Scenario: Disable a skill that is not enabled

- **WHEN** the model calls `disable_skill("repo-read")` but "repo-read" is not in `skills_loaded`
- **THEN** the system returns `{disabled: false}` with a message indicating the skill was not enabled

### Requirement: Query active grants

The `grant_status` MCP tool SHALL return all active Grant records for the current session. Each record MUST include: `grant_id`, `skill_id`, `scope`, `ttl_seconds`, `expires_at`, `status`, and `granted_by`.

#### Scenario: Multiple active grants

- **WHEN** "repo-read" and "web-search" are both enabled and the model calls `grant_status`
- **THEN** the system returns a list of 2 Grant records, each with `status: "active"` and correct expiration times

#### Scenario: No active grants

- **WHEN** no skills are enabled and the model calls `grant_status`
- **THEN** the system returns an empty list

### Requirement: Policy-based authorization evaluation

The policy engine SHALL evaluate enable_skill requests using the following precedence: (1) check global blocked list, (2) check skill-specific policy override, (3) apply risk-level default thresholds (`low → auto`, `medium → reason`, `high → approval`). A skill in the blocked list MUST always be denied.

#### Scenario: Blocked skill denied regardless of risk level

- **WHEN** "dangerous-tool" is in the policy's `blocked_tools` list and the model calls `enable_skill("dangerous-tool")`
- **THEN** the system returns `{granted: false, decision: "denied"}` regardless of the skill's risk_level

#### Scenario: Skill-specific policy overrides default

- **WHEN** "special-tool" has `risk_level: "high"` but its skill-specific policy sets `auto_grant: true`
- **THEN** `enable_skill("special-tool")` is auto-granted without user approval

### Requirement: Grant TTL expiration

Each Grant MUST have a TTL. When a Grant's TTL expires, the system SHALL mark its status as "expired". Expired grants MUST be cleaned up during the next grant lifecycle check (SessionStart or UserPromptSubmit). The associated skill MUST be removed from `skills_loaded` and `active_tools` MUST be recomputed.

#### Scenario: Grant expires between turns

- **WHEN** "repo-read" is enabled with `ttl: 60` and 90 seconds pass before the next user message
- **THEN** the UserPromptSubmit hook detects the expired grant, removes "repo-read" from `skills_loaded`, and recomputes `active_tools` without repo-read's tools

#### Scenario: Turn-scoped grant expires after one turn

- **WHEN** "repo-read" is enabled with `scope: "turn"`
- **THEN** the grant is valid only for the current model response turn; the next UserPromptSubmit hook marks it expired and removes the skill

### Requirement: Grant max TTL enforcement

The policy engine SHALL enforce a maximum TTL per skill (from skill-specific policy or global default). If the requested TTL exceeds the maximum, the system MUST cap it to the maximum value.

#### Scenario: Requested TTL exceeds maximum

- **WHEN** the model calls `enable_skill("repo-read", ttl=99999)` and the policy max_ttl for "repo-read" is 7200
- **THEN** the created Grant has `ttl_seconds: 7200` (capped)

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

