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

- [Claude Code Plugin Reference](https://code.claude.com/docs/en/plugins-reference)
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks)
- [Claude Code Tools Reference](https://code.claude.com/docs/en/tools-reference)
- [Claude Code MCP Integration](https://code.claude.com/docs/en/mcp)
- [ivan-magda/claude-code-plugin-template](https://github.com/ivan-magda/claude-code-plugin-template)
- [anthropics/claude-code Official Plugin Repository](https://github.com/anthropics/claude-code/tree/main/plugins)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- Skill-Hub Project Documentation (this project's `Skill-Hub Project Prep Edition.md`, `Handwritten Skills Long Edition.md`)
