# session-lifecycle Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
### Requirement: Session initialization via SessionStart hook

The SessionStart hook SHALL: (1) load existing session state from SQLite or create a new SessionState, (2) clean up expired grants, (3) build or refresh the skill index if metadata cache is empty, (4) recompute `active_tools`, (5) persist updated state to SQLite, (6) return `additionalContext` with the skill catalog summary.

#### Scenario: Fresh session initialization

- **WHEN** a new Claude Code session starts and no prior state exists for this session_id
- **THEN** the hook creates a new SessionState with empty `skills_loaded` and `active_tools`, builds the skill index from `skills/` directory, and injects the skill catalog summary into additionalContext

#### Scenario: Session state restoration

- **WHEN** a session starts and a prior SessionState exists in SQLite for this session_id
- **THEN** the hook restores the previous state including `skills_loaded`, cleans up any expired grants, recomputes `active_tools`, and injects updated state into additionalContext

#### Scenario: Expired grants cleaned on session start

- **WHEN** a session resumes and 2 of 3 grants have expired since the last interaction
- **THEN** the hook removes the 2 expired skills from `skills_loaded`, recomputes `active_tools` based on the 1 remaining skill, and persists the cleaned state

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

### Requirement: Session state persistence to SQLite

The state_manager SHALL persist `SessionState` as serialized JSON to the `sessions` table in SQLite. Every state mutation (add/remove skill, stage change, grant update) MUST update the `updated_at` timestamp. The SQLite database SHALL use WAL journal mode for concurrent access by hook handler and MCP server processes.

#### Scenario: State survives process restart

- **WHEN** the hook handler process writes SessionState to SQLite and a new hook handler process starts
- **THEN** the new process can load the same SessionState by session_id with all fields intact

#### Scenario: Concurrent read by MCP server

- **WHEN** the hook handler is writing state to SQLite while the MCP server reads state
- **THEN** the MCP server reads a consistent snapshot (WAL mode) without blocking the hook handler

### Requirement: Session ID discovery

The system SHALL discover the session_id from hook input using the following priority: (1) `input.session_id`, (2) `input.sessionId`, (3) `input.conversation_id`, (4) environment variable `CLAUDE_SESSION_ID`, (5) auto-generate based on PID + timestamp and persist to a marker file. Once discovered, the session_id MUST remain stable for the entire session.

#### Scenario: Session ID from hook input

- **WHEN** the hook input JSON contains `{"session_id": "abc-123"}`
- **THEN** the system uses "abc-123" as the session_id for all subsequent operations

#### Scenario: Session ID auto-generation fallback

- **WHEN** the hook input contains no recognizable session ID field and no environment variable is set
- **THEN** the system generates a stable session_id, writes it to a marker file, and reuses it for subsequent hook invocations in the same session

### Requirement: PostToolUse processing

The PostToolUse hook SHALL: (1) update `skill_last_used_at` for the skill whose tool was called, (2) record a structured audit log entry. The hook MUST NOT block or modify the tool's output.

#### Scenario: Update last_used_at after tool call

- **WHEN** a tool belonging to "repo-read" is successfully called
- **THEN** `LoadedSkillInfo.last_used_at` for "repo-read" is updated to the current timestamp

#### Scenario: Audit log recorded after tool call

- **WHEN** the Read tool is called successfully while "repo-read" is enabled
- **THEN** the PostToolUse hook writes an audit record with `event_type: "tool.call"`, `skill_id: "repo-read"`, `tool_name: "Read"`, `decision: "allow"`

### Requirement: Cross-platform path and command compatibility

The plugin SHALL work on Windows, macOS, and Linux. Hook commands and MCP server commands MUST use platform-independent entry points (console_scripts). File paths MUST use `os.path` or `pathlib` for cross-platform compatibility. The `${CLAUDE_PLUGIN_DATA}` and `${CLAUDE_PLUGIN_ROOT}` environment variables SHALL be used for all path references.

#### Scenario: Plugin loads on Windows

- **WHEN** the plugin is installed on Windows where `python3` command does not exist
- **THEN** the console_script entry points (`tg-hook`, `tg-mcp`) work correctly via the platform-native Python launcher

#### Scenario: SQLite database path on different platforms

- **WHEN** `${CLAUDE_PLUGIN_DATA}` resolves to different paths on Windows vs macOS
- **THEN** the SQLite database is created at the correct platform-specific path using `pathlib.Path`

### Requirement: Runtime state and persisted state are semantically distinct

The system SHALL maintain a semantic separation between **runtime state** (values a turn computes and consumes while it executes) and **persisted state** (the minimal durable record required to recover, continue, or audit a session). A turn MUST NOT treat a previous turn's runtime-derived value as authoritative input for its own governance decisions, and the persisted record MUST NOT be consumed directly as runtime state without an explicit per-turn reconstruction.

#### Scenario: A derived value from an earlier turn is not reused as authoritative input

- **WHEN** a turn produces a derived value — such as the set of tools currently visible to the model — and a subsequent turn begins on the same session
- **THEN** the new turn SHALL recompute that derived value from current authoritative sources and SHALL NOT feed the earlier turn's result into its own rewrite or gate-check decisions

#### Scenario: Persisted record is not handed directly to per-turn logic

- **WHEN** a hook or meta-tool entry loads the persisted record for a session
- **THEN** it SHALL first construct a fresh runtime view from (persisted record, current skill index, current policy, current clock) and only then invoke rewrite or gate-check logic against that view

### Requirement: Persisted state contains only recovery, continuity, and audit fields

The persisted session record SHALL contain only fields needed to (a) identify the session, (b) restore cross-turn continuity of currently authorized skills and their grant state, or (c) anchor audit records. It MUST NOT persist fields whose sole purpose is to serve as a single turn's rewrite input or display cache; such fields are runtime-only and SHALL be recomputed on demand at turn start.

#### Scenario: Persisted record excludes pure per-turn derivations

- **WHEN** a session is persisted after a turn completes
- **THEN** the persisted record SHALL include session identity, the set of enabled skills with their grant state, and the timestamps required for audit; it SHALL NOT persist a field whose only role is to cache the current turn's active tool set or composed context

#### Scenario: Audit replay works from persisted state alone

- **WHEN** an audit event is reconstructed from the audit log and the persisted record
- **THEN** the reconstruction SHALL succeed without consulting any runtime-only value, because every field the audit event depends on is either in the persisted record or in the event's own payload

### Requirement: Runtime state is reconstructed safely from persisted state plus current context

At the start of every turn the system SHALL build a complete runtime view from (a) the loaded persisted record, (b) the current skill index and policy, and (c) the current clock. The reconstruction SHALL be deterministic given the same inputs, and MUST complete before any rewrite, prompt composition, or gate-check observes the new turn's state.

#### Scenario: Every turn begins with a fresh runtime view

- **WHEN** a hook or meta-tool entry is invoked for a turn
- **THEN** the system SHALL load persisted state, expire grants whose TTL has passed, and derive the turn's active tool set and display context from the loaded state plus the live skill index and policy — before any other governance logic runs

#### Scenario: Identical inputs yield equivalent runtime views

- **WHEN** the same persisted record is reconstructed twice under identical skill-index, policy, and clock inputs
- **THEN** the two resulting runtime views SHALL be equivalent for every governance decision they drive — the same tools allowed, the same skills treated as enabled, the same authorization status reported

### Requirement: System degrades safely when persisted state is missing, stale, or incomplete

When the persisted record is absent, carries fields from an older code version, or references skills or grants that no longer resolve under the current skill index or policy, the system SHALL degrade to a safe runtime view that excludes unresolved items but continues to operate. Under no such condition SHALL the system crash, elevate authorization beyond what the persisted record still justifies, or use a stale field as if it were current-turn authoritative input.

#### Scenario: No persisted record exists for the session

- **WHEN** a turn begins and no persisted record is found for the session id
- **THEN** the system SHALL construct a fresh empty runtime view — no skills loaded, no authorized tools beyond the always-available meta-tools — and proceed without error

#### Scenario: Persisted record references an unknown skill

- **WHEN** the persisted record lists a skill that no longer exists in the current skill index
- **THEN** the system SHALL exclude that skill from the runtime view, leave the persisted entry untouched for audit purposes, and SHALL NOT grant any tools on behalf of the unknown skill

#### Scenario: Persisted record carries fields from an older code version

- **WHEN** the loaded persisted record includes fields that the current code treats as runtime-only
- **THEN** the system SHALL ignore those legacy fields when deriving the runtime view, compute the runtime view from current authoritative sources instead, and retain the legacy fields on disk only if they are still needed for audit or continuity

