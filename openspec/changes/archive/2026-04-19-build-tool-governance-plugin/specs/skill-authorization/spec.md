## ADDED Requirements

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
