# Closeout: migrate-demos-to-stage-first-governance

## 1. Change Completion Summary

This change successfully migrated the demo acceptance layer to Stage-first governance, establishing `simulator-demo` as the canonical demonstration of Stage-first skill governance behavior.

**Completed work:**

- **Legacy examples marked deprecated**: `examples/01-knowledge-link`, `examples/02-doc-edit-staged`, `examples/03-lifecycle-and-risk` marked as DEPRECATED/Legacy in `examples/README.md`
- **simulator-demo established as canonical**: Updated as the authoritative Stage-first governance acceptance target
- **Skill fixtures updated**: Created `yuque-doc-edit-staged` (3-stage workflow) and `yuque-knowledge-link` (no-stage fallback) in `examples/simulator-demo/fixtures/skills/`
- **Three scenarios updated**:
  - Scenario 01: Stage-first discovery and metadata validation
  - Scenario 02: Stage transition governance (legal/illegal transitions)
  - Scenario 03: Lifecycle, terminal stages, and grant expiration
- **Verification infrastructure**: Added `verify_stage_first.py` with 11 Stage-first checks, integrated into `run_simulator.sh`
- **Documentation updated**: Root README, examples README, simulator-demo docs (README/SCOPE/SCENARIOS), and authoring guide cross-references
- **Generated artifacts policy**: `.gitignore` updated, 9 previously tracked artifact files removed from git index

## 2. Modified Files Inventory

### Legacy Examples
- `examples/01-knowledge-link/README.md` - Added DEPRECATED notice
- `examples/02-doc-edit-staged/README.md` - Added DEPRECATED notice
- `examples/03-lifecycle-and-risk/README.md` - Added DEPRECATED notice

### simulator-demo Source
**Fixtures:**
- `examples/simulator-demo/fixtures/skills/yuque-doc-edit-staged/SKILL.md` - 3-stage workflow (analysis → execution → verification)
- `examples/simulator-demo/fixtures/skills/yuque-knowledge-link/SKILL.md` - no-stage skill with skill-level allowed_tools

**Scenarios:**
- `examples/simulator-demo/scenarios/scenario_01_discovery.py` - Stage-first discovery, metadata validation, no-stage fallback
- `examples/simulator-demo/scenarios/scenario_02_staged.py` - Stage transition governance, legal/illegal transitions
- `examples/simulator-demo/scenarios/scenario_03_lifecycle.py` - Terminal stage blocking, grant expiration, persistence

**Simulator Helpers:**
- `examples/simulator-demo/simulator/mcp_subprocess.py` - Fixed list_skills bug (collect all content blocks)
- `examples/simulator-demo/simulator/core.py` - Added get_state_snapshot() stage state parsing, enable_skill(ttl=...) support

**Verification:**
- `examples/simulator-demo/run_simulator.sh` - Integrated verify_stage_first.py
- `examples/simulator-demo/verify_stage_first.py` - 11 Stage-first governance checks
- `examples/simulator-demo/.gitignore` - Exclude generated artifacts

**Documentation:**
- `examples/simulator-demo/README.md` - Updated Purpose, Key Behaviors, Current Status
- `examples/simulator-demo/SCOPE.md` - Updated In/Out Scope, Stage-first metadata fields
- `examples/simulator-demo/SCENARIOS.md` - Complete rewrite matching Stage-first implementation

### Documentation Entrypoints
- `README.md` (line 282-283) - Enhanced examples/ description, points to simulator-demo
- `README_CN.md` (line 277-278) - Chinese translation, points to simulator-demo
- `examples/README.md` - Identifies simulator-demo as canonical, marks legacy examples deprecated
- `docs/skill_stage_authoring.md` - Added "11. Complete Examples" cross-reference section

### OpenSpec Artifacts
- `openspec/changes/migrate-demos-to-stage-first-governance/proposal.md`
- `openspec/changes/migrate-demos-to-stage-first-governance/design.md`
- `openspec/changes/migrate-demos-to-stage-first-governance/specs/delivery-demo-harness/spec.md`
- `openspec/changes/migrate-demos-to-stage-first-governance/tasks.md`

### Generated Artifacts Removed from Tracking
- `.scenario-01-data/governance.db`
- `.scenario-01-data/events.jsonl`
- `.scenario-01-data/audit_summary.md`
- `.scenario-02-data/governance.db`
- `.scenario-02-data/events.jsonl`
- `.scenario-02-data/audit_summary.md`
- `.scenario-03-data/governance.db`
- `.scenario-03-data/events.jsonl`
- `.scenario-03-data/audit_summary.md`

## 3. Simulator-demo Layer Bugfix Record

Three bugs were discovered and fixed in the simulator-demo acceptance layer during this change. **All fixes are scoped to simulator-demo helpers, not core runtime.**

### Bug 1: `mcp_subprocess.py` - list_skills only returned first skill

**Problem:**
- `call_tool()` method only extracted the first content block from MCP response
- When `list_skills` returned a list of skills, only the first skill was visible
- Caused Scenario 01 to fail: could not discover `yuque-knowledge-link` (no-stage skill)

**Fix:**
- Modified `call_tool()` to collect and parse all content blocks
- Properly handles list responses from MCP tools

**Scope:**
- simulator-demo MCP wrapper (`examples/simulator-demo/simulator/mcp_subprocess.py`)
- Not a core runtime issue

### Bug 2: `core.py` - get_state_snapshot() could not read stage state

**Problem:**
- `get_state_snapshot()` only read `grants` table
- Could not access `current_stage`, `stage_history`, `exited_stages` from session state
- Blocked Scenario 02/03 verification of stage persistence

**Fix:**
- Added parsing of `sessions.state_json.skills_loaded` to extract stage state
- Returns complete snapshot including stage workflow state

**Scope:**
- simulator-demo helper (`examples/simulator-demo/simulator/core.py`)
- Not a core runtime issue

### Bug 3: `core.py` - enable_skill() did not support TTL parameter

**Problem:**
- Scenario 03 needed to construct naturally expiring grants to test expired grant behavior
- `enable_skill()` wrapper did not pass `ttl` parameter to MCP tool
- Could not verify "expired grant does not contribute to active_tools"

**Fix:**
- Added `ttl` parameter to `enable_skill()` method
- Passes through to MCP `enable_skill` tool

**Scope:**
- simulator-demo helper (`examples/simulator-demo/simulator/core.py`)
- Not a core runtime issue

**Summary:**
- No modifications to `src/` core runtime
- No modifications to `enable_skill` / `change_stage` core implementations
- All bugfixes directly serve demo acceptance requirements

## 4. E2E Verification Results

### Overall Results
- ✅ `./run_simulator.sh` passed all three scenarios
- ✅ `verify_stage_first.py` passed 11/11 Stage-first governance checks
- ✅ Used real `tg-hook` and `tg-mcp` subprocess boundaries
- ✅ Generated real `governance.db` and `audit_log` tables
- ✅ Generated artifacts correctly ignored by git

### Scenario 01: Stage-first Discovery
**Verified behaviors:**
- Discovered 2 skills: `yuque-doc-edit-staged` (staged) and `yuque-knowledge-link` (no-stage)
- `read_skill` returned complete Stage-first metadata for staged skill:
  - `initial_stage: "analysis"`
  - `stages: ["analysis", "execution", "verification"]`
  - Terminal stage identified: `verification` (empty `allowed_next_stages`)
- `read_skill` returned skill-level `allowed_tools` for no-stage skill (fallback behavior)
- Unauthorized tool call correctly denied with `tool_not_available` error
- `skill.read` events recorded in audit_log

### Scenario 02: Stage Transition Governance
**Verified behaviors:**
- `enable_skill` entered `initial_stage` ("analysis")
- `active_tools` changed based on `current_stage`:
  - analysis stage: `["yuque_doc_read", "yuque_doc_list"]`
  - execution stage: `["yuque_doc_update", "yuque_doc_create"]`
- Legal transition succeeded: analysis → execution
- Illegal transition denied: execution → analysis (not in `allowed_next_stages`)
- `error_bucket='stage_transition_not_allowed'` recorded for illegal transition
- `stage.transition.allow` and `stage.transition.deny` events in audit_log

### Scenario 03: Lifecycle and Terminal Stages
**Verified behaviors:**
- Terminal stage blocked further transitions: verification → execution denied
- Stage state persisted to SQLite:
  - `current_stage` updated after each transition
  - `stage_history` accumulated all entered stages
  - `exited_stages` tracked all exited stages
- Expired grant (TTL=2s) did not contribute to `active_tools` after expiration
- Tool call allowed before expiration, denied after expiration
- `disable_skill` removed tools from `active_tools`
- `grant.expire` and `skill.disable` events recorded in audit_log

### Verification Script Results
`verify_stage_first.py` validated:
1. ✅ Scenario 01: skill.read events present
2. ✅ Scenario 01: tool_not_available for unauthorized tool
3. ✅ Scenario 02: stage.transition.allow event present
4. ✅ Scenario 02: stage.transition.deny event present
5. ✅ Scenario 02: error_bucket field in deny event
6. ✅ Scenario 02: legal transition succeeded
7. ✅ Scenario 02: illegal transition denied
8. ✅ Scenario 03: terminal stage blocked transition
9. ✅ Scenario 03: grant expired (status='expired')
10. ✅ Scenario 03: tool denied after expiration
11. ✅ Scenario 03: skill.disable event present

## 5. Acceptance Criteria Mapping

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Legacy examples deprecated | ✅ | `examples/README.md` marks 01/02/03 as DEPRECATED |
| simulator-demo canonical | ✅ | Root README, examples README point to simulator-demo |
| read_skill returns stage metadata | ✅ | Scenario 01 verifies initial_stage, stages, terminal stage |
| No-stage fallback works | ✅ | Scenario 01 verifies skill-level allowed_tools |
| enable_skill enters initial_stage | ✅ | Scenario 02 verifies current_stage="analysis" after enable |
| active_tools follows current_stage | ✅ | Scenario 02 verifies tools change with stage transitions |
| Legal transition allowed | ✅ | Scenario 02: analysis → execution succeeds |
| Illegal transition denied | ✅ | Scenario 02: execution → analysis denied |
| Terminal stage denies transitions | ✅ | Scenario 03: verification → execution denied |
| Expired grant no active_tools | ✅ | Scenario 03: TTL=2s grant expires, tools unavailable |
| Stage state persistence | ✅ | Scenario 03: current_stage, stage_history, exited_stages in DB |
| disable/revoke removes tools | ✅ | Scenario 03: disable_skill removes tools from active_tools |
| Audit contains stage events | ✅ | stage.transition.allow/deny, error_bucket verified |
| run_simulator.sh runs all scenarios | ✅ | Script executes 01/02/03 and calls verify_stage_first.py |
| Generated artifacts not committed | ✅ | .gitignore excludes .scenario-*-data/, 9 files removed from index |

**All acceptance criteria met.**

## 6. Scope Boundary

**Confirmed NOT done (as intended):**

- ❌ Did not migrate old examples' SKILL.md or scripts to Stage-first format
- ❌ Did not delete old examples (marked deprecated, kept for reference)
- ❌ Did not add a fourth scenario
- ❌ Did not modify `src/` core runtime code
- ❌ Did not rename `active_tools` / `allowed_tools` in core runtime
- ❌ Did not introduce Tool registry / Redis / workflow engine
- ❌ Did not refactor runtime unit tests
- ❌ Did not commit generated artifacts (`.scenario-*-data/` directories)

**Scope was strictly limited to:**
- Demo acceptance layer (`examples/simulator-demo/`)
- Documentation entrypoints (README, examples/README, authoring guide)
- Legacy example deprecation notices
- Simulator-demo helper bugfixes (not core runtime)

## 7. Remaining Work / Known Notes

**No blockers identified.**

**Status:**
- All Stage 1-12 tasks complete (75/77 tasks)
- Stage 13 (Final Documentation Sync) ready to begin
- Ready for final verification after Stage 13

**Notes:**
- Generated artifacts (`.scenario-*-data/`) exist locally but are correctly ignored by git
- 9 previously tracked artifact files show as deleted (D) in git status - this is expected and correct
- All three scenarios run successfully through real subprocess boundaries
- All Stage-first governance behaviors verified through acceptance tests
