## 1. Phase 1 — Project Scaffold + Base Models

- [x] 1.1 Initialize Python project: `pyproject.toml` with dependencies (mcp, pydantic, langchain-core, cachetools, pyyaml), console_scripts entry points (`tg-hook`, `tg-mcp`), dev dependencies (pytest, ruff, mypy), and src layout
- [x] 1.2 Create plugin directory skeleton: `.claude-plugin/`, `skills/governance/`, `hooks/`, `agents/`, `config/`, `src/tool_governance/{core,models,storage,utils}/`, `tests/`
- [x] 1.3 Write `.claude-plugin/plugin.json` manifest with name, version, description, hooks and mcpServers references
- [x] 1.4 Define Pydantic models: `models/skill.py` (SkillMetadata, StageDefinition, SkillContent), `models/grant.py` (Grant), `models/state.py` (LoadedSkillInfo, SessionState), `models/policy.py` (SkillPolicy, GovernancePolicy)
- [x] 1.5 Implement `utils/cache.py`: TTLCache wrapper with version/hash-aware cache keys, maxsize=100, ttl=300s
- [x] 1.6 Implement `core/skill_indexer.py`: scan skills/ directory, parse YAML frontmatter (safe_load), build SkillMetadata index, read_skill with cache, file size limit (100KB), description truncation (500 chars), stages parsing
- [x] 1.7 Write `skills/governance/SKILL.md` — the plugin's self-governance skill definition with 8 meta-tools in allowed_tools
- [x] 1.8 Write example skills: `skills/repo-read/SKILL.md` (low risk, Read/Glob/Grep), `skills/code-edit/SKILL.md` (medium risk, 2 stages: analysis + execution), `skills/web-search/SKILL.md` (low risk, WebSearch/WebFetch)
- [x] 1.9 Unit tests: `test_skill_indexer.py` (scanning, parsing, malformed YAML, oversized files, stages, caching), `test_models.py` (serialization roundtrip, validation)
- [x] 1.10 Verify: `pip install -e .` succeeds, `tg-hook --help` and `tg-mcp --help` entry points resolve, pytest passes

> **Docs sync after Phase 1**: None — no deltas to docs/ yet.

## 2. Phase 2 — Core Governance Logic

- [x] 2.1 Implement `storage/sqlite_store.py`: create `sessions`, `grants`, `audit_log` tables with indexes; WAL journal mode; busy_timeout=5s; CRUD for sessions and grants; append-only audit insert
- [x] 2.2 Implement `core/state_manager.py`: load_or_init (session ID discovery per D2 priority chain), save, add/remove skills_loaded, get_active_tools delegation
- [x] 2.3 Implement `core/policy_engine.py`: evaluate() with blocked-list → skill-specific policy → risk-level default chain; is_tool_allowed(); max TTL enforcement
- [x] 2.4 Implement `core/grant_manager.py`: create_grant (with TTL cap), revoke_grant, cleanup_expired (returns expired skill_ids), get_active_grants, is_grant_valid
- [x] 2.5 Implement `core/tool_rewriter.py`: recompute_active_tools (meta_tools ∪ stage_tools union − blocked_tools), get_stage_tools (stage-aware, fallback to first stage if current_stage=None)
- [x] 2.6 Implement `core/prompt_composer.py`: compose_context (≤800 chars), compose_skill_catalog, compose_active_tools_prompt; enabled skills show detail, unenabled show summary only
- [x] 2.7 Implement `bootstrap.py`: GovernanceRuntime facade that assembles all modules from data_dir + skills_dir
- [x] 2.8 Write `config/default_policy.yaml`: default risk thresholds (low=auto, medium=reason, high=approval), default TTL=3600, default scope=session, blocked_tools=[]
- [x] 2.9 LangChain integration: `tools/` directory with @tool-decorated wrappers for list_skills, read_skill, enable_skill, disable_skill, grant_status, run_skill_action
- [x] 2.10 Unit tests: `test_state_manager.py`, `test_policy_engine.py`, `test_grant_manager.py`, `test_tool_rewriter.py`, `test_prompt_composer.py`, `test_sqlite_store.py` — each covering core scenarios from specs

> **Docs sync after Phase 2**: None — core logic validated internally, no runtime findings yet.

## 3. Phase 3 — Plugin Integration + Hook Orchestration

- [x] 3.1 Implement `mcp_server.py`: stdio MCP server exposing 8 tools (list_skills, read_skill, enable_skill, disable_skill, grant_status, run_skill_action, change_stage, refresh_skills); each tool delegates to GovernanceRuntime
- [x] 3.2 Implement `core/skill_executor.py`: registration-based dispatch table (D4), register built-in handlers for example skills (repo-read, code-edit ops)
- [x] 3.3 Write `.mcp.json`: declare tool-governance MCP server using `tg-mcp` console_script entry point
- [x] 3.4 Implement `hook_handler.py`: stdin JSON → event dispatch → stdout JSON; MCP tool name normalization (extract short_name from `mcp__<server>__<tool>`)
- [x] 3.5 Implement SessionStart handler: load/init state, cleanup expired grants, build skill index if empty, recompute active_tools, return additionalContext with catalog summary
- [x] 3.6 Implement UserPromptSubmit handler: cleanup expired grants, recompute active_tools per turn, compose additionalContext via prompt_composer, persist state, record audit
- [x] 3.7 Implement PreToolUse handler: meta-tool always-allow check, active_tools membership check, deny with guidance additionalContext for unauthorized tools
- [x] 3.8 Implement PostToolUse handler: update skill_last_used_at, record structured audit log entry
- [x] 3.9 Write `hooks/hooks.json`: bind SessionStart, UserPromptSubmit, PreToolUse, PostToolUse to `tg-hook` entry point with timeouts (5000ms, 3000ms, 3000ms, 3000ms)
- [x] 3.10 Integration tests: `test_integration.py` — simulate full flow (SessionStart → list → read → enable → UserPromptSubmit → tool call → PreToolUse → PostToolUse); simulate deny flow; simulate TTL expiry; simulate stage switching
- [x] 3.11 Local plugin load verification: install plugin in Claude Code, verify MCP server connects, 8 tools discoverable, hooks trigger on events, complete 8-step chain end-to-end
- [x] 3.12 Record U1-U8 findings: document actual hook input field names, Windows behavior, matcher format, and all other uncertainty items resolved during integration

> **Docs sync after Phase 3**:
> - `docs/技术方案文档.md` S10: Replace [不确定项] U1-U8 with verified findings
> - `docs/技术方案文档.md` S4.2-4.3: Update .mcp.json and hooks.json with actual configs (console_script entries, confirmed matcher format)
> - `docs/需求文档.md` S5.1 F6: Update run_skill_action with confirmed delegation mechanism

## 4. Phase 4 — Observability, E2E Testing + Docs

- [ ] 4.1 Implement structured audit logging: ensure all 9 event types (skill.list, skill.read, skill.enable, skill.disable, tool.call, grant.expire, grant.revoke, stage.change, prompt.submit) recorded with consistent fields
- [ ] 4.2 Implement funnel metrics support: ensure audit_log queries can produce shown→read→enable→tool counts per session and per skill
- [ ] 4.3 Implement misuse call bucketing: classify denied tool calls into whitelist_violation, wrong_skill_tool, parameter_error; record error_bucket in audit detail
- [ ] 4.4 Implement optional Langfuse integration: conditional import, session→trace mapping, observation per skill operation, graceful fallback when langfuse not installed
- [ ] 4.5 E2E test suite: full 8-step governance chain, multi-skill concurrent enable, stage switching with active_tools verification
- [ ] 4.6 Security/boundary tests: deny unauthorized tool call, TTL expiration cleanup, turn-scoped grant expiry, blocked skill rejection, max TTL capping
- [ ] 4.7 Performance benchmarks: measure hook handler latency (target <50ms), MCP tool response time (target <100ms), cache hit rate (target >95%); record results
- [ ] 4.8 Code quality: ruff lint pass, mypy type check pass, test coverage report (target >80% for core modules)
- [ ] 4.9 Write README.md: installation guide, configuration, usage tutorial, architecture diagram, core chain explanation
- [ ] 4.10 Write CHANGELOG.md, finalize version number in pyproject.toml and plugin.json

> **Docs sync after Phase 4**:
> - `docs/技术方案文档.md` S6: Add performance benchmark results (actual hook latency, cache hit rate)
> - `docs/开发计划.md` S3: Update each phase with completion status and any deviations from plan
> - `docs/需求文档.md` S5.1 F6: Finalize run_skill_action example skill definitions if changed during Phase 4
