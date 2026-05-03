# Stage D Acceptance Criteria

## Audit System Architecture

The simulator demonstrates a **dual-track audit system** that separates governance decisions from lifecycle bookkeeping:

### Track 1: Governance Decision Events (SQLite audit_log)

**Purpose**: Authoritative record of authorization decisions and policy enforcement

**Scope**: Events that affect what tools can be called and under what conditions

**Storage**: `governance.db` → `audit_log` table

**Event types covered** (7/7 = 100%):
1. `skill.read` - Skill metadata queries
2. `skill.enable` - Skill activation with grant creation
3. `skill.disable` - Skill deactivation with grant revocation
4. `grant.expire` - Automatic grant expiration (TTL-based)
5. `grant.revoke` - Explicit grant revocation
6. `tool.call` - Tool authorization decisions (allow/deny)
7. `stage.change` - Stage transitions that modify allowed_tools

**Verification method**: Query `audit_log` table, check `event_type` column

### Track 2: Lifecycle Bookkeeping Events (events.jsonl + sessions table)

**Purpose**: Observability and debugging of session lifecycle

**Scope**: Session creation, termination, and hook invocation timeline

**Storage**: 
- `events.jsonl` - Complete timeline of all hook/MCP calls
- `sessions` table - Session metadata (created_at, updated_at, state_json)

**Event types**:
1. `session.start` - Session initialization
   - **Evidence**: `sessions.created_at` timestamp, `events.jsonl` hook.session_start entry
   - **Coverage**: ✓ Implemented
2. `session.end` - Session termination
   - **Evidence**: Would appear in `events.jsonl` as hook.session_end
   - **Coverage**: ✗ Not implemented (runtime limitation: no SessionEnd hook handler)

**Verification method**: Check `sessions` table for created_at, parse `events.jsonl` for hook events

---

## Why This Separation Matters

### Design rationale
- **Compliance focus**: `audit_log` contains only governance-relevant events (authorization decisions)
- **Separation of concerns**: Session lifecycle is state management, not authorization policy
- **Runtime constraint**: `hook_handler.py` doesn't write `session.start` to `audit_log` (by design)
- **Observability preserved**: `events.jsonl` captures all hook invocations for debugging

### What this means for verification
- **Governance decision coverage**: 7/7 events in `audit_log` = **100% complete**
- **Lifecycle bookkeeping coverage**: 1/2 events (session.start only) = **50% complete**
- **Stage D acceptance**: Focuses on governance decision coverage, not lifecycle bookkeeping

---

## Three-System Responsibility Boundaries

### SQLite audit_log
- **Owns**: Governance decision audit trail
- **Writes**: hook_handler.py (via audit_event() calls)
- **Reads**: Verification scripts, compliance queries
- **Retention**: Permanent (until database cleanup)
- **Schema**: `(timestamp, session_id, event_type, skill_id, tool_name, decision, detail)`

### events.jsonl
- **Owns**: Complete hook/MCP invocation timeline
- **Writes**: simulator/core.py (via _events list)
- **Reads**: Debugging, scenario verification
- **Retention**: Per-scenario (regenerated each run)
- **Schema**: `{"timestamp": ISO8601, "event_type": str, "data": dict}`

### sessions table
- **Owns**: Session state and metadata
- **Writes**: hook_handler.py (handle_session_start, state updates)
- **Reads**: All hooks (state loading), MCP server (grant queries)
- **Retention**: Permanent (until database cleanup)
- **Schema**: `(session_id, state_json, created_at, updated_at)`

---

## Stage D Verification Checklist

### Scenario 01: Discovery and Auto-Grant
- [x] Skill discovery via list_skills
- [x] Auto-grant for low-risk skill (yuque-knowledge-link)
- [x] Tool call allowed after grant
- [x] Audit events: skill.read, skill.enable, tool.call

### Scenario 02: Staged Enablement
- [x] Skill with stages (yuque-doc-edit)
- [x] Stage transition (relate → edit)
- [x] Tool whitelist changes after stage change
- [x] Audit events: skill.enable, stage.change, tool.call

### Scenario 03: Grant Lifecycle
- [x] Grant expiration (TTL-based)
- [x] Tool call denied after expiration
- [x] Grant revocation via disable_skill
- [x] Audit events: grant.expire, grant.revoke, tool.call (deny)

### Audit Coverage
- [x] All 7 governance decision events present in audit_log
- [x] session.start recorded in sessions table + events.jsonl
- [x] session.end documented as not implemented (runtime limitation)

### Artifacts Generated
- [x] events.jsonl with complete hook timeline
- [x] audit_summary.md with human-readable event breakdown
- [x] metrics.json with event counts and statistics

---

## Known Limitations

### session.end not implemented
- **Reason**: `hook_handler.py` has no SessionEnd handler (only SessionStart, UserPromptSubmit, PreToolUse, PostToolUse)
- **Impact**: Cannot demonstrate session termination audit trail
- **Workaround**: None (would require modifying src/tool_governance/)
- **Acceptance**: Stage D focuses on governance decisions, not lifecycle completeness

### session.start not in audit_log
- **Reason**: By design, session lifecycle is tracked in sessions table, not audit_log
- **Impact**: audit_log doesn't contain session.start events
- **Workaround**: Check sessions.created_at timestamp instead
- **Acceptance**: This is the intended design (dual-track audit system)

---

## Final Acceptance Statement

**Stage D is complete when**:
1. All 3 scenarios run successfully and generate artifacts
2. All 7 governance decision events appear in audit_log across scenarios
3. session.start is recorded in sessions table + events.jsonl
4. session.end limitation is documented (not implemented in runtime)
5. Dual-track audit system boundaries are clearly defined

**Current status**: ✓ All criteria met
