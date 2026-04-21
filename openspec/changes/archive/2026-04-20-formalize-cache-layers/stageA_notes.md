# Stage A Notes — formalize-cache-layers

> Internal reference. Not synced to `docs/`. Not consumed downstream by Stages B–D
> beyond confirming design.md D4 migration table is accurate.
> Generated: 2026-04-19.

## 1.1 · `SkillIndexer._index` read/write inventory

All references stay **inside** `src/tool_governance/core/skill_indexer.py` —
no external module touches `_index` directly.

| Line | Kind | Method | Snippet |
|---:|---|---|---|
| 138 | declare | `__init__` | `self._index: dict[str, SkillMetadata] = {}` |
| 167 | write (clear) | `build_index` | `self._index.clear()` |
| 171 | **read (leak)** | `build_index` | `return self._index` (returns the live dict when `skills_dir` missing — caller gets a mutable ref, not a copy) |
| 185 | read (copy-out) | `build_index` | `return dict(self._index)` |
| 200 | read (presence) | `list_skills` | `if not self._index:` |
| 201 | side-effect | `list_skills` | `self.build_index()` (lazy rebuild when empty) |
| 202 | read | `list_skills` | `return list(self._index.values())` |
| 223 | read (single) | `read_skill` | `meta = self._index.get(skill_id)` |
| 252 | read (size) | `refresh` | `return len(self._index)` |
| 261 | read (copy-out) | `current_index` | `return dict(self._index)` |
| 301 | write (single) | `_index_one` | `self._index[skill_id] = meta` |

**Observations**:

- Only **3 write points** (declare / clear / single-insert) and **7 read points**
- L171 is the only path that returns a live reference instead of a copy; negligible
  leak (only hit when `skills_dir` is missing) — **out of scope** for this change
- No external module grep-matches `_index` on `SkillIndexer` — private-by-convention
  is also private-in-practice

## 1.2 · `VersionedTTLCache` current call sites

| File:Line | Role |
|---|---|
| `src/tool_governance/utils/cache.py:11` | class definition |
| `src/tool_governance/core/skill_indexer.py:19` | import |
| `src/tool_governance/core/skill_indexer.py:135` | `__init__(cache=)` optional parameter |
| `src/tool_governance/core/skill_indexer.py:137` | `self._cache = cache or VersionedTTLCache()` (default construction) |
| `src/tool_governance/core/skill_indexer.py:227–228` | `make_key(skill_id, version=meta.version)` + `self._cache.get(key)` in `read_skill` |
| `src/tool_governance/core/skill_indexer.py:245` | `self._cache.put(key, content)` in `read_skill` |
| `src/tool_governance/core/skill_indexer.py:250` | `self._cache.clear()` in `refresh` |
| `src/tool_governance/bootstrap.py:24, 110` | runtime wiring: `cache = VersionedTTLCache(maxsize=100, ttl=300)` passed into `SkillIndexer` |
| `src/tool_governance/models/skill.py:30` | docstring mention only |
| `tests/test_skill_indexer.py:14, 291–324` | import + `TestVersionedTTLCache` unit tests (make_key / hash_content / get-miss / put-get / invalidate / clear) |
| `tests/functional/test_functional_fixture_sanity.py:14, 21` | constructs cache for fixture sanity check |

**Confirmation**: all `VersionedTTLCache` traffic lands on the **doc path** (`read_skill` + `refresh`)
and on the constructor boundary (`bootstrap`). Metadata read/write **never** touches
the cache today.

## 1.3 · `current_index()` consumers

Grep shows a **single external caller**:

| File:Line | Context |
|---|---|
| `src/tool_governance/mcp_server.py:296` | `state.skills_metadata = rt.indexer.current_index()` inside `refresh_skills()` |

**Narrower than expected**: the tasks.md guidance listed "mcp_server / tests / hook_handler"
as potential consumers, but the actual footprint is **only** `mcp_server.refresh_skills`.
`hook_handler` goes through `build_index()`, not `current_index()` (`hook_handler.py:107`).
Tests that poke the indexer use `build_index()` directly.

**Implication for Stage C**: migrating `current_index()` to read from `metadata_cache`
is a 1-site swap (L296 contract is `dict[str, SkillMetadata]` — maintain that shape
and the caller is untouched).

## 1.4 · `SessionState.skills_metadata` ↔ `SkillIndexer._index` crossing

Direct writers of `state.skills_metadata`:

| File:Line | Source | Operation |
|---|---|---|
| `src/tool_governance/mcp_server.py:65` | `rt.indexer.build_index()` return dict | full assignment (session-start path) |
| `src/tool_governance/mcp_server.py:296` | `rt.indexer.current_index()` return dict | full assignment (refresh path) |
| `src/tool_governance/hook_handler.py:107` | `rt.indexer.build_index()` return dict | full assignment (session-start path in hook) |

Readers: `tool_rewriter`, `prompt_composer`, `mcp_server` (multiple lookups),
`hook_handler` (multiple lookups), `langchain_tools.enable_skill_tool`.
**All read-only**. None of them write back into `_index`.

Tests manipulate `state.skills_metadata` directly for setup (e.g. `test_integration.py:281`
`state.skills_metadata.pop(...)`), but never against `_index`.

**Conclusion**: the two structures are **independent memory** coupled only by
`build_index()`/`current_index()` returning a **copy** (`dict(self._index)` at L185/L261).
`SessionState.skills_metadata` is downstream of `_index`, serialised to SQLite on each
hook `save`, and survives process death. `_index` dies with the process. **Zero
crossing writes**; the data flow is unidirectional: `_index → return copy → skills_metadata`.

## 1.5 · Where the unified cache contract should land

Scope is narrow and clean:

- **Primary owner**: `src/tool_governance/core/skill_indexer.py` — constructor needs a second
  optional `metadata_cache: VersionedTTLCache | None = None`; backwards-compat for
  the current `cache=` parameter (maps to `doc_cache`, emit `DeprecationWarning`)
- **Abstraction class**: `src/tool_governance/utils/cache.py` — **no structural change
  required** (D1 selected two instances of the existing class). May add a short
  docstring clarifying metadata vs doc usage; nothing else
- **Bootstrap**: `src/tool_governance/bootstrap.py:110` — eventually wires a second
  `VersionedTTLCache(maxsize=100, ttl=300)` instance. Can defer to Stage C migration
  and in Stage B rely on `SkillIndexer.__init__` constructing a default instance
  on its own
- **Consumer surface** (`mcp_server` / `hook_handler` / `tool_rewriter` / `prompt_composer` /
  `langchain_tools`): **zero code change**. They already consume `dict[str, SkillMetadata]`
  return values from `build_index()` / `current_index()` — we keep that shape

**Confirms design.md D4 table**. No surprises. Migration table is actionable as written.

## 1.6 · Next-stage minimal-intrusion plan (for Stage B)

Per design.md D6 (backward-compat) + Stage B task list:

1. `SkillIndexer.__init__`:
   - **Add**: `metadata_cache: VersionedTTLCache | None = None` parameter → default `VersionedTTLCache()`
   - **Map legacy**: the existing `cache=` positional parameter remains, interpreted as
     `doc_cache`; emit `DeprecationWarning` if `cache=` is used instead of the new
     `doc_cache=` / `metadata_cache=` keyword form
2. `build_index()`:
   - **Keep** writes to `self._index` (read path still goes through it in Stage B)
   - **Add** shadow-write: for each indexed metadata, also call
     `metadata_cache.put(make_key(skill_id, version=meta.version), meta)`
3. **No read-path changes** in Stage B — `list_skills` / `current_index` / `read_skill`
   keep current shape. The shadow cache is observed via new tests only
4. New tests under `tests/test_skill_indexer.py`:
   - Asserts `metadata_cache.currsize == len(self._index)` after `build_index()`
   - Asserts custom `metadata_cache` instance receives `put` calls (inject a spy or
     subclass that counts `.put` invocations)
   - Asserts `DeprecationWarning` fires when the legacy `cache=` form is used
5. **Files touched by Stage B**: `skill_indexer.py`, `test_skill_indexer.py`,
   optionally a docstring note in `cache.py`. Nothing else.

**Risk buffer**: Stage B's shadow cache is **observable but inert** — if it turns out
to be wrong, Stage C simply doesn't migrate to it and Stage B can be reverted without
any behavior change.

## Scope confirmation (what Stage A did NOT touch)

- No `src/tool_governance/**/*.py` edits
- No `tests/**/*.py` edits
- No `docs/**` edits
- No Redis, no `SessionState` changes, no observability changes
- Only file created outside the change directory: none

All inventory conclusions are derived from `rg` searches + reads of the explicitly
allowed files (`utils/cache.py`, `core/skill_indexer.py`, `models/state.py`,
`storage/sqlite_store.py`, `tests/test_skill_indexer.py`).
