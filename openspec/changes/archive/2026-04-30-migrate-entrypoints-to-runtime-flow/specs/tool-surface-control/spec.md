# tool-surface-control Specification Delta

## MODIFIED Requirements

### Requirement: Tool rewrite consumes runtime context, not persisted state

The `tool_rewriter.compute_active_tools(ctx: RuntimeContext)` function SHALL compute the active tools list from a runtime context, not from `SessionState`. The legacy `tool_rewriter.recompute_active_tools(state: SessionState)` function is DEPRECATED and SHALL emit a `DeprecationWarning`. The deprecated function SHALL act as a thin adapter: it builds a minimal `RuntimeContext` from `state`, calls `compute_active_tools(ctx)`, assigns the result to `state.active_tools` (for backward compatibility), and returns the list. All new code MUST use `compute_active_tools(RuntimeContext)`.

#### Scenario: compute_active_tools does not mutate its input

- **WHEN** `compute_active_tools(ctx)` is called with a `RuntimeContext`
- **THEN** the function returns a list of tool names and does NOT modify `ctx` (which is frozen) or any `SessionState` passed to `build_runtime_context`

#### Scenario: recompute_active_tools emits DeprecationWarning

- **WHEN** legacy code calls `recompute_active_tools(state)`
- **THEN** the function emits a `DeprecationWarning` with message "recompute_active_tools(state) is deprecated. Use compute_active_tools(RuntimeContext) instead."

#### Scenario: recompute_active_tools still works for backward compatibility

- **WHEN** legacy code calls `recompute_active_tools(state)` with a `SessionState` containing `skills_loaded` and `skills_metadata`
- **THEN** the function: (1) builds a minimal `RuntimeContext`, (2) calls `compute_active_tools(ctx)`, (3) assigns the result to `state.active_tools`, (4) returns the list (same behavior as before, but with a deprecation warning)

### Requirement: LangChain tool shim follows unified runtime flow

All LangChain tool wrapper functions (`enable_skill_tool`, `disable_skill_tool`, `run_skill_action_tool`) SHALL follow the same unified four-step pattern as MCP entry points: (1) load persisted state, (2) derive runtime context, (3) mutate only persisted-only fields, (4) save persisted state. LangChain tool wrappers MUST NOT directly read `state.active_tools` or `state.skills_metadata`; they SHALL read from `RuntimeContext` instead.

#### Scenario: enable_skill_tool derives runtime view before returning

- **WHEN** the model calls `enable_skill_tool("repo-read")` via LangChain
- **THEN** the wrapper: (1) loads state, (2) adds "repo-read" to `skills_loaded`, (3) builds `RuntimeContext` to derive `active_tools`, (4) mirrors `ctx.active_tools` to `state.active_tools` via `sync_from_runtime`, (5) saves state, (6) returns `{"granted": true, "allowed_tools": list(ctx.active_tools)}`

#### Scenario: run_skill_action_tool reads metadata from runtime context

- **WHEN** the model calls `run_skill_action_tool("repo-read", "query", {...})` via LangChain
- **THEN** the wrapper: (1) loads state, (2) builds `RuntimeContext`, (3) reads skill metadata from `ctx.all_skills_metadata.get("repo-read")`, not from `state.skills_metadata`

### Requirement: Grant expiry removes tools from runtime view

When a grant expires and is cleaned up by `grant_manager.cleanup_expired`, the corresponding skill MUST be removed from `skills_loaded`. On the next turn, `build_runtime_context` SHALL derive a `RuntimeContext` where `active_tools` does NOT include the expired skill's tools. The persisted `skills_loaded` entry MAY be retained for audit purposes (with a flag or separate table), but it MUST NOT contribute tools to the runtime view.

#### Scenario: Expired grant not in runtime active_tools

- **WHEN** "repo-read" is enabled with TTL=5 seconds, 10 seconds pass, and `cleanup_expired` runs
- **THEN**: (1) "repo-read" is removed from `skills_loaded`, (2) the next `build_runtime_context` call produces a `RuntimeContext` where `active_tools` does NOT include Read/Glob/Grep from "repo-read", (3) the persisted state no longer lists "repo-read" in `skills_loaded`

#### Scenario: Audit log records grant expiry

- **WHEN** a grant expires and is cleaned up
- **THEN** the system emits a `grant.expire` audit event with `session_id`, `skill_id`, `grant_id`, and `detail={"reason": "ttl_expired"}` (existing behavior, unchanged by this requirement)
