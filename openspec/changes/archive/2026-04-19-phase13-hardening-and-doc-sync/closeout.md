# Closeout — phase13-hardening-and-doc-sync

## Verification results

| Check | Command | Result |
|---|---|---|
| Full regression | `python -m pytest -v` | **122 passed**, 0 failed (baseline was 104 at the start of Stage A) |
| Plugin manifest | `claude plugin validate .` (claude CLI 2.1.111) | **✔ Validation passed** |
| Smoke import | `python -c "import tool_governance.mcp_server; import tool_governance.hook_handler; ..."` | All modules load; `PromptComposer()` instantiates without args (matches the D5 doc-sync); `ToolRewriter(blocked_tools=None)` works |
| Plugin manifest parse | `json.load('.claude-plugin/plugin.json')` | Loads; name=`tool-governance-plugin`, version=`0.1.0` |
| Hook manifest parse | `hooks/hooks.json` | Loads; `SessionStart / UserPromptSubmit / PreToolUse / PostToolUse` wired to the `tg-hook` console script |

Plugin is loadable by the Claude Code CLI as-is. No further validation step
is required to close this change.

## What each drift produced

| ID  | Fix summary | Primary file(s) |
|-----|-------------|-----------------|
| D1  | PostToolUse stamps exactly one skill (added `matched` flag, outer-loop break). | `src/tool_governance/hook_handler.py` |
| D2  | `run_skill_action` denies when `meta is None`; emits `skill.action.deny` audit with `detail.reason="meta_missing"`; no dispatch. | `src/tool_governance/mcp_server.py` |
| D3  | `refresh_skills` now single-scans via new `SkillIndexer.current_index()` read-only accessor. | `src/tool_governance/mcp_server.py`, `src/tool_governance/core/skill_indexer.py` |
| D4  | Test gap-fill for `meta is None` branches across MCP entry points (`change_stage`, `enable_skill`, `read_skill`, `ToolRewriter.recompute_active_tools`). | `tests/test_integration.py::TestMetaNoneEdgeCases` |
| D5  | Doc sync: `PromptComposer` (no constructor args, stateless) and `ToolRewriter(blocked_tools=…)` with `@staticmethod get_stage_tools`. | `docs/technical_design.md` §3.2.4, §3.2.5; Chinese mirror |
| D6  | `enable_skill_tool` LangChain wrapper mirrors `mcp_server.enable_skill` exactly: `scope` and `granted_by` coercion identical. | `src/tool_governance/tools/langchain_tools.py` |
| D7  | New `grant.revoke` audit event emitted once per revocation in `GrantManager.revoke_grant()`; `reason` discriminator defaults to `"explicit"`. Event boundary with `skill.disable` and `grant.expire` is explicit and non-overlapping. | `src/tool_governance/core/grant_manager.py` |
| D8  | Doc + docstring sync: `state.active_grants` is keyed by **`skill_id`**, not `grant_id`. Stale docstrings corrected. Re-keying explicitly deferred. | `src/tool_governance/models/state.py`, `src/tool_governance/core/state_manager.py`; `docs/technical_design.md` §10-B; Chinese mirror |
| D9  | **Deferred** — backlog. | — |
| D10 | **Deferred** — backlog. | — |

## Final Drift Resolution Matrix

| ID  | status   | handling    | evidence |
|-----|----------|-------------|----------|
| D1  | closed   | fix         | `src/tool_governance/hook_handler.py::handle_post_tool_use`; `tests/test_integration.py::TestPostToolUseSingleStamp` |
| D2  | closed   | fix         | `src/tool_governance/mcp_server.py::run_skill_action`; `tests/test_integration.py::TestRunSkillActionMetaMissing` |
| D3  | closed   | fix         | `src/tool_governance/mcp_server.py::refresh_skills`, `src/tool_governance/core/skill_indexer.py::SkillIndexer.current_index`; `tests/test_integration.py::TestRefreshSkillsSingleScan` |
| D4  | closed   | fix (tests) | `tests/test_integration.py::TestMetaNoneEdgeCases` + Stage A/B test classes |
| D5  | closed   | doc-sync    | `docs/technical_design.md` §3.2.4, §3.2.5; `docs/技术方案文档.md` 3.2.4, 3.2.5 |
| D6  | closed   | fix         | `src/tool_governance/tools/langchain_tools.py::enable_skill_tool`; `tests/test_integration.py::TestEnableSkillParity` |
| D7  | closed   | fix         | `src/tool_governance/core/grant_manager.py::revoke_grant`; `tests/test_grant_manager.py::TestRevoke` (4 new), `tests/test_integration.py::TestDisableSkillAuditOrdering` |
| D8  | closed   | doc-sync    | `src/tool_governance/models/state.py::SessionState.active_grants`, `src/tool_governance/core/state_manager.py::remove_from_skills_loaded`; `docs/technical_design.md` §10-B; `docs/技术方案文档.md` state-model note |
| D9  | deferred | backlog     | `openspec/changes/phase13-hardening-and-doc-sync/proposal.md` §"Out of Scope" |
| D10 | deferred | backlog     | same as D9 |

## Scope guard — items NOT implemented (by design)

- **Phase 4 backlog** — Langfuse integration, funnel metrics, additional
  error buckets, CHANGELOG, benchmarks: none implemented.
- **D9 / D10**: deferred per proposal §"Out of Scope".
- **`active_grants` re-keying**: the dict stays keyed by `skill_id`
  (invariant documented, migration explicitly deferred).
- **`docs/requirements.md` / `docs/需求文档.md`**: untouched — this round was
  implementation/modelling semantics and doc sync, not requirements clarification.
- **EN/CN doc version-stamp drift** (v1.1 vs v1.2): noted in the proposal,
  not reconciled.

## Test delta

| Stage | Baseline | After stage | Net new | Classes added |
|-------|----------|-------------|---------|----------------|
| A (D2, D1) | 104 | 109 | +5 | `TestRunSkillActionMetaMissing` (2), `TestPostToolUseSingleStamp` (3) |
| B (D6, D3, D7) | 109 | 118 | +9 | `TestRevoke` (+4 cases), `TestEnableSkillParity` (2), `TestRefreshSkillsSingleScan` (1), `TestDisableSkillAuditOrdering` (2) |
| C (D4, D5, D8) | 118 | 122 | +4 | `TestMetaNoneEdgeCases` (4) |
| D (this stage) | 122 | 122 | 0 | — (verification only) |
