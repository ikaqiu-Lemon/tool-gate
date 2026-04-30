# session-lifecycle Specification Delta

## MODIFIED Requirements

### Requirement: Persisted state excludes derived fields

The `SessionState` persisted to SQLite SHALL exclude derived fields (`active_tools`, `skills_metadata`) from the JSON payload. The `state_manager.save` method MUST use `SessionState.to_persisted_dict()` to filter out fields in `SessionState.DERIVED_FIELDS`. Legacy sessions with derived fields in their JSON MUST load without error (pydantic ignores extra fields). The authoritative sources for derived fields are: `RuntimeContext.active_tools` (rebuilt each turn) and `SkillIndexer.current_index()` (for metadata).

#### Scenario: Persisted JSON excludes active_tools and skills_metadata

- **WHEN** a SessionState with `skills_loaded`, `active_grants`, `active_tools`, and `skills_metadata` is saved to SQLite
- **THEN** the `sessions.state_json` column contains only `skills_loaded`, `active_grants`, `session_id`, `created_at`, `updated_at` (derived fields excluded)

#### Scenario: Legacy session with derived fields loads cleanly

- **WHEN** a session JSON from a previous version contains `active_tools` and `skills_metadata` fields
- **THEN** `state_manager.load_or_init` loads the session without error, ignoring the extra fields, and the next turn's `build_runtime_context` derives fresh values from current sources

#### Scenario: Audit replay works from persisted state alone

- **WHEN** an audit tool loads a session from SQLite to replay governance decisions
- **THEN** the tool can reconstruct `skills_loaded` and `active_grants` history without needing `active_tools` or `skills_metadata` (which are derivable from the skill index at replay time)

### Requirement: MCP entry points follow unified runtime flow

All 8 MCP meta-tool entry points (`list_skills`, `read_skill`, `enable_skill`, `disable_skill`, `grant_status`, `run_skill_action`, `change_stage`, `refresh_skills`) SHALL follow the unified four-step pattern: (1) load persisted state via `state_manager.load_or_init`, (2) derive runtime context via `build_runtime_context(state, indexer, policy, clock)`, (3) mutate only persisted-only fields (`skills_loaded`, `active_grants`, `updated_at`), (4) save persisted state via `state_manager.save`. MCP entry points MUST NOT directly read `state.active_tools` or `state.skills_metadata`; they SHALL read from `RuntimeContext.active_tools` and `RuntimeContext.all_skills_metadata` instead.

#### Scenario: enable_skill derives runtime view before returning allowed_tools

- **WHEN** the model calls `enable_skill("repo-read")` via MCP
- **THEN** the entry point: (1) loads state, (2) adds "repo-read" to `skills_loaded`, (3) builds `RuntimeContext` to derive `active_tools`, (4) mirrors `ctx.active_tools` to `state.active_tools` via `sync_from_runtime` (compat shim), (5) saves state, (6) returns `{"granted": true, "allowed_tools": list(ctx.active_tools)}`

#### Scenario: list_skills reads metadata from runtime context

- **WHEN** the model calls `list_skills` via MCP
- **THEN** the entry point: (1) loads state, (2) builds `RuntimeContext` with metadata from `indexer.current_index()` (or fallback to `state.skills_metadata` on cold start), (3) returns skills from `ctx.all_skills_metadata.values()`, not from `state.skills_metadata`

#### Scenario: refresh_skills does not update state.skills_metadata

- **WHEN** the model calls `refresh_skills` via MCP
- **THEN** the entry point: (1) calls `indexer.refresh()` to clear caches and rescan, (2) does NOT write to `state.skills_metadata` (it's a derived field), (3) the next turn's `build_runtime_context` picks up fresh metadata from `indexer.current_index()`
