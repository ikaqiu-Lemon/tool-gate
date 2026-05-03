## Context

### Background

The tool-gate project has three complete example workspaces (01-knowledge-link, 02-doc-edit-staged, 03-lifecycle-and-risk) that demonstrate governance capabilities through end-to-end demos. These examples show *what* the governance system does, but they don't explicitly demonstrate *how* the subprocess isolation and protocol boundaries work.

The governance chain involves multiple process boundaries:
- **Agent**: Simulates Claude's decision-making (which skill to enable, which tool to call)
- **Hook subprocesses**: Short-lived processes invoked via `tg-hook` for SessionStart, UserPromptSubmit, PreToolUse, PostToolUse
- **MCP server subprocess**: Long-lived `tg-mcp` process handling meta-tool requests via stdio protocol
- **SQLite WAL**: Shared state storage enabling coordination between hook and MCP processes

### Current State

Each example workspace (01, 02, 03) has:
- `scripts/agent_realistic_simulation.py`: Agent that makes governance decisions
- `start_simulation.sh`: Entry point that sets environment variables and runs the agent
- `logs/session_*/`: Generated session artifacts (events.jsonl, audit_summary.md, metrics.json, state snapshots)

These examples work well for demonstrating governance *outcomes*, but they don't make the subprocess boundaries and protocol communication explicit.

### Constraints

- **No changes to src/**: The simulator is a demo tool, not a core implementation change
- **No changes to existing examples**: Examples 01, 02, 03 remain unchanged
- **Reuse existing infrastructure**: Use real `tg-hook` and `tg-mcp` binaries, not mocks
- **Demonstrate real protocols**: Show actual stdin/stdout JSON communication, not in-process function calls

### Stakeholders

- **Reviewers**: Need to understand how subprocess isolation works
- **New contributors**: Need to see the protocol boundaries to understand the architecture
- **Test infrastructure developers**: Need a foundation for replay and regression testing

---

## Goals / Non-Goals

### Goals

1. **Demonstrate subprocess isolation**: Show that hooks and MCP server run in separate processes with stdin/stdout boundaries
2. **Validate protocol correctness**: Prove that JSON-RPC (hooks) and stdio (MCP) protocols are followed correctly
3. **Verify shared state integrity**: Show that SQLite WAL enables consistent state across process boundaries
4. **Generate complete audit trails**: Produce all 9 event types with correct timestamps and ordering
5. **Support scenario coverage**: Enable scenarios derived from examples 01, 02, 03 without duplicating their code
6. **Provide verification mechanisms**: Validate audit completeness, state consistency, and protocol compliance

### Non-Goals

1. **Replace existing examples**: Examples 01, 02, 03 remain the canonical end-to-end demos
2. **Implement new governance features**: This is a demo tool, not a feature addition
3. **Modify src/ implementation**: No changes to PolicyEngine, GrantManager, ToolRewriter, etc.
4. **Create a testing framework**: This is a demonstration tool, not a test harness (though it could inform future test infrastructure)
5. **Support all possible scenarios**: Focus on the key governance paths from examples 01, 02, 03

---

## Decisions

### Decision 1: Four-layer architecture

**Choice**: Separate Agent, ClaudeCodeSimulator, Hook subprocess wrapper, and MCP subprocess wrapper into distinct layers.

**Rationale**:
- **Agent layer**: Simulates Claude's decision-making (which skill to enable, which tool to call). This is the "what to do" layer.
- **ClaudeCodeSimulator layer**: Orchestrates the governance chain (invoke hooks, call MCP, capture state). This is the "how to coordinate" layer.
- **Hook subprocess wrapper**: Manages `tg-hook` process lifecycle (spawn, stdin write, stdout read, cleanup). This is the "subprocess boundary" layer.
- **MCP subprocess wrapper**: Manages `tg-mcp` process lifecycle (spawn, stdio protocol, persistent connection). This is the "long-lived subprocess" layer.

**Alternatives considered**:
- **Monolithic agent**: Agent directly spawns subprocesses. Rejected because it mixes decision-making with subprocess management.
- **In-process simulation**: Call hook_handler and mcp_server functions directly. Rejected because it doesn't demonstrate subprocess isolation.

**Why this matters**: Separating layers makes it clear where process boundaries exist and how communication flows across them.

---

### Decision 2: Real subprocesses, not mocks

**Choice**: Use actual `tg-hook` and `tg-mcp` binaries installed via `pip install -e .`, not mock implementations.

**Rationale**:
- **Authenticity**: Demonstrates the real protocol boundaries that exist in production
- **Validation**: Proves that the installed binaries work correctly
- **Simplicity**: No need to maintain parallel mock implementations

**Alternatives considered**:
- **Mock subprocesses**: Implement fake hook/MCP handlers in Python. Rejected because it doesn't prove the real binaries work.
- **Hybrid approach**: Real MCP, mocked hooks. Rejected because hooks are equally important to demonstrate.

**Why this matters**: Using real subprocesses proves that the governance chain works as designed, not just in a simulated environment.

---

### Decision 3: Scenario scripts, not inline scenarios

**Choice**: Define scenarios as separate Python scripts (scenario_01_discovery.py, scenario_02_staged.py, scenario_03_lifecycle.py) that use the ClaudeCodeSimulator API.

**Rationale**:
- **Reusability**: ClaudeCodeSimulator is a library that scenarios can use
- **Clarity**: Each scenario is self-contained and maps to one example
- **Extensibility**: New scenarios can be added without modifying the simulator core

**Alternatives considered**:
- **Inline scenarios**: Define scenarios as data structures (JSON/YAML). Rejected because scenarios need conditional logic (e.g., "if enable_skill succeeds, then call tool").
- **Single monolithic script**: One script with all scenarios. Rejected because it's harder to understand and maintain.

**Why this matters**: Separating scenarios from the simulator core makes it easier to understand what each scenario demonstrates.

---

### Decision 4: SQLite as the source of truth for verification

**Choice**: After each scenario completes, read SQLite directly to verify audit events, grants, and state.

**Rationale**:
- **Ground truth**: SQLite is what the real system uses, so it's the authoritative source
- **Completeness**: Can verify that all expected events were written
- **Ordering**: Can verify temporal ordering of events via `created_at` timestamps

**Alternatives considered**:
- **Parse logs only**: Read events.jsonl instead of SQLite. Rejected because logs are derived from SQLite, not the source of truth.
- **Trust without verification**: Assume everything worked. Rejected because the point is to demonstrate correctness.

**Why this matters**: Verification proves that the governance chain works correctly, not just that it produces output.

---

### Decision 5: Session artifacts match existing examples

**Choice**: Generate the same four artifacts as examples 01, 02, 03: events.jsonl, audit_summary.md, metrics.json, state_before.json, state_after.json.

**Rationale**:
- **Consistency**: Users already understand these artifacts from examples
- **Reuse**: Can reuse the session logging code from examples
- **Comparability**: Can compare simulator output to example output

**Alternatives considered**:
- **New artifact format**: Invent a simulator-specific format. Rejected because it adds cognitive load.
- **Minimal artifacts**: Only generate events.jsonl. Rejected because human-readable summaries are valuable.

**Why this matters**: Consistent artifacts make it easier to understand what the simulator demonstrates.

---

### Decision 6: Three core scenarios derived from examples

**Choice**: Implement three scenarios that map to examples 01, 02, 03:
- **Scenario 01 (Discovery)**: Low-risk auto-grant + whitelist violation
- **Scenario 02 (Staged)**: require_reason + stage transitions + blocked_tools
- **Scenario 03 (Lifecycle)**: TTL expiration + disable_skill + approval_required

**Rationale**:
- **Coverage**: These three scenarios cover all major governance paths
- **Traceability**: Each scenario maps to an existing example, making it easy to understand
- **Completeness**: Together they demonstrate all 9 audit event types

**Alternatives considered**:
- **One comprehensive scenario**: Combine all behaviors into one scenario. Rejected because it's harder to understand.
- **Many fine-grained scenarios**: One scenario per requirement. Rejected because it's too granular for a demo.

**Why this matters**: Three scenarios strike a balance between coverage and comprehensibility.

---

### Decision 7: Hook invocation sequence follows Claude Code lifecycle

**Choice**: Each scenario follows the same hook sequence:
1. **SessionStart**: Initialize state, inject skill catalog
2. **UserPromptSubmit**: Cleanup expired grants, recompute active_tools
3. **PreToolUse**: Check whitelist, allow or deny
4. **PostToolUse**: Audit log, update last_used_at

**Rationale**:
- **Realism**: This is the actual sequence Claude Code uses
- **Completeness**: Demonstrates all four hook types
- **Clarity**: Makes the governance chain explicit

**Alternatives considered**:
- **Skip SessionStart**: Start directly with UserPromptSubmit. Rejected because SessionStart is important for initialization.
- **Skip PostToolUse**: Only demonstrate PreToolUse. Rejected because PostToolUse is important for audit logging.

**Why this matters**: Following the real lifecycle proves that the simulator demonstrates actual behavior.

---

### Decision 8: MCP server lifecycle: start once, reuse across requests

**Choice**: Start the MCP server subprocess once at the beginning of a scenario, send multiple requests, then shut down at the end.

**Rationale**:
- **Realism**: This is how Claude Code uses MCP servers (long-lived stdio connection)
- **Efficiency**: Avoids repeated startup overhead
- **Protocol demonstration**: Shows that the stdio protocol supports multiple requests

**Alternatives considered**:
- **Restart per request**: Spawn a new MCP server for each meta-tool call. Rejected because it's not how MCP works.
- **Never shut down**: Leave the MCP server running after the scenario. Rejected because it leaks processes.

**Why this matters**: Demonstrating the long-lived MCP server pattern is important for understanding the architecture.

---

### Decision 9: State flow: MCP writes, hooks read

**Choice**: The MCP server writes grants and skills_loaded to SQLite, and hooks read this state to compute active_tools.

**Rationale**:
- **Separation of concerns**: MCP handles meta-tools (enable_skill, disable_skill), hooks handle authorization (PreToolUse)
- **Shared state**: SQLite WAL enables concurrent reads (hooks) and single writer (MCP)
- **Realism**: This is how the real system works

**Alternatives considered**:
- **Hooks write state**: Hooks update grants directly. Rejected because hooks are short-lived and shouldn't manage state.
- **In-memory state**: Share state via shared memory. Rejected because SQLite is what the real system uses.

**Why this matters**: Demonstrating the MCP-writes-hooks-read pattern proves that SQLite WAL enables correct coordination.

---

### Decision 10: Audit artifacts generated from SQLite, not captured from stdout

**Choice**: After a scenario completes, read the audit_log table from SQLite and generate events.jsonl, audit_summary.md, metrics.json.

**Rationale**:
- **Completeness**: SQLite contains all events, including those written by hooks and MCP
- **Ordering**: SQLite timestamps provide correct temporal ordering
- **Reuse**: Can reuse session logging code from examples

**Alternatives considered**:
- **Capture stdout**: Parse hook and MCP stdout to extract events. Rejected because stdout is for protocol responses, not audit events.
- **Dual logging**: Write events to both SQLite and a separate log file. Rejected because it's redundant.

**Why this matters**: Using SQLite as the source for audit artifacts proves that the audit trail is complete and correctly ordered.

---

### Decision 11: Dual-track audit system for governance decisions vs. lifecycle bookkeeping

**Choice**: Separate audit evidence into two tracks based on event purpose:
- **Governance decision events** → SQLite `audit_log` table (authoritative for compliance)
- **Lifecycle bookkeeping events** → `events.jsonl` + `sessions` table (observability and debugging)

**Rationale**:

The governance runtime (hook_handler.py) supports 4 hook event types:
- SessionStart, UserPromptSubmit, PreToolUse, PostToolUse

Of these, only governance-relevant decisions are written to the `audit_log` table:
- **Governance decisions**: skill.enable, skill.disable, tool.call (allow/deny), grant.expire, grant.revoke, stage.change
- **Metadata queries**: skill.read, skill.list (recorded for audit trail completeness)
- **User interactions**: prompt.submit (marks interaction boundaries)

**Session lifecycle events are NOT written to audit_log**:
- `session.start`: Tracked in `sessions` table (created_at timestamp), appears in events.jsonl
- `session.end`: Not implemented in current runtime (no SessionEnd hook handler)

**Why this design**:
1. **Compliance focus**: audit_log contains only governance-relevant events (what was allowed/denied, what changed)
2. **Separation of concerns**: Session lifecycle is state management, not authorization
3. **Runtime limitation**: hook_handler.py doesn't write session.start to audit_log (by design)
4. **Observability preserved**: events.jsonl captures all hook invocations for debugging

**Alternatives considered**:
- **Write session.start to audit_log**: Would require modifying hook_handler.py (violates Stage D constraint)
- **Implement SessionEnd hook**: Would require runtime changes and verification (out of scope)
- **Single-track audit**: Would mix lifecycle bookkeeping with governance decisions (reduces clarity)

**Why this matters**: Clarifies that the simulator demonstrates governance decision auditing, not comprehensive session lifecycle tracking. The dual-track system provides complete observability while keeping audit_log focused on compliance-relevant events.

**Acceptance criteria impact**:
- **Canonical event coverage** should be measured separately for:
  - **Governance decisions** (7 events): skill.read, skill.enable, skill.disable, grant.expire, grant.revoke, tool.call, stage.change → verify in audit_log
  - **Lifecycle bookkeeping** (2 events): session.start, session.end → verify in events.jsonl + sessions table
- **Stage D verification** focuses on governance decision coverage (7/7 = 100%), not lifecycle bookkeeping (1/2 = 50%)

---

## Bug Fix: Hook Handler Indexer Initialization

### Discovery Context

During Stage D implementation (Scenario 01), a critical bug was discovered that prevented the simulator from working correctly. The bug existed in the governance runtime itself, not in the simulator code.

### Root Cause

**Process isolation + Stage D persistence strategy created a failure mode:**

1. **Stage D excluded `skills_metadata` from persistence** (it's a derived field in `SessionState.DERIVED_FIELDS`)
2. **Each hook invocation spawns a new subprocess** that loads persisted state from SQLite
3. **Loaded state has empty `skills_metadata`** (because it's not persisted)
4. **Only `handle_session_start` had the indexer initialization check**
5. **`handle_user_prompt_submit` and `handle_pre_tool_use` operated with empty metadata**
6. **Empty metadata → empty `active_tools` → all tool calls denied with `whitelist_violation`**

### The Fix

Added the same initialization check to both handlers:

**`handle_user_prompt_submit` (hook_handler.py:185-186)**:
```python
# After expired grants cleanup
if not state.skills_metadata:
    state.skills_metadata = rt.indexer.build_index()
```

**`handle_pre_tool_use` (hook_handler.py:313-314)**:
```python
# After loading state
if not state.skills_metadata:
    state.skills_metadata = rt.indexer.build_index()
```

### Why This Is the Minimal Fix

1. **Single-line check**: Only adds 2 lines of code (one per function)
2. **Reuses existing logic**: Calls the same `rt.indexer.build_index()` that `handle_session_start` uses
3. **Consistent pattern**: Matches the existing pattern in `handle_session_start`
4. **No helper needed**: The check is simple enough that extracting a helper would add complexity without benefit
5. **No behavior change**: Only adds missing initialization, doesn't alter any existing logic

### Why No Common Helper

Three reasons:
1. **Single-line simplicity**: The check is trivial (`if not state.skills_metadata: state.skills_metadata = rt.indexer.build_index()`)
2. **Different contexts**: Each handler has different surrounding logic (session creation vs. state loading)
3. **Code style consistency**: `handle_session_start` also uses an inline check, not a helper

If future handlers need the same check, or if the initialization logic becomes more complex, a helper can be extracted then.

### Impact on Simulator

**Before fix**:
- Scenario 01 Step 5 (UserPromptSubmit): "No skills registered"
- Scenario 01 Step 6 (PreToolUse): `decision: "deny"`, `error_bucket: "whitelist_violation"`

**After fix**:
- Scenario 01 Step 5: Shows complete skill catalog with 2 skills
- Scenario 01 Step 6: `decision: "allow"` for authorized tools

### Regression Tests

Added `tests/test_hook_indexer_initialization.py` with 3 test cases:
1. **`test_user_prompt_submit_initializes_indexer_when_metadata_empty`**: Verifies UserPromptSubmit initializes indexer
2. **`test_pre_tool_use_initializes_indexer_when_metadata_empty`**: Verifies PreToolUse initializes indexer
3. **`test_pre_tool_use_denies_unauthorized_tool_after_indexer_init`**: Verifies authorization still works correctly after initialization

All 241 tests pass (no regressions).

### Why This Bug Matters

This bug would have prevented the governance system from working correctly in any production scenario where:
- Hook handlers run as separate processes (the normal deployment model)
- Skills metadata is not persisted (Stage D design decision)
- Multiple hook invocations occur in a session (every real session)

The fix ensures that every hook handler can independently rebuild the skill index from the filesystem when needed, making the system resilient to process boundaries.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Scenario Script (scenario_01_discovery.py)                  │
│ - Defines agent actions (enable_skill, call_tool, etc.)     │
│ - Uses ClaudeCodeSimulator API                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ ClaudeCodeSimulator                                          │
│ - Orchestrates governance chain                             │
│ - Manages hook and MCP subprocess lifecycle                 │
│ - Captures state snapshots                                  │
│ - Generates session artifacts                               │
└─────────────────────────────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                ▼                       ▼
┌───────────────────────────┐  ┌───────────────────────────┐
│ HookSubprocess            │  │ MCPSubprocess             │
│ - Spawns tg-hook          │  │ - Spawns tg-mcp           │
│ - Writes JSON to stdin    │  │ - Stdio protocol handshake│
│ - Reads JSON from stdout  │  │ - Persistent connection   │
│ - Waits for exit          │  │ - Graceful shutdown       │
└───────────────────────────┘  └───────────────────────────┘
                │                       │
                └───────────┬───────────┘
                            ▼
                ┌───────────────────────┐
                │ SQLite WAL            │
                │ - governance.db       │
                │ - audit_log table     │
                │ - grants table        │
                │ - session_state table │
                └───────────────────────┘
```

### Sequence Diagram: Happy Path (Scenario 01)

```
Scenario Script → ClaudeCodeSimulator → HookSubprocess → tg-hook → SQLite
                                      → MCPSubprocess → tg-mcp → SQLite

1. Scenario: session_start()
   → ClaudeCodeSimulator.invoke_hook("SessionStart", {...})
   → HookSubprocess.invoke(event_json)
   → spawn tg-hook, write to stdin, read from stdout
   → tg-hook reads state from SQLite, returns additionalContext
   → ClaudeCodeSimulator captures response

2. Scenario: enable_skill("yuque-knowledge-link")
   → ClaudeCodeSimulator.call_mcp_tool("enable_skill", {...})
   → MCPSubprocess.call_tool(tool_name, params)
   → send JSON-RPC request via stdio
   → tg-mcp evaluates policy, creates grant, writes to SQLite
   → tg-mcp returns {granted: true, allowed_tools: [...]}
   → ClaudeCodeSimulator captures response

3. Scenario: user_prompt_submit()
   → ClaudeCodeSimulator.invoke_hook("UserPromptSubmit", {...})
   → HookSubprocess.invoke(event_json)
   → tg-hook reads grants from SQLite, recomputes active_tools
   → tg-hook returns additionalContext with updated tool list
   → ClaudeCodeSimulator captures response

4. Scenario: call_tool("yuque_search", {...})
   → ClaudeCodeSimulator.invoke_hook("PreToolUse", {...})
   → tg-hook checks active_tools, tool is in whitelist
   → tg-hook returns {permissionDecision: "allow"}
   → ClaudeCodeSimulator.invoke_hook("PostToolUse", {...})
   → tg-hook writes audit event to SQLite

5. Scenario: call_tool("rag_paper_search", {...})  # unauthorized
   → ClaudeCodeSimulator.invoke_hook("PreToolUse", {...})
   → tg-hook checks active_tools, tool NOT in whitelist
   → tg-hook returns {permissionDecision: "deny", additionalContext: "..."}
   → tg-hook writes audit event with error_bucket=whitelist_violation

6. Scenario: session_end()
   → ClaudeCodeSimulator.generate_session_artifacts()
   → Read audit_log from SQLite
   → Generate events.jsonl, audit_summary.md, metrics.json
   → Read session_state from SQLite
   → Generate state_before.json, state_after.json
```

### Core Happy Path

The core happy path that every scenario must demonstrate:

1. **SessionStart**: Initialize state, inject skill catalog
2. **enable_skill**: MCP call → policy evaluation → grant creation → SQLite write
3. **UserPromptSubmit**: Hook reads grants → recomputes active_tools → returns updated context
4. **PreToolUse (allow)**: Hook checks whitelist → tool in active_tools → allow
5. **PostToolUse**: Hook writes audit event to SQLite
6. **PreToolUse (deny)**: Hook checks whitelist → tool NOT in active_tools → deny with guidance
7. **Session artifacts**: Read SQLite → generate events.jsonl, audit_summary.md, metrics.json, state snapshots

### Scenario Abstraction

Each scenario is a Python script that uses the ClaudeCodeSimulator API:

**Scenario 01 (Discovery)**: Derived from example 01-knowledge-link
- SessionStart
- list_skills (MCP)
- read_skill("yuque-knowledge-link") (MCP)
- enable_skill("yuque-knowledge-link") → auto-grant (MCP)
- UserPromptSubmit
- PreToolUse("yuque_search") → allow
- PostToolUse("yuque_search")
- PreToolUse("rag_paper_search") → deny (whitelist_violation)
- Session artifacts

**Scenario 02 (Staged)**: Derived from example 02-doc-edit-staged
- SessionStart
- enable_skill("yuque-doc-edit") without reason → deny (reason_missing)
- enable_skill("yuque-doc-edit", reason="...") → grant with stage=analysis
- UserPromptSubmit
- PreToolUse("yuque_get_doc") → allow (in analysis stage)
- PreToolUse("yuque_update_doc") → deny (not in analysis stage)
- change_stage("yuque-doc-edit", "execution") (MCP)
- UserPromptSubmit
- PreToolUse("yuque_update_doc") → allow (in execution stage)
- PreToolUse("run_command") → deny (blocked_tools)
- Session artifacts

**Scenario 03 (Lifecycle)**: Derived from example 03-lifecycle-and-risk
- SessionStart (with pre-existing grant that has expired)
- UserPromptSubmit → cleanup_expired_grants → grant.expire event
- PreToolUse("yuque_search") → deny (expired skill)
- enable_skill("yuque-knowledge-link") → re-grant
- disable_skill("yuque-doc-edit") → grant.revoke + skill.disable (strict ordering)
- enable_skill("yuque-bulk-delete") → deny (approval_required)
- Session artifacts

### Allow/Deny Decision Boundaries

**Allow decisions** (PreToolUse returns `permissionDecision: "allow"`):
- Tool is in active_tools (computed from enabled skills + current stage)
- Tool is not in blocked_tools

**Deny decisions** (PreToolUse returns `permissionDecision: "deny"`):
- Tool not in active_tools → error_bucket: whitelist_violation
- Tool in blocked_tools → error_bucket: blocked
- Skill not enabled → guidance: "use read_skill → enable_skill"
- Wrong stage → guidance: "use change_stage"

**MCP meta-tool decisions**:
- enable_skill without reason (require_reason=true) → deny (reason_missing)
- enable_skill for high-risk skill → deny (approval_required)
- enable_skill for low-risk skill → auto-grant

### Real vs. Mock Components

**Real (must use actual subprocesses)**:
- `tg-hook` binary: Real hook handler subprocess
- `tg-mcp` binary: Real MCP server subprocess
- SQLite database: Real governance.db with WAL mode
- stdin/stdout communication: Real pipes, not in-process function calls

**Mock (can simulate)**:
- Agent decision-making: Scenario scripts simulate Claude's choices
- Business tool execution: Don't actually call yuque_search, just demonstrate authorization
- Time progression: Can fast-forward time for TTL expiration (set grant.expires_at in the past)

**Why this matters**: Real subprocesses prove the protocol works; mocked agent and tools keep the demo focused on governance.

---

## Risks / Trade-offs

### Risk 1: Subprocess overhead

**Risk**: Spawning subprocesses for every hook invocation adds latency.

**Mitigation**: This is a demo tool, not a performance benchmark. The overhead is acceptable for demonstration purposes. Document that real Claude Code has the same overhead.

---

### Risk 2: SQLite contention

**Risk**: Concurrent hook invocations might cause SQLite lock contention.

**Mitigation**: Use WAL mode (already configured in src/). WAL allows concurrent reads and single writer. Document that this is the same configuration used in production.

---

### Risk 3: Subprocess cleanup failures

**Risk**: If a subprocess hangs or crashes, it might not be cleaned up properly.

**Mitigation**: Implement timeout handling (kill subprocess after N seconds). Use context managers to ensure cleanup even on exceptions.

---

### Risk 4: Protocol version skew

**Risk**: If the hook or MCP protocol changes, the simulator might break.

**Mitigation**: The simulator uses the installed `tg-hook` and `tg-mcp` binaries, so it automatically uses the current protocol version. If the protocol changes, the simulator will break at the same time as the examples, making it easy to detect.

---

### Risk 5: Scenario drift from examples

**Risk**: If examples 01, 02, 03 change, the scenarios might no longer accurately represent them.

**Mitigation**: Document the mapping between scenarios and examples. When examples change, update the corresponding scenario. Consider adding a test that compares scenario output to example output.

---

## Migration Plan

### Deployment Steps

1. **Create simulator directory**: `examples/simulator-demo/` (or similar location)
2. **Implement ClaudeCodeSimulator**: Core orchestration logic
3. **Implement HookSubprocess**: Hook subprocess wrapper
4. **Implement MCPSubprocess**: MCP subprocess wrapper
5. **Implement scenario scripts**: scenario_01_discovery.py, scenario_02_staged.py, scenario_03_lifecycle.py
6. **Add entry point**: `run_simulator.sh` or similar
7. **Update documentation**: Add simulator to examples/README.md and root README.md

### Rollback Strategy

Since this is a new demo tool (not a change to existing functionality), rollback is simple:
- Delete the simulator directory
- Remove documentation links

No impact on existing examples or src/ implementation.

---

## Open Questions

### Q1: Where should the simulator live?

**Options**:
- `examples/simulator-demo/`: Alongside existing examples
- `tools/simulator/`: Separate tools directory
- `examples/00-simulator/`: Numbered like other examples

**Recommendation**: `examples/simulator-demo/` to keep it with the examples it demonstrates.

---

### Q2: Should scenarios be runnable independently or only via the simulator?

**Options**:
- Independent: Each scenario is a standalone script
- Orchestrated: One entry point runs all scenarios

**Recommendation**: Both. Each scenario is a standalone script, and there's also a `run_all_scenarios.sh` that runs them in sequence.

---

### Q3: Should the simulator generate a comparison report between its output and example output?

**Options**:
- Yes: Compare metrics.json from simulator vs. example
- No: Manual comparison only

**Recommendation**: Defer to implementation phase. Nice-to-have but not required for initial version.

---

### Q4: Should the simulator support custom scenarios beyond the three derived from examples?

**Options**:
- Yes: Provide a scenario API for users to write their own
- No: Only the three built-in scenarios

**Recommendation**: Yes, but document that the three built-in scenarios are the canonical demonstrations. Custom scenarios are for exploration.

---

### Q5: How should the simulator handle environment variables (GOVERNANCE_DATA_DIR, etc.)?

**Options**:
- Require user to set them: Like existing examples
- Set them automatically: Simulator sets them to a temp directory

**Recommendation**: Set them automatically to a temp directory (e.g., `.simulator-data/`) to make the simulator easier to run. Document that this is different from examples, which use `.demo-data/`.
