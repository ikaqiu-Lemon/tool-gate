# Closeout: migrate-entrypoints-to-runtime-flow

**Completed:** 2026-04-28  
**OpenSpec validation:** ✅ Passing  
**Test suite:** ✅ 238 tests passing

---

## Migration Checklist

### Entry Points Migrated to RuntimeContext

All four hook entry points now accept `RuntimeContext` instead of raw `SessionState`:

- ✅ `PromptComposer.compose()` - accepts `ctx: RuntimeContext | None`
- ✅ `HookHandler.pre_tool_use()` - accepts `ctx: RuntimeContext`
- ✅ `HookHandler.post_tool_use()` - accepts `ctx: RuntimeContext`
- ✅ `HookHandler.user_prompt_submit()` - accepts `ctx: RuntimeContext`

### RuntimeContext Construction

- ✅ `build_runtime_context()` function in `src/tool_governance/core/runtime_context.py`
- ✅ Grant expiry filtering: expired grants don't contribute tools to `ctx.active_tools`
- ✅ `HookHandler` builds `RuntimeContext` before calling hooks
- ✅ `RuntimeContext` includes `state`, `indexer`, `clock`, and `active_tools` fields

### Persistence Boundary

- ✅ `SessionState.DERIVED_FIELDS = {"active_tools", "skills_metadata"}`
- ✅ `SessionState.to_persisted_dict()` excludes derived fields
- ✅ `StateManager.save()` uses `to_persisted_dict()`
- ✅ `skills_metadata` always fetched from `indexer.current_index()` at runtime
- ✅ `active_tools` computed from `active_grants` and `skills_metadata` at runtime

### Deprecated APIs

The following APIs still exist for backward compatibility but emit `DeprecationWarning`:

- `ToolRewriter.recompute_active_tools(state)` - should pass `indexer` parameter
- Direct access to `state.skills_metadata` - should use `indexer.current_index()`
- Direct access to `state.active_tools` - should use `ctx.active_tools` from `RuntimeContext`

**Trigger conditions:**
- `recompute_active_tools()` called without `indexer` parameter
- Test code directly reads `state.skills_metadata` (all instances migrated in this change)

---

## Test Coverage

### New Test Files

- `tests/test_runtime_context.py` - RuntimeContext construction and grant filtering
- `tests/test_grant_expiry_runtime_view.py` - Grant expiry filtering in `build_runtime_context()`

### Modified Test Files

**Core tests:**
- `tests/test_state_manager.py` - Updated persistence contract tests
- `tests/test_prompt_composer.py` - Migrated to RuntimeContext
- `tests/test_tool_rewriter.py` - Added indexer parameter support
- `tests/test_hook_lifecycle.py` - Migrated to RuntimeContext

**Functional tests:**
- `tests/functional/test_functional_happy_path.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_policy_e2e.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_policy_e2e_lifecycle.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_revoke.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_stage.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_ttl.py` - Migrated to RuntimeContext
- `tests/functional/test_functional_phase4_scenarios.py` - Migrated to RuntimeContext

**Integration tests:**
- `tests/test_integration.py` - Migrated to RuntimeContext

### Test Results

```
$ pytest -q
238 passed in 2.45s
```

All tests passing, including:
- 18 tests in `test_state_manager.py` (persistence contract)
- 3 tests in `test_grant_expiry_runtime_view.py` (grant expiry filtering)
- 35 tests in hook lifecycle and prompt composer
- 182 functional and integration tests

---

## Documentation Updates

- ✅ `docs/technical_design.md` - Added Addendum explaining relationship to `separate-runtime-and-persisted-state`
- ✅ `docs/dev_plan.md` - Added entry for `migrate-entrypoints-to-runtime-flow`
- ✅ `openspec/changes/migrate-entrypoints-to-runtime-flow/tasks.md` - All stages marked complete
- ✅ `docs/requirements.md` - No changes required (no new requirements)

---

## Verification Summary

| Check | Status | Notes |
|-------|--------|-------|
| All tests passing | ✅ | 238/238 tests pass |
| OpenSpec validation | ✅ | `openspec validate` passes |
| No direct `state.skills_metadata` access | ✅ | All migrated to `indexer.current_index()` |
| No direct `state.active_tools` access | ✅ | All migrated to `ctx.active_tools` |
| Persistence contract enforced | ✅ | `to_persisted_dict()` excludes derived fields |
| Grant expiry filtering | ✅ | Expired grants don't contribute tools |
| Documentation updated | ✅ | technical_design.md, dev_plan.md |

---

## Backlog / Future Work

**Not in scope for this change:**

1. **Hot-reloading of skill metadata:** Now that `skills_metadata` is runtime-derived, we could implement automatic reloading when skill files change on disk. This would require:
   - File watcher on `skills/` directory
   - `SkillIndexer.refresh()` call on file change
   - Hook to notify active sessions

2. **StateStore abstraction:** The current `StateManager` uses JSON file storage. A future change could introduce a `StateStore` interface to support Redis, SQLite, or other backends.

3. **Observability taxonomy:** Add structured logging for:
   - Grant expiry events
   - RuntimeContext construction
   - Skill metadata refresh

4. **Deprecation removal:** After a grace period, remove the deprecated APIs:
   - `recompute_active_tools()` without `indexer` parameter
   - Direct `state.skills_metadata` access in public APIs

**Deferred from separate-runtime-and-persisted-state:**

This change completes the deferred work from `separate-runtime-and-persisted-state`:
- ✅ Exclude `skills_metadata` from persistence
- ✅ Exclude `active_tools` from persistence
- ✅ Introduce `RuntimeContext` as the hook entry point contract

---

## Commit History

- `da1762d` - chore(openspec): archive add-delivery-demo-workspaces
- `83fc08c` - stage D: preflight, fast policy, wrap-up and invariants
- `fe628f6` - stage C-root: wire examples/README to QUICKSTART
- `50649cd` - stage C-03: migrate 03-lifecycle-and-risk README
- `2e049ab` - stage C-02: migrate 02-doc-edit-staged README

**Stage E commit:** (pending)

---

## Sign-off

All acceptance criteria from `proposal.md` and `specs/` met:
- ✅ All hook entry points accept `RuntimeContext`
- ✅ `skills_metadata` and `active_tools` excluded from persistence
- ✅ Grant expiry filtering implemented
- ✅ All tests passing
- ✅ Documentation updated

**Ready for archive.**
