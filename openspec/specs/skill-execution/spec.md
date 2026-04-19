# skill-execution Specification

## Purpose
TBD - created by archiving change build-tool-governance-plugin. Update Purpose after archive.
## Requirements
### Requirement: Validate grant before execution

The `run_skill_action` MCP tool SHALL verify that the specified skill is enabled and its Grant is not expired before dispatching any operation. If the grant is invalid, the system MUST reject the request.

#### Scenario: Execute with valid grant

- **WHEN** "repo-read" is enabled with an active grant and the model calls `run_skill_action("repo-read", "search", {pattern: "TODO"})`
- **THEN** the system proceeds to operation validation and dispatch

#### Scenario: Execute with expired grant

- **WHEN** "repo-read"'s grant has expired and the model calls `run_skill_action("repo-read", "search", {pattern: "TODO"})`
- **THEN** the system returns an error indicating the grant has expired and the skill must be re-enabled

#### Scenario: Execute for unenabled skill

- **WHEN** "repo-read" is not in skills_loaded and the model calls `run_skill_action("repo-read", "search", {})`
- **THEN** the system returns an error indicating the skill is not enabled

### Requirement: Validate operation in allowed_ops

The system SHALL check that the requested `op` is in the skill's `allowed_ops` list before dispatching. Operations not in the whitelist MUST be rejected.

#### Scenario: Allowed operation passes

- **WHEN** "repo-read" defines `allowed_ops: ["search", "read_file"]` and the model calls `run_skill_action("repo-read", "search", {})`
- **THEN** the system dispatches to the registered handler for ("repo-read", "search")

#### Scenario: Disallowed operation rejected

- **WHEN** "repo-read" defines `allowed_ops: ["search", "read_file"]` and the model calls `run_skill_action("repo-read", "delete", {})`
- **THEN** the system returns an error indicating "delete" is not in the allowed operations for "repo-read"

### Requirement: Dispatch via registered handler table

The system SHALL use a registration-based dispatch table mapping `(skill_id, op)` tuples to handler functions. If no handler is registered for the requested operation, the system MUST return an error. V1 provides built-in handlers for example skills.

#### Scenario: Dispatch to registered handler

- **WHEN** a handler is registered for ("repo-read", "search") and the model calls `run_skill_action("repo-read", "search", {pattern: "TODO"})`
- **THEN** the system invokes the registered handler with `{pattern: "TODO"}` and returns its result

#### Scenario: No handler registered

- **WHEN** no handler is registered for ("custom-skill", "custom-op") and the model calls `run_skill_action("custom-skill", "custom-op", {})`
- **THEN** the system returns `{error: "No handler for custom-skill.custom-op"}`

### Requirement: Return structured execution result

The `run_skill_action` tool MUST return a structured response containing the execution result. On success, the response SHALL include `{result: <handler_output>}`. On failure, it SHALL include `{error: <error_message>}`.

#### Scenario: Successful execution

- **WHEN** the handler for ("repo-read", "search") returns `{matches: ["file1.py:10", "file2.py:25"]}`
- **THEN** `run_skill_action` returns `{result: {matches: ["file1.py:10", "file2.py:25"]}}`

#### Scenario: Handler raises an exception

- **WHEN** the handler for an operation throws an exception during execution
- **THEN** `run_skill_action` catches the exception and returns `{error: <exception_message>}` without crashing the MCP server

