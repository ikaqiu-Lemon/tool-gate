## ADDED Requirements

### Requirement: Hook subprocess isolation

The simulator MUST execute hook handlers in isolated subprocess boundaries with stdin/stdout communication.

#### Scenario: Hook subprocess receives JSON event via stdin
- **WHEN** the simulator sends a SessionStart event to the hook subprocess
- **THEN** the hook subprocess reads the event from stdin, processes it, and writes the response to stdout

#### Scenario: Hook subprocess returns permission decision
- **WHEN** the simulator sends a PreToolUse event for an unauthorized tool
- **THEN** the hook subprocess returns a JSON response with `permissionDecision: "deny"` via stdout

#### Scenario: Multiple hook invocations use separate processes
- **WHEN** the simulator invokes SessionStart, UserPromptSubmit, and PreToolUse hooks
- **THEN** each hook invocation spawns a separate subprocess with independent stdin/stdout streams

### Requirement: MCP server subprocess isolation

The simulator MUST execute the MCP server in an isolated subprocess with stdio protocol communication.

#### Scenario: MCP server initialization handshake
- **WHEN** the simulator starts the MCP server subprocess
- **THEN** the MCP server completes the stdio protocol handshake and reports available tools

#### Scenario: MCP tool invocation via stdio
- **WHEN** the simulator sends an enable_skill request to the MCP server
- **THEN** the MCP server processes the request, updates shared state, and returns the result via stdio

#### Scenario: MCP server persists across multiple requests
- **WHEN** the simulator sends multiple meta-tool requests in sequence
- **THEN** the MCP server subprocess remains running and handles all requests without restarting

### Requirement: Governance chain demonstration

The simulator MUST demonstrate the complete governance chain from agent action through hook authorization to MCP execution.

#### Scenario: Successful tool call chain
- **WHEN** the simulator executes a scenario where an enabled skill's tool is called
- **THEN** the chain flows: UserPromptSubmit hook → active_tools recompute → PreToolUse allow → MCP tool execution → PostToolUse audit

#### Scenario: Denied tool call chain
- **WHEN** the simulator executes a scenario where an unauthorized tool is called
- **THEN** the chain flows: PreToolUse deny → guidance message → no MCP execution → audit log entry with whitelist_violation

#### Scenario: Skill enablement chain
- **WHEN** the simulator executes a scenario where a skill is enabled
- **THEN** the chain flows: enable_skill MCP call → policy evaluation → grant creation → SQLite persistence → active_tools update

### Requirement: Shared state integrity

The simulator MUST persist and share governance state through SQLite with correct concurrent access patterns.

#### Scenario: Hook reads state written by MCP
- **WHEN** the MCP server creates a grant via enable_skill
- **THEN** the next UserPromptSubmit hook invocation reads the grant from SQLite and includes its tools in active_tools

#### Scenario: Multiple hook invocations see consistent state
- **WHEN** the simulator invokes PreToolUse and PostToolUse hooks in sequence
- **THEN** both hooks read the same grant and skill state from SQLite

#### Scenario: State survives subprocess termination
- **WHEN** the simulator terminates a hook subprocess after writing audit events
- **THEN** subsequent hook or MCP invocations read the persisted audit events from SQLite

### Requirement: Audit trail completeness

The simulator MUST emit complete audit trails with all governance events in correct temporal order.

#### Scenario: Session lifecycle events
- **WHEN** the simulator runs a complete scenario from start to finish
- **THEN** the audit log contains session.start and session.end events with correct timestamps

#### Scenario: Skill lifecycle events
- **WHEN** the simulator enables and disables a skill
- **THEN** the audit log contains skill.read, skill.enable, and skill.disable events in temporal order

#### Scenario: Tool call events
- **WHEN** the simulator executes allowed and denied tool calls
- **THEN** the audit log contains tool.call events with decision (allow/deny) and error_bucket classification

#### Scenario: Grant lifecycle events
- **WHEN** the simulator demonstrates TTL expiration or explicit revocation
- **THEN** the audit log contains grant.expire or grant.revoke events with correct timestamps

#### Scenario: Stage transition events
- **WHEN** the simulator demonstrates a staged skill workflow
- **THEN** the audit log contains stage.change events showing transitions between stages

### Requirement: Session artifact generation

The simulator MUST generate human-readable and machine-readable session artifacts.

#### Scenario: JSONL event stream generation
- **WHEN** the simulator completes a scenario
- **THEN** it generates an events.jsonl file with one JSON object per line in temporal order

#### Scenario: Markdown audit summary generation
- **WHEN** the simulator completes a scenario
- **THEN** it generates an audit_summary.md file with session metadata, skill funnel, tool call statistics, and governance analysis

#### Scenario: JSON metrics generation
- **WHEN** the simulator completes a scenario
- **THEN** it generates a metrics.json file with structured counters for skills, tools, denials, and violations

#### Scenario: State snapshot generation
- **WHEN** the simulator starts and ends a scenario
- **THEN** it generates state_before.json and state_after.json files showing skills_metadata, skills_loaded, and active_grants

### Requirement: Scenario coverage

The simulator MUST support scenarios that demonstrate governance behaviors derived from existing examples.

#### Scenario: Low-risk auto-grant scenario
- **WHEN** the simulator runs a discovery scenario (derived from example 01)
- **THEN** it demonstrates list_skills, read_skill, enable_skill with auto-grant, and whitelist violation for unauthorized tools

#### Scenario: Staged workflow scenario
- **WHEN** the simulator runs a staged editing scenario (derived from example 02)
- **THEN** it demonstrates require_reason enforcement, stage transitions via change_stage, and blocked_tools global red line

#### Scenario: Lifecycle and risk scenario
- **WHEN** the simulator runs a lifecycle scenario (derived from example 03)
- **THEN** it demonstrates TTL expiration, disable_skill with revoke ordering, and approval_required denial

#### Scenario: Mixed MCP environment
- **WHEN** the simulator runs any scenario with multiple MCP servers registered
- **THEN** it demonstrates that only tools from enabled skills are allowed, regardless of MCP registration

### Requirement: Protocol correctness

The simulator MUST validate that hook and MCP communication follows correct protocol formats.

#### Scenario: Hook JSON-RPC format validation
- **WHEN** the simulator sends events to hook subprocesses
- **THEN** each event contains required fields (event, session_id) and receives a valid JSON response

#### Scenario: MCP stdio protocol validation
- **WHEN** the simulator communicates with the MCP server
- **THEN** all messages follow the stdio protocol format with proper initialization, request, and response structures

#### Scenario: Error handling in subprocess communication
- **WHEN** a hook or MCP subprocess returns an error
- **THEN** the simulator captures the error, logs it, and continues execution without crashing

### Requirement: Subprocess lifecycle management

The simulator MUST correctly manage the lifecycle of hook and MCP subprocesses.

#### Scenario: Hook subprocess cleanup
- **WHEN** a hook invocation completes
- **THEN** the simulator waits for the subprocess to exit and closes stdin/stdout streams

#### Scenario: MCP server graceful shutdown
- **WHEN** the simulator completes all scenarios
- **THEN** it sends a shutdown signal to the MCP server and waits for graceful termination

#### Scenario: Subprocess timeout handling
- **WHEN** a hook or MCP subprocess does not respond within the timeout period
- **THEN** the simulator terminates the subprocess and logs a timeout error

### Requirement: Verification and observability

The simulator MUST provide mechanisms to verify correct governance behavior.

#### Scenario: Audit log verification
- **WHEN** the simulator completes a scenario
- **THEN** it validates that all expected audit events are present with correct timestamps and ordering

#### Scenario: State consistency verification
- **WHEN** the simulator completes a scenario
- **THEN** it verifies that state_after.json reflects all grants, skills, and tools from the scenario execution

#### Scenario: Metrics validation
- **WHEN** the simulator completes a scenario
- **THEN** it validates that metrics.json counters match the actual number of events in the audit log

#### Scenario: Protocol compliance verification
- **WHEN** the simulator runs any scenario
- **THEN** it validates that all subprocess communication follows the expected protocol format
