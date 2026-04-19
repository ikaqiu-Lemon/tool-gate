# tool-surface-control Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
### Requirement: Per-turn prompt and tool rewriting via UserPromptSubmit

The UserPromptSubmit hook SHALL trigger on every user message, before the model responds. It MUST: (1) clean up expired grants, (2) recompute `active_tools` based on current `skills_loaded` and `current_stage`, (3) inject an `additionalContext` string containing the skill catalog summary and active tools prompt. This hook is the core control point corresponding to Skill-Hub's `wrap_model_call`.

#### Scenario: First turn with no skills enabled

- **WHEN** the user sends the first message in a session with no skills enabled
- **THEN** the hook injects additionalContext containing the skill catalog summary (names, descriptions, risk levels) and a guidance prompt to use `list_skills → read_skill → enable_skill`

#### Scenario: Turn after enabling a skill

- **WHEN** "repo-read" was enabled in the previous turn and the user sends a new message
- **THEN** the hook injects additionalContext listing "repo-read" as active with its allowed tools (Read, Glob, Grep), and the active_tools list is updated to include these tools

#### Scenario: Grant expires between turns

- **WHEN** "repo-read" had a short TTL that expired before the current user message
- **THEN** the hook removes "repo-read" from skills_loaded, recomputes active_tools without repo-read's tools, and the additionalContext reflects the updated state

### Requirement: active_tools full recomputation per turn

The `active_tools` list SHALL be fully recomputed each turn (not incrementally appended). The computation formula is: `active_tools = meta_tools ∪ ⋃{stage_tools(skill, current_stage) | skill ∈ skills_loaded} - blocked_tools`. Meta-tools (list_skills, read_skill, enable_skill, disable_skill, grant_status, run_skill_action, change_stage, refresh_skills) SHALL always be included.

#### Scenario: Multiple skills enabled

- **WHEN** "repo-read" (allowed: Read, Glob, Grep) and "web-search" (allowed: WebSearch, WebFetch) are both enabled
- **THEN** active_tools contains the union: meta-tools + Read + Glob + Grep + WebSearch + WebFetch

#### Scenario: Skill with stages uses current_stage tools

- **WHEN** "code-edit" is enabled with `current_stage: "analysis"` (allowed: Read, Glob, Grep)
- **THEN** active_tools includes Read, Glob, Grep from code-edit but NOT Edit or Write (which belong to the "execution" stage)

#### Scenario: Skill with stages but no current_stage set

- **WHEN** "code-edit" is enabled but `current_stage` is None
- **THEN** active_tools uses the first defined stage's allowed_tools as default

### Requirement: PreToolUse interception

The PreToolUse hook SHALL intercept every tool call and check whether the tool is in the current `active_tools` list. Meta-tools MUST always be allowed. Tools not in `active_tools` MUST be denied with a reason message guiding the model to the authorization flow.

#### Scenario: Allowed tool call passes through

- **WHEN** "repo-read" is enabled and the model calls the Read tool
- **THEN** the hook returns `{permissionDecision: "allow"}`

#### Scenario: Unauthorized tool call is denied

- **WHEN** no skill allowing Edit is enabled and the model calls the Edit tool
- **THEN** the hook returns `{permissionDecision: "deny", permissionDecisionReason: "Tool 'Edit' is not in active_tools..."}` with additionalContext guiding toward `read_skill → enable_skill`

#### Scenario: Meta-tool always allowed

- **WHEN** the model calls `mcp__tool-governance__list_skills` regardless of session state
- **THEN** the hook returns `{permissionDecision: "allow"}`

#### Scenario: MCP tool name normalization

- **WHEN** the model calls a tool with full MCP name `mcp__tool-governance__list_skills`
- **THEN** the hook extracts short name `list_skills`, recognizes it as a meta-tool, and allows it

### Requirement: Stage switching via change_stage

The `change_stage` MCP tool SHALL accept `skill_id` and `stage_id`. The skill MUST already be enabled and MUST have stages defined. On success, the system SHALL update `LoadedSkillInfo.current_stage` and recompute `active_tools`.

#### Scenario: Switch from analysis to execution stage

- **WHEN** "code-edit" is enabled at stage "analysis" and the model calls `change_stage("code-edit", "execution")`
- **THEN** `current_stage` updates to "execution", active_tools now includes Edit and Write (execution stage tools), and the system returns `{changed: true, new_active_tools: [...]}`

#### Scenario: Switch stage for skill without stages

- **WHEN** "repo-read" has no stages defined and the model calls `change_stage("repo-read", "any-stage")`
- **THEN** the system returns an error indicating the skill does not support stages

#### Scenario: Switch to nonexistent stage

- **WHEN** the model calls `change_stage("code-edit", "nonexistent")`
- **THEN** the system returns an error indicating the stage_id is not defined for this skill

#### Scenario: Switch stage for unenabled skill

- **WHEN** "code-edit" is not in skills_loaded and the model calls `change_stage("code-edit", "execution")`
- **THEN** the system returns an error indicating the skill must be enabled first

### Requirement: additionalContext output budget

The `additionalContext` injected by UserPromptSubmit SHALL be within 800 characters. Enabled skills MUST show more detail (current stage, allowed_tools). Unenabled skills MUST show only name, description, and risk_level.

#### Scenario: Context with many skills registered

- **WHEN** 10 skills are registered but only 1 is enabled
- **THEN** the additionalContext stays within 800 characters, with the enabled skill showing full detail and the remaining 9 showing only summary lines

