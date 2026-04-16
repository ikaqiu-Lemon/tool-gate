## ADDED Requirements

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
