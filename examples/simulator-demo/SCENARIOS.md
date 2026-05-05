# Simulator Demo Scenarios

This document describes the three scenarios that demonstrate Stage-first governance capabilities through subprocess isolation.

## Overview

Each scenario demonstrates specific aspects of the Stage-first governance system:

1. **Scenario 01: Discovery** - Skill discovery, Stage-first metadata (staged vs no-stage skills)
2. **Scenario 02: Staged** - Stage transition governance (legal/illegal transitions, active_tools changes)
3. **Scenario 03: Lifecycle** - Terminal stages, TTL expiration, and stage state persistence

All scenarios use real subprocess boundaries (tg-hook and tg-mcp) and generate complete audit trails in `governance.db` and `events.jsonl`.

---

## Scenario 01: Discovery

### Purpose

Demonstrate Stage-first metadata discovery for both staged and no-stage skills, and verify unauthorized tool rejection.

### Skills Used

- **yuque-doc-edit-staged**: A staged skill with 3 stages (analysis → execution → verification)
- **yuque-knowledge-link**: A no-stage skill with skill-level allowed_tools

### Expected Flow

#### 1. Skill Discovery
- **Action**: `list_skills` (MCP meta-tool)
- **Expected**: Returns 2 skills (yuque-doc-edit-staged, yuque-knowledge-link)
- **Verification**: Both staged and no-stage skills are discovered

#### 2. Read Staged Skill Metadata
- **Action**: `read_skill("yuque-doc-edit-staged")` (MCP meta-tool)
- **Expected**: Returns Stage-first metadata:
  - `initial_stage: "analysis"`
  - `stages: ["analysis", "execution", "verification"]`
  - Each stage has `allowed_tools` list
  - `verification` stage has `allowed_next_stages: []` (terminal)
- **Verification**: Staged skill exposes stage workflow metadata

#### 3. Read No-Stage Skill Metadata
- **Action**: `read_skill("yuque-knowledge-link")` (MCP meta-tool)
- **Expected**: Returns fallback behavior:
  - No `stages` field
  - Skill-level `allowed_tools` list
- **Verification**: No-stage skill uses traditional skill-level tool list

#### 4. Enable Staged Skill
- **Action**: `enable_skill("yuque-doc-edit-staged")` (MCP meta-tool)
- **Expected**: Grant created with `current_stage: "analysis"` (initial_stage)
- **Verification**: Staged skill enters initial_stage on enable

#### 5. Verify Active Tools (Analysis Stage)
- **Action**: `PreToolUse` hook with analysis-stage tool
- **Expected**: Tool allowed (in current stage's allowed_tools)
- **Verification**: Active tools filtered by current_stage

#### 6. Unauthorized Tool Rejection
- **Action**: `PreToolUse` hook with execution-stage tool (while in analysis stage)
- **Expected**: Tool denied with `tool_not_available` error
- **Verification**: Tools from other stages are not available

### Key Validations

- ✅ Staged skills expose `initial_stage`, `stages`, and per-stage `allowed_tools`
- ✅ No-stage skills use skill-level `allowed_tools` (fallback behavior)
- ✅ Terminal stages have `allowed_next_stages: []`
- ✅ Unauthorized tools (from different stages) are rejected

---

## Scenario 02: Staged Workflow

### Purpose

Demonstrate stage transition governance: legal vs illegal transitions, active_tools changes, and stage state persistence.

### Skills Used

- **yuque-doc-edit-staged**: 3-stage workflow (analysis → execution → verification)

### Expected Flow

#### 1. Enable Skill
- **Action**: `enable_skill("yuque-doc-edit-staged")` (MCP meta-tool)
- **Expected**: Grant created with `current_stage: "analysis"`
- **Verification**: Skill enters initial_stage

#### 2. Verify Initial Stage Tools
- **Action**: `PreToolUse` hook with `yuque_get_doc` (analysis tool)
- **Expected**: Tool allowed
- **Verification**: Analysis stage tools are active

#### 3. Attempt Illegal Transition
- **Action**: `change_stage("yuque-doc-edit-staged", "verification")` (MCP meta-tool)
- **Expected**: Transition denied (verification not in analysis.allowed_next_stages)
- **Verification**: Stage transition governance enforces allowed_next_stages

#### 4. Legal Transition to Execution
- **Action**: `change_stage("yuque-doc-edit-staged", "execution")` (MCP meta-tool)
- **Expected**: Transition allowed, `current_stage` updated to "execution"
- **Verification**: Legal transitions succeed

#### 5. Verify Execution Stage Tools
- **Action**: `PreToolUse` hook with `yuque_update_doc` (execution tool)
- **Expected**: Tool allowed (now in execution stage)
- **Verification**: Active tools change with current_stage

#### 6. Verify Analysis Tool Removed
- **Action**: `PreToolUse` hook with `yuque_get_doc` (analysis tool)
- **Expected**: Tool denied (no longer in current stage's allowed_tools)
- **Verification**: Previous stage's tools are removed

#### 7. Transition to Terminal Stage
- **Action**: `change_stage("yuque-doc-edit-staged", "verification")` (MCP meta-tool)
- **Expected**: Transition allowed, `current_stage` updated to "verification"
- **Verification**: Can enter terminal stage

#### 8. Verify Stage State Persistence
- **Action**: Read `sessions` table `state_json` field
- **Expected**: `skills_loaded` contains:
  - `current_stage: "verification"`
  - `stage_history: ["analysis", "execution", "verification"]`
  - `exited_stages: ["analysis", "execution"]`
- **Verification**: Stage state is persisted in SQLite

### Key Validations

- ✅ Skill enters `initial_stage` on enable
- ✅ Active tools change with `current_stage`
- ✅ Illegal transitions are denied (not in `allowed_next_stages`)
- ✅ Legal transitions succeed and update `current_stage`
- ✅ Stage state persisted (`current_stage`, `stage_history`, `exited_stages`)

---

## Scenario 03: Lifecycle and Terminal Stages

### Purpose

Demonstrate terminal stage blocking, TTL expiration, and disable_skill cleanup.

### Skills Used

- **yuque-doc-edit-staged**: 3-stage workflow with terminal stage (verification)

### Expected Flow

#### 1. Enable and Transition to Terminal Stage
- **Action**: Enable skill, transition through analysis → execution → verification
- **Expected**: Skill reaches terminal stage (verification)
- **Verification**: Terminal stage is reachable

#### 2. Attempt Transition from Terminal Stage
- **Action**: `change_stage("yuque-doc-edit-staged", "analysis")` (MCP meta-tool)
- **Expected**: Transition denied (verification.allowed_next_stages is empty)
- **Verification**: Terminal stages block all transitions

#### 3. Verify Stage State Persistence
- **Action**: Read `sessions` table `state_json` field
- **Expected**: `current_stage: "verification"`, `stage_history` contains all 3 stages
- **Verification**: Terminal stage state is persisted

#### 4. Enable Skill with Short TTL
- **Action**: `enable_skill("yuque-knowledge-link", ttl=2)` (MCP meta-tool)
- **Expected**: Grant created with `expires_at` = now + 2 seconds
- **Verification**: Short-lived grants can be created

#### 5. Verify Tool Allowed Before Expiration
- **Action**: `PreToolUse` hook with `yuque_search` (immediately)
- **Expected**: Tool allowed (grant still active)
- **Verification**: Active grants contribute tools

#### 6. Wait for Expiration
- **Action**: Sleep 3 seconds
- **Expected**: Grant expires (expires_at < now)
- **Verification**: Time-based expiration

#### 7. Verify Tool Denied After Expiration
- **Action**: `PreToolUse` hook with `yuque_search` (after sleep)
- **Expected**: Tool denied (expired grant does not contribute tools)
- **Verification**: Expired grants do NOT contribute to active_tools

#### 8. Disable Skill
- **Action**: `disable_skill("yuque-doc-edit-staged")` (MCP meta-tool)
- **Expected**: Grant revoked, skill removed from `skills_loaded`
- **Verification**: disable_skill removes tools from active_tools

#### 9. Verify Disabled Skill Tools Removed
- **Action**: `PreToolUse` hook with any yuque-doc-edit-staged tool
- **Expected**: Tool denied (skill disabled)
- **Verification**: Disabled skills do not contribute tools

### Key Validations

- ✅ Terminal stages block all transitions (`allowed_next_stages: []`)
- ✅ Terminal stage state is persisted
- ✅ Expired grants (TTL) do NOT contribute tools to active_tools
- ✅ `disable_skill` removes tools from active_tools
- ✅ Stage state persists across enable/disable cycles

---

## Verification Criteria

Each scenario is considered successful if:

1. ✅ All expected behaviors are verified through subprocess calls
2. ✅ Stage metadata is correctly exposed (staged vs no-stage skills)
3. ✅ Stage transitions follow governance rules (allowed_next_stages)
4. ✅ Active tools change with current_stage
5. ✅ Terminal stages block further transitions
6. ✅ Expired grants do not contribute tools
7. ✅ State persistence verified (governance.db queries)

---

## Implementation Notes

### Subprocess Boundaries

- **Hook invocations**: Each PreToolUse spawns a separate tg-hook subprocess
- **MCP server**: Single tg-mcp subprocess persists across all meta-tool calls within a scenario
- **SQLite**: Shared state storage (`governance.db`), written by MCP and hooks, read by both

### Protocol Formats

- **Hook protocol**: JSON events via stdin, JSON responses via stdout
- **MCP protocol**: stdio protocol with initialization handshake, then JSON-RPC requests/responses

### Audit Events

While the scenarios focus on behavioral verification, they also generate audit events:

- `skill.enable` - Skill enablement
- `stage.transition.allow` - Legal stage transition
- `stage.transition.deny` - Illegal stage transition
- `tool.call` - Tool authorization decisions
- `grant.expire` - TTL expiration (Scenario 03)
- `grant.revoke` - Explicit revocation via disable_skill (Scenario 03)

### Known Constraints

- **Expired grants in skills_loaded**: Expired grants are filtered at runtime (do not contribute tools) but remain in `sessions.state_json.skills_loaded` until explicit cleanup
- **Artifacts are runtime-generated**: `events.jsonl` and other artifacts are generated by running scenarios, not pre-created
- **No human approval workflow**: All scenarios use auto-grant or programmatic enable_skill
