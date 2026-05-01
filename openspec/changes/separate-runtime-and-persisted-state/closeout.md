# Closeout · separate-runtime-and-persisted-state

**Completion window**: Stage A 2026-04-21 · Stages B/C/D 2026-04-21 · Stage C3 minimal closeout patch 2026-04-21
**Scope boundary**: L1 (session) layer semantic refactor.  Zero change to
SQLite schema, `.mcp.json`, `hooks/hooks.json`, `config/default_policy.yaml`,
cache layer (`SkillIndexer` / `VersionedTTLCache`), observability taxonomy,
Langfuse, or any consumer-side return shape.  MCP / LangChain entry-point
migration explicitly out of scope.

## New / modified state abstractions

**New**:

- `src/tool_governance/core/runtime_context.py`
  - `RuntimeContext` — frozen dataclass, never persisted, holds
    `active_tools` / `enabled_skills` / `all_skills_metadata` / `policy` / `clock`
  - `EnabledSkillView` — `(skill_id, metadata, loaded_info)` triple
  - `PolicySnapshot` — frozen view of `blocked_tools`
  - `build_runtime_context(state, metadata, blocked_tools, clock)` —
    pure constructor; fallback metadata chain
    `indexer.current_index()` → `state.skills_metadata`
- `tool_rewriter.compute_active_tools(ctx) -> list[str]` — new rewrite
  entry point consuming the runtime view
- `SessionState.DERIVED_FIELDS` — `frozenset({"active_tools"})` (narrowed
  at the minimal C3 closeout patch; `skills_metadata` exclusion deferred
  to the MCP / LangChain entry-point migration follow-up — see backlog #1)
- `SessionState.to_persisted_dict()` — used by `state_manager.save` to
  exclude `active_tools` from the persisted payload (Stage C3 minimal
  closeout)
- `SessionState.sync_from_runtime(runtime_active_tools)` — compat shim
  that mirrors `ctx.active_tools` onto `state.active_tools`
- `ToolRewriter.blocked_tools` — readonly property, removes private
  `_blocked` access from consumers
- `tests/test_runtime_context.py` — 7 cases covering the boundary
- `tests/test_hook_lifecycle.py` — 6 integration cases covering the
  full lifecycle + degradation + legacy fallback

**Modified**:

- `src/tool_governance/core/prompt_composer.py` — `compose_context` /
  `compose_skill_catalog` / `compose_active_tools_prompt` accept
  `SessionState | RuntimeContext`; runtime-view path reads only from
  ctx, legacy path preserved byte-for-byte
- `src/tool_governance/hook_handler.py` — four handlers follow the
  explicit `load → derive → rewrite/compose/gate → persist` order;
  `_classify_deny_bucket` and the gate check both consume ctx
- `src/tool_governance/core/state_manager.py` — `save` routes through
  `SessionState.to_persisted_dict()` (Stage C3 minimal closeout);
  `active_tools` no longer written to the `sessions` table
- `src/tool_governance/models/state.py` — field-level classification
  comments; `DERIVED_FIELDS` (narrowed to `{"active_tools"}`) /
  `to_persisted_dict` / `sync_from_runtime`
- `src/tool_governance/core/tool_rewriter.py` — `blocked_tools`
  property + `compute_active_tools(ctx)` module function;
  `recompute_active_tools(state)` retained unchanged as compat path
- `tests/test_state_manager.py` — contract tests
  (`TestPersistedFieldContract`, `TestAuditReplayFromPersistedState`)
  enabled and aligned with the narrowed exclusion: assert
  `active_tools` is absent AND `skills_metadata` is still present
- `tests/functional/test_functional_*.py` — seven functional tests
  that read `state.active_tools` after a fresh `load_or_init` now call
  `rt.tool_rewriter.recompute_active_tools(state)` first.  Test-side
  adaptation only; no MCP / LangChain production code touched

**Removed**: none.  All legacy signatures remain callable.

## Final field classification (L1 session state)

| Field on `SessionState` | Class | Persistence | Notes |
|---|---|---|---|
| `session_id` | **persisted-only** | sqlite | Row identity |
| `skills_loaded` (+ `LoadedSkillInfo.*`) | **persisted-only** | sqlite | Cross-turn continuity of enabled skills, `current_stage`, `last_used_at` |
| `active_grants` | **persisted-only** | sqlite | Grant-state continuity |
| `created_at` / `updated_at` | **persisted-only** | sqlite | Audit anchors |
| `skills_metadata` | **derived** (compat mirror) | sqlite | Real authority = `SkillIndexer.current_index()`; still persisted until MCP / LangChain entry-point migration (backlog #1) — unmigrated readers in `mcp_server.py` and `tools/langchain_tools.py` still consume `state.skills_metadata` directly |
| `active_tools` | **derived** (compat mirror) | **never** (excluded at C3) | Real authority = `RuntimeContext.active_tools`; held in-memory via `sync_from_runtime` during a turn but excluded from `state_manager.save`'s persisted payload |
| `RuntimeContext.active_tools` | **runtime-only** | never | Tuple, frozen, rebuilt each turn |
| `RuntimeContext.enabled_skills` | **runtime-only** | never | Resolved via indexer + `skills_loaded` |
| `RuntimeContext.all_skills_metadata` | **runtime-only** | never | Shared view used by deny-bucket classifier |
| `RuntimeContext.policy` | **runtime-only** | never | `PolicySnapshot` with `blocked_tools` |
| `RuntimeContext.clock` | **runtime-only** | never | Turn timestamp |

## Verified scenarios

All passing under `pytest -q`:

| Spec Requirement | Scenario | Test |
|---|---|---|
| session-lifecycle · Runtime state and persisted state are semantically distinct | Rewrite does not mutate its source state | `tests/test_tool_rewriter.py::TestComputeActiveToolsFromRuntimeContext::test_compute_active_tools_does_not_mutate_state` |
| session-lifecycle · Persisted state contains only recovery, continuity, and audit fields | `PostToolUse` writes durable `last_used_at`; doesn't round-trip derived fields | `tests/test_hook_lifecycle.py::TestLifecycleLoadDeriveRewritePersist::test_post_tool_use_writes_durable_last_used_at` |
| session-lifecycle · Runtime state reconstructed safely from persisted state + current context | `SessionStart` runs load → derive → compose → persist end-to-end | `tests/test_hook_lifecycle.py::TestLifecycleLoadDeriveRewritePersist::test_session_start_persists_durable_fields_only_after_derive` |
| session-lifecycle · Identical inputs yield equivalent runtime views | Two `build_runtime_context` calls with the same inputs | `tests/test_runtime_context.py::TestBuildRuntimeContext::test_idempotent_under_same_inputs` |
| session-lifecycle · Safe degradation — no persisted record | First-ever session handles `PreToolUse` cleanly | `tests/test_hook_lifecycle.py::TestDegradationAndCompat::test_pre_tool_use_on_missing_persisted_state` |
| session-lifecycle · Safe degradation — unknown loaded skill | Persisted `skills_loaded` entry with no index match | `tests/test_hook_lifecycle.py::TestDegradationAndCompat::test_pre_tool_use_with_unknown_loaded_skill` + `tests/test_runtime_context.py::TestBuildRuntimeContext::test_unknown_skill_is_skipped_safely` + `tests/test_prompt_composer.py::TestComposeFromRuntimeContext::test_compose_handles_unknown_skill_in_persisted_state` |
| session-lifecycle · Safe degradation — legacy derived fields | Legacy JSON loaded, derived values ignored | `tests/test_hook_lifecycle.py::TestDegradationAndCompat::test_session_start_with_legacy_derived_fields` |
| tool-surface-control · Rewrite consumes runtime state | `compute_active_tools(ctx)` returns ctx's tools | `tests/test_tool_rewriter.py::TestComputeActiveToolsFromRuntimeContext::test_compute_active_tools_returns_ctx_tools` |
| tool-surface-control · Rewrite matches legacy output | Equivalence anchor between new and legacy paths | `tests/test_runtime_context.py::TestBuildRuntimeContext::test_matches_tool_rewriter_output` |
| tool-surface-control · Prompt composition consumes runtime state | Composer accepts `RuntimeContext` directly | `tests/test_prompt_composer.py::TestComposeFromRuntimeContext::test_compose_accepts_runtime_context` |
| tool-surface-control · Composition ignores stale prior-turn derivations | Stale `state.active_tools` bypassed when ctx is passed | `tests/test_prompt_composer.py::TestComposeFromRuntimeContext::test_compose_ignores_stale_state_active_tools_when_ctx_passed` |
| tool-surface-control · Policy / index changes take effect next turn | Two consecutive `UserPromptSubmit` calls with swapped metadata | `tests/test_hook_lifecycle.py::TestLifecycleLoadDeriveRewritePersist::test_user_prompt_submit_composes_from_runtime_view` |
| RuntimeContext immutability | Frozen dataclass rejects attribute reassignment | `tests/test_runtime_context.py::TestRuntimeContextIsImmutable::test_frozen_dataclass_rejects_mutation` |

**Test totals**:
- Pre-change baseline: **204 passed**
- Post-Stage-D: **222 passed, 2 skipped**
- Post-Stage-C3 minimal closeout patch: **225 passed, 0 skipped**
  (2 previously-skipped contract tests in `TestPersistedFieldContract`
  enabled; 1 new `TestAuditReplayFromPersistedState` test covering the
  session-lifecycle scenario "Audit replay works from persisted state
  alone"; 7 functional tests updated to recompute `active_tools` after
  `load_or_init`)

## Backlog — deferred to future change

1. **`skills_metadata` exclusion from persisted payload** — the Stage
   C3 minimal closeout patch only excludes `active_tools`; removing
   `skills_metadata` is deferred to the MCP / LangChain entry-point
   migration follow-up because unmigrated readers (`mcp_server.py`
   lines 64/69/127/229/264/296 and `tools/langchain_tools.py:74`)
   still consume `state.skills_metadata` directly.  The persisted-field
   contract test explicitly asserts this deferred scope
   (`test_persisted_json_excludes_active_tools`:
   `skills_metadata` MUST still be present until the follow-up lands).
2. **MCP meta-tool migration** — 8 `@mcp.tool` entries in
   `mcp_server.py` (`list_skills` / `read_skill` / `enable_skill` /
   `disable_skill` / `grant_status` / `run_skill_action` /
   `change_stage` / `refresh_skills`) still follow the pre-Stage-C
   `recompute_active_tools(state)` pattern.  Any unification around
   `RuntimeContext` must land together with item 1 so the persisted
   dict can finally drop `skills_metadata` without regression.
3. **`recompute_active_tools(state)` DeprecationWarning + `tests/test_tool_rewriter.py` migration** —
   holding off so the MCP migration above can land without production
   log noise.  Tasks 3.2 / 3.4 remain unchecked with explicit deferral
   notes.
4. **Grant-expiry runtime-view regression test** — existing tests cover
   `cleanup_expired` semantics; a ctx-visibility test for expired
   grants was not added this round (task 3.21 kept deferred).
5. **LangChain tool shim migration** — `tools/langchain_tools.py:74`
   reads `state.skills_metadata` the same way MCP does; moves with
   item 2.
6. **Open questions from design.md** (all three non-blocking):
   - OQ1 `RuntimeContext` naming — settled at `RuntimeContext`
     (vs `RuntimeView`)
   - OQ2 degradation audit event naming — not emitted this round;
     revisit when observability taxonomy is next touched
   - OQ3 `recompute_active_tools` deprecation window — tied to items
     1–3 above
7. **Policy_engine.is_tool_allowed migration** — hook gate is already
   off this path (Stage C uses `ctx.active_tools_set()` directly), but
   the function remains for MCP callers; it will naturally retire with
   item 2.

## Recommended commands

**Minimal subset** (verify this change didn't regress its own surface):
```
pytest tests/test_runtime_context.py tests/test_tool_rewriter.py tests/test_prompt_composer.py tests/test_hook_lifecycle.py tests/test_state_manager.py -q
```

**Functional parity** (external behaviour unchanged):
```
pytest tests/functional -q
```

**Full regression**:
```
pytest -q
```

**Artifact validation**:
```
openspec validate separate-runtime-and-persisted-state
```

**Archive** (not executed in Stage D per user direction):
```
openspec archive separate-runtime-and-persisted-state
# or
/opsx:archive separate-runtime-and-persisted-state
```
