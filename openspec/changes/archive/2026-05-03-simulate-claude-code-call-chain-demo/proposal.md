## Example-Derived Demo Requirements

### Analysis of Existing Examples

**Example 01 (knowledge-link)**: Demonstrates the **basic discovery-to-execution flow**:
- SessionStart → skill catalog injection
- list_skills → read_skill → enable_skill (low-risk auto-grant)
- PreToolUse allow/deny with whitelist enforcement
- PostToolUse audit logging
- Mixed tool environment (yuque + web-search + internal-doc MCPs)
- Whitelist violation when attempting unauthorized tools (rag_paper_search)
- refresh_skills for dynamic skill discovery

**Example 02 (doc-edit-staged)**: Demonstrates **policy-driven staged workflows**:
- require_reason enforcement (deny without reason, grant with reason)
- Two-stage workflow (analysis → execution) with different tool sets per stage
- change_stage mechanics and audit trail
- blocked_tools global red line (run_command always denied)
- Stage-aware whitelist violations

**Example 03 (lifecycle-and-risk)**: Demonstrates **session lifecycle and risk escalation**:
- TTL expiration and automatic grant cleanup
- disable_skill with strict revoke → disable audit ordering (D7 invariant)
- High-risk skill with approval_required (enable_skill denied)
- Two-layer defense: approval_required + blocked_tools
- grant.expire / grant.revoke / skill.disable audit sequence
- Long-running session state management

### Core Governance Chain Coverage

All three examples demonstrate parts of the **Agent → Hook subprocess → MCP subprocess → SQLite shared state → audit logging** chain:

1. **SessionStart hook**: Loads state, injects skill catalog into additionalContext
2. **UserPromptSubmit hook**: Cleanup expired grants, recompute active_tools, inject updated context
3. **PreToolUse hook**: Whitelist check, deny with guidance or allow
4. **PostToolUse hook**: Audit logging, update last_used_at
5. **MCP meta-tools**: list_skills, read_skill, enable_skill, disable_skill, grant_status, change_stage, run_skill_action, refresh_skills
6. **SQLite shared state**: Grants, skills_loaded, audit_log, session state
7. **Policy evaluation**: risk_level → auto/reason/approval, require_reason, blocked_tools, max_ttl
8. **Audit trail**: skill.read, skill.enable, skill.disable, grant.expire, grant.revoke, tool.call, stage.change

### What a Unified Simulator Must Demonstrate

**Core chain elements** (must be in every scenario):
- Hook subprocess isolation (stdin/stdout JSON-RPC)
- MCP subprocess isolation (stdio protocol)
- SQLite WAL shared state (concurrent reads, single writer)
- Audit log completeness (all events with timestamps)
- State snapshots (before/after session)

**Scenario-specific capabilities** (choose based on scenario):
- Low-risk auto-grant (01)
- Medium-risk require_reason (02)
- High-risk approval_required (03)
- Stage transitions (02)
- TTL expiration (03)
- Grant revocation (03)
- Whitelist violations (01, 02, 03)
- Blocked tools (02, 03)
- Mixed MCP environment (01)

### What Should NOT Be in the Core Simulator

**Example-specific details** that belong in scenario scripts, not the core simulator:
- Yuque domain logic (mock responses, doc IDs, repo names)
- Specific skill definitions (yuque-knowledge-link, yuque-doc-edit, yuque-bulk-delete)
- Business story narrative (Alice, knowledge engineer, RAG notes)
- Specific tool names (yuque_search, yuque_update_doc, run_command)

**Implementation details** that belong in src/, not the demo:
- PolicyEngine evaluation logic
- GrantManager lifecycle management
- ToolRewriter computation
- SkillIndexer scanning
- SQLiteStore persistence

### Bug Discovered During Stage D Implementation

While implementing Scenario 01, a critical bug was discovered in the hook handler:

**Root cause**: `handle_user_prompt_submit` and `handle_pre_tool_use` lacked the indexer initialization check that `handle_session_start` had. When Stage D excluded `skills_metadata` from persistence, hook subprocesses started with empty metadata, causing all tool calls to be rejected with `whitelist_violation`.

**Impact**: Without this fix, the governance chain would fail in any scenario where hooks are invoked after skills are enabled, because the hook subprocess wouldn't know about the enabled skills.

**Fix**: Added the same indexer initialization check (`if not state.skills_metadata: state.skills_metadata = rt.indexer.build_index()`) to both `handle_user_prompt_submit` and `handle_pre_tool_use`.

This bug fix is documented in `BUG_FIX_INDEXER_INITIALIZATION.md` and covered by regression tests in `tests/test_hook_indexer_initialization.py`.

### Recommended Simulator Architecture

**Core simulator** (reusable across scenarios):
- `ClaudeCodeSimulator`: Orchestrates hook/MCP subprocess lifecycle
- `HookSubprocess`: Manages tg-hook stdin/stdout communication
- `MCPSubprocess`: Manages tg-mcp stdio protocol
- `StateInspector`: Reads SQLite state snapshots
- `AuditVerifier`: Validates audit log completeness and ordering
- `SessionLogger`: Generates events.jsonl, audit_summary.md, metrics.json

**Scenario scripts** (one per example):
- `scenario_01_discovery.py`: Low-risk auto-grant + whitelist violation
- `scenario_02_staged.py`: require_reason + stage transitions + blocked_tools
- `scenario_03_lifecycle.py`: TTL expiration + revocation + approval_required

---

## Why

### Problem Statement

The current examples (01, 02, 03) demonstrate tool-gate's governance capabilities through **end-to-end workspace demos**, but they lack a **unified simulator** that explicitly shows the **subprocess isolation and protocol boundaries** that make the governance chain work.

Reviewers and developers need to see:
1. How hook subprocesses communicate via stdin/stdout JSON
2. How MCP subprocesses use stdio protocol
3. How SQLite WAL enables shared state without race conditions
4. How audit events flow through the entire chain
5. How session state evolves across hook invocations

### Why Now

- **Phase 4 delivery**: Examples are complete, but the "how it works under the hood" story is implicit
- **Developer onboarding**: New contributors need to understand subprocess boundaries
- **Testing infrastructure**: A simulator enables replay, fuzzing, and regression testing
- **Documentation gap**: Current docs explain *what* happens, not *how* the plumbing works

### Why OpenSpec

Using OpenSpec to design the simulator ensures:
1. **Clear scope**: proposal locks down what's in/out before implementation
2. **Reviewable design**: design.md can be reviewed before code is written
3. **Testable specs**: specs/ defines observable behaviors for each capability
4. **Traceable tasks**: tasks.md breaks implementation into verifiable steps

---

## What Changes

This change will **design and specify** a Claude Code call chain simulator that:

1. **Simulates the full governance chain**: Agent → Hook subprocess → MCP subprocess → SQLite → Audit
2. **Demonstrates subprocess isolation**: Real stdin/stdout communication, no in-process shortcuts
3. **Validates protocol correctness**: JSON-RPC for hooks, stdio for MCP
4. **Verifies shared state integrity**: SQLite WAL concurrent access patterns
5. **Generates complete audit trails**: All 9 event types with correct timestamps and ordering
6. **Produces session logs**: events.jsonl, audit_summary.md, metrics.json, state snapshots
7. **Supports multiple scenarios**: Reusable core + pluggable scenario scripts

**Deliverables** (OpenSpec artifacts only, no implementation):
- `proposal.md` (this document)
- `design.md` (architecture, subprocess boundaries, protocol details)
- `specs/` (one spec per capability: subprocess-isolation, protocol-correctness, state-integrity, audit-completeness, scenario-coverage)
- `tasks.md` (implementation checklist)

---

## Capabilities

### New Capabilities

- `subprocess-isolation`: Demonstrate hook and MCP subprocesses with real stdin/stdout boundaries
- `protocol-correctness`: Validate JSON-RPC (hooks) and stdio (MCP) protocol compliance
- `state-integrity`: Verify SQLite WAL shared state across concurrent subprocess invocations
- `audit-completeness`: Ensure all 9 event types are logged with correct timestamps and ordering
- `scenario-coverage`: Support pluggable scenarios that exercise different governance paths

### Modified Capabilities

None. This change adds new demo infrastructure without modifying existing examples or src/ implementation.

---

## Impact

### In Scope

- **OpenSpec artifacts**: proposal, design, specs, tasks
- **Simulator design**: Architecture, subprocess boundaries, protocol details
- **Scenario planning**: Which governance paths each scenario should exercise
- **Audit verification**: How to validate event completeness and ordering
- **Session logging**: How to generate events.jsonl, audit_summary.md, metrics.json
- **Demo entry point**: How users run the simulator and interpret results

### Out of Scope

- **Implementation code**: No Python code in this change (implementation follows in separate change)
- **src/ modifications**: No changes to tool_governance core modules
- **tests/ modifications**: No changes to existing test suites
- **Example refactoring**: No changes to 01/02/03 workspace structure
- **Archive**: This change does not archive itself (implementation change will)

### Affected Areas

- `examples/` directory: New subdirectory for simulator demo
- Root `README.md`: Add link to simulator demo in documentation section
- `examples/README.md`: Add simulator demo to the examples overview

### Success Criteria

1. **Proposal clarity**: Reviewers can understand what the simulator will demonstrate and why
2. **Design completeness**: design.md provides enough detail for implementation without ambiguity
3. **Spec coverage**: Each capability has a spec that defines observable behaviors and verification methods
4. **Task granularity**: tasks.md breaks implementation into ~10-15 verifiable steps
5. **Scenario alignment**: Scenarios map cleanly to existing example capabilities (01→discovery, 02→staged, 03→lifecycle)
6. **No implementation**: This change contains only OpenSpec artifacts, no code
