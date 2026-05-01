# Claude Code Tool Governance Plugin -- Development Plan

> Version: v2.1 | Updated: 2026-04-15
> Based on Skill-Hub project experience, Claude Code official plugin specification (2026), and ivan-magda/claude-code-plugin-template standards

---

## 1. Project Overview

### 1.1 Project Name

`tool-governance-plugin` (tentative)

### 1.2 Project Positioning

A **Python tool governance runtime in the form of a Claude Code plugin**, rather than a simple permission panel or tool filter.

Core positioning: **Humans define boundaries, the system enforces, risks escalate** -- Users define governance policies, the system automatically enforces capability exposure, authorization verification, and lifecycle reclamation at runtime, with high-risk actions explicitly escalated to human confirmation.

### 1.3 Core Objectives

1. **Dynamically reduce the tool surface per task**: Deliver only the minimal tool set needed for the current task phase
2. **Explicit authorization and knowledge disclosure**: Separate "understanding capabilities" from "execution permissions" through the `list_skills` / `read_skill` / `enable_skill` flow (dual-plane architecture)
3. **Per-turn state-driven Prompt/Tool rewriting**: After each user message, re-inject the skill catalog summary and updated active_tools hints based on the current session state (corresponding to `wrap_model_call` in Skill-Hub)
4. **Session state management and reclamation**: Maintain session-level state including skill metadata, enabled skills, and currently visible tools, with TTL/LRU reclamation
5. **Stage granularity support**: A single Skill can expose different tool sets per stage, supporting `change_stage` stage transitions
6. **Observability and audit closed loop**: Structured logging at key nodes (skill.read/enable, tool.call), supporting funnel analysis and miscall bucketing
7. **Compliance with Claude Code plugin specification**: Strict adherence to the official plugin standard, distributable via the plugin marketplace

### 1.4 Tech Stack

| Category | Choice |
|----------|--------|
| Language | Python 3.11+ |
| Core Framework | LangChain |
| Data Models/Config | Pydantic v2 |
| Caching | cachetools (LRU/TTL) |
| MCP Server | mcp Python SDK (stdio) |
| HTTP Hook Service | FastAPI (optional) |
| Persistence | SQLite (`${CLAUDE_PLUGIN_DATA}`) |
| Testing | pytest + pytest-asyncio |
| Package Management | pyproject.toml + uv/pip |
| Observability/Audit (optional) | Langfuse |

### 1.5 Key Design Decisions

> **[Uncertain]** The following decisions are based on the current understanding (2026-04) of the Claude Code plugin system. Some behaviors may change with version updates.

1. **Fixed meta-tool surface + server-side sub-capability dispatch**: Since Claude Code's support for MCP `tools/list_changed` dynamic refresh is not yet fully stable, this project adopts a "fixed small set of meta-tools + `run_skill_action` server-side dispatch" strategy, rather than relying on dynamically adding/removing MCP tools within a session.
2. **Hook type selection**: Prefer `command` type hooks that invoke Python scripts, communicating via stdin/stdout JSON; for more complex state management, optionally use HTTP hooks + FastAPI local service.
3. **Plugin-level hooks.json**: Hook configuration is placed in the plugin root directory `hooks/hooks.json`, distributed with the plugin, and executed in parallel with user's existing hooks.

---

## 2. Plugin Directory Structure

Strictly follows the [Claude Code Plugin Reference](https://code.claude.com/docs/en/plugins-reference) and the [ivan-magda/claude-code-plugin-template](https://github.com/ivan-magda/claude-code-plugin-template) template standard:

```
tool-governance-plugin/
├── .claude-plugin/
│   └── plugin.json                 # Plugin manifest (required)
├── skills/
│   └── governance/
│       └── SKILL.md                # Governance skill description (knowledge plane entry)
├── agents/                         # Optional: dedicated governance agent
│   └── governance-advisor.md
├── hooks/
│   └── hooks.json                  # Hook configuration (event bindings)
├── .mcp.json                       # MCP Server declaration (meta-tool exposure)
│
├── src/                            # Python source code (governance core)
│   └── tool_governance/
│       ├── __init__.py
│       ├── mcp_server.py           # MCP Server entry point (stdio)
│       ├── hook_handler.py         # Hook event handler entry point
│       ├── core/
│       │   ├── __init__.py
│       │   ├── skill_indexer.py    # Skill index building and querying
│       │   ├── state_manager.py    # Session state management
│       │   ├── policy_engine.py    # Policy engine (authorization/risk assessment)
│       │   ├── prompt_composer.py  # Prompt composition (skill catalog injection, active tool hints)
│       │   ├── tool_rewriter.py    # Tool list rewriting (active_tools computation)
│       │   └── grant_manager.py    # Authorization lifecycle management
│       ├── models/
│       │   ├── __init__.py
│       │   ├── skill.py            # Skill data model
│       │   ├── state.py            # Session state data model
│       │   ├── grant.py            # Authorization record data model
│       │   └── policy.py           # Policy configuration data model
│       ├── storage/
│       │   ├── __init__.py
│       │   └── sqlite_store.py     # SQLite persistence
│       └── utils/
│           ├── __init__.py
│           ├── cache.py            # LRU/TTL cache wrapper
│           └── logging.py          # Logging and audit
│
├── scripts/
│   └── ensure_daemon.sh            # Optional: ensure background service is alive
│
├── tests/
│   ├── __init__.py
│   ├── test_skill_indexer.py
│   ├── test_state_manager.py
│   ├── test_policy_engine.py
│   ├── test_prompt_composer.py
│   ├── test_tool_rewriter.py
│   ├── test_grant_manager.py
│   └── test_integration.py
│
├── config/
│   └── default_policy.yaml         # Default policy configuration
│
├── pyproject.toml                  # Python project configuration
├── README.md                       # Usage documentation
└── CHANGELOG.md                    # Changelog
```

### Structure Notes

- `.claude-plugin/plugin.json` is the only file placed inside the `.claude-plugin/` directory
- `skills/`, `hooks/`, `agents/`, `.mcp.json` must be placed in the plugin root directory, not inside `.claude-plugin/`
- Python source code is placed in `src/tool_governance/`, following the standard Python project layout (src layout)
- `${CLAUDE_PLUGIN_ROOT}` is used for path references in hook commands, ensuring cross-platform portability

---

## 3. Development Phases

The project is divided into **4 phases**, each including design, coding, testing, and documentation, delivering runnable artifacts incrementally.

---

### Phase 1: Project Scaffolding and Base Models (~1 week)

**Goal**: Set up the project skeleton, define data models, complete the skill indexer module.

#### 1.1 Specific Tasks

| # | Task | Deliverable |
|---|------|-------------|
| 1 | Initialize Python project (pyproject.toml, src layout, pytest config) | Buildable and installable Python package |
| 2 | Create plugin directory skeleton (.claude-plugin/, skills/, hooks/, .mcp.json) | Compliant plugin directory structure |
| 3 | Write plugin.json manifest | Manifest passing plugin validation |
| 4 | Define Pydantic data models (Skill, SessionState, Grant, Policy); SkillMetadata must support stage-level allowed_tools; SessionState's skills_loaded must track version and last_used_at | Data models under `models/` |
| 5 | Implement `skill_indexer.py`: scan the skills/ directory, parse YAML frontmatter (including stages field), build index; interface reserved for multi-source extension | Runnable index building and querying |
| 6 | Write `cache.py`: LRU/TTL cache wrapper based on cachetools, cache key supports version/hash | Cache utility module |
| 7 | Write SKILL.md governance skill description | Built-in governance skill file for the plugin |
| 8 | Write unit tests for the above modules | All tests passing |

#### 1.2 Acceptance Criteria

- `pyproject.toml` can install dependencies successfully
- `skill_indexer` can scan a sample skills directory and return a structured index
- Data models can serialize/deserialize correctly
- All unit tests pass

---

### Phase 2: Core Governance Logic Implementation (~2 weeks)

**Goal**: Implement state management, policy engine, tool rewriting, authorization management, and other core modules.

#### 2.1 Specific Tasks

| # | Task | Deliverable |
|---|------|-------------|
| 1 | Implement `state_manager.py`: session state creation, loading, updating, persistence; skills_loaded tracks skill_id+version; maintain skill_last_used_at for LRU reclamation; support current_stage state | State management module |
| 2 | Implement `sqlite_store.py`: SQLite-based state and audit persistence; audit log table supports structured fields (event_type, decision, error_bucket, etc.) | Storage module |
| 3 | Implement `policy_engine.py`: risk assessment, eligibility determination, authorization policy evaluation | Policy engine |
| 4 | Implement `grant_manager.py`: grant creation/query/expiry/revocation/TTL checks | Authorization management module |
| 5 | Implement `tool_rewriter.py`: compute active_tools based on skills_loaded + current_stage (supports stage-level allowed_tools) | Tool rewriting module |
| 6 | Implement `prompt_composer.py`: generate skill catalog summary, current active tools hint, authorization guidance prompt (corresponding to PromptComposer in Skill-Hub) | Prompt composition module |
| 7 | Write default policy configuration `default_policy.yaml` | Policy configuration file |
| 8 | LangChain integration: wrap meta-tools as LangChain Tools; use ChatPromptTemplate for prompt template management | LangChain integration |
| 9 | Write unit tests for the above modules | All tests passing |

#### 2.2 Acceptance Criteria

- State management correctly maintains skills_metadata, skills_loaded (with version), active_tools, current_stage
- Policy engine returns allow/deny/ask decisions based on risk levels and policy configuration
- Grant TTL expiry and manual revocation logic works correctly
- `tool_rewriter` outputs the minimal tool list based on current state (including stage)
- `prompt_composer` generates skill catalog summaries and active tool hints as expected
- active_tools are correctly recalculated after changes to skills_loaded or current_stage
- All unit tests pass

---

### Phase 3: Plugin Integration and Hook Orchestration (~2 weeks)

**Goal**: Implement the MCP Server and Hook Handler, integrating core logic into the Claude Code plugin system.

#### 3.1 Specific Tasks

| # | Task | Deliverable |
|---|------|-------------|
| 1 | Implement `mcp_server.py`: stdio MCP Server exposing 8 meta-tools (list_skills, read_skill, enable_skill, disable_skill, grant_status, run_skill_action, change_stage, refresh_skills) | Runnable MCP Server |
| 2 | Write `.mcp.json` configuration declaring the MCP Server startup command | MCP configuration file |
| 3 | Implement `hook_handler.py`: handle **SessionStart, UserPromptSubmit, PreToolUse, PostToolUse** four event types | Hook handler entry point |
| 4 | Write `hooks/hooks.json`: bind four event types to Python scripts | Hook configuration file |
| 5 | Implement SessionStart hook: initialize session, load/restore state, reclaim expired grants, build skill index | Session initialization logic |
| 6 | **Implement UserPromptSubmit hook (corresponding to wrap_model_call)**: after each user message, call prompt_composer to inject skill catalog summary and current active_tools hint into additionalContext; call tool_rewriter to recalculate active_tools based on latest skills_loaded + current_stage | **Per-turn Prompt/Tool rewriting** |
| 7 | Implement PreToolUse hook: check if the tool call is in active_tools, return allow/deny/ask | Tool call interception |
| 8 | Implement PostToolUse hook: update skill_last_used_at, record audit log (with structured fields) | Post-call processing |
| 9 | Local plugin loading validation: load the plugin in Claude Code, test the complete 8-step core pipeline | Local validation passed |

#### 3.2 Acceptance Criteria

- MCP Server communicates normally via stdio, 8 meta-tools can be discovered and called by Claude
- **UserPromptSubmit hook fires on every turn**, model receives updated skill state hints each turn
- **After enable_skill, on the next turn the model receives "newly available tools" notification via UserPromptSubmit**
- PreToolUse correctly intercepts non-allowlisted tool calls
- change_stage can switch stages and correctly update active_tools
- Complete 8-step core pipeline runs end-to-end: initialization -> catalog injection -> discovery -> reading -> authorization -> tool recalculation -> execution -> state writeback
- Plugin can be loaded and used normally in Claude Code

> **[Uncertain]** The exact command format for `claude plugin add` may vary by Claude Code version. Refer to the actual version's CLI documentation. Plugins can also be installed via `/plugin install <path>` or by directly copying to the `~/.claude/plugins/` directory.

---

### Phase 4: Observability, End-to-End Testing, and Documentation (~1.5 weeks)

**Goal**: Implement observability infrastructure, complete integration testing, performance validation, documentation, and prepare for release.

#### 4.1 Specific Tasks

| # | Task | Deliverable |
|---|------|-------------|
| 1 | Implement observability infrastructure: structured audit records supporting funnel metrics (shown/read/enable/tool/task) and miscall bucketing (outside-allowlist/wrong-tool-in-domain/parameter-error) | Observability module |
| 2 | Integrate Langfuse observation points: instrumentation at skill.read, skill.enable, tool.call nodes, linking trace/session/observation | Langfuse integration |
| 3 | Write end-to-end tests: simulate the complete 8-step core pipeline (including UserPromptSubmit per-turn rewrite verification) | Integration tests |
| 4 | Write rejection tests: verify non-allowlisted calls are intercepted, grants expire after TTL, tool set changes after stage switch | Security tests |
| 5 | Performance testing: measure hook processing latency (target < 50ms), cache hit rate | Performance report |
| 6 | Complete README.md: installation guide, configuration instructions, usage tutorial, architecture diagram, core pipeline explanation | Usage documentation |
| 7 | Complete plugin.json metadata (author, keywords, license, etc.) | Release-ready manifest |
| 8 | Code review and refactoring: type hint completion, docstring additions, code quality checks | Clean codebase |
| 9 | (Optional) Provide evaluation scaffolding: offline replay dataset template, control group framework, confusion matrix generation script | Evaluation tools |
| 10 | Write CHANGELOG.md, finalize version number | Release preparation |

#### 4.2 Acceptance Criteria

- Observability infrastructure correctly records funnel data at each stage and miscall buckets
- After Langfuse integration, a complete governance flow produces a full trace in Langfuse
- End-to-end tests cover the core 8-step pipeline, all passing
- Stage switching, TTL expiry, interception, and other edge case tests pass
- Hook processing latency is within acceptable range
- README is complete and clear, new users can install and use the plugin following the documentation
- Code passes linter (ruff) and type checking (mypy)

---

## 4. Phase Dependencies and Milestones

```
Phase 1 ──> Phase 2 ──> Phase 3 ──> Phase 4
Scaffolding  Core Logic   Plugin       Testing &
                          Integration  Release
```

| Milestone | Timepoint | Marker |
|-----------|-----------|--------|
| M1: Project buildable | Phase 1 complete | pyproject.toml installs successfully, skill_indexer runs, data models include stage/version |
| M2: Core logic usable | Phase 2 complete | All unit tests pass for state management + policy engine + tool rewriter + PromptComposer |
| M3: Plugin loadable | Phase 3 complete | Plugin loaded in Claude Code, 8-step core pipeline runs end-to-end (including UserPromptSubmit per-turn rewrite) |
| M4: Release ready | Phase 4 complete | Observability system ready, tests passing, documentation complete, distributable |

---

## 5. Risks and Uncertainties

> v2.1 newly added risk items are marked with **[NEW]**.

| Risk | Impact | Mitigation |
|------|--------|------------|
| Claude Code plugin API changes | Hook event format or plugin.json schema may change with version updates | Continuously monitor official documentation, centralize adaptation logic in `hook_handler.py` and `mcp_server.py` |
| Unstable MCP tool dynamic refresh | Cannot dynamically add/remove MCP tools within a session | Adopt fixed meta-tool surface + `run_skill_action` server-side dispatch strategy |
| Python environment dependencies | User's machine may not have Python installed or version may be incompatible | Clearly state Python version requirements in README; consider Docker solution in the future |
| Hook processing latency | Excessive hook latency degrades the Claude Code user experience | Keep single hook < 50ms; use in-process caching to reduce IO |
| `${CLAUDE_PLUGIN_DATA}` path behavior | Actual path may differ across platforms/versions | Test coverage on Windows/macOS/Linux |
| Plugin hooks interacting with user hooks | Plugin hooks executing in parallel with user's existing hooks may cause conflicts | Governance plugin hooks only perform checks and state updates, not modifying user behavior |
| **[NEW]** UserPromptSubmit hook latency accumulation | Hook fires on every message, higher frequency than SessionStart | prompt_composer and tool_rewriter use cached results to avoid redundant computation |
| **[NEW]** Cannot directly override tool list | Claude Code does not support request.override(tools=...), can only "soft guide + hard intercept" | UserPromptSubmit injects additionalContext for guidance + PreToolUse deny for hard interception; effectiveness needs empirical validation |
| **[NEW]** Stage mechanism SKILL.md format | The stages field is not part of the official Claude Code SKILL.md standard | Treated as a custom frontmatter field, does not affect Claude Code's native parsing |

---

## 5-A. Skill-Hub Concept to Claude Code Plugin Mapping

> This plugin migrates the governance mechanisms from the Skill-Hub project to the Claude Code plugin system. Below are the key concept mappings:

| Skill-Hub Concept | Claude Code Plugin Equivalent | Notes |
|-------------------|-------------------------------|-------|
| `before_agent` | **SessionStart hook** | Restore state, build index, reclaim expired grants at session start |
| `wrap_model_call` (per-turn) | **UserPromptSubmit hook** | Inject skill summary and active_tools hints after each user message |
| `request.override(tools=...)` | **PreToolUse hook (deny)** + **additionalContext guidance** | Claude Code does not support directly overriding tool list; replaced with hook interception + prompt guidance combination |
| `PromptComposer` | **prompt_composer.py** -> UserPromptSubmit's additionalContext | Inject skill catalog and tool hints into model context |
| LangChain state | **SessionState + SQLite** | Session-level state persisted to local database |
| Redis (cross-instance resumption) | **SQLite** (sufficient for single machine) | Claude Code plugins run locally, no cross-instance needed; SQLite meets persistence requirements |
| Langfuse observability | **Langfuse integration** + **SQLite audit log** | Dual channel: Langfuse for trace linking, SQLite for structured audit |
| `read_skill` / `enable_skill` | **MCP meta-tools** | Exposed to the model via MCP Server |
| `allowed_tools` allowlist | **PreToolUse hook hard interception** | Tool calls not on the allowlist are denied by hook |
| `change_stage` | **MCP meta-tool change_stage** | Model explicitly calls to switch stages |

### Key Differences

1. **Cannot directly override tool list**: Skill-Hub's `request.override(tools=...)` can directly rewrite the tool set visible to the model. Claude Code plugins cannot do this. This project's alternative approach is:
   - Use **UserPromptSubmit hook**'s additionalContext to tell the model "currently available tools are..."
   - Use **PreToolUse hook** to hard-intercept tool calls not on the allowlist
   - The combination achieves an equivalent "soft guidance + hard interception" effect

2. **Fixed MCP tool list**: Due to unreliable dynamic refresh, this project uses a fixed set of 8 meta-tools + `run_skill_action` server-side dispatch, rather than dynamically adding/removing MCP tools.

---

## 5-B. Source Document Feature Coverage Checklist

> The following lists all core feature points from `Skill-Hub Project Prep Edition.md` and `Handwritten Skills Long Edition.md` and their coverage status in this plan.

| Source Document Feature | Coverage | Corresponding Phase |
|------------------------|----------|-------------------|
| Core pipeline step 1: before_agent initialization | ✅ SessionStart hook | Phase 3 |
| Core pipeline step 2: wrap_model_call inject catalog + base tools | ✅ UserPromptSubmit hook + prompt_composer | Phase 3 |
| Core pipeline step 3: model assesses the problem | ✅ Model autonomous behavior, supported by meta-tools | Phase 3 |
| Core pipeline step 4: enable_skill authorization | ✅ MCP meta-tool + policy_engine | Phase 2-3 |
| Core pipeline step 5: next-turn wrap_model_call recalculates active_tools | ✅ UserPromptSubmit hook fires every turn | Phase 3 |
| Core pipeline step 6: model calls within minimal tool set | ✅ PreToolUse hook interception | Phase 3 |
| Core pipeline step 7: update runtime state (skills_loaded, active_tools, skill_last_used_at) | ✅ PostToolUse hook + state_manager | Phase 3 |
| Core pipeline step 8: session snapshot writeback + Langfuse observability | ✅ SQLite persistence + Langfuse integration | Phase 3-4 |
| Knowledge/execution dual-plane (read_skill vs enable_skill) | ✅ | Phase 2-3 |
| PromptComposer | ✅ Standalone module prompt_composer.py | Phase 2 |
| SkillGate (policy + allowed_tools) | ✅ policy_engine + PreToolUse hook | Phase 2-3 |
| Stage granularity (change_stage, current_stage) | ✅ Data model + MCP tool + tool_rewriter | Phase 1-3 |
| Versioned skill snapshots (skills_loaded with version) | ✅ Data model | Phase 1 |
| skill_last_used_at | ✅ SessionState field | Phase 1-2 |
| Three state types (skills_metadata, skills_loaded, active_tools) | ✅ | Phase 1-2 |
| active_tools recalculated every turn (not append) | ✅ tool_rewriter design | Phase 2 |
| Two-layer cache (metadata session-level + document LRU/TTL) | ✅ | Phase 1-2 |
| Cache key with version/hash | ✅ cache.py | Phase 1 |
| Explicit refresh (refresh_skills) | ✅ MCP meta-tool | Phase 3 |
| In-session consistency (no hot updates) | ✅ Design principle | Phase 2 |
| Session state isolated by session_id | ✅ | Phase 2 |
| Policy runtime admission control | ✅ policy_engine.py | Phase 2 |
| Funnel metrics (shown->read->enable->tool->task) | ✅ Structured audit log | Phase 4 |
| Miscall bucketing (outside-allowlist/wrong-tool-in-domain/parameter-error) | ✅ Audit log error_bucket field | Phase 4 |
| Langfuse trace/session/observation | ✅ | Phase 4 |
| Input safety (safe_load, file size limits, description truncation) | ✅ skill_indexer | Phase 1 |
| Multi-source skill loading (base/team/project/user) | ⚠️ V1 single directory, interface reserved for multi-source extension | Phase 1 |
| Replay evaluation framework | ⚠️ Scaffolding template provided (optional) | Phase 4 |

---

## 6. Current Progress

> Updated: 2026-04-17. Tracks hardening rounds after the initial Phase 1–3 review.

### phase13-hardening-and-doc-sync — Stage A (D2, D1): **done**

- **D2** `run_skill_action` now denies by default when `skills_metadata[skill_id]`
  is `None` (returns `"metadata unavailable; operation denied"` and emits a
  `skill.action.deny` audit event with `detail.reason="meta_missing"`). The
  pre-fix branch that silently bypassed `allowed_ops` is gone.
- **D1** `handle_post_tool_use` now stamps `last_used_at` on exactly one skill
  per PostToolUse event. An explicit `matched` flag ensures the outer skill
  loop exits after the first (top-level or stage-level) match — later skills
  can no longer overwrite the timestamp.
- **Tests**: `tests/test_integration.py` — added `TestRunSkillActionMetaMissing`
  (2 cases) and `TestPostToolUseSingleStamp` (3 cases).
- **Suite**: 104 → **109 passed** (`python -m pytest -q`). No regressions.
- **Scope guard**: no changes to D3 / D6 / D7 / D4 / D5 / D8 in this stage;
  no edits to `docs/requirements.md` or `docs/technical_design.md` in this
  stage (reserved for later stages per plan).

### phase13-hardening-and-doc-sync — Stage B (D6, D3, D7): **done**

- **D6** `enable_skill_tool` (LangChain wrapper) now mirrors
  `mcp_server.enable_skill` exactly. `scope` is coerced via
  `"turn" if scope == "turn" else "session"` and `granted_by` via
  `"auto" if decision.decision == "auto" else "policy"`. Both entry points
  therefore build equivalent `Grant` objects (`scope`, `granted_by`,
  `allowed_ops` all match) and write to `state.active_grants[skill_id]`
  identically. An unrecognised `scope` no longer raises
  `pydantic.ValidationError` from the LangChain path; it coerces to
  `"session"` on both paths.
- **D3** `refresh_skills` now performs exactly one directory scan per call.
  A new `SkillIndexer.current_index()` read-only accessor returns the
  freshly-built index to `mcp_server.refresh_skills` without a second
  `build_index()` call. The response shape
  (`{"refreshed": True, "skill_count": count}`) is unchanged.
- **D7** New `grant.revoke` audit event, emitted **by
  `GrantManager.revoke_grant()`** exactly once per revocation. Fields:
  `session_id`, `skill_id`, `event_type="grant.revoke"`,
  `detail={"grant_id": ..., "reason": ...}`. `reason` defaults to
  `"explicit"`; callers may pass a different discriminator. `SQLiteStore`
  gained no new API (an existing `get_grant(grant_id)` lookup was reused).
  Event boundary with existing events:
  - `grant.revoke` = grant status flipped `active → revoked` via
    `revoke_grant()`. Currently reached only from the explicit
    `disable_skill` paths (MCP + LangChain) with `reason="explicit"`.
  - `skill.disable` = unchanged; emitted by the entry point *after*
    `revoke_grant()` returns. An explicit disable therefore emits
    `grant.revoke` → `skill.disable`, in that order.
  - `grant.expire` = unchanged; emitted by the hook-handler TTL sweep.
    `cleanup_expired` transitions status to `"expired"` (not `"revoked"`)
    and does not go through `revoke_grant()`, so `grant.revoke` and
    `grant.expire` never fire for the same grant.
- **Tests**: `tests/test_grant_manager.py` — added 4 cases
  (`grant.revoke` emission, custom-reason discriminator, unknown-id
  no-op, `cleanup_expired` does not emit `grant.revoke`).
  `tests/test_integration.py` — added `TestEnableSkillParity` (2 cases),
  `TestRefreshSkillsSingleScan` (1 case), `TestDisableSkillAuditOrdering`
  (2 cases: revoke-then-disable order, disable-without-grant emits
  `skill.disable` only).
- **Suite**: 109 → **118 passed**. No regressions.
- **Scope guard**: `docs/requirements.md` not touched. `docs/technical_design.md`
  has doc-sync notes only at this stage (no full rewrite); detailed
  signature and state-model edits are deferred to Stage C per plan.

### phase13-hardening-and-doc-sync — Stage C (D4, D5, D8): **done**

- **D4** Coverage audit against the Stage A/B spec checklist passed;
  `tests/test_integration.py` gained a `TestMetaNoneEdgeCases` class
  (4 cases) that exercises the `meta is None` branch across MCP entry
  points beyond `run_skill_action` — `change_stage`, `enable_skill`
  (unknown skill), `read_skill` (unknown skill), and
  `ToolRewriter.recompute_active_tools` (loaded skill without metadata
  contributes zero tools). No code change.
- **D5** `docs/technical_design.md` §3.2.4 (`PromptComposer`) and §3.2.5
  (`ToolRewriter`) signature blocks rewritten to match the
  implementation: `PromptComposer` takes no constructor arguments
  (stateless formatter, reads from `SessionState`); `ToolRewriter` takes
  `blocked_tools: list[str] | None = None` and `get_stage_tools` is a
  `@staticmethod`. Chinese mirror `docs/技术方案文档.md` synced in the
  same shape. No code change.
- **D8** `state.active_grants` is keyed by **`skill_id`**. The
  stale docstrings in `src/tool_governance/models/state.py` and
  `src/tool_governance/core/state_manager.py` that described the dict as
  `grant_id`-keyed were corrected to match the actual invariant.
  `docs/technical_design.md` gained a state-model note stating the
  invariants: at most one active `Grant` per `(session_id, skill_id)`;
  the authoritative `grant_id` lives inside the stored `Grant` object;
  re-keying is explicitly deferred. Chinese mirror synced.
- **Suite**: 118 → **122 passed**. No regressions.
- **Scope guard**: `docs/requirements.md` untouched — this round was
  implementation/modelling semantics, not requirements. `docs/technical_design.md`
  is now fully in sync with the implementation for the affected sections.

### Drift Resolution Matrix — final for this round

| ID  | status   | handling | evidence |
|-----|----------|----------|----------|
| D1  | closed   | fix      | `src/tool_governance/hook_handler.py::handle_post_tool_use`; `tests/test_integration.py::TestPostToolUseSingleStamp` |
| D2  | closed   | fix      | `src/tool_governance/mcp_server.py::run_skill_action`; `tests/test_integration.py::TestRunSkillActionMetaMissing` |
| D3  | closed   | fix      | `src/tool_governance/mcp_server.py::refresh_skills`, `src/tool_governance/core/skill_indexer.py::SkillIndexer.current_index`; `tests/test_integration.py::TestRefreshSkillsSingleScan` |
| D4  | closed   | fix (tests) | `tests/test_integration.py::TestMetaNoneEdgeCases` (+ Stage A/B test classes) |
| D5  | closed   | doc-sync | `docs/technical_design.md` §3.2.4, §3.2.5; `docs/技术方案文档.md` 3.2.4, 3.2.5 |
| D6  | closed   | fix      | `src/tool_governance/tools/langchain_tools.py::enable_skill_tool`; `tests/test_integration.py::TestEnableSkillParity` |
| D7  | closed   | fix      | `src/tool_governance/core/grant_manager.py::revoke_grant`; `tests/test_grant_manager.py::TestRevoke` (4 new), `tests/test_integration.py::TestDisableSkillAuditOrdering` |
| D8  | closed   | doc-sync | `src/tool_governance/models/state.py::SessionState.active_grants`, `src/tool_governance/core/state_manager.py::remove_from_skills_loaded`; `docs/technical_design.md` §10-B "active_grants key-semantics note"; `docs/技术方案文档.md` "active_grants key 语义说明" |
| D9  | deferred | backlog  | tracked in `openspec/changes/phase13-hardening-and-doc-sync/` proposal §"Out of Scope"; not implemented this round |
| D10 | deferred | backlog  | same as D9 |

### Close-out

- **phase13-hardening-and-doc-sync closed on 2026-04-19**; D1–D4, D6, D7
  fixed; D5, D8 doc-synced; D9, D10 deferred; Phase 4 not started.
- Stage D (re-review prep + closeout) — **done** (`closeout.md`,
  `review-inputs.md` landed; `openspec validate` passed; full suite
  167/167 green at re-verify time, closeout baseline 122 at commit
  `de787c7`).
- Backlog only (not this round): D9, D10, Phase 4 items.

### Functional test harness — `openspec/changes/add-functional-test-plan/`

> Added 2026-04-18. Stages A–H landed; functional 45/45 green, full
> suite 167/167. Policy fixtures (`tests/fixtures/policies/*.yaml`)
> now drive a real `bootstrap.load_policy` → `PolicyEngine` path —
> `test_functional_policy_fixtures.py`, `test_functional_policy_e2e.py`
> and `test_functional_policy_e2e_lifecycle.py` prove low / medium /
> high / `blocked_tools` / skill-specific override branches end-to-end
> without patching the engine. Subprocess smoke lane
> (`test_functional_smoke_subprocess.py`) exercises `tg-mcp` (8 meta-
> tools), `mock_sensitive_stdio`, and three `tg-hook` event contracts.
> **This is a test-harness enhancement, not a production feature
> expansion** — no `src/tool_governance/` changes landed in this
> round. See [`tests/functional/README.md`](../tests/functional/README.md)
> for the full coverage tables.

---

- [Claude Code Plugin Reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Tools Reference](https://code.claude.com/docs/en/tools-reference)
- [Claude Code MCP Integration](https://code.claude.com/docs/en/mcp)
- [ivan-magda/claude-code-plugin-template](https://github.com/ivan-magda/claude-code-plugin-template)
- [anthropics/claude-code Official Plugin Repository](https://github.com/anthropics/claude-code/tree/main/plugins)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- Skill-Hub Project Documentation (this project's `Skill-Hub Project Prep Edition.md`, `Handwritten Skills Long Edition.md`)

---

## Addendum — Delivery Demo Workspaces (`examples/`)

**Source change**: `openspec/changes/add-delivery-demo-workspaces/` *(archived 2026-04-21; directory removed 2026-05-01)*  
**Phase A completion**: 2026-04-19

Phase A produced three self-contained demo workspaces under `examples/`
covering the full governance pipeline without pytest:

- `01-knowledge-link/` — first-time discovery + low-risk auto-grant + confounder interception + `refresh_skills` episode
- `02-doc-edit-staged/` — `require_reason` + staged `change_stage` + global `blocked_tools` red line
- `03-lifecycle-and-risk/` — TTL expiry + explicit `disable_skill` + high-risk `approval_required` + audit closure

Phase A deliverables: 3 workspace READMEs, 6 skeleton SKILL.md files, 3
`demo_policy.yaml`, 3 `.mcp.json` (relative paths), 4 contract markdown
files, and 16 JSON Schema files (Draft 2020-12, each with `input` +
`output` subschemas). No Python, no core-code change.

**Note**: The change directory was removed as part of `remove-legacy-delivery-demo-changes` cleanup (2026-05-01). All requirements from this change have been migrated to `openspec/specs/delivery-demo-harness/`. The demo workspaces remain fully functional under `examples/`.

Phase B (future change) will implement `mock_*_stdio.py` servers per the
contract tables and schema files, then backfill measured stdout /
`governance.db` audit rows into each workspace README §5.

### Phase B completion (2026-04-19)

Phase B shipped four types of mock MCP stdio servers under each workspace's
`mcp/` directory (six Python files total):

- `mock_yuque_stdio.py` — three per-workspace variants tailored to each demo's
  hardcoded sample scope (example 01 covers `yuque_list_comments` for the
  refresh episode; example 02 adds a `version` field for write-back conflict
  demo; example 03 adds `yuque_delete_doc` for the two-layer defense demo).
- `mock_web_search_stdio.py` / `mock_internal_doc_stdio.py` — confounder MCPs
  in example 01.
- `mock_shell_stdio.py` — confounder MCP in example 02; module docstring
  carries the verbatim "混杂变量工具 / 不代表本项目支持任意 shell 执行"
  disclaimer.

Each mock runs `jsonschema.validate` on every hardcoded output sample against
its paired `schemas/<tool>.schema.json` at module import time; mismatch exits
non-zero before `mcp.run()`. A `tools/list` handshake smoke across all six
Python files was green (5 + 1 + 1 + 3 + 1 + 5 = 16 tool registrations match
contract tables).

Remaining Phase B items left intentionally open:
- **10.9 Live Claude CLI capture** — each workspace can start and answer MCP
  `tools/list`; live end-to-end interactive stdout capture is a per-delivery
  rehearsal, not a one-time task.
- **10.10 SKILL.md SOP bodies** — skeletons with `<!-- Phase B 前补齐 -->`
  retained; SOP depth is deferred to the next iteration since the runnability
  contract does not depend on SOP text.

---

## Addendum — Cache Layer Formalization (`formalize-cache-layers`)

**Source change**: `openspec/changes/formalize-cache-layers/`
**Completion**: Stage A 2026-04-19, Stages B/C/D 2026-04-20

Narrow-scope internal refactor: promotes skill metadata from an implicit
private dict inside `SkillIndexer` to a formal `VersionedTTLCache`
instance that shares one contract with the existing document cache.
External behaviour of MCP entry points (`list_skills`, `read_skill`,
`refresh_skills`), hook entry points, and SQLite-persisted
`SessionState.skills_metadata` is unchanged.

Stage deliverables:
- **Stage A** (discovery): inventory of existing read/write points for
  `SkillIndexer._index` and `VersionedTTLCache` — recorded in change-local
  `stageA_notes.md`. Zero code change.
- **Stage B** (abstraction): added `metadata_cache` keyword-only
  parameter + read-only property on `SkillIndexer`; shadow-writes during
  `build_index`; legacy `cache=` keeps working under `DeprecationWarning`
  mapping to `doc_cache`.
- **Stage C** (migration): removed `SkillIndexer._index`; replaced with a
  lightweight `_indexed_skills` registry (`skill_id → (version, source_path)`);
  `list_skills` / `current_index` / `read_skill` now route through the
  metadata cache with disk-rebuild fallback on miss; `refresh()` clears both
  cache layers within one call. Six new scenario tests in
  `tests/test_skill_indexer.py::TestStageC_CacheLayerFormalization` and
  four shared-contract tests in new `tests/test_cache.py`.
- **Stage D** (closeout): synced `docs/technical_design.md` §3.4 and mirror
  `docs/技术方案文档.md` §3.4; full regression **204 passed**; zero
  consumer-side code change (`mcp_server.py`, `hook_handler.py`,
  `tool_rewriter.py`, `prompt_composer.py`, `langchain_tools.py` untouched).

Deferred to a follow-up change (not archived with this one):
- Metadata-specific TTL tuning (OQ1 in design.md) — currently shares
  doc-cache default (300s / 100 entries).
- Version-field-missing degradation hardening (OQ2) — still silently
  shares `"unknown"` slot.
- Legacy `cache=` alias removal — still accepted under
  `DeprecationWarning`; production callers (`bootstrap.py`, functional
  fixtures) already migrated to `doc_cache=` keyword.

---

## Addendum — Runtime vs Persisted Session State (`separate-runtime-and-persisted-state`)

**Source change**: `openspec/changes/separate-runtime-and-persisted-state/`
**Completion**: Stages A/B/C/D 2026-04-21

Internal semantic refactor at the **L1 (session) layer**: introduces an
explicit runtime-only `RuntimeContext` that hook handlers build once
per turn from the loaded `SessionState` + live `SkillIndexer`.  The
persisted record is narrowed to recovery / continuity / audit fields;
derived fields (`active_tools`, `skills_metadata`) are runtime-authoritative
and kept on `SessionState` only as a compat mirror for unmigrated
consumers.  External behaviour of MCP entry points, hook entry points,
SQLite schema, cache layers (§3.4), and observability is unchanged.

Stage deliverables:

- **Stage A** (inventory): field classification + entry-flow catalog
  recorded in change-local `stageA_notes.md`; field comments in
  `models/state.py`; two skip-marked C3 contract tests.  Baseline: 204 passed.
- **Stage B** (boundary introduction): `core/runtime_context.py` with
  `RuntimeContext` + `build_runtime_context`; `SessionState.to_persisted_dict` + `DERIVED_FIELDS`; `ToolRewriter.blocked_tools` readonly property;
  `hook_handler` wires ctx into `_classify_deny_bucket` and
  `handle_post_tool_use` lookup.  Tests: 7 new in `test_runtime_context.py`.
- **Stage C** (rewrite / compose migration): `tool_rewriter.compute_active_tools(ctx)`; composer union-typed `SessionState | RuntimeContext`
  signatures with legacy fallback; all 4 hook handlers follow the
  explicit `load → derive → rewrite/compose/gate → persist` lifecycle;
  `SessionState.sync_from_runtime` compat shim; 11 new tests across
  `test_tool_rewriter`, `test_prompt_composer`, and new
  `tests/test_hook_lifecycle.py` (integration-style with real
  `GovernanceRuntime` in tmp dirs).
- **Stage D** (closeout): full regression **222 passed, 2 skipped**;
  `openspec validate` clean; docs addenda here + in §3 of
  `docs/technical_design.md`; change closeout at
  `openspec/changes/separate-runtime-and-persisted-state/closeout.md`.
  Zero change to SQLite schema, `.mcp.json`, `hooks/hooks.json`,
  `config/default_policy.yaml`, or any consumer-side return shape.

Deferred to a follow-up change (not archived with this one):

- **C3 serialization exclusion**: `state_manager.save` still dumps the
  full pydantic model; `SessionState.to_persisted_dict` exists but is
  not yet used on the save path.  Two contract tests in
  `tests/test_state_manager.py::TestPersistedFieldContract` wait for
  the flip.
- **MCP meta-tool migration**: the 8 `@mcp.tool` entries in `mcp_server.py`
  still read `state.active_tools` (kept in sync by
  `SessionState.sync_from_runtime`).  They have not been migrated to
  the runtime-view-first pattern.
- **`recompute_active_tools(state)` DeprecationWarning**: deferred to
  avoid warning-noise while MCP callers still use the legacy path.
- **`grant_expired → runtime view skip` regression test**: Stage A/B
  cover `cleanup_expired` semantics; an explicit ctx-visibility test
  for expired grants was not added this round.

---

## Addendum — Demo Workspace Onboarding Hardening (`harden-demo-workspace-onboarding`)

**Source change**: `openspec/changes/harden-demo-workspace-onboarding/` *(directory removed 2026-05-01)*  
**Completion**: Stages A–D 2026-04-21 (docs-only; no governance core touched)

Narrow-scope documentation hardening targeting zero-knowledge readers of
the three demo workspaces under `examples/`. Motivated by a concrete
reproduction: readers following the old workspace README §2 executed
`pip install -e ".[dev]"` from inside a workspace directory and hit
`ERROR: file:///.../examples/01-knowledge-link does not appear to be a
Python project`.

Deliverables:

- `examples/QUICKSTART.md` (new, ~234 lines) — single shared entry
  document covering install / plugin-hooks-MCP wiring / double-path
  first-run (Method B offline `tg-hook` replay as default, Method A
  Claude Code CLI as advanced) / verify SQL / reset command /
  troubleshooting catalog (8+ failure classes, indexed by symptom).
- Rewritten `examples/01-knowledge-link/README.md`,
  `examples/02-doc-edit-staged/README.md`,
  `examples/03-lifecycle-and-risk/README.md` — preflight box, §2
  cleaned of install noise and promoted to Method-B-first with
  workspace-scoped replay examples, §5.3 Verify and §8 Reset +
  workspace-specific troubleshooting added. `§3` operations table,
  `§4` system behavior, `§5.1` audit rows, `§5.2` 실측 record,
  `§6` contract table, and `§7` code anchors preserved verbatim.
- `scripts/check-demo-env.sh` (new) — POSIX-sh preflight that checks

**Note**: The change directory was removed as part of `remove-legacy-delivery-demo-changes` cleanup (2026-05-01). All requirements from this change have been migrated to `openspec/specs/delivery-demo-harness/`. The onboarding improvements remain in place under `examples/`.
  Python 3.11+, `tg-hook` / `tg-mcp` / `claude` on PATH, per-workspace
  `.mcp.json` JSON validity, and `mcp/*.py` syntactic validity.
  Outputs ✅/⚠️/❌; exits non-zero only on ❌.
- `examples/03-lifecycle-and-risk/config/demo_policy.fast.yaml` (new)
  — TTL-only variant of the main policy (`default_ttl: 60`,
  `yuque-knowledge-link.max_ttl: 5`) so the live-demo expiry loop
  completes in seconds rather than 120s. All non-TTL fields must
  stay in lockstep with `demo_policy.yaml`.
- Root `examples/README.md` — two minimal cross-links: top-of-§2
  callout pointing zero-knowledge readers to QUICKSTART; end-of-§5
  pointer to the shared troubleshooting catalog.

Runtime catch during Stage B self-test: `tg-hook`'s stdin protocol
reads the `event` key, not the `hook_event_name` key that the root
`examples/README.md §5.1` template used; the old aspirational
examples returned `{}` silently. QUICKSTART §3.1 uses the correct
key and documents real stdout shapes (SessionStart →
`additionalContext`; PreToolUse on out-of-scope tool →
`hookSpecificOutput.permissionDecision: "deny"`). QUICKSTART §6
T-9 catalogs the `{}` symptom. The spec remained unchanged — the
issue was a template-vs-runtime discrepancy, not a capability delta.

Archive order: archived after `add-delivery-demo-workspaces`
(delivery-demo-harness spec already promoted to
`openspec/specs/delivery-demo-harness/` when the predecessor change
was archived 2026-04-21).

---

## migrate-entrypoints-to-runtime-flow (2026-04-28)

**Goal:** Migrate all hook entry points to accept `RuntimeContext` instead of raw `SessionState`, separating runtime-derived state from persisted state.

**Stages:**
- **Stage A (Inventory):** Cataloged all hook entry points and their current signatures. Identified that `compose()`, `pre_tool_use()`, `post_tool_use()`, and `user_prompt_submit()` all accept raw `SessionState`.
- **Stage B (RuntimeContext):** Created `RuntimeContext` dataclass with `state`, `indexer`, `clock`, and `active_tools` fields. Implemented `build_runtime_context()` to construct it from `SessionState` and `SkillIndexer`. Added grant expiry filtering logic so expired grants don't contribute tools to `active_tools`.
- **Stage C (Migration):** Updated all four hook entry points to accept `RuntimeContext` instead of `SessionState`. Updated `HookHandler` to build `RuntimeContext` before calling hooks. Migrated all tests to use `RuntimeContext`.
- **Stage D (Persistence):** Marked `skills_metadata` and `active_tools` as derived fields, excluded from persistence via `SessionState.to_persisted_dict()`. Updated `StateManager.save()` to use the new method. Added `indexer` parameter to `recompute_active_tools()` so it can fetch metadata from the indexer instead of persisted state.
- **Stage E (Closeout):** Documentation updates, validation, and archival.

**Key design decisions:**
- `RuntimeContext` is the single source of truth for hook entry points. Hooks should never directly access `state.skills_metadata` or `state.active_tools`.
- `skills_metadata` is now always fetched from `SkillIndexer.current_index()` at runtime, ensuring it reflects the latest skill definitions on disk.
- `active_tools` is computed from `active_grants` and `skills_metadata` at runtime, filtered by grant expiry.
- Persisted state only contains durable fields: `skills_loaded`, `active_grants`, `last_used_at`.

**Test coverage:**
- 238 tests passing, including new tests for grant expiry filtering (`test_grant_expiry_runtime_view.py`) and hook lifecycle (`test_hook_lifecycle.py`).
- All functional tests updated to use `RuntimeContext` and pass `indexer` to `recompute_active_tools()`.

**Commits:**
- Stage B: `83fc08c` - stage C-root: wire examples/README to QUICKSTART
- Stage C: `50649cd` - stage C-03: migrate 03-lifecycle-and-risk README
- Stage C: `2e049ab` - stage C-02: migrate 02-doc-edit-staged README
- Stage D: `b5cb88b` - stage D: exclude skills_metadata from persistence, add grant expiry filtering

**Related changes:**
- Completes the deferred work from `separate-runtime-and-persisted-state` (see `docs/technical_design.md` Addendum).
- Enables future work on skill hot-reloading and dynamic metadata updates without state file churn.
