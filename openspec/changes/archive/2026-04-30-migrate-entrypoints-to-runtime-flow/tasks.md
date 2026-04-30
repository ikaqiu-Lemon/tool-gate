## Stage A — MCP 入口迁移 (8 个 meta-tool)

**改哪些文件**:`src/tool_governance/mcp_server.py`、`tests/test_mcp_runtime_flow.py`(新增)。

**不改哪些文件**:`hook_handler.py`(已在前序 change 迁移)、`tools/langchain_tools.py`(留到 Stage B)、`core/tool_rewriter.py`(留到 Stage C)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `mcp_server.py` 和新增测试文件;参考 `hook_handler.py` 中已迁移的四步模板。

- [x] A.1 新增 `_build_runtime_ctx(rt, state)` helper 函数
- [x] A.2 `list_skills` 迁移:从 `ctx.all_skills_metadata` 读取
- [x] A.3 `read_skill` 迁移:从 `ctx.all_skills_metadata` 读取
- [x] A.4 `enable_skill` 迁移:load → derive → mutate persisted-only → save
- [x] A.5 `disable_skill` 迁移:load → derive → mutate persisted-only → save
- [x] A.6 `grant_status` 迁移:只读操作，但为一致性仍走四步
- [x] A.7 `run_skill_action` 迁移:从 `ctx.all_skills_metadata` 读取
- [x] A.8 `change_stage` 迁移:修改 `skills_loaded[skill_id].current_stage` 后 derive
- [x] A.9 `refresh_skills` 迁移:不再更新 `state.skills_metadata`(它是派生字段)
- [x] A.10 新增 `tests/test_mcp_runtime_flow.py`:对每个 MCP 入口断言不直接读取 `state.active_tools` / `state.skills_metadata`
- [x] A.11 运行 `pytest tests/test_mcp_runtime_flow.py -q` 通过
- [x] A.12 运行 `pytest tests/functional -q` 回归通过

## Stage B — LangChain tool shim 迁移

**改哪些文件**:`src/tool_governance/tools/langchain_tools.py`。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`core/tool_rewriter.py`(留到 Stage C)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `langchain_tools.py`;参考 Stage A 的迁移模式。

- [x] B.1 `enable_skill_tool` 迁移:同 Stage A.4
- [x] B.2 `disable_skill_tool` 迁移:同 Stage A.5
- [x] B.3 `run_skill_action_tool` 迁移:同 Stage A.7
- [x] B.4 其他 LangChain tool(如有)按相同模式迁移
- [x] B.5 运行 `pytest tests/test_langchain_tools.py -q` 通过(若存在)
- [x] B.6 运行 `pytest -q` 全量回归

## Stage C — Legacy adapter + DeprecationWarning + test migration

**改哪些文件**:`src/tool_governance/core/tool_rewriter.py`、`tests/test_tool_rewriter.py`。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`langchain_tools.py`(Stage B 已完成)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `tool_rewriter.py` 和其单测。

- [x] C.1 `recompute_active_tools(state)` 改为 thin adapter + DeprecationWarning
- [x] C.2 `tests/test_tool_rewriter.py` 断言迁移:将"就地修改 state"断言改为"`compute_active_tools` 返回值正确 + state 未被修改"
- [x] C.3 新增 `test_recompute_active_tools_emits_deprecation_warning`
- [x] C.4 运行 `pytest tests/test_tool_rewriter.py -q` 通过

## Stage D — Persisted field exclusion + grant expiry regression test

**改哪些文件**:`src/tool_governance/models/state.py`、`tests/test_state_manager.py`、`tests/test_grant_expiry_runtime_view.py`(新增)。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`langchain_tools.py`(Stage B 已完成)、`tool_rewriter.py`(Stage C 已完成)。

**上下文守则**:只打开 `models/state.py`、`state_manager.py`(确认 save 路径)、相关测试。

- [x] D.1 `SessionState.DERIVED_FIELDS` 扩展为 `{"active_tools", "skills_metadata"}`
- [x] D.2 确认 `state_manager.save` 通过 `to_persisted_dict()` 排除派生字段
- [x] D.3 更新 `tests/test_state_manager.py::TestPersistedFieldContract`:断言 `skills_metadata` 也被排除
- [x] D.4 新增 `tests/test_grant_expiry_runtime_view.py`:验证 grant 过期后 `ctx.active_tools` 不含该 skill 的工具
- [x] D.5 运行 `pytest tests/test_state_manager.py tests/test_grant_expiry_runtime_view.py -q` 通过
- [x] D.6 运行 `pytest -q` 全量回归 — 238 passed

## Stage E — Spec / document alignment + closeout

**改哪些文件**:`docs/technical_design.md`(更新 "Runtime vs Persisted State" 小节)、`docs/dev_plan.md`(追加本 change 条目)、本 change 目录新增 `closeout.md`。

**不改哪些文件**:任何生产代码(应已在 Stage A-D 冻结)、`docs/requirements.md`(requirement delta 在 specs/ 下)。

**上下文守则**:只读 `docs/` 三份 md;事实从本 change 的 design / specs 取。

- [x] E.1 运行 `pytest -q` 全量，记录 passed 数量 — 238 passed
- [x] E.2 运行 `openspec validate migrate-entrypoints-to-runtime-flow` 通过 — ✅
- [x] E.3 `docs/technical_design.md` · 更新 "Runtime vs Persisted State" 小节
- [x] E.4 `docs/dev_plan.md` · 追加本 change 的 Stage A-E 条目
- [x] E.5 产出 `closeout.md`:迁移清单、测试覆盖、DeprecationWarning 触发条件、后续 backlog(若有)
- [x] E.6 确认本 change **未**修改 `docs/requirements.md` — ✅ 未修改
- [x] E.7 对照 proposal §"In Scope" 与 specs/ Requirement 做自查 — ✅ 所有验收标准满足
- [x] E.8 产出 · 运行结果汇总表(full pytest、openspec validate、各 Stage commit hash) — 见 closeout.md
