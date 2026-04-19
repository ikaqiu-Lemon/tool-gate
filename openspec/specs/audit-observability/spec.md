# audit-observability Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
### Requirement: Structured audit logging

The system SHALL record structured audit log entries to the `audit_log` table in SQLite. Each entry MUST include: `timestamp`, `session_id`, `event_type`, `skill_id` (if applicable), `tool_name` (if applicable), `decision`, and `detail` (JSON). The audit log table MUST be append-only — no UPDATE or DELETE operations SHALL be exposed.

#### Scenario: skill.enable event logged

- **WHEN** the model successfully enables "repo-read"
- **THEN** an audit entry is written with `event_type: "skill.enable"`, `skill_id: "repo-read"`, `decision: "granted"`, and detail containing scope and TTL

#### Scenario: tool.call deny event logged

- **WHEN** PreToolUse hook denies a call to the Edit tool
- **THEN** an audit entry is written with `event_type: "tool.call"`, `tool_name: "Edit"`, `decision: "deny"`, and detail containing the reason

#### Scenario: grant.expire event logged

- **WHEN** a grant for "repo-read" expires during UserPromptSubmit cleanup
- **THEN** an audit entry is written with `event_type: "grant.expire"`, `skill_id: "repo-read"`, `decision: "expired"`

### Requirement: Key event types coverage

The audit system SHALL record the following event types at minimum: `skill.list`, `skill.read`, `skill.enable`, `skill.disable`, `tool.call`, `grant.expire`, `grant.revoke`, `stage.change`, `prompt.submit`. Each event type MUST be consistently named across all recording sites.

#### Scenario: Complete lifecycle produces all event types

- **WHEN** a session goes through: list_skills → read_skill → enable_skill → tool call → change_stage → disable_skill
- **THEN** the audit log contains entries for `skill.list`, `skill.read`, `skill.enable`, `tool.call`, `stage.change`, `skill.disable` in chronological order

### Requirement: Funnel metrics tracking

The audit system SHALL support funnel analysis across the stages: `shown` (list_skills) → `read` (read_skill) → `enable` (enable_skill) → `tool` (tool.call) → `task` (task completion). Each stage's count MUST be queryable per session_id and per skill_id to identify pipeline bottlenecks.

#### Scenario: Funnel query for a session

- **WHEN** an analyst queries funnel metrics for session "abc-123"
- **THEN** the system returns counts like: shown=5, read=3, enable=2, tool_calls=10, showing where drop-offs occur

#### Scenario: Funnel query for a specific skill

- **WHEN** an analyst queries funnel metrics for skill "code-edit"
- **THEN** the system returns how many times code-edit was shown, read, enabled, and how many tool calls were made under its grants

### Requirement: Misuse call bucketing

The audit system SHALL classify denied tool calls into three buckets: (1) `whitelist_violation` — tool not in any enabled skill's allowed_tools, (2) `wrong_skill_tool` — tool belongs to a different skill than intended, (3) `parameter_error` — correct tool but invalid parameters. The bucket classification MUST be recorded in the audit log's `detail` field as `error_bucket`.

#### Scenario: Whitelist violation bucket

- **WHEN** the model calls the Bash tool while no enabled skill includes Bash in its allowed_tools
- **THEN** the audit entry includes `error_bucket: "whitelist_violation"`

#### Scenario: Wrong skill tool bucket

- **WHEN** the model calls Edit while "repo-read" (read-only) is enabled, but Edit belongs to "code-edit" which is not enabled
- **THEN** the audit entry includes `error_bucket: "wrong_skill_tool"` with detail indicating Edit belongs to "code-edit"

### Requirement: Audit log queryability

The audit log SHALL support queries by `session_id`, `event_type`, `skill_id`, and time range. SQLite indexes on `session_id` and `event_type` columns MUST be created to ensure query performance.

#### Scenario: Query all events for a session

- **WHEN** querying `SELECT * FROM audit_log WHERE session_id = 'abc-123' ORDER BY timestamp`
- **THEN** all audit entries for that session are returned in chronological order using the session_id index

#### Scenario: Query denied calls by event type

- **WHEN** querying `SELECT * FROM audit_log WHERE event_type = 'tool.call' AND decision = 'deny'`
- **THEN** all denied tool call entries are returned using the event_type index

### Requirement: Langfuse trace integration

The system SHALL optionally integrate with Langfuse for distributed tracing. When Langfuse is configured (via `langfuse` optional dependency), each session MUST map to a Langfuse session, each skill operation (read/enable/disable) MUST create an observation, and each tool call MUST be traced. When Langfuse is not installed, the system MUST function normally using SQLite-only audit logging.

#### Scenario: Langfuse configured and available

- **WHEN** the `langfuse` package is installed and configured with API credentials
- **THEN** a complete governance flow (list → read → enable → tool call) produces a Langfuse trace with linked observations visible in the Langfuse dashboard

#### Scenario: Langfuse not installed

- **WHEN** the `langfuse` package is not installed
- **THEN** the system operates normally with SQLite audit logging only, no import errors or warnings about missing Langfuse

