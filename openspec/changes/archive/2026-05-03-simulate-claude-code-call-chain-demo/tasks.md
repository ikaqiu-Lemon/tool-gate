## Stage A: Example Alignment and Demo Scope Confirmation

**Goal**: Lock down what the simulator must demonstrate based on the three existing examples, without writing any running code.

**Files to modify**:
- `examples/simulator-demo/SCOPE.md` (new): Document the mapping between examples and simulator scenarios
- `examples/simulator-demo/SCENARIOS.md` (new): Define the three core scenarios in detail

**Files NOT to modify**:
- `examples/01-knowledge-link/`, `examples/02-doc-edit-staged/`, `examples/03-lifecycle-and-risk/`: No changes to existing examples
- `src/tool_governance/`: No changes to core implementation
- `tests/`: No changes to existing tests

**Verification**:
- SCOPE.md clearly maps each example to simulator capabilities
- SCENARIOS.md defines expected inputs, hook/MCP calls, and audit events for each scenario
- Reviewers can confirm that the simulator scope matches the proposal's Example-derived Demo Requirements

**Completion criteria**:
- [x] A.1 Create `examples/simulator-demo/` directory structure
- [x] A.2 Document example-to-scenario mapping in SCOPE.md (01→discovery, 02→staged, 03→lifecycle)
- [x] A.3 Define Scenario 01 (Discovery) in SCENARIOS.md: list_skills, read_skill, enable_skill (auto-grant), PreToolUse allow/deny, whitelist_violation
- [x] A.4 Define Scenario 02 (Staged) in SCENARIOS.md: require_reason, change_stage, blocked_tools, stage-aware whitelist
- [x] A.5 Define Scenario 03 (Lifecycle) in SCENARIOS.md: TTL expiration, disable_skill, approval_required, grant.revoke ordering
- [x] A.6 Document which governance events each scenario must produce (session.start, skill.enable, tool.call, grant.expire, etc.)
- [x] A.7 Confirm that all 9 audit event types are covered across the three scenarios

**Scope control**:
- Only document what examples 01, 02, 03 already demonstrate
- Do not invent new governance features
- Do not expand beyond the three core scenarios

---

## Stage B: Simulator Skeleton

**Goal**: Build the subprocess orchestration skeleton without implementing full functionality.

**Files to modify**:
- `examples/simulator-demo/simulator/core.py` (new): ClaudeCodeSimulator class
- `examples/simulator-demo/simulator/hook_subprocess.py` (new): HookSubprocess wrapper
- `examples/simulator-demo/simulator/mcp_subprocess.py` (new): MCPSubprocess wrapper
- `examples/simulator-demo/simulator/__init__.py` (new): Package initialization

**Files NOT to modify**:
- `src/tool_governance/`: No changes to tg-hook or tg-mcp implementation
- `examples/01-*/`, `examples/02-*/`, `examples/03-*/`: No changes to existing examples
- `hooks/hooks.json`, `.claude-plugin/plugin.json`: No changes to plugin configuration

**Verification**:
- Can instantiate ClaudeCodeSimulator
- Can spawn a hook subprocess (tg-hook) and capture stdout (even if response is empty)
- Can spawn MCP subprocess (tg-mcp) and complete stdio handshake
- No full scenario runs yet

**Completion criteria**:
- [x] B.1 Implement ClaudeCodeSimulator.__init__: Set up session_id, data_dir, environment variables
- [x] B.2 Implement HookSubprocess.invoke: Spawn tg-hook, write JSON to stdin, read JSON from stdout, wait for exit
- [x] B.3 Implement MCPSubprocess.start: Spawn tg-mcp, complete stdio protocol handshake
- [x] B.4 Implement MCPSubprocess.call_tool: Send JSON-RPC request, receive response
- [x] B.5 Implement MCPSubprocess.shutdown: Send shutdown signal, wait for graceful exit
- [x] B.6 Add timeout handling for subprocess invocations (default 10s)
- [x] B.7 Add context manager support for subprocess cleanup (ensure processes are killed on exception)
- [x] B.8 Write smoke test: Spawn tg-hook with SessionStart event, verify it returns JSON

**Scope control**:
- Only implement subprocess spawning and communication
- Do not implement scenario logic yet
- Do not implement audit artifact generation yet
- Use real tg-hook and tg-mcp binaries (installed via pip), not mocks

---

## Stage C: Governance Chain Integration

**Goal**: Connect the simulator to the real governance chain (hooks, MCP, SQLite) and generate session artifacts.

**Files to modify**:
- `examples/simulator-demo/simulator/core.py`: Add session lifecycle methods (session_start, user_prompt_submit, call_tool)
- `examples/simulator-demo/simulator/artifacts.py` (new): Session artifact generation (events.jsonl, audit_summary.md, metrics.json, state snapshots)
- `examples/simulator-demo/simulator/verification.py` (new): Audit log and state verification

**Files NOT to modify**:
- `src/tool_governance/`: No changes to core governance logic
- `examples/01-*/`, `examples/02-*/`, `examples/03-*/`: No changes to existing examples

**Verification**:
- Can run a minimal scenario: SessionStart → enable_skill → UserPromptSubmit → PreToolUse → PostToolUse
- SQLite governance.db is created and contains audit events
- Session artifacts are generated (events.jsonl, audit_summary.md, metrics.json, state_before.json, state_after.json)

**Completion criteria**:
- [x] C.1 Implement ClaudeCodeSimulator.session_start: Invoke SessionStart hook, capture additionalContext
- [x] C.2 Implement ClaudeCodeSimulator.enable_skill: Call enable_skill via MCP, capture grant result
- [x] C.3 Implement ClaudeCodeSimulator.user_prompt_submit: Invoke UserPromptSubmit hook, capture active_tools
- [x] C.4 Implement ClaudeCodeSimulator.call_tool: Invoke PreToolUse → (if allow) PostToolUse, capture decisions
- [x] C.5 Implement ClaudeCodeSimulator.disable_skill: Call disable_skill via MCP, capture revocation
- [x] C.6 Implement ClaudeCodeSimulator.change_stage: Call change_stage via MCP, capture stage transition
- [x] C.7 Implement ClaudeCodeSimulator.capture_state_snapshot: Read session_state from SQLite, save to JSON
- [x] C.8 Implement ArtifactGenerator.generate_events_jsonl: Read audit_log from SQLite, write JSONL
- [x] C.9 Implement ArtifactGenerator.generate_audit_summary: Read audit_log, generate Markdown report
- [x] C.10 Implement ArtifactGenerator.generate_metrics: Count events by type, write JSON
- [x] C.11 Implement Verifier.verify_audit_completeness: Check that all expected events are present
- [x] C.12 Implement Verifier.verify_state_consistency: Check that state_after.json matches expected grants/skills
- [x] C.13 Write integration test: Run minimal scenario, verify all artifacts are generated

**Scope control**:
- Only implement the governance chain integration
- Do not implement full scenario scripts yet
- Reuse session logging patterns from examples 01, 02, 03 (do not reinvent)

---

## Stage C.5: Runtime Bug Fix (Discovered During Stage D)

**Goal**: Fix critical hook handler indexer initialization bug discovered during Scenario 01 implementation.

**Context**: While implementing Scenario 01, discovered that `handle_user_prompt_submit` and `handle_pre_tool_use` failed to initialize the skill indexer when `skills_metadata` was empty (excluded from persistence in Stage D). This caused all tool calls to be denied with `whitelist_violation`.

**Files to modify**:
- `src/tool_governance/hook_handler.py`: Add indexer initialization checks
- `tests/test_hook_indexer_initialization.py` (new): Regression tests

**Files NOT to modify**:
- `examples/01-*/`, `examples/02-*/`, `examples/03-*/`: No changes to existing examples
- Other src/ files: Only hook_handler.py needs changes

**Verification**:
- All 241 existing tests still pass (no regressions)
- New regression tests pass
- Scenario 01 now completes successfully (PreToolUse returns "allow" for authorized tools)

**Completion criteria**:
- [x] C.5.1 Add indexer initialization check to `handle_user_prompt_submit` (line 185-186)
- [x] C.5.2 Add indexer initialization check to `handle_pre_tool_use` (line 313-314)
- [x] C.5.3 Create regression test: `test_user_prompt_submit_initializes_indexer_when_metadata_empty`
- [x] C.5.4 Create regression test: `test_pre_tool_use_initializes_indexer_when_metadata_empty`
- [x] C.5.5 Create regression test: `test_pre_tool_use_denies_unauthorized_tool_after_indexer_init`
- [x] C.5.6 Verify all 241 tests pass (no regressions)
- [x] C.5.7 Re-run Scenario 01 and verify PreToolUse now returns "allow" for authorized tools
- [x] C.5.8 Document bug fix in `BUG_FIX_INDEXER_INITIALIZATION.md`

**Scope control**:
- Only fix the indexer initialization bug
- Do not refactor hook handler code
- Do not extract common helper (single-line check is simple enough)
- Minimal fix: 2 lines of code added

---

## Stage D: Demo Scenarios and Verification

**Goal**: Implement the three core scenarios and verify they demonstrate the expected governance behaviors.

**Files to modify**:
- `examples/simulator-demo/scenarios/scenario_01_discovery.py` (new): Discovery scenario
- `examples/simulator-demo/scenarios/scenario_02_staged.py` (new): Staged workflow scenario
- `examples/simulator-demo/scenarios/scenario_03_lifecycle.py` (new): Lifecycle and risk scenario
- `examples/simulator-demo/run_simulator.sh` (new): Entry point to run all scenarios
- `examples/simulator-demo/README.md` (new): Demo runbook and verification notes

**Files NOT to modify**:
- `src/tool_governance/`: No changes to core implementation
- `examples/01-*/`, `examples/02-*/`, `examples/03-*/`: No changes to existing examples
- Root `README.md`: Only add a link to simulator demo (no structural changes)

**Verification**:
- Run `./run_simulator.sh` and verify all three scenarios complete successfully
- Verify that each scenario generates the expected audit events (compare to SCENARIOS.md from Stage A)
- Verify that allow/deny decisions match expectations
- Verify that SQLite state is correctly shared between hook and MCP subprocesses

**Completion criteria**:
- [x] D.1 Implement scenario_01_discovery.py: SessionStart → list_skills → read_skill → enable_skill (auto) → call yuque_search (allow) → call rag_paper_search (deny)
- [x] D.2 Verify Scenario 01 produces: session.start, skill.read, skill.enable (granted_by=auto), tool.call (allow), tool.call (deny, whitelist_violation)
- [x] D.3 Implement scenario_02_staged.py: enable_skill without reason (deny) → enable_skill with reason (grant, stage=analysis) → call yuque_update_doc (deny) → change_stage → call yuque_update_doc (allow) → call run_command (deny, blocked)
- [x] D.4 Verify Scenario 02 produces: skill.enable (denied, reason_missing), skill.enable (granted, stage=analysis), tool.call (deny, whitelist_violation), stage.change, tool.call (allow), tool.call (deny, blocked)
- [x] D.5 Implement scenario_03_lifecycle.py: SessionStart (with expired grant) → UserPromptSubmit (grant.expire) → enable_skill (re-grant) → disable_skill (grant.revoke + skill.disable) → enable_skill high-risk (deny, approval_required)
- [x] D.6 Verify Scenario 03 produces: grant.expire, skill.enable (granted), grant.revoke, skill.disable (strict ordering: revoke before disable), skill.enable (denied, approval_required)
- [x] D.7 Implement run_simulator.sh: Set GOVERNANCE_DATA_DIR, run all three scenarios, generate summary report (Alternative: scenarios run individually - documented in README.md)
- [x] D.8 Write README.md: Explain what the simulator demonstrates, how to run it, how to interpret results
- [x] D.9 Add verification section to README.md: SQL queries to check audit events, state snapshots, metrics
- [x] D.10 Verify that all 9 audit event types are produced across the three scenarios:
  - **Governance decision events (7)**: skill.read, skill.enable, skill.disable, grant.expire, grant.revoke, tool.call, stage.change → verify in SQLite audit_log
  - **Lifecycle bookkeeping events (2)**: session.start (sessions table + events.jsonl), session.end (not implemented in runtime)
  - **Acceptance**: 7/7 governance decision events in audit_log = 100% coverage for governance decisions
  - **Known limitation**: session.end not implemented (requires SessionEnd hook handler in runtime)
- [x] D.11 Verify subprocess isolation: Confirm that tg-hook and tg-mcp are real subprocesses (check process list during execution)
- [x] D.12 Verify protocol correctness: Log stdin/stdout communication, confirm JSON-RPC format for hooks and stdio format for MCP
- [x] D.13 Verify shared state: Confirm that grants written by MCP are read by hooks (check SQLite timestamps)
- [x] D.14 Update `examples/README.md`: Add simulator demo to the examples overview
- [x] D.15 Update root `README.md`: Add link to simulator demo in documentation section

**Scope control**:
- Only implement the three scenarios defined in Stage A
- Do not add new governance features
- Do not modify existing examples
- Reuse skills and policies from examples (do not create new ones)
- Keep the simulator focused on demonstrating subprocess boundaries and protocol correctness

---

## Verification Summary

After completing all stages, the simulator must demonstrate:

1. **Subprocess isolation**: tg-hook and tg-mcp run as real subprocesses with stdin/stdout communication
2. **Protocol correctness**: JSON-RPC for hooks, stdio for MCP
3. **Shared state integrity**: SQLite WAL enables MCP writes and hook reads
4. **Audit completeness**: All 9 event types with correct timestamps and ordering
5. **Scenario coverage**: Three scenarios covering all major governance paths from examples 01, 02, 03
6. **Allow/deny decisions**: Correct whitelist enforcement, blocked_tools, require_reason, approval_required
7. **Session artifacts**: events.jsonl, audit_summary.md, metrics.json, state_before.json, state_after.json

**Final verification command**:
```bash
cd examples/simulator-demo
./run_simulator.sh
# Check that all three scenarios complete successfully
# Check that logs/ contains session artifacts for each scenario
# Run verification queries from README.md to confirm audit events
```
