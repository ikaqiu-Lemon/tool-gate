# Stage A Notes — separate-runtime-and-persisted-state

Purpose: field classification + entry inventory + state-flow baseline for later stages. No behavioural change in Stage A.

## 1. `SessionState` field classification

Source: `src/tool_governance/models/state.py`. Classifications align with design §D2.

| Field | Type | Classification | Who reads it | Who writes it |
|---|---|---|---|---|
| `session_id` | `str` | **persisted-only** | every hook / MCP tool (identifies the row in `sessions` table) | created once in `StateManager.load_or_init` when a row is missing; never mutated after |
| `skills_metadata` | `dict[str, SkillMetadata]` | **derived** (currently also persisted; to be downgraded) | `tool_rewriter.recompute_active_tools` (looks up `meta` per loaded skill); `prompt_composer.compose_skill_catalog`; `hook_handler._classify_deny_bucket`; `mcp_server.enable_skill / disable_skill / run_skill_action / change_stage` | populated on first `SessionStart` (`state.skills_metadata = rt.indexer.build_index()`) and on `refresh_skills` (`state.skills_metadata = rt.indexer.current_index()`); also round-tripped through SQLite JSON |
| `skills_loaded` | `dict[str, LoadedSkillInfo]` | **persisted-only** (cross-turn continuity) | rewriter (iterates loaded skills); composer (`[ENABLED]` tag); every MCP tool that checks enablement | `StateManager.add_to_skills_loaded / remove_from_skills_loaded`; `handle_post_tool_use` stamps `last_used_at`; `mcp_server.change_stage` flips `current_stage` |
| `active_tools` | `list[str]` | **derived** (to be removed from persisted payload) | `policy_engine.is_tool_allowed` (gate check in `handle_pre_tool_use`); composer `compose_active_tools_prompt` | `tool_rewriter.recompute_active_tools` mutates in place on every `SessionStart` / `UserPromptSubmit` / `enable_skill` / `disable_skill` / `change_stage` / `refresh_skills`; round-tripped through SQLite JSON |
| `active_grants` | `dict[str, Grant]` | **persisted-only** | `mcp_server.disable_skill` (looks up grant to revoke) | `mcp_server.enable_skill` sets `state.active_grants[skill_id] = grant`; `disable_skill` / grant expiry sweeps remove entries |
| `created_at` | `datetime` | **persisted-only** (audit anchor) | — (inspection only; no governance decision depends on it) | set once by pydantic default factory; preserved by `sqlite_store.save_session` INSERT path |
| `updated_at` | `datetime` | **persisted-only** (audit anchor) | — | `sqlite_store.save_session` rewrites on every upsert |

`LoadedSkillInfo` sub-fields (`skill_id`, `version`, `current_stage`, `last_used_at`) are all **persisted-only** — they carry cross-turn state that must survive hook process restarts.

### Classification summary

- **persisted-only**: `session_id`, `skills_loaded`, `active_grants`, `created_at`, `updated_at`, all `LoadedSkillInfo.*`
- **derived** (authoritative elsewhere, currently also persisted): `skills_metadata` (real authority = `SkillIndexer._metadata_cache`, since `formalize-cache-layers`), `active_tools` (real authority = `tool_rewriter.recompute_active_tools` output)
- **runtime-only**: none today — all derivations are written back to `SessionState` rather than held in an ephemeral context object

## 2. Entry inventory — what each entry does to state

Pattern notation:
- **L** = `state_manager.load_or_init(sid)`
- **M** = mutates the persisted state (specifically which field below)
- **D** = calls a derivation that rewrites `active_tools` / `skills_metadata` *into* the state object (the behavior this change targets)
- **S** = `state_manager.save(state)`
- **A** = `store.append_audit(...)` (does not touch `SessionState`)

### Hook handlers (`src/tool_governance/hook_handler.py`)

| Entry | Sequence | Notes |
|---|---|---|
| `handle_session_start` | **L** → M (cleanup expired grants from `skills_loaded`) → M (first-time `skills_metadata = indexer.build_index()` if empty) → **D** (`recompute_active_tools`) → **S** → A | Only place today that populates `skills_metadata` from the indexer |
| `handle_user_prompt_submit` | **L** → M (cleanup expired) → **D** (`recompute_active_tools`) → **S** → A | Runs every turn; **D** mutates `active_tools` in place |
| `handle_pre_tool_use` | meta-tool fast-path returns without L/S; otherwise **L** → (no mutation) → consults `policy_engine.is_tool_allowed` (reads `state.active_tools`) → A only | Read-only on state; persisted `active_tools` is consumed directly as gate-check input — **this is the main place D2 classification matters** |
| `handle_post_tool_use` | **L** → M (stamp `skills_loaded[sid].last_used_at`) → **S** → A | `active_tools` untouched here |

### MCP meta-tools (`src/tool_governance/mcp_server.py`)

| Entry | Sequence | Notes |
|---|---|---|
| `list_skills` | **L** → M (lazy `skills_metadata = indexer.build_index()` if empty) → **S** → A | Touches derived field; no rewrite |
| `read_skill` | (no L/S) → A | Stateless w.r.t. `SessionState`; delegates to indexer |
| `enable_skill` | **L** → M (`add_to_skills_loaded`, `active_grants[skill_id] = grant`) → **D** (`recompute_active_tools`) → **S** → A | Derives + persists in same step |
| `disable_skill` | **L** → M (`remove_from_skills_loaded`, revoke grant) → **D** → **S** → A | Same pattern |
| `grant_status` | (no L/S) → reads `grant_manager` only | Stateless w.r.t. `SessionState` |
| `run_skill_action` | **L** → (no M; uses `skills_loaded`, `skills_metadata` for gate check) → A | Read-only on state |
| `change_stage` | **L** → M (`skills_loaded[sid].current_stage = stage_id`) → **D** → **S** → A | Stage flip forces recompute |
| `refresh_skills` | **L** → M (`skills_metadata = indexer.current_index()`, after `indexer.refresh()`) → **S** → A | Does **not** call **D** — any stale `active_tools` survives until the next hook with **D** |

### Key observations from the inventory

1. **12 entries total** (4 hook + 8 MCP tool).  Of these, **7 invoke D** (the implicit `recompute_active_tools` step that mutates persisted state), **5 do not**.  The five that skip D are the places most at risk of consuming a stale `active_tools` — notably `handle_pre_tool_use`, which is the actual gate check, and `refresh_skills`, which can leave `skills_metadata` and `active_tools` inconsistent for one turn.
2. **`active_tools` is written 7 times per session lifecycle** but its only true consumer is `policy_engine.is_tool_allowed` inside `pre_tool_use` plus the composer.  Every write is a derivation from `(skills_loaded, skills_metadata, blocked_tools)`; no entry uses the *previous* `active_tools` as input to anything.  This confirms `active_tools` is purely derived and can be runtime-only.
3. **`skills_metadata` has three writers** (`SessionStart` lazy init, `list_skills` lazy init, `refresh_skills`) and is read by rewriter + composer + several MCP tools.  All reads go through `state.skills_metadata.get(skill_id)` — a drop-in replacement by `indexer.current_index()` or per-skill `indexer._get_metadata(skill_id)` is feasible without touching consumer sites beyond the single lookup call.
4. **Persistence path is uniform**: every **S** goes through `StateManager.save` → `SQLiteStore.save_session` → `json.dumps(state.model_dump())` → `UPSERT sessions`.  No special handling per field.  This means Stage C3's serialization-boundary change (exclude derived fields on dump) can be a single-line change in `StateManager.save`.

## 3. Current load → rewrite → writeback order

Canonical sequence for a **mutating** entry (applies to `SessionStart`, `UserPromptSubmit`, `enable_skill`, `disable_skill`, `change_stage`, `post_tool_use`):

```
1. state_manager.load_or_init(sid)
       ├─ sqlite_store.load_session(sid)        # JSON → dict
       └─ SessionState.model_validate(dict)     # dict → pydantic (or fresh SessionState)

2. [entry-specific persisted-state mutations on `state`]
       e.g. state.skills_loaded[...] = ..., state.active_grants[...] = ...

3. tool_rewriter.recompute_active_tools(state)
       └─ mutates state.active_tools in place   # <-- DERIVATION written INTO persisted object

4. state_manager.save(state)
       ├─ SessionState.model_dump(mode="json")  # includes active_tools, skills_metadata
       └─ sqlite_store.save_session(sid, json)  # UPSERT

5. store.append_audit(...)                       # side-effect, no state read
```

For **read-only** entries (`pre_tool_use`, `read_skill`, `grant_status`, `run_skill_action`):

```
1. state_manager.load_or_init(sid)
2. [consult state.active_tools / state.skills_metadata / state.skills_loaded]
3. append_audit(...)
```

### Where the mix-up lives

- **Step 2 and Step 3 both mutate `state`**, but only Step 2 mutations are *authoritative* (truth about the session).  Step 3 is a *derivation* that happens to be written into the same object.  The serialization in Step 4 cannot tell them apart.
- **Read-only entries consume `state.active_tools` directly** — they trust that a prior write path executed Step 3.  Any entry that mutates persisted state without calling Step 3 (today: `post_tool_use`) leaves `active_tools` correct only because `post_tool_use`'s mutation (`last_used_at`) does not affect the derivation.  This fragility is invisible in the current code.

## 4. Baseline test count

Pre-Stage-A baseline (before any Stage A changes): **204 passed** (full `pytest -q`, 2026-04-21).

After Stage A additions (field-classification comments + two skip-marked contract tests in `tests/test_state_manager.py::TestPersistedFieldContract`): **204 passed, 2 skipped** — target met.  Both skips will be lifted in Stage C3.

## 5. How Stage B minimally introduces the runtime/persisted boundary

Given the inventory, Stage B is strictly *additive*:

- **New module** `src/tool_governance/core/runtime_context.py` defines a read-only `RuntimeContext` plus a pure `build_runtime_context(state, indexer, policy, clock) -> RuntimeContext` constructor.
- **`RuntimeContext` fields** carry exactly what rewriter + composer consume today:
  - `active_tools: tuple[str, ...]` — computed fresh from `(state.skills_loaded, indexer.current_index(), policy.blocked_tools)`
  - `enabled_skills_view: tuple[(skill_id, SkillMetadata, LoadedSkillInfo), ...]` — the (skill, metadata, loaded-info) triples the rewriter and composer both need
  - `policy_snapshot` — the blocked-tools set + any future policy knobs relevant to rewrite
  - `clock: datetime` — for deterministic tests
- **`build_runtime_context` is pure**: it reads from `state`, `indexer`, `policy`, and the clock; it does not call `state_manager.save`, does not mutate `state`, and does not populate `state.active_tools` or `state.skills_metadata`.  This keeps Stage B entirely non-behavioral.
- **No caller migration in Stage B**.  The 12 entries keep their current behavior.  The only new consumers of `RuntimeContext` are Stage B's unit tests, which assert:
  1. Empty `SessionState` → `active_tools = meta-tools − blocked`
  2. `skills_loaded` references a skill absent from the indexer → that skill is silently skipped in the view (matches spec "System degrades safely" case)
  3. Same inputs yield equivalent `RuntimeContext` across two calls (idempotency)
  4. Computed `active_tools` equals `tool_rewriter.recompute_active_tools(clone_of_state)` for the same inputs — the behavioural anchor that licenses Stage C to flip the callers

- **Why this is the minimum**:
  - It introduces the type boundary design §D1 calls for without renaming, removing, or re-signing any existing public function.
  - It ships with the regression anchor (test #4) that Stage C needs to prove equivalence when flipping callers.
  - It leaves `SessionState`, `state_manager`, hook handlers, MCP tools, and SQLite untouched — meaning a Stage B commit can ship even if Stage C is deferred indefinitely without harm.

Stage C can then migrate callers in four small segments (C1 rewriter/composer new signatures, C2 hook/mcp entries to four-step flow, C3 serialization exclusion, C4 degradation tests) with every segment validated against the Stage B regression anchor.
