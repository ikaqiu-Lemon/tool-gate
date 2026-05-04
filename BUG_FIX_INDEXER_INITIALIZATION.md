# Bug Fix: Hook Handler Indexer Initialization

## Summary

Fixed a critical bug where `handle_user_prompt_submit` and `handle_pre_tool_use` failed to initialize the skill indexer when `skills_metadata` was empty, causing all tool calls to be denied with `tool_not_available` errors.

## Root Cause

**Process isolation + Stage D persistence strategy:**

1. **Stage D excludes `skills_metadata` from persistence** (it's a derived field in `SessionState.DERIVED_FIELDS`)
2. **Each hook invocation spawns a new subprocess** that loads persisted state from SQLite
3. **Loaded state has empty `skills_metadata`** (because it's not persisted)
4. **`handle_user_prompt_submit` and `handle_pre_tool_use` didn't check for empty metadata** and initialize the indexer
5. **Empty metadata → empty `active_tools` → all tool calls denied**

## The Bug

Only `handle_session_start` had the initialization check:

```python
# handle_session_start (CORRECT)
if not state.skills_metadata:
    state.skills_metadata = rt.indexer.build_index()
```

But `handle_user_prompt_submit` and `handle_pre_tool_use` were missing this check, causing them to operate with empty skill metadata in fresh hook subprocesses.

## The Fix

Added the same initialization check to both handlers:

### `handle_user_prompt_submit` (line 185-186)

```python
# After expired grants cleanup
if not state.skills_metadata:
    state.skills_metadata = rt.indexer.build_index()
```

### `handle_pre_tool_use` (line 313-314)

```python
# After loading state
if not state.skills_metadata:
    state.skills_metadata = rt.indexer.build_index()
```

## Files Changed

- `src/tool_governance/hook_handler.py`: Added indexer initialization checks
- `tests/test_hook_indexer_initialization.py`: Added regression tests (3 test cases)

## Test Results

- **New tests**: 3 passed
- **Full test suite**: 241 passed (no regressions)
- **Scenario 01**: Now completes successfully with tool calls allowed

## Verification

Before fix:
```
Step 5 (UserPromptSubmit): "No skills registered"
Step 6 (PreToolUse): decision = "deny"
```

After fix:
```
Step 5 (UserPromptSubmit): Shows skill catalog with 2 skills
Step 6 (PreToolUse): decision = "allow" ✓
```

## Why This Matters

This bug would have prevented the governance system from working correctly in production scenarios where:
- Hook handlers run as separate processes (the normal deployment model)
- Skills metadata is not persisted (Stage D design)
- Multiple hook invocations occur in a session

The fix ensures that every hook handler can independently rebuild the skill index from the filesystem when needed, making the system resilient to process boundaries.
