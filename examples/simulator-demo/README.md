# Simulator Demo

**Status**: Canonical Stage-first Governance Acceptance Demo

This directory contains the canonical acceptance demonstration for Stage-first governance. It validates that the runtime correctly implements stage workflow metadata, stage transition governance, terminal stages, and expired grant exclusion through real subprocess boundaries.

## Purpose

The simulator demonstrates **Stage-first governance behaviors**:
- **Stage workflow metadata discovery**: `read_skill` returns `initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools`
- **Stage transition governance**: Legal transitions succeed, illegal transitions denied with `stage_transition_not_allowed`
- **Active tools follow current stage**: `active_tools` reflects only the current stage's `allowed_tools`
- **Terminal stage enforcement**: Stages with `allowed_next_stages=[]` block further transitions
- **No-stage skill fallback**: Skills without `stages` field use skill-level `allowed_tools` directly
- **Expired grant exclusion**: Grants past their TTL do not contribute tools to runtime `active_tools`
- **Stage state persistence**: `current_stage`, `stage_history`, `exited_stages` persist to SQLite and restore correctly

The simulator also demonstrates **subprocess isolation and protocol boundaries**:
- Hook subprocess isolation (tg-hook via stdin/stdout)
- MCP server subprocess isolation (tg-mcp via stdio protocol)
- SQLite WAL shared state coordination
- Complete audit trail generation

## What This Demo Validates

**Scenario 01: Stage-first Discovery and Metadata**
- ✓ `list_skills` discovers both staged and no-stage skills
- ✓ `read_skill` returns complete stage workflow metadata for staged skills
- ✓ `read_skill` shows fallback behavior (skill-level `allowed_tools`) for no-stage skills
- ✓ Terminal stages identified via `allowed_next_stages=[]`
- ✓ Unauthorized tools denied with `tool_not_available`

**Scenario 02: Stage Transition Governance**
- ✓ `enable_skill` enters `initial_stage` automatically
- ✓ `active_tools` reflects current stage's `allowed_tools` only
- ✓ Legal transitions succeed (analysis → execution)
- ✓ Illegal transitions denied with `stage_transition_not_allowed`
- ✓ Stage state persists to SQLite (`current_stage`, `stage_history`, `exited_stages`)

**Scenario 03: Lifecycle, Terminal Stages, and Expiration**
- ✓ Full stage lifecycle (analysis → execution → verification)
- ✓ Terminal stage blocks further transitions (verification → execution denied)
- ✓ Stage state restores from SQLite after session restart
- ✓ Expired grants (TTL elapsed) do not contribute tools to `active_tools`
- ✓ `disable_skill` removes tools from `active_tools`

All scenarios run through **real subprocess boundaries** (tg-hook, tg-mcp, governance.db). Artifacts are generated from actual execution, not mocked.

## Running the Scenarios

Each scenario runs independently and generates its own artifacts:

```bash
cd examples/simulator-demo

# Scenario 01: Stage-first discovery and metadata
python scenarios/scenario_01_discovery.py

# Scenario 02: Stage transition governance
python scenarios/scenario_02_staged.py

# Scenario 03: Lifecycle, terminal stages, and expiration
python scenarios/scenario_03_lifecycle.py
```

Each scenario creates a `.scenario-XX-data/` directory containing:
- `governance.db` - SQLite database with audit_log, sessions, grants, and persisted stage state
- `events.jsonl` - Complete timeline of hook/MCP invocations
- `audit_summary.md` - Human-readable audit event summary
- `metrics.json` - Event counts and statistics

**Note**: These artifacts are generated from actual execution through real subprocess boundaries. They are not static mocks or pre-written files.

## Verification

To verify Stage-first governance behaviors:

```bash
# Check stage transition audit events in Scenario 02
sqlite3 .scenario-02-data/governance.db "SELECT event_type, detail FROM audit_log WHERE event_type LIKE 'stage.%' ORDER BY created_at;"

# Verify stage state persistence in Scenario 03
sqlite3 .scenario-03-data/governance.db "SELECT state_json FROM sessions WHERE session_id = 'scenario-03';"

# Check all audit event types across scenarios
for db in .scenario-*-data/governance.db; do
  echo "=== $db ==="
  sqlite3 "$db" "SELECT DISTINCT event_type FROM audit_log ORDER BY event_type;"
done
```

Expected audit events include:
- `stage.transition.allow` - Legal stage transitions
- `stage.transition.deny` - Illegal transitions (e.g., from terminal stage)
- `grant.expire` - Grant TTL expiration
- `skill.enable`, `skill.disable` - Skill lifecycle
- `tool.call` - Tool authorization decisions
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
- `fixtures/skills/`: Skill definitions for testing Stage-first governance
  - `yuque-doc-edit-staged/`: Staged skill with three stages (`analysis` → `execution` → `verification`). The `verification` stage is terminal (`allowed_next_stages: []`), demonstrating stage transition governance and terminal stage behavior.
  - `yuque-knowledge-link/`: No-stage skill that uses `allowed_tools` directly without defining stages. Demonstrates backward compatibility and fallback behavior for skills that don't adopt the Stage-first model.

## Constraints

- No changes to `src/tool_governance/`
- No changes to existing examples (01, 02, 03)
- Uses real `tg-hook` and `tg-mcp` binaries (not mocks)
- Demonstrates subprocess boundaries, not in-process simulation
