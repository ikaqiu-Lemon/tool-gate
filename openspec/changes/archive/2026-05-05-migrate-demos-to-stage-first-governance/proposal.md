## Why

The first two changes of the Stage-first Skill governance refactor (`formalize-stage-workflow-metadata` and `enforce-stage-transition-governance`) have established the metadata schema and runtime enforcement mechanisms. However, the demonstration layer remains disconnected: legacy examples (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`) predate the Stage-first model and do not validate the new governance behaviors. Without a canonical acceptance target that exercises the full Stage-first pipeline through real hook/MCP subprocess boundaries, we cannot verify that the refactor delivers its promised capabilities or guide users toward the correct usage patterns.

This change completes the Stage-first governance refactor by migrating the demonstration and acceptance layer to prove the system works end-to-end.

## What Changes

This change will:

1. **Mark legacy examples as deprecated** — Add clear deprecation notices to `examples/01-knowledge-link`, `examples/02-doc-edit-staged`, and `examples/03-lifecycle-and-risk` READMEs indicating they are historical artifacts and not canonical Stage-first demos. These examples will remain in place for reference but will not be migrated or maintained.

2. **Migrate `examples/simulator-demo` to Stage-first acceptance target** — Update the simulator-demo scenarios, SKILL.md files, verification artifacts, and runbook to demonstrate all Stage-first governance behaviors through real subprocess boundaries (not static mocks).

3. **Update demo entry points** — Modify `examples/README.md` and root `README.md` to direct users to `examples/simulator-demo` as the canonical Stage-first governance demonstration.

4. **Update authoring guide references** — Add minimal cross-references in `docs/skill_stage_authoring.md` pointing to real simulator-demo examples without rewriting the core standard.

5. **Provide end-to-end verification** — Ensure `examples/simulator-demo/run_simulator.sh` (or equivalent) can serve as the acceptance command for Stage-first governance.

## Capabilities

### New Capabilities

None. This change does not introduce new runtime capabilities — it migrates the demonstration layer to validate existing Stage-first governance behaviors.

### Modified Capabilities

- `delivery-demo-harness`: The existing delivery demo harness spec will be updated to reflect Stage-first governance scenarios. The simulator-demo workspace will demonstrate:
  - `read_skill` returning stage workflow metadata (`initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools`)
  - `enable_skill` entering `initial_stage` or first stage
  - `current_stage` controlling `active_tools`
  - Legal `change_stage` succeeding
  - Illegal `change_stage` being rejected with `stage_transition_not_allowed`
  - Terminal stage refusing further transitions
  - No-stage Skill fallback remaining valid
  - Expired grants not contributing tools to runtime view
  - Stage state persistence and recovery
  - Audit records containing `stage.transition.allow`, `stage.transition.deny`, and `error_bucket` fields

## Impact

**Affected code:**
- `examples/simulator-demo/` — scenarios, SKILL.md files, verification artifacts, runbook
- `examples/01-knowledge-link/README.md`, `examples/02-doc-edit-staged/README.md`, `examples/03-lifecycle-and-risk/README.md` — deprecation notices
- `examples/README.md` — demo entry point redirection
- Root `README.md` — demo entry point redirection (if applicable)
- `docs/skill_stage_authoring.md` — minimal cross-references to simulator-demo

**Not affected:**
- Core governance runtime (`src/tool_governance/core/`)
- Metadata schema (`models/skill.py`)
- MCP server (`mcp_server.py`)
- Hook handler (`hook_handler.py`)
- Policy engine, state manager, grant manager
- SQLite schema
- Core runtime test expectations (unless blocking bugs are discovered during demo verification)

**Test scope:**
- Simulator-demo verification tests, scripts, and `run_simulator.sh` are in scope
- Demo acceptance tests may be updated
- Core runtime unit tests remain unchanged unless blocking bugs require fixes
- This is not a runtime unit test refactor

**Systems:**
- Demonstration and acceptance layer only
- No production runtime changes unless blocking bugs are discovered during verification

**Dependencies:**
- Requires completed `formalize-stage-workflow-metadata` change (archived)
- Requires completed `enforce-stage-transition-governance` change (archived)

## Acceptance Criteria

1. Legacy examples (`01-knowledge-link`, `02-doc-edit-staged`, `03-lifecycle-and-risk`) clearly marked as Deprecated / Legacy
2. `examples/README.md` points to `simulator-demo` as the canonical Stage-first demo
3. Simulator-demo proves `read_skill` returns stage workflow metadata (`initial_stage`, `stages`, `allowed_next_stages`, `stage.allowed_tools`)
4. Simulator-demo proves `enable_skill` enters `initial_stage` (or first stage)
5. Simulator-demo proves `active_tools` changes with `current_stage`
6. Simulator-demo proves legal stage transitions succeed
7. Simulator-demo proves illegal transitions are rejected with `stage_transition_not_allowed`
8. Simulator-demo proves terminal stages refuse further transitions
9. Simulator-demo proves no-stage Skill fallback still works
10. Simulator-demo proves expired grants don't contribute tools to runtime view
11. Simulator-demo proves stage state persists and recovers across sessions
12. Simulator-demo audit artifacts contain `stage.transition.allow`, `stage.transition.deny`, and `error_bucket` fields
13. `run_simulator.sh` (or equivalent) runs all scenarios end-to-end
14. All related tests pass
15. `openspec validate` passes (format and specification compliance)
16. `/opsx:verify` confirms examples/docs/simulator align with runtime behavior (completeness, correctness, coherence)
