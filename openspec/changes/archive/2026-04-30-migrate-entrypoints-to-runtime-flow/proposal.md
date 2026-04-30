## Why

这是 `separate-runtime-and-persisted-state` change 的 follow-up，承接其 closeout.md 中 intentionally deferred 的 4 个 backlog 任务：

1. **Backlog #2 · MCP meta-tool migration**: `mcp_server.py` 的 8 个 `@mcp.tool` 入口仍沿用 pre-Stage-C 的 `recompute_active_tools(state)` 模式，未迁移到统一的"load → derive → rewrite/compose/gate → persist"四步 runtime flow。
2. **Backlog #3 · `recompute_active_tools(state)` DeprecationWarning + test migration**: 为避免 MCP 迁移期间产生生产日志噪音，`tool_rewriter.recompute_active_tools(state)` 的 DeprecationWarning 和 `tests/test_tool_rewriter.py` 中"就地修改 state"断言的迁移被推迟。
3. **Backlog #4 · Grant-expiry runtime-visible tools regression test**: 现有测试覆盖了 `cleanup_expired` 语义，但缺少一条显式的 ctx-visibility 回归测试，验证 grant 过期后 `RuntimeContext.active_tools` 不再包含该 skill 的工具。
4. **Backlog #5 · LangChain tool shim migration**: `tools/langchain_tools.py:74` 仍直接读取 `state.skills_metadata`，与 MCP 入口有相同的迁移需求。

本 change **不扩展新需求**，仅完成上一 change 中为避免影响面过大而 intentionally deferred 的收尾工作。

## What Changes

- **8 个 MCP meta-tool 入口迁移**:
  - `list_skills` / `read_skill` / `enable_skill` / `disable_skill` / `grant_status` / `run_skill_action` / `change_stage` / `refresh_skills` 全部改为统一四步流程:`load_or_init(sid) → build_runtime_context(state, ...) → mutate persisted-only fields → save(state)`
  - 移除对 `state.skills_metadata` 的直接读取，改为从 `indexer.current_index()` 或 `RuntimeContext.all_skills_metadata` 获取
  - 移除对 `state.active_tools` 的直接读取，改为从 `RuntimeContext.active_tools` 获取
- **LangChain tool shim 迁移**:
  - `tools/langchain_tools.py` 中的 `enable_skill_tool` / `disable_skill_tool` / `run_skill_action_tool` 等函数按相同模式迁移
- **Legacy adapter + DeprecationWarning**:
  - `tool_rewriter.recompute_active_tools(state)` 改为 thin adapter:内部委托 `compute_active_tools(build_runtime_context(...))` 后把结果赋回 `state.active_tools`，并发出 `DeprecationWarning`
  - 在代码注释中明确标注:"This function is deprecated. Use `compute_active_tools(RuntimeContext)` instead."
- **Test migration**:
  - `tests/test_tool_rewriter.py` 中"就地修改 state"的断言迁移为"`compute_active_tools` 返回值正确 + runtime_ctx / state 均未被修改"
  - 新增 `tests/test_mcp_runtime_flow.py`:验证 8 个 MCP 入口均走四步流程，且不直接读取 `state.active_tools` / `state.skills_metadata`
  - 新增 grant 过期后 runtime-visible tools 的 regression test
- **Persisted field exclusion 完成**:
  - `SessionState.DERIVED_FIELDS` 从 `{"active_tools"}` 扩展为 `{"active_tools", "skills_metadata"}`
  - `state_manager.save` 通过 `to_persisted_dict()` 排除这两个字段，不再写入 SQLite
  - 更新 `tests/test_state_manager.py::TestPersistedFieldContract`:断言序列化 JSON 既不含 `active_tools` 也不含 `skills_metadata`

### In Scope

- 8 个 MCP meta-tool 入口的四步流程迁移
- LangChain tool shim 的四步流程迁移
- `recompute_active_tools(state)` 改为 thin adapter + DeprecationWarning
- `tests/test_tool_rewriter.py` 断言迁移
- Grant 过期后 runtime-visible tools 的 regression test
- `skills_metadata` 从持久化 payload 中排除
- Spec / document alignment

### Out of Scope

显式排除以下范围，避免 scope creep:

- **不做 Redis / L3 跨实例缓存**(与前序 change 非目标一致)
- **不做 StateStore / CacheStore abstraction**(不引入通用存储接口层)
- **不做 observability taxonomy 标准化**(审计 event schema 不动)
- **不做 cache layer 重构**(`formalize-cache-layers` 已归档，保持其接口)
- **不改 SQLite schema / grants 表 / audit_log 表**
- **不改 SKILL.md parse / SkillIndexer 实现**
- **不改 policy / blocked_tools / 任何 YAML 配置格式**
- **不改 `.mcp.json` / `hooks/hooks.json` / MCP 对外返回 shape**

## Capabilities

### New Capabilities

(无)本期是对已有 `session-lifecycle` 与 `tool-surface-control` 契约的收尾工作，不引入新 capability。

### Modified Capabilities

- `session-lifecycle`:完成 `skills_metadata` 从持久化 payload 的排除，使持久态定义彻底收窄到 `skills_loaded` / `active_grants` / 审计锚点
- `tool-surface-control`:完成所有入口(MCP + LangChain)到统一 runtime flow 的迁移，废弃 `recompute_active_tools(state)` 的就地修改语义

## Impact

- **代码**:
  - `src/tool_governance/mcp_server.py` —— 8 个 `@mcp.tool` 入口按四步流程改写
  - `src/tool_governance/tools/langchain_tools.py` —— LangChain tool shim 按四步流程改写
  - `src/tool_governance/core/tool_rewriter.py` —— `recompute_active_tools(state)` 改为 thin adapter + DeprecationWarning
  - `src/tool_governance/models/state.py` —— `DERIVED_FIELDS` 扩展为 `{"active_tools", "skills_metadata"}`
  - `src/tool_governance/core/state_manager.py` —— 确认 `save` 路径通过 `to_persisted_dict()` 排除派生字段
- **测试**:
  - `tests/test_tool_rewriter.py` —— 断言迁移:"就地修改 state" → "返回值正确 + 输入未被修改"
  - `tests/test_mcp_runtime_flow.py`(新增)—— 验证 8 个 MCP 入口的四步流程
  - `tests/test_state_manager.py::TestPersistedFieldContract` —— 断言扩展:排除 `skills_metadata`
  - `tests/test_grant_expiry_runtime_view.py`(新增)—— Grant 过期后 runtime-visible tools 的 regression test
- **依赖**:不新增
- **非影响**:`.mcp.json`、`hooks/hooks.json`、`config/default_policy.yaml`、SQLite schema、grants / audit_log 表、`SkillIndexer` 及其 cache、Langfuse 集成

## Risks / Rollback

- **风险 R1 · MCP 入口迁移遗漏**:8 个入口手工改造容易漏一两处
  - **缓解**:新增 `tests/test_mcp_runtime_flow.py`，对每个入口做"不直接读取 `state.active_tools` / `state.skills_metadata`"的契约测试
- **风险 R2 · DeprecationWarning 噪音**:若有未迁移的调用点，生产日志会出现 warning
  - **缓解**:本 change 已迁移所有已知调用点(MCP + LangChain + tests)，warning 仅作为未来扩展的防护
- **风险 R3 · 持久 JSON 字段收缩的向后兼容**:老 session 的 `state_json` 里仍有 `skills_metadata`
  - **缓解**:pydantic `BaseModel` 默认允许多余字段;`tests/test_state_manager.py` 已有兼容性测试覆盖
- **回滚路径**:
  - 本 change 预计落在 2-3 个 commit(MCP 迁移 + LangChain 迁移 + test migration)
  - 外部契约全程未变，回滚 = `git revert <commit(s)>`
