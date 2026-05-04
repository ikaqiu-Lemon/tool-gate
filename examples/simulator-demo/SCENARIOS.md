# Simulator Demo Scenarios

This document defines the three core scenarios that the simulator will execute, derived from examples 01, 02, and 03.

---

## Scenario 01: Discovery (from example 01-knowledge-link)

### Overview

**Purpose**: Demonstrate basic skill discovery, low-risk auto-grant, and runtime available tool set enforcement.

**Derived from**: `examples/01-knowledge-link/`

**User context**: User wants to search for RAG-related documents in their knowledge base.

### Expected Flow

#### 1. Session Initialization
- **Action**: SessionStart hook invocation
- **Expected**: Hook loads state, returns additionalContext with skill catalog
- **Audit**: `session.start` event

#### 2. Skill Discovery
- **Action**: list_skills (MCP meta-tool)
- **Expected**: Returns list of available skills including "yuque-knowledge-link"
- **Audit**: `skill.list` event (if tracked)

#### 3. Skill Understanding
- **Action**: read_skill("yuque-knowledge-link") (MCP meta-tool)
- **Expected**: Returns SOP, allowed_tools: [yuque_search, yuque_list_docs, yuque_get_doc], risk_level: low
- **Audit**: `skill.read` event with risk=low

#### 4. Skill Enablement (Auto-Grant)
- **Action**: enable_skill("yuque-knowledge-link") (MCP meta-tool)
- **Expected**: Policy evaluation → low risk → auto-grant, creates Grant with ttl=3600
- **Audit**: `skill.enable` event with decision=granted, granted_by=auto

#### 5. Active Tools Recompute
- **Action**: UserPromptSubmit hook invocation
- **Expected**: Hook reads grants from SQLite, recomputes active_tools = meta_tools + [yuque_search, yuque_list_docs, yuque_get_doc]
- **Audit**: None (hook doesn't write audit for UserPromptSubmit)

#### 6. Authorized Tool Call (Allow)
- **Action**: PreToolUse("yuque_search", {query: "RAG", type: "doc"})
- **Expected**: Hook checks active_tools → yuque_search is in runtime available tool set → allow
- **Audit**: None (PreToolUse doesn't write audit on allow)
- **Action**: PostToolUse("yuque_search")
- **Expected**: Hook writes audit event, updates last_used_at
- **Audit**: `tool.call` event with tool=yuque_search, decision=allow

#### 7. Unauthorized Tool Call (Deny)
- **Action**: PreToolUse("rag_paper_search", {query: "RAG survey 2026"})
- **Expected**: Hook checks active_tools → rag_paper_search NOT in runtime available tool set → deny with guidance
- **Audit**: `tool.call` event with tool=rag_paper_search, decision=deny, error_bucket=tool_not_available

#### 8. Session End
- **Action**: Generate session artifacts
- **Expected**: Read audit_log from SQLite, generate events.jsonl, audit_summary.md, metrics.json, state snapshots
- **Audit**: `session.end` event

### Expected Audit Events

1. `session.start` - Session initialization
2. `skill.read` - Read yuque-knowledge-link skill (risk=low)
3. `skill.enable` - Enable yuque-knowledge-link (decision=granted, granted_by=auto)
4. `tool.call` - yuque_search (decision=allow)
5. `tool.call` - rag_paper_search (decision=deny, error_bucket=tool_not_available)
6. `session.end` - Session termination

### Expected Session Artifacts

- `events.jsonl`: 6 events in temporal order
- `audit_summary.md`: Session metadata, skill funnel (1 shown, 1 read, 1 enabled), tool call statistics (1 allow, 1 deny)
- `metrics.json`: shown_skills=1, read_skills=1, enabled_skills=1, total_tool_calls=2, successful_tool_calls=1, denied_tool_calls=1, tool_not_available_count=1
- `state_before.json`: Empty grants, no skills loaded
- `state_after.json`: 1 grant (yuque-knowledge-link), 1 skill loaded

### Out of Scope for This Scenario

- Stage transitions (covered in Scenario 02)
- TTL expiration (covered in Scenario 03)
- Grant revocation (covered in Scenario 03)
- require_reason enforcement (covered in Scenario 02)
- approval_required denial (covered in Scenario 03)

---

## Scenario 02: Staged Workflow (from example 02-doc-edit-staged)

### Overview

**Purpose**: Demonstrate require_reason enforcement, stage transitions, and blocked_tools global red line.

**Derived from**: `examples/02-doc-edit-staged/`

**User context**: User wants to edit a document, but must first read it (analysis stage) before modifying it (execution stage).

### Expected Flow

#### 1. Session Initialization
- **Action**: SessionStart hook invocation
- **Expected**: Hook loads state, returns additionalContext with skill catalog
- **Audit**: `session.start` event

#### 2. Skill Enablement Without Reason (Deny)
- **Action**: enable_skill("yuque-doc-edit") without reason parameter (MCP meta-tool)
- **Expected**: Policy evaluation → require_reason=true → deny (reason_missing)
- **Audit**: `skill.enable` event with decision=denied, reason=reason_missing

#### 3. Skill Enablement With Reason (Grant)
- **Action**: enable_skill("yuque-doc-edit", reason="Update related docs section") (MCP meta-tool)
- **Expected**: Policy evaluation → require_reason satisfied → grant with stage=analysis (default stage)
- **Audit**: `skill.enable` event with decision=granted, stage=analysis

#### 4. Active Tools Recompute (Analysis Stage)
- **Action**: UserPromptSubmit hook invocation
- **Expected**: Hook reads grants, recomputes active_tools = meta_tools + [yuque_get_doc, yuque_list_docs] (analysis stage tools)
- **Audit**: None

#### 5. Read Tool Call (Allow in Analysis Stage)
- **Action**: PreToolUse("yuque_get_doc", {doc_id: "rag-overview-v2"})
- **Expected**: Hook checks active_tools → yuque_get_doc is in analysis stage available tools → allow
- **Audit**: None (PreToolUse doesn't write on allow)
- **Action**: PostToolUse("yuque_get_doc")
- **Audit**: `tool.call` event with tool=yuque_get_doc, decision=allow, stage=analysis

#### 6. Write Tool Call (Deny in Analysis Stage)
- **Action**: PreToolUse("yuque_update_doc", {doc_id: "rag-overview-v2", body: "..."})
- **Expected**: Hook checks active_tools → yuque_update_doc NOT in analysis stage available tools → deny with guidance
- **Audit**: `tool.call` event with tool=yuque_update_doc, decision=deny, error_bucket=tool_not_available, stage=analysis

#### 7. Stage Transition
- **Action**: change_stage("yuque-doc-edit", "execution") (MCP meta-tool)
- **Expected**: State manager updates stage to execution, returns new active_tools
- **Audit**: `stage.change` event with skill=yuque-doc-edit, from=analysis, to=execution

#### 8. Active Tools Recompute (Execution Stage)
- **Action**: UserPromptSubmit hook invocation
- **Expected**: Hook reads grants, recomputes active_tools = meta_tools + [yuque_get_doc, yuque_update_doc] (execution stage tools)
- **Audit**: None

#### 9. Write Tool Call (Allow in Execution Stage)
- **Action**: PreToolUse("yuque_update_doc", {doc_id: "rag-overview-v2", body: "..."})
- **Expected**: Hook checks active_tools → yuque_update_doc is in execution stage available tools → allow
- **Audit**: None
- **Action**: PostToolUse("yuque_update_doc")
- **Audit**: `tool.call` event with tool=yuque_update_doc, decision=allow, stage=execution

#### 10. Blocked Tool Call (Deny via Global Red Line)
- **Action**: PreToolUse("run_command", {cmd: "df -h"})
- **Expected**: Hook checks blocked_tools → run_command is globally blocked → deny (reason=blocked)
- **Audit**: `tool.call` event with tool=run_command, decision=deny, error_bucket=blocked

#### 11. Session End
- **Action**: Generate session artifacts
- **Audit**: `session.end` event

### Expected Audit Events

1. `session.start` - Session initialization
2. `skill.enable` - yuque-doc-edit (decision=denied, reason=reason_missing)
3. `skill.enable` - yuque-doc-edit (decision=granted, stage=analysis)
4. `tool.call` - yuque_get_doc (decision=allow, stage=analysis)
5. `tool.call` - yuque_update_doc (decision=deny, error_bucket=tool_not_available, stage=analysis)
6. `stage.change` - yuque-doc-edit (from=analysis, to=execution)
7. `tool.call` - yuque_update_doc (decision=allow, stage=execution)
8. `tool.call` - run_command (decision=deny, error_bucket=blocked)
9. `session.end` - Session termination

### Expected Session Artifacts

- `events.jsonl`: 9 events in temporal order
- `audit_summary.md`: Skill funnel (1 shown, 1 read, 1 enabled, 1 denied), stage transitions (1), tool call statistics (2 allow, 2 deny)
- `metrics.json`: enabled_skills=1, denied_skills=1, reason_missing_count=1, total_tool_calls=4, successful_tool_calls=2, denied_tool_calls=2, tool_not_available_count=1, blocked_tools_count=1, stage_changes=1
- `state_before.json`: Empty grants
- `state_after.json`: 1 grant (yuque-doc-edit, stage=execution)

### Out of Scope for This Scenario

- Auto-grant (covered in Scenario 01)
- TTL expiration (covered in Scenario 03)
- Grant revocation (covered in Scenario 03)
- approval_required denial (covered in Scenario 03)

---

## Scenario 03: Lifecycle and Risk (from example 03-lifecycle-and-risk)

### Overview

**Purpose**: Demonstrate TTL expiration, grant revocation with strict ordering, and high-risk skill denial.

**Derived from**: `examples/03-lifecycle-and-risk/`

**User context**: User continues a long-running session where a previous grant has expired, then cleans up permissions and attempts a high-risk operation.

### Expected Flow

#### 1. Session Initialization (With Expired Grant)
- **Setup**: Pre-create a grant for "yuque-knowledge-link" with expires_at in the past
- **Action**: SessionStart hook invocation
- **Expected**: Hook loads state, cleanup_expired_grants marks grant as expired
- **Audit**: `session.start` event

#### 2. Active Tools Recompute (Expired Grant Cleanup)
- **Action**: UserPromptSubmit hook invocation
- **Expected**: Hook runs cleanup_expired_grants, writes grant.expire event, recomputes active_tools (expired skill's tools removed)
- **Audit**: `grant.expire` event with skill=yuque-knowledge-link, reason=ttl

#### 3. Expired Tool Call (Deny)
- **Action**: PreToolUse("yuque_search", {query: "RAG"})
- **Expected**: Hook checks active_tools → yuque_search NOT in runtime available tool set (expired) → deny with guidance
- **Audit**: `tool.call` event with tool=yuque_search, decision=deny, error_bucket=tool_not_available

#### 4. Re-Authorization
- **Action**: enable_skill("yuque-knowledge-link") (MCP meta-tool)
- **Expected**: Policy evaluation → low risk → auto-grant, creates new Grant
- **Audit**: `skill.enable` event with decision=granted, granted_by=auto

#### 5. Active Tools Recompute (Re-Authorized)
- **Action**: UserPromptSubmit hook invocation
- **Expected**: Hook reads new grant, recomputes active_tools (yuque tools restored)
- **Audit**: None

#### 6. Grant Revocation (Strict Ordering)
- **Action**: disable_skill("yuque-doc-edit") (MCP meta-tool)
- **Expected**: GrantManager.revoke_grant writes grant.revoke, then StateManager.unload_skill writes skill.disable
- **Audit**: `grant.revoke` event with skill=yuque-doc-edit, then `skill.disable` event (strict ordering: revoke timestamp < disable timestamp)

#### 7. High-Risk Skill Enablement (Deny)
- **Action**: enable_skill("yuque-bulk-delete", reason="Clean up old docs") (MCP meta-tool)
- **Expected**: Policy evaluation → approval_required=true → deny (approval_required)
- **Audit**: `skill.enable` event with decision=denied, reason=approval_required

#### 8. Session End
- **Action**: Generate session artifacts
- **Audit**: `session.end` event

### Expected Audit Events

1. `session.start` - Session initialization
2. `grant.expire` - yuque-knowledge-link (reason=ttl)
3. `tool.call` - yuque_search (decision=deny, error_bucket=tool_not_available)
4. `skill.enable` - yuque-knowledge-link (decision=granted, granted_by=auto)
5. `grant.revoke` - yuque-doc-edit
6. `skill.disable` - yuque-doc-edit (timestamp > grant.revoke timestamp)
7. `skill.enable` - yuque-bulk-delete (decision=denied, reason=approval_required)
8. `session.end` - Session termination

### Expected Session Artifacts

- `events.jsonl`: 8 events in temporal order
- `audit_summary.md`: Skill funnel (enabled=1, disabled=1, denied=1), grant lifecycle (1 expire, 1 revoke), tool call statistics (0 allow, 1 deny)
- `metrics.json`: enabled_skills=1, disabled_skills=1, denied_skills=1, grant_expire_count=1, grant_revoke_count=1, total_tool_calls=1, denied_tool_calls=1, tool_not_available_count=1
- `state_before.json`: 1 expired grant (yuque-knowledge-link)
- `state_after.json`: 1 grant (yuque-knowledge-link, re-authorized)

### Out of Scope for This Scenario

- Auto-grant demonstration (covered in Scenario 01, but used here for re-authorization)
- Stage transitions (covered in Scenario 02)
- require_reason enforcement (covered in Scenario 02)
- blocked_tools (covered in Scenario 02)

---

## Audit Event Coverage Across All Scenarios

### 9 Audit Event Types

The simulator must produce all 9 canonical audit event types across the three scenarios:

| Event Type | Scenario 01 | Scenario 02 | Scenario 03 | Description |
|------------|:-----------:|:-----------:|:-----------:|-------------|
| `session.start` | ✓ | ✓ | ✓ | Session initialization |
| `session.end` | ✓ | ✓ | ✓ | Session termination |
| `skill.read` | ✓ | - | - | Read skill SOP and metadata |
| `skill.enable` | ✓ (granted) | ✓ (denied + granted) | ✓ (granted + denied) | Skill enablement decision |
| `skill.disable` | - | - | ✓ | Skill disabled and unloaded |
| `grant.expire` | - | - | ✓ | Grant expired due to TTL |
| `grant.revoke` | - | - | ✓ | Grant explicitly revoked |
| `tool.call` | ✓ (allow + deny) | ✓ (allow + deny) | ✓ (deny) | Tool call authorization decision |
| `stage.change` | - | ✓ | - | Stage transition |

**Coverage**: All 9 event types are covered across the three scenarios.

### Core Happy Path Events (Must Appear in Every Scenario)

1. `session.start` - Every scenario starts with session initialization
2. `session.end` - Every scenario ends with session termination
3. `skill.enable` - Every scenario enables at least one skill
4. `tool.call` - Every scenario attempts at least one tool call

### Scenario-Specific Events

- **Scenario 01 only**: `skill.read` (explicit read_skill call)
- **Scenario 02 only**: `stage.change` (stage transition)
- **Scenario 03 only**: `grant.expire`, `grant.revoke`, `skill.disable` (lifecycle events)

---

## Verification Criteria

Each scenario is considered successful if:

1. ✅ All expected audit events are present in SQLite audit_log table
2. ✅ Audit events have correct timestamps (temporal ordering)
3. ✅ Allow/deny decisions match expectations
4. ✅ Session artifacts are generated (events.jsonl, audit_summary.md, metrics.json, state snapshots)
5. ✅ State snapshots reflect expected grants and skills
6. ✅ Metrics counters match actual event counts

---

## Implementation Notes

### Subprocess Boundaries

- **Hook invocations**: Each SessionStart, UserPromptSubmit, PreToolUse, PostToolUse spawns a separate tg-hook subprocess
- **MCP server**: Single tg-mcp subprocess persists across all meta-tool calls within a scenario
- **SQLite**: Shared state storage, written by MCP and hooks, read by both

### Protocol Formats

- **Hook protocol**: JSON events via stdin, JSON responses via stdout (not JSON-RPC, just plain JSON)
- **MCP protocol**: stdio protocol with initialization handshake, then JSON-RPC requests/responses

### Time Progression

- **Scenario 03 TTL expiration**: Pre-create grant with expires_at in the past, no need to wait for real time to pass
