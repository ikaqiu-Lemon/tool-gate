# functional-test-harness Specification

## Purpose
TBD - created by archiving change add-functional-test-plan. Update Purpose after archive.
## Requirements
### Requirement: Mock Skills Fixture Directory

The functional test suite MUST load skills from a dedicated
`tests/fixtures/skills/` directory whose entries all use a
`mock_` prefix on their `skill_id`, and SHALL NOT depend on any skill
shipped under the plugin's production `skills/` tree.

#### Scenario: Fixture directory is isolated from shipped skills
- **WHEN** a functional test initializes `SkillIndexer` with the fixture path
- **THEN** every indexed `skill_id` starts with `mock_`
- **AND** no production skill (e.g. `governance`) appears in the returned index

#### Scenario: Axis coverage fixtures are present
- **WHEN** the fixture directory is scanned
- **THEN** the index includes at least one mock skill per axis: risk_level
  `low`/`medium`/`high`, with-stages vs no-stages, with `allowed_ops` vs empty,
  a malformed-frontmatter case, and an oversized-file case
- **AND** malformed and oversized fixtures are skipped without aborting the
  scan of valid siblings

### Requirement: Local stdio Mock MCP Server Fixture

The functional test suite MUST provide a local, in-repo stdio MCP server
fixture (named with the `mock_` prefix) that the harness can launch as a
subprocess to exercise `mcp__<server>__<tool>` name matching, PreToolUse
interception, and `run_skill_action` dispatch, and SHALL NOT require network
access or any third-party MCP binary.

#### Scenario: Harness launches mock MCP over stdio
- **WHEN** the harness starts the mock MCP server as a subprocess and sends
  an MCP `tools/list` request on stdin
- **THEN** the server responds on stdout within the test timeout
- **AND** the returned tool names follow the `mcp__mock_<server>__<tool>`
  format

#### Scenario: PreToolUse matches MCP-namespaced tool names
- **WHEN** a PreToolUse event names a tool `mcp__mock_<server>__<tool>` that
  is not in `active_tools`
- **THEN** `handle_pre_tool_use` returns `permissionDecision: "deny"`

### Requirement: Core 8-Step Pipeline Functional Coverage

The functional test suite MUST execute the 8-step core governance pipeline
(SessionStart → UserPromptSubmit injection → list_skills → read_skill →
enable_skill → active_tools recompute → gated tool call → PostToolUse
writeback) end-to-end against `mcp_server.py` and `hook_handler.py` via
their real stdio entry points, using mock fixtures as inputs.

#### Scenario: End-to-end happy path
- **WHEN** the harness drives the full 8 steps using a `mock_` low-risk
  skill
- **THEN** `enable_skill` returns `granted: true`
- **AND** the gated tool call passes PreToolUse with decision `allow`
- **AND** PostToolUse updates `skill_last_used_at` for exactly one skill

#### Scenario: Hook contract shape is enforced
- **WHEN** `hook_handler.py` handles any of SessionStart / UserPromptSubmit /
  PreToolUse / PostToolUse
- **THEN** stdout is a single JSON object
- **AND** PreToolUse responses include `hookSpecificOutput.hookEventName`
  and `hookSpecificOutput.permissionDecision`

### Requirement: Lifecycle and Interception Coverage

The functional test suite MUST cover `change_stage`, TTL expiry,
PreToolUse deny for non-allowlisted tools, explicit `disable_skill`
(grant revoke), and `refresh_skills`, asserting both the observable
state deltas and the audit event sequence for each.

#### Scenario: change_stage updates active_tools
- **WHEN** a mock skill with stages is enabled and `change_stage` is called
- **THEN** `active_tools` is recomputed to the target stage's `allowed_tools`

#### Scenario: TTL expiry reclaims grant on next turn
- **WHEN** a grant with a past `expires_at` exists at UserPromptSubmit time
- **THEN** the next UserPromptSubmit removes the skill from `skills_loaded`
- **AND** emits a `grant.expire` audit event but no `grant.revoke`

#### Scenario: Explicit disable emits revoke then disable
- **WHEN** `disable_skill` is called on an enabled mock skill
- **THEN** audit events are emitted in order: `grant.revoke` then
  `skill.disable`

#### Scenario: refresh_skills performs a single scan
- **WHEN** `refresh_skills` is invoked
- **THEN** the fixture directory is scanned exactly once per call
- **AND** the response is `{"refreshed": true, "skill_count": <N>}`

#### Scenario: PreToolUse deny for non-allowlisted tool
- **WHEN** a tool outside `active_tools` is requested and it is not a
  meta-tool
- **THEN** PreToolUse returns `permissionDecision: "deny"` with a
  `permissionDecisionReason`

### Requirement: MCP and LangChain Entry-Point Parity Coverage

The functional test suite MUST assert that `mcp_server.enable_skill` and
the LangChain `enable_skill_tool` wrapper produce equivalent `Grant`
records and identical `state.active_grants[skill_id]` entries for the
same inputs, including coercion of unrecognised `scope` values to
`"session"` and `granted_by` selection from the policy decision.

#### Scenario: Equivalent grants from both entry points
- **WHEN** both entry points are invoked with identical `skill_id`,
  `reason`, `scope`, and `ttl` against the same session
- **THEN** the resulting `Grant` objects match on `scope`, `granted_by`,
  and `allowed_ops`
- **AND** `state.active_grants[skill_id]` is populated identically

#### Scenario: Unknown scope coerces on both paths
- **WHEN** either entry point receives `scope="forever"`
- **THEN** the call does not raise
- **AND** the stored grant has `scope="session"`

