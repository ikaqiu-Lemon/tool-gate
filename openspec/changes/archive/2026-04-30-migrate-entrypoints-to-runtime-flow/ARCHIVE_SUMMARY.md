# Archive Summary: migrate-entrypoints-to-runtime-flow

**Archived:** 2026-04-30  
**Status:** ✅ Complete  
**Test Coverage:** 238 passed (Phase 13 baseline: ≥104)

## Overview

This change migrated all 8 MCP entry points and the LangChain integration to a unified four-step runtime flow pattern, eliminating direct reads of `state.active_tools` and `state.skills_metadata`. The migration established `RuntimeContext` as the single source of truth for runtime-visible state.

## Backlog Items Closed

This change fully resolved the following deferred work items from `docs/technical_design.md`:

- **3.10** "Migrate all entry points to unified runtime flow" → ✅ Complete
- **3.2** "Exclude skills_metadata from persisted state" → ✅ Complete  
- **3.4** "Add grant expiry filtering in build_runtime_context" → ✅ Complete
- **3.21** "Deprecate recompute_active_tools(state)" → ✅ Complete

## Key Deliverables

### Code Changes

1. **RuntimeContext as source of truth** (`src/tool_governance/core/runtime_context.py`)
   - `build_runtime_context()` now filters expired grants before computing `active_tools`
   - All 8 MCP entry points use `_build_runtime_ctx()` helper
   - LangChain integration (`langchain_tools.py`) migrated to runtime flow

2. **Derived fields excluded from persistence** (`src/tool_governance/models/state.py`)
   - `SessionState.DERIVED_FIELDS = frozenset({"active_tools", "skills_metadata"})`
   - `to_persisted_dict()` excludes both fields from JSON serialization
   - `state_manager.save()` uses `to_persisted_dict()` to prevent derived field persistence

3. **Tool rewriter deprecation** (`src/tool_governance/core/tool_rewriter.py`)
   - `recompute_active_tools(state)` emits `DeprecationWarning` and delegates to `compute_active_tools(ctx)`
   - New `compute_active_tools(ctx)` function accepts `RuntimeContext` directly
   - Legacy callers still work but are warned to migrate

### Test Coverage

- **test_mcp_runtime_flow.py**: Verifies all 8 MCP entry points follow unified pattern using poisoned state
- **test_grant_expiry_runtime_view.py**: Regression tests for expired grant filtering in `RuntimeContext.active_tools`
- **test_tool_rewriter.py**: Verifies deprecation warning, immutability, and runtime context consumption
- **Functional tests**: All migrated to create grants for loaded skills and read from `indexer.current_index()`

### Documentation

- **docs/technical_design.md**: Updated Addendum to reflect deferred work completion
- **docs/dev_plan.md**: Added entry documenting the 4-stage migration and key decisions
- **openspec/specs/**: Delta specs merged into main specs (session-lifecycle, tool-surface-control)
- **closeout.md**: Comprehensive migration checklist and acceptance criteria

## Spec Changes

### session-lifecycle/spec.md

Added 2 new requirements:
1. **Persisted state excludes derived fields**: `active_tools` and `skills_metadata` not serialized
2. **MCP entry points follow unified runtime flow**: All 8 entry points use four-step pattern

### tool-surface-control/spec.md

Added 3 new requirements:
1. **Tool rewriting consumes RuntimeContext**: `recompute_active_tools` deprecated, `compute_active_tools` uses `ctx`
2. **LangChain tool surface follows unified runtime flow**: `get_allowed_tools` builds `RuntimeContext` and returns `ctx.active_tools`
3. **Expired grants removed from runtime-visible tool surface**: `build_runtime_context` filters expired grants

## Migration Stages

- **Stage A**: Establish `RuntimeContext` as runtime view container
- **Stage B**: Migrate 8 MCP entry points to `_build_runtime_ctx()` helper
- **Stage C**: Migrate LangChain integration to runtime flow
- **Stage D**: Exclude `skills_metadata` from persistence, add grant expiry filtering
- **Stage E**: Documentation sync and closeout

## Verification Results

- ✅ All 36 tasks completed (A.1-A.6, B.1-B.10, C.1-C.6, D.1-D.6, E.1-E.8)
- ✅ 238 tests passed (exceeds Phase 13 baseline of 104)
- ✅ `openspec validate` passed
- ✅ No scope creep (no Redis, StateStore abstraction, or observability taxonomy)
- ✅ All entry points verified to use `RuntimeContext` (poisoned state test)
- ✅ Expired grant regression tests in place

## Follow-up Work

The following items remain for future changes:

1. **Remove `state.active_tools` field entirely** (blocked on full deprecation cycle)
2. **Remove `state.skills_metadata` field entirely** (blocked on full deprecation cycle)
3. **Migrate remaining legacy callers** of `recompute_active_tools(state)` to `compute_active_tools(ctx)`
4. **Consider making `RuntimeContext` immutable** (dataclass with frozen=True)

## Notes

- The migration maintained backward compatibility via `sync_from_runtime()` for legacy code paths
- All functional tests updated to create grants for loaded skills (required by new grant expiry filtering)
- Delta specs successfully merged into main specs without conflicts
- No breaking changes to external APIs (MCP protocol unchanged)

---

**Archive Location:** `openspec/changes/archive/2026-04-30-migrate-entrypoints-to-runtime-flow/`  
**Commit Range:** 83fc08c..11fb29a  
**Primary Commits:**
- b5cb88b: stage D: exclude skills_metadata from persistence, add grant expiry filtering
- 7fd70c2: stage E: documentation updates and closeout
- 11fb29a: chore: mark Stage E tasks complete
