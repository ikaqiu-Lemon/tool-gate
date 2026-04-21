# Closeout · formalize-cache-layers

**Completion window**: Stage A 2026-04-19 · Stages B/C/D 2026-04-20
**Scope boundary**: internal refactor of the L2 (in-process) cache. Zero change to
`mcp_server`, `hook_handler`, `SessionState`, SQLite schema, Langfuse, hooks JSON,
`.mcp.json`, or any consumer module's return shape.

## Cache abstractions — what landed

**New**:
- `SkillIndexer._metadata_cache: VersionedTTLCache` — formal metadata cache instance
- `SkillIndexer.metadata_cache` read-only property — stable public handle
- `SkillIndexer.doc_cache` read-only property — paired naming for the existing doc cache
- `SkillIndexer._indexed_skills: dict[str, (version, source_path)]` — authoritative
  registry of "what the last scan discovered"; replaces the old `_index` metadata dict
- `SkillIndexer._get_metadata(skill_id)` — cache-first lookup with disk-rebuild fallback
- `SkillIndexer._parse_skill_file(skill_id, path)` — shared low-level parser for both
  the scan path and the cache-miss rehydrate path
- `tests/test_cache.py` — shared-contract tests proving role-agnostic behaviour

**Modified**:
- `SkillIndexer.__init__`: new `metadata_cache` + `doc_cache` keyword-only parameters;
  legacy `cache=` accepted with `DeprecationWarning` (maps to `doc_cache`);
  `cache` + `doc_cache` combo raises `TypeError`
- `SkillIndexer.build_index` / `list_skills` / `current_index` / `read_skill` /
  `refresh`: routed through `_get_metadata` / `_metadata_cache`; external return
  shapes unchanged
- `utils/cache.py` module docstring: documents the two usage roles

**Removed**:
- `SkillIndexer._index: dict[str, SkillMetadata]` — eliminated; replaced by the
  registry + metadata cache split
- `SkillIndexer._cache` Stage-B alias (fully replaced by `_doc_cache`)

## Final contract — metadata / doc cache

Both caches satisfy the same four-dimensional contract:

| Dimension | Value |
|---|---|
| Key | `f"{skill_id}::{version}"` via `VersionedTTLCache.make_key` |
| Value type | metadata = `SkillMetadata`, doc = `SkillContent` |
| TTL / maxsize | per-instance constructor args; defaults `maxsize=100`, `ttl=300` |
| Invalidate | `invalidate(key)` per-entry, `clear()` whole-pool, TTL auto-expiry, LRU overflow |
| Observability | `hits` / `misses` counters per instance |

**Cache-is-not-truth invariants enforced in code**:
- miss → rebuild-from-disk via `_parse_skill_file` + cache put
- version drift on disk → registry updated to new version, cache stored under new key
- rehydrate failure → registry entry pruned (never return stale cached value as fresh)
- `refresh()` clears metadata + doc caches within one call

## Verified scenarios (all passing)

| Spec Requirement | Scenario | Test |
|---|---|---|
| Two-layer caching | Repeated catalog listing hits formal cache | `TestMetadataCacheShadow::test_metadata_cache_size_matches_index` + `TestStageC_CacheLayerFormalization::test_cached_and_rebuilt_metadata_are_identical` |
| Two-layer caching | Metadata + doc entries honor common invalidation surface | `TestStageC::test_refresh_clears_both_cache_layers` |
| Two-layer caching | Document cache expires after TTL | `TestVersionedTTLCache` (existing) |
| Refresh skills index | Refresh removes stale document entries | `TestStageC::test_doc_version_bump_supersedes_cached_doc` |
| Refresh skills index | Refresh removes stale metadata entries | `TestStageC::test_metadata_version_bump_supersedes_cache` |
| Refresh skills index | Refresh surfaces post-rebuild skill count | existing `test_refresh_clears_and_rebuilds` |
| Cache is a performance layer | Cache loss does not change governance behaviour | `TestStageC::test_cached_and_rebuilt_metadata_are_identical` |
| Cache is a performance layer | Cached and rebuilt values are interchangeable | same |
| Version change invalidates prior | Version bump supersedes cached doc | `TestStageC::test_doc_version_bump_supersedes_cached_doc` |
| Version change invalidates prior | Version bump supersedes cached metadata | `TestStageC::test_metadata_version_bump_supersedes_cache` |
| Safe fallback | Cache miss triggers clean rebuild | `TestStageC::test_cache_miss_triggers_clean_rebuild` |
| Safe fallback | Refresh failure degrades safely | `TestStageC::test_refresh_failure_drops_stale_entries` |
| Shared contract (cross-role) | make_key / hit-miss / invalidate / clear role-agnostic | `tests/test_cache.py::TestSharedCacheContract` (4 cases) |

**Test totals**:
- `tests/test_skill_indexer.py` + `tests/test_cache.py` → **37 passed**
- `tests/functional/` → **52 passed**
- full suite → **204 passed** (Stage B baseline 194 + 10 new; original 167 baseline + 37 cumulative Stage A–C additions across unrelated work)

## Backlog — explicitly deferred to next propose

Not in scope of this change; must not block archive of the current change:

1. **Metadata-specific TTL tuning** (design.md OQ1) — currently shares doc cache's
   300s default. Consider lengthening (metadata changes less often than doc).
2. **Missing-version degradation** (design.md OQ2) — when SKILL.md has no
   `version:` field, `make_key` falls back to the literal `"unknown"`, so all
   version-less skills share one cache slot. Currently documented only.
3. **Long-term `current_index()` deprecation** (design.md OQ3) — may be folded
   into `list_skills` later; safe to keep for now.
4. **L3 / cross-instance cache** (Redis / shared cache) — out of scope by design.
   Any future propose should re-open the L2/L3 split separately.
5. **Legacy `cache=` parameter removal** — still accepted under
   `DeprecationWarning`. Production callers (`bootstrap.py`, functional
   fixtures) migrated in this change; only the test that *asserts* the
   deprecation warning still uses it. Safe to delete the alias in a
   follow-up after external integrations confirm they are not calling it.

## Recommended commands

**Minimal subset** (verify this change didn't regress cache behaviour):
```
python -m pytest tests/test_skill_indexer.py tests/test_cache.py -q
```

**Functional parity** (external behaviour unchanged):
```
python -m pytest tests/functional -q
```

**Full regression** (Stage D final):
```
python -m pytest -q
```

**Artifact validation**:
```
openspec validate formalize-cache-layers
```

**Archive** (not executed in Stage D — user decision):
```
openspec archive formalize-cache-layers
# or
/opsx:archive formalize-cache-layers
```
