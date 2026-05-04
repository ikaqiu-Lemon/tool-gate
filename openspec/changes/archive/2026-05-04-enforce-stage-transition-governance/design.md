# Design: enforce-stage-transition-governance

## Context

### Current State

The `formalize-stage-workflow-metadata` change established stage workflow metadata as a declarative contract:
- `SkillMetadata.initial_stage: str | None` — declares which stage to enter on enable
- `StageDefinition.allowed_next_stages: list[str]` — declares valid transitions from each stage
- `LoadedSkillInfo.current_stage: str | None` — tracks current stage per enabled skill
- `ToolRewriter.get_stage_tools(skill_meta, current_stage)` — selects stage-specific allowed_tools
- `RuntimeContext.active_tools` — computed from current stage tools
- `mcp_server.enable_skill` — creates grants and adds to skills_loaded
- `mcp_server.change_stage` — accepts stage_id parameter
- `StateManager` — persists SessionState to SQLite
- Audit mechanism — records governance events

### Current Gaps

1. **`enable_skill` does not initialize stage state** — When a staged skill is enabled, `current_stage` is not set, `stage_entered_at` is not initialized, and no stage history is created.

2. **`change_stage` does not validate transitions** — Any `change_stage` call is accepted regardless of whether the target stage exists or is in `allowed_next_stages`.

3. **No stage lifecycle tracking** — Missing `stage_entered_at`, `stage_history`, and `exited_stages` fields to track stage progression.

4. **No terminal stage enforcement** — Stages with `allowed_next_stages: []` do not block further transitions at runtime.

5. **Stage-specific errors incomplete** — Error buckets like `invalid_initial_stage`, `stage_not_found`, `stage_not_initialized`, `stage_transition_not_allowed`, `skill_has_no_stages` are not consistently returned.

### Constraints

- Must preserve no-stage skill compatibility (existing skills without stages continue working)
- Must not break existing MCP tool contracts (return shapes unchanged)
- Must use existing audit mechanism (no observability taxonomy redesign)
- Must persist stage state in existing SQLite schema (no schema migration)
- Must not expand scope to demo migration, tool registry, or workflow engine features

---

## Goals / Non-Goals

### Goals

1. **Initialize stage state on enable_skill** — Staged skills enter `initial_stage` (or first stage) with initialized `current_stage`, `stage_entered_at`, `stage_history`, and `exited_stages`.

2. **Validate stage transitions in change_stage** — Enforce `allowed_next_stages` constraints, deny invalid transitions with specific error buckets, and only update state on valid transitions.

3. **Enforce terminal stages** — Stages with `allowed_next_stages: []` block all further transitions.

4. **Fail safely for invalid initial_stage** — If `initial_stage` references a nonexistent stage, deny enable_skill without creating a grant.

5. **Persist and restore stage state** — All stage state fields survive session save/restore cycles.

6. **Audit stage transitions** — Record both allowed and denied transitions with full context (from_stage, to_stage, error_bucket).

7. **Maintain no-stage skill compatibility** — Skills without stages continue using skill-level `allowed_tools`; calling `change_stage` on them returns `skill_has_no_stages`.

### Non-Goals

- ❌ Migrate simulator-demo or mark old examples deprecated
- ❌ Update demo runbooks or README files
- ❌ Introduce Tool registry or rename active_tools/allowed_tools
- ❌ Implement Redis, StateStore, or CacheStore abstractions
- ❌ Redesign observability taxonomy
- ❌ Build complex human approval workflows
- ❌ Create a general-purpose workflow engine

---

## Decisions

### Decision 1: Extend LoadedSkillInfo for stage state

**Choice:** Add stage lifecycle fields directly to `LoadedSkillInfo` model.

**Rationale:**
- `LoadedSkillInfo` already tracks per-skill runtime state (`skill_id`, `version`, `current_stage`, `last_used_at`)
- Adding `stage_entered_at`, `stage_history`, `exited_stages` keeps all stage state co-located
- Pydantic model serialization handles persistence automatically via existing `SessionState.to_persisted_dict()` flow
- No SQLite schema migration needed (JSON field accommodates new subfields)

**New fields:**
```python
class StageTransitionRecord(BaseModel):
    from_stage: str
    to_stage: str
    transitioned_at: datetime

class LoadedSkillInfo(BaseModel):
    skill_id: str
    version: str
    current_stage: str | None = None
    last_used_at: datetime | None = None
    stage_entered_at: datetime | None = None          # NEW
    stage_history: list[StageTransitionRecord] = []   # NEW
    exited_stages: list[str] = []                     # NEW
```

**Why `StageTransitionRecord` only stores successful transitions:**
- Per specs: `stage_history` SHALL record successful transitions only
- Denied attempts are recorded in audit, not in `stage_history`
- This keeps the skill's workflow path clean and unambiguous
- No `decision` field needed in `StageTransitionRecord` (all entries are implicitly "allow")

**Why `exited_stages` not `completed_stages`:**
- Semantic clarity: "exited" means "left this stage" (factual)
- "completed" implies business-level task completion (subjective)
- Stage transitions are structural, not semantic

**Alternatives considered:**
- Separate `StageState` table in SQLite → rejected (adds complexity, breaks existing serialization flow)
- Store stage_history in audit log only → rejected (loses per-skill queryability, audit is append-only)

---

### Decision 2: enable_skill initialization logic

**Choice:** Determine target initial stage with this precedence:
1. If `skill.initial_stage` exists and is valid → use it
2. If `skill.initial_stage` is None/empty and `skill.stages` exists → use first stage
3. If `skill.initial_stage` exists but is invalid → fail safely with `invalid_initial_stage`
4. If `skill.stages` is empty/None → set `current_stage=None` (no-stage skill)

**Implementation in `mcp_server.enable_skill`:**

```python
# After policy evaluation succeeds...
skill_meta = state.skills_metadata.get(skill_id)

if skill_meta and skill_meta.stages:
    # Staged skill: determine initial stage
    if skill_meta.initial_stage:
        # Validate initial_stage exists
        stage_ids = [s.stage_id for s in skill_meta.stages]
        if skill_meta.initial_stage not in stage_ids:
            # Fail safely
            audit_log.record("skill.enable", session_id, skill_id=skill_id,
                           decision="deny", detail={"error_bucket": "invalid_initial_stage"})
            return {"granted": False, "error": "invalid_initial_stage"}
        target_stage = skill_meta.initial_stage
    else:
        # Fallback to first stage
        target_stage = skill_meta.stages[0].stage_id
    
    # Initialize stage state
    loaded_info = LoadedSkillInfo(
        skill_id=skill_id,
        version=skill_meta.version,
        current_stage=target_stage,
        stage_entered_at=datetime.now(timezone.utc),
        stage_history=[],
        exited_stages=[]
    )
else:
    # No-stage skill: current_stage remains None
    loaded_info = LoadedSkillInfo(
        skill_id=skill_id,
        version=skill_meta.version if skill_meta else "unknown",
        current_stage=None
    )

state.skills_loaded[skill_id] = loaded_info
# ... create grant, rebuild RuntimeContext, save state
```

**Rationale:**
- Explicit validation prevents silent failures
- Fail-safe behavior (no grant, no tools) protects against misconfigured skills
- Fallback to first stage provides sensible default for skills without `initial_stage`
- No-stage skills remain unaffected

**Alternatives considered:**
- Silent fallback to first stage when `initial_stage` is invalid → rejected (hides configuration errors)
- Raise exception on invalid `initial_stage` → rejected (breaks MCP contract, should return error response)

---

### Decision 3: change_stage validation sequence

**Choice:** Validate in this order (fail-fast on first violation):

1. **Load state and metadata** — Get `SessionState`, `RuntimeContext`, `SkillMetadata`
2. **Check skill enabled** — Verify `skill_id in state.skills_loaded`
3. **Check metadata exists** — Verify `skill_meta is not None`
4. **Check skill has stages** — If `not skill_meta.stages` → deny with `skill_has_no_stages`
5. **Check target stage exists** — If `target_stage_id not in stage_ids` → deny with `stage_not_found`
6. **Check current_stage initialized** — If `loaded_info.current_stage is None` → deny with `stage_not_initialized`
7. **Find current stage definition** — Lookup `current_stage` in `skill_meta.stages`
8. **Check allowed_next_stages** — 
   - If `allowed_next_stages == []` → deny with `stage_transition_not_allowed` (terminal stage)
   - If `target_stage_id not in allowed_next_stages` → deny with `stage_transition_not_allowed`
   - Else → allow
9. **On allow:** Update state, rebuild RuntimeContext, save, audit
10. **On deny:** Audit only, no state mutation

**Implementation in `mcp_server.change_stage`:**

```python
def change_stage(skill_id: str, stage_id: str) -> dict:
    state = state_manager.load_or_init(session_id)
    ctx = build_runtime_context(state, indexer.current_index(), blocked_tools, clock)
    
    # 2. Check enabled
    if skill_id not in state.skills_loaded:
        return {"changed": False, "error": "skill_not_enabled"}
    
    loaded_info = state.skills_loaded[skill_id]
    skill_meta = ctx.all_skills_metadata.get(skill_id)
    
    # 3. Check metadata
    if not skill_meta:
        return {"changed": False, "error": "skill_metadata_unavailable"}
    
    # 4. Check has stages
    if not skill_meta.stages:
        audit_log.record("stage.transition.deny", session_id, skill_id=skill_id,
                       detail={"to_stage": stage_id, "error_bucket": "skill_has_no_stages"})
        return {"changed": False, "error": "skill_has_no_stages"}
    
    # 5. Check target exists
    stage_ids = [s.stage_id for s in skill_meta.stages]
    if stage_id not in stage_ids:
        audit_log.record("stage.transition.deny", session_id, skill_id=skill_id,
                       detail={"to_stage": stage_id, "error_bucket": "stage_not_found"})
        return {"changed": False, "error": "stage_not_found"}
    
    # 6. Check current_stage initialized
    if loaded_info.current_stage is None:
        audit_log.record("stage.transition.deny", session_id, skill_id=skill_id,
                       detail={"to_stage": stage_id, "error_bucket": "stage_not_initialized"})
        return {"changed": False, "error": "stage_not_initialized"}
    
    # 7. Find current stage definition
    current_stage_def = next(s for s in skill_meta.stages if s.stage_id == loaded_info.current_stage)
    
    # 8. Check allowed_next_stages
    if stage_id not in current_stage_def.allowed_next_stages:
        # Terminal stage or not in allowlist
        audit_log.record("stage.transition.deny", session_id, skill_id=skill_id,
                       detail={"from_stage": loaded_info.current_stage, "to_stage": stage_id,
                              "error_bucket": "stage_transition_not_allowed"})
        return {"changed": False, "error": "stage_transition_not_allowed"}
    
    # 9. Allow: update state
    from_stage = loaded_info.current_stage
    loaded_info.exited_stages.append(from_stage)
    loaded_info.stage_history.append(StageTransitionRecord(
        from_stage=from_stage,
        to_stage=stage_id,
        transitioned_at=datetime.now(timezone.utc)
    ))
    loaded_info.current_stage = stage_id
    loaded_info.stage_entered_at = datetime.now(timezone.utc)
    
    # Rebuild RuntimeContext with new current_stage
    ctx = build_runtime_context(state, indexer.current_index(), blocked_tools, clock)
    state.sync_from_runtime(ctx)  # Update active_tools compat field
    state_manager.save(state)
    
    audit_log.record("stage.transition.allow", session_id, skill_id=skill_id,
                   detail={"from_stage": from_stage, "to_stage": stage_id})
    
    return {"changed": True, "new_active_tools": list(ctx.active_tools)}
```

**Rationale:**
- Fail-fast order minimizes unnecessary computation
- Each error bucket maps to exactly one validation failure
- Denied transitions leave state unchanged (atomic semantics)
- Terminal stage check uses same error bucket as allowlist violation (both are "transition not allowed")

**Alternatives considered:**
- Separate error bucket for terminal stage → rejected (overcomplicates taxonomy, both are "not allowed")
- Allow self-transitions (stage → same stage) → rejected (specs require target in `allowed_next_stages`)

---

### Decision 4: RuntimeContext and active_tools computation

**Choice:** No changes to `RuntimeContext` or `ToolRewriter.get_stage_tools()` needed.

**Rationale:**
- `ToolRewriter.get_stage_tools(skill_meta, current_stage)` already selects stage-specific `allowed_tools`
- `RuntimeContext.active_tools` is already computed from `current_stage` via `build_runtime_context()`
- This change only ensures `current_stage` is correctly initialized (enable_skill) and updated (change_stage)
- Once `current_stage` is set, existing machinery handles tool exposure automatically

**Behavior confirmation:**
- Staged skill with `current_stage="analysis"` → `active_tools` includes analysis stage tools
- After `change_stage` to "execution" → `active_tools` recomputed to execution stage tools
- No-stage skill with `current_stage=None` → `get_stage_tools()` returns `skill.allowed_tools`
- Expired grants do not contribute tools to `active_tools` (filtered by `build_runtime_context()`)
- `blocked_tools` still filtered after stage tool selection

**No changes needed to:**
- `src/tool_governance/core/runtime_context.py`
- `src/tool_governance/core/tool_rewriter.py`

**Changes needed to:**
- `src/tool_governance/mcp_server.py` — `enable_skill` and `change_stage` implementations
- `src/tool_governance/tools/langchain_tools.py` — `enable_skill_tool` wrapper (mirror MCP changes)

---

### Decision 5: Error bucket taxonomy

**Choice:** Introduce 5 new stage-specific error buckets:

| Error Bucket | Produced By | Condition |
|--------------|-------------|-----------|
| `invalid_initial_stage` | `enable_skill` | `initial_stage` configured but not in `stages` list |
| `skill_has_no_stages` | `change_stage` | Skill has no `stages` field |
| `stage_not_found` | `change_stage` | Target stage_id not in `stages` list |
| `stage_not_initialized` | `change_stage` | `current_stage` is None (skill enabled but stage not set) |
| `stage_transition_not_allowed` | `change_stage` | Target not in `allowed_next_stages` OR terminal stage (`allowed_next_stages: []`) |

**Return structure (MCP tool response):**
```python
# Success
{"changed": True, "new_active_tools": [...]}
{"granted": True, "allowed_tools": [...]}

# Failure
{"changed": False, "error": "<error_bucket>"}
{"granted": False, "error": "<error_bucket>"}
```

**Audit detail structure:**
```python
# Successful transition
audit_log.record("stage.transition.allow", session_id,
                skill_id=skill_id,
                detail={"from_stage": "analysis", "to_stage": "execution"})

# Denied transition
audit_log.record("stage.transition.deny", session_id,
                skill_id=skill_id,
                detail={"from_stage": "analysis", "to_stage": "deployment",
                       "error_bucket": "stage_transition_not_allowed"})

# Invalid initial_stage
audit_log.record("skill.enable", session_id,
                skill_id=skill_id,
                decision="deny",
                detail={"error_bucket": "invalid_initial_stage"})
```

**Rationale:**
- Distinct error buckets enable precise debugging and metrics
- Error strings are machine-readable (no free-form messages)
- Audit records preserve full context (from/to stages, error reason)
- Existing audit mechanism accommodates new event types without schema changes

**Alternatives considered:**
- Generic `stage_error` bucket → rejected (loses diagnostic precision)
- HTTP-style error codes (400, 404) → rejected (not idiomatic for this codebase)

---

### Decision 6: Audit event design

**Choice:** Use existing `audit_log.record()` mechanism with two new event types:

**Event types:**
- `stage.transition.allow` — Successful stage transition
- `stage.transition.deny` — Denied stage transition
- `skill.enable` (existing, extended) — Now includes `invalid_initial_stage` denials

**Audit record fields:**
```python
{
    "timestamp": "2026-05-03T10:30:00Z",
    "session_id": "session-abc123",
    "event_type": "stage.transition.allow",
    "skill_id": "yuque-knowledge-link",
    "decision": "allow",
    "detail": {
        "from_stage": "analysis",
        "to_stage": "execution"
    }
}

{
    "timestamp": "2026-05-03T10:31:00Z",
    "session_id": "session-abc123",
    "event_type": "stage.transition.deny",
    "skill_id": "yuque-knowledge-link",
    "decision": "deny",
    "detail": {
        "from_stage": "analysis",
        "to_stage": "deployment",
        "error_bucket": "stage_transition_not_allowed"
    }
}
```

**Rationale:**
- Reuses existing `SQLiteStore.record_audit()` without schema changes
- `detail` JSON field accommodates stage-specific context
- `decision` field ("allow"/"deny") enables funnel analysis
- Denied transitions recorded in audit but NOT in `stage_history` (per specs)

**No changes needed to:**
- `src/tool_governance/storage/sqlite_store.py` (audit table schema unchanged)
- Observability taxonomy (no new metrics or trace structure)

---

### Decision 7: Test strategy

**Test organization:**

#### Unit tests: `tests/test_stage_transition_governance.py`

**enable_skill tests:**
- `test_enable_staged_skill_with_initial_stage` — Enters configured initial_stage
- `test_enable_staged_skill_without_initial_stage` — Enters first stage
- `test_enable_invalid_initial_stage_fails_safely` — Returns `invalid_initial_stage`, no grant created
- `test_enable_no_stage_skill_preserves_compatibility` — `current_stage=None`, uses skill.allowed_tools
- `test_enable_initializes_stage_entered_at` — Timestamp set
- `test_enable_initializes_empty_stage_history` — `stage_history=[]`, `exited_stages=[]`

**change_stage tests:**
- `test_change_stage_valid_transition_succeeds` — Updates state, returns success
- `test_change_stage_target_not_found` — Returns `stage_not_found`
- `test_change_stage_current_stage_not_initialized` — Returns `stage_not_initialized`
- `test_change_stage_terminal_stage_denies` — `allowed_next_stages: []` blocks transition
- `test_change_stage_target_not_in_allowlist` — Returns `stage_transition_not_allowed`
- `test_change_stage_no_stage_skill_denies` — Returns `skill_has_no_stages`
- `test_change_stage_denied_does_not_mutate_state` — `current_stage`, `stage_history`, `exited_stages` unchanged

**Persistence tests:**
- `test_current_stage_persists_and_restores` — Save/load cycle preserves `current_stage`
- `test_stage_entered_at_persists_and_restores`
- `test_stage_history_persists_and_restores`
- `test_exited_stages_persists_and_restores`

**active_tools tests:**
- `test_active_tools_reflects_current_stage` — Analysis stage exposes read tools
- `test_active_tools_updates_after_change_stage` — Execution stage exposes write tools
- `test_blocked_tools_still_filtered` — Global blocklist applied to stage tools
- `test_expired_grant_removes_stage_tools` — Expired skill's tools removed from active_tools
- `test_no_stage_skill_uses_top_level_allowed_tools` — Fallback behavior preserved

**Audit tests:**
- `test_allowed_transition_audited` — `stage.transition.allow` record exists
- `test_denied_transition_audited` — `stage.transition.deny` record exists with error_bucket
- `test_denied_transition_not_in_stage_history` — Denied attempt not recorded in `stage_history`
- `test_invalid_initial_stage_audited` — `skill.enable` deny record with `invalid_initial_stage`

#### Integration tests: `tests/test_integration.py` (extend existing)

- `test_full_stage_lifecycle` — enable → change_stage → change_stage → terminal stage → deny
- `test_stage_state_survives_session_restart` — Enable staged skill, save, load, verify state intact

**Coverage target:** 95%+ for new code paths in `mcp_server.py`, `langchain_tools.py`, `models/state.py`

---

### Decision 8: Compatibility and migration strategy

**Backward compatibility guarantees:**

1. **No-stage skills unchanged** — Skills without `stages` field continue working exactly as before
   - `current_stage` remains None
   - `allowed_tools` comes from skill-level field
   - `change_stage` returns `skill_has_no_stages` (new error, but no-op behavior)

2. **Staged skills without `initial_stage`** — Automatically enter first stage (sensible default)

3. **Staged skills without `allowed_next_stages`** — Default is `[]` (terminal stage)
   - **Impact:** Existing staged skills become terminal by default if `allowed_next_stages` is not specified
   - **Mitigation:** This is correct behavior (no transitions allowed unless explicitly declared)
   - **Action required:** Skill authors must add `allowed_next_stages` to enable transitions
   - **Test/fixture updates:** Add `allowed_next_stages` to test skills where transitions are expected

4. **MCP tool contracts unchanged** — Return shapes for `enable_skill` and `change_stage` remain compatible
   - Success: `{"granted": true, "allowed_tools": [...]}` / `{"changed": true, "new_active_tools": [...]}`
   - Failure: `{"granted": false, "error": "..."}` / `{"changed": false, "error": "..."}`

5. **SQLite schema unchanged** — New fields stored in existing JSON columns

**Migration steps:**

1. **Code changes** — Update `mcp_server.py`, `langchain_tools.py`, `models/state.py`
2. **Test updates** — Add `allowed_next_stages` to test fixtures where stage transitions are tested
3. **Skill updates** — Add `allowed_next_stages` to existing staged skills in `skills/` directory (if any)
4. **Documentation** — Update `docs/skill_stage_authoring.md` to emphasize `allowed_next_stages` requirement

**No demo migration in this change** — `examples/` workspaces updated in follow-up `migrate-demos-to-stage-first-governance` change.

---

## Risks / Trade-offs

### Risk 1: Existing staged skills become terminal by default

**Risk:** Staged skills without explicit `allowed_next_stages` will have `allowed_next_stages: []` (default), making them terminal stages that block all transitions.

**Mitigation:**
- This is correct behavior per specs (no transitions allowed unless explicitly declared)
- Skill authors must add `allowed_next_stages` to enable transitions
- Update test fixtures to include `allowed_next_stages` where transitions are expected
- Document in `docs/skill_stage_authoring.md`

**Trade-off:** Requires skill authors to be explicit about allowed transitions (good for safety, requires more upfront design).

---

### Risk 2: Invalid initial_stage in production skills

**Risk:** If a production skill has `initial_stage` pointing to a nonexistent stage, `enable_skill` will fail.

**Mitigation:**
- Fail-safe behavior prevents exposing tools from misconfigured skills
- Error bucket `invalid_initial_stage` provides clear diagnostic
- Audit record captures the failure for debugging
- Skill validation tests should catch this before deployment

**Trade-off:** Strict validation may surface latent configuration errors (good for correctness, may require immediate fixes).

---

### Risk 3: Stage state persistence overhead

**Risk:** Adding `stage_history`, `exited_stages`, `stage_entered_at` increases `SessionState` JSON size.

**Mitigation:**
- `stage_history` grows linearly with transitions (typically < 10 entries per skill per session)
- `exited_stages` is a simple string list (typically < 10 entries)
- SQLite TEXT column accommodates growth
- Existing `SessionState.to_persisted_dict()` excludes derived fields (`active_tools`, `skills_metadata`)

**Trade-off:** Slightly larger session records (acceptable for auditability and state recovery).

---

### Risk 4: Terminal stage confusion

**Risk:** Users may not understand why `change_stage` is denied from a terminal stage.

**Mitigation:**
- Error bucket `stage_transition_not_allowed` is clear
- Audit record includes `from_stage` and `to_stage` for debugging
- Documentation explains terminal stage semantics

**Trade-off:** Requires users to understand stage workflow design (acceptable for advanced feature).

---

## Migration Plan

### Deployment Steps

1. **Merge code changes** — `mcp_server.py`, `langchain_tools.py`, `models/state.py`
2. **Run tests** — Verify all new tests pass, no regressions in existing tests
3. **Update test fixtures** — Add `allowed_next_stages` to staged skills in `tests/fixtures/skills/`
4. **Update production skills** — Add `allowed_next_stages` to any staged skills in `skills/` directory
5. **Deploy plugin** — No SQLite migration needed (JSON fields accommodate new subfields)
6. **Monitor audit logs** — Check for `invalid_initial_stage` or `stage_transition_not_allowed` errors

### Rollback Strategy

If critical issues arise:

1. **Revert code changes** — Git revert commits for `mcp_server.py`, `langchain_tools.py`, `models/state.py`
2. **Existing sessions continue working** — New fields ignored by old code (Pydantic `extra="ignore"`)
3. **No data loss** — Stage state fields remain in SQLite, can be read after re-deploying fix
4. **Audit records preserved** — New event types (`stage.transition.allow/deny`) remain in audit log

**Rollback safety:** No destructive changes to data model or schema; new fields are additive.

---

## Open Questions

### OQ1: Should stage_history have a max length?

**Question:** Should `stage_history` be capped (e.g., last 50 transitions) to prevent unbounded growth?

**Decision:** No cap in V1. Monitor session sizes in production; add LRU eviction if needed.

**Rationale:** Most skills have < 10 transitions per session; premature optimization adds complexity.

**Status:** Non-blocking. Deferred to future optimization if session size becomes an issue.

---

### OQ2: Should invalid_initial_stage be a warning instead of an error?

**Question:** Should we allow enable_skill to succeed with a fallback to first stage, logging a warning instead of failing?

**Decision:** Fail safely (return error, no grant). Strict validation prevents misconfigured skills from exposing tools.

**Rationale:** Configuration errors should be surfaced immediately, not silently papered over.

**Status:** Closed. Design decision finalized.

---

### OQ3: Should we support stage transition reasons?

**Question:** Should `change_stage` accept an optional `reason` parameter (like `enable_skill` does)?

**Decision:** Not in V1. Can be added later if needed for audit/compliance.

**Rationale:** Stage transitions are structural (workflow progression), not authorization decisions requiring justification.

**Status:** Non-blocking. Deferred to future enhancement if audit requirements change.
