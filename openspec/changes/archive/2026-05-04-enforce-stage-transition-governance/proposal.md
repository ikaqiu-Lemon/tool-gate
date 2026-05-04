## Why

The previous change `formalize-stage-workflow-metadata` established stage workflow metadata as a declarative contract in SKILL.md files (`initial_stage`, `allowed_next_stages`, stage definitions). However, metadata alone provides no runtime enforcement — the system currently accepts any `change_stage` call regardless of whether the transition is valid, and `enable_skill` does not initialize stage state. This creates a gap between declared workflow boundaries and actual runtime behavior.

This change closes that gap by making stage workflow metadata govern actual runtime transitions. Without enforcement, stage metadata is documentation that can be ignored; with enforcement, it becomes a binding contract that prevents invalid state transitions, ensures skills enter their declared initial stage, and guarantees that `active_tools` reflects the current stage's allowed tools.

## What Changes

This change implements runtime stage transition governance:

1. **`enable_skill` initializes stage state** — When a staged skill is enabled, the system enters `initial_stage` (if configured) or the first stage, initializing `current_stage`, `stage_entered_at`, `stage_history`, and `exited_stages`.

2. **`change_stage` validates `allowed_next_stages`** — Stage transitions are checked against the current stage's `allowed_next_stages` list. Invalid transitions (target not in allowlist, terminal stage, uninitialized state) are denied with specific error buckets.

3. **Terminal stage enforcement** — Stages with `allowed_next_stages: []` block further transitions, signaling workflow completion.

4. **No-stage skill compatibility** — Skills without stage definitions continue using `skill.allowed_tools` fallback; calling `change_stage` on them returns `skill_has_no_stages` error.

5. **Stage state persistence** — `current_stage`, `stage_entered_at`, `stage_history`, and `exited_stages` are persisted in `LoadedSkillInfo` and restored across sessions.

6. **Stage-specific error taxonomy** — Introduces error buckets: `stage_transition_not_allowed`, `stage_not_found`, `skill_has_no_stages`, `stage_not_initialized`, `invalid_initial_stage`.

7. **Stage transition audit** — All transition attempts (allowed/denied) are recorded with skill_id, from_stage, to_stage, error_bucket, and timestamp.

8. **Runtime tests** — Comprehensive test coverage for initialization, valid/invalid transitions, terminal stages, no-stage fallback, and state recovery.

**Breaking changes:** None. No-stage skills retain existing behavior; staged skills gain enforcement without API changes.

## Capabilities

### New Capabilities

- `stage-transition-validation`: Runtime validation of stage transitions against `allowed_next_stages` metadata, including terminal stage enforcement and error taxonomy.

### Modified Capabilities

- `skill-lifecycle-management`: `enable_skill` now initializes stage state for staged skills; `change_stage` now validates transitions instead of accepting all requests.

## Impact

**Affected code:**
- `src/tool_governance/mcp_server.py` — `enable_skill` and `change_stage` MCP tool implementations
- `src/tool_governance/tools/langchain_tools.py` — `enable_skill_tool` LangChain wrapper
- `src/tool_governance/core/state_manager.py` — Stage state initialization and update logic
- `src/tool_governance/models/state.py` — `LoadedSkillInfo` gains `stage_history` and `exited_stages` fields
- `src/tool_governance/storage/sqlite_store.py` — Audit log for stage transition events
- `tests/` — New test modules for stage transition validation

**Affected APIs:**
- `enable_skill` return shape unchanged, but now initializes `current_stage` for staged skills
- `change_stage` return shape unchanged, but now includes validation and may return error responses

**Dependencies:**
- Builds on `formalize-stage-workflow-metadata` (already archived)
- No new external dependencies

**Systems:**
- SQLite schema unchanged (existing `LoadedSkillInfo` JSON field accommodates new subfields)
- Audit log table gains new event types (`stage.transition.allow`, `stage.transition.deny`)
- No changes to MCP protocol, hooks, or cache layers
