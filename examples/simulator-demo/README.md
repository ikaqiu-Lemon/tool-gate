# Simulator Demo

**Status**: Stage A complete (documentation and scope definition)

This directory will contain a Claude Code call chain simulator that demonstrates subprocess isolation, protocol boundaries, and governance chain integration.

## Purpose

The simulator demonstrates:
- Hook subprocess isolation (tg-hook via stdin/stdout)
- MCP server subprocess isolation (tg-mcp via stdio protocol)
- SQLite WAL shared state coordination
- Complete audit trail generation
- Three core governance scenarios derived from examples 01, 02, 03

## Current Status

**Stage A (Complete)**: Documentation and scope definition
- ✓ SCOPE.md: Example-to-scenario mapping
- ✓ SCENARIOS.md: Three core scenario definitions
- ✓ Audit event coverage confirmed

**Stage B (Complete)**: Simulator skeleton
- ✓ ClaudeCodeSimulator orchestration class
- ✓ HookSubprocess wrapper with error handling
- ✓ MCPSubprocess wrapper with real MCP SDK handshake
- ✓ Smoke tests passing (4/4)

**Stage C (Complete)**: Governance chain integration
- ✓ SessionStart → UserPromptSubmit → PreToolUse → PostToolUse chain
- ✓ MCP list_skills tool integration
- ✓ Hook response parsing (hookSpecificOutput structure)
- ✓ Integration test passing
- ✓ Event tracking in all governance methods
- ✓ State snapshot (reads from SQLite governance.db)
- ✓ Artifact generation (events.jsonl, audit_summary.md, metrics.json)
- ✓ Audit completeness verification (verify_audit_completeness)
- ✓ State consistency verification (verify_state_consistency)
- ✓ Stage C verification script passing

**Stage D (Complete)**: Demo scenarios and verification
- ✓ Scenario 01: Discovery and auto-grant workflow
- ✓ Scenario 02: Staged enablement with stage transitions
- ✓ Scenario 03: Grant lifecycle with expiration and revocation
- ✓ All 7 governance decision events verified in audit_log
- ✓ Dual-track audit system (governance decisions + lifecycle bookkeeping)

## Running the Scenarios

Each scenario runs independently and generates its own artifacts:

```bash
cd examples/simulator-demo

# Scenario 01: Discovery and auto-grant
python scenarios/scenario_01_discovery.py

# Scenario 02: Staged workflow
python scenarios/scenario_02_staged.py

# Scenario 03: Grant lifecycle
python scenarios/scenario_03_lifecycle.py
```

Each scenario creates a `.scenario-XX-data/` directory containing:
- `governance.db` - SQLite database with audit_log, sessions, grants
- `events.jsonl` - Complete timeline of hook/MCP invocations
- `audit_summary.md` - Human-readable audit event summary
- `metrics.json` - Event counts and statistics

## Verification

To verify governance decision event coverage:

```bash
# Check audit events in Scenario 01
sqlite3 .scenario-01-data/governance.db "SELECT DISTINCT event_type FROM audit_log ORDER BY event_type;"

# Verify all 7 governance decision events across all scenarios
python verify_stage_d.py
```

Expected output: All 7 governance decision events covered (100%)

## Documentation

- `SCOPE.md`: Maps existing examples to simulator capabilities
- `SCENARIOS.md`: Defines the three core scenarios in detail
- `ACCEPTANCE_CRITERIA.md`: Verification boundaries and acceptance criteria
- `STAGE_D_COMPLETE.md`: Stage D completion summary

## Implementation

- `simulator/`: Core simulator implementation
  - `core.py`: ClaudeCodeSimulator orchestration class
  - `hook_subprocess.py`: Hook subprocess wrapper
  - `mcp_subprocess.py`: MCP subprocess wrapper
- `scenarios/`: Three demonstration scenarios
  - `scenario_01_discovery.py`: Discovery and auto-grant
  - `scenario_02_staged.py`: Staged workflow with transitions
  - `scenario_03_lifecycle.py`: Grant lifecycle management

## Constraints

- No changes to `src/tool_governance/`
- No changes to existing examples (01, 02, 03)
- Uses real `tg-hook` and `tg-mcp` binaries (not mocks)
- Demonstrates subprocess boundaries, not in-process simulation
