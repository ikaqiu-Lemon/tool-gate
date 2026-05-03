# Event Coverage and Audit Trail Explanation

## Event Recording Dual-Track System

The simulator uses a **dual-track event recording system** by design:

### Track 1: In-Memory Events (`events.jsonl`)
**Source**: `ClaudeCodeSimulator._events` list  
**Scope**: All simulator orchestration events  
**Purpose**: Complete audit trail of simulator actions

Events recorded:
- `hook.session_start` - SessionStart hook invocation
- `hook.user_prompt_submit` - UserPromptSubmit hook invocation
- `hook.pre_tool_use` - PreToolUse hook invocation (includes decision)
- `hook.post_tool_use` - PostToolUse hook invocation
- `mcp.enable_skill` - MCP enable_skill tool call
- `mcp.disable_skill` - MCP disable_skill tool call
- `mcp.change_stage` - MCP change_stage tool call

**Written by**: `ClaudeCodeSimulator.generate_artifacts()`

### Track 2: SQLite Audit Log (`governance.db.audit_log`)
**Source**: `tg-hook` and `tg-mcp` subprocesses  
**Scope**: Governance runtime events  
**Purpose**: Persistent governance state and audit trail

Events recorded by governance runtime:
- `session.start` - Session initialization
- `session.end` - Session cleanup
- `skill.read` - Skill metadata read
- `skill.enable` - Skill enablement
- `skill.disable` - Skill disablement
- `grant.expire` - Grant TTL expiration
- `grant.revoke` - Grant revocation
- `tool.call` - Tool invocation attempt
- `stage.change` - Stage transition

**Written by**: `tg-hook` and `tg-mcp` via SQLite INSERT

## Why Event Counts Differ

**This is by design**, not a bug:

1. **Different granularity**: 
   - `events.jsonl` tracks simulator orchestration (hook/MCP subprocess invocations)
   - `audit_log` tracks governance runtime decisions (policy evaluation, grant lifecycle)

2. **Different writers**:
   - `events.jsonl` written by Python simulator
   - `audit_log` written by Rust governance runtime

3. **Different purposes**:
   - `events.jsonl` proves subprocess isolation and protocol boundaries
   - `audit_log` proves governance policy enforcement and state transitions

## Example: Stage C Verification

```
events.jsonl: 4 events
  - hook.session_start
  - hook.user_prompt_submit
  - hook.pre_tool_use
  - hook.post_tool_use

audit_log: 2 entries
  - session.start (from SessionStart hook)
  - (UserPromptSubmit may not write to audit_log if no state change)
```

**Why fewer audit_log entries?**  
Not every hook invocation results in a governance state change. The governance runtime only writes to `audit_log` when there's a meaningful state transition (session creation, grant creation, policy decision, etc.).

## Stage D Verification Strategy

### Dual-Track Verification
Both tracks must be verified:

1. **events.jsonl verification**:
   - Proves simulator orchestration is complete
   - Proves subprocess invocations happened
   - Proves protocol boundaries are respected

2. **audit_log verification**:
   - Proves governance runtime processed events
   - Proves policy decisions were made
   - Proves state transitions occurred

### Canonical Event Coverage (9 types)
Stage D scenarios must collectively cover all 9 canonical audit events in `audit_log`:

| Event Type | Scenario | Verification Method |
|------------|----------|---------------------|
| session.start | All | Query audit_log for event_type='session.start' |
| session.end | Scenario 03 | Query audit_log for event_type='session.end' |
| skill.read | Scenario 01 | Query audit_log for event_type='skill.read' |
| skill.enable | Scenarios 01, 02 | Query audit_log for event_type='skill.enable' |
| skill.disable | Scenario 03 | Query audit_log for event_type='skill.disable' |
| grant.expire | Scenario 03 | Query audit_log for event_type='grant.expire' |
| grant.revoke | Scenario 03 | Query audit_log for event_type='grant.revoke' |
| tool.call | All | Query audit_log for event_type='tool.call' |
| stage.change | Scenario 02 | Query audit_log for event_type='stage.change' |

### Verification Criteria

**Pass criteria**:
- All 9 canonical event types appear in `audit_log` across all scenarios
- `events.jsonl` contains corresponding simulator orchestration events
- State snapshots show expected state transitions
- Artifacts are generated and parseable

**Fail criteria**:
- Missing canonical event types in `audit_log`
- `events.jsonl` missing expected orchestration events
- State snapshots inconsistent with expected state
- Artifacts missing or malformed

## Summary

- **events.jsonl**: Simulator orchestration audit trail (Python-side)
- **audit_log**: Governance runtime audit trail (Rust-side)
- **Both are correct**: They track different layers of the system
- **Stage D verification**: Must check both tracks for completeness
