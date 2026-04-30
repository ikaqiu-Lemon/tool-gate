## Overview

本 change 是 `separate-runtime-and-persisted-state` 的 follow-up，完成其 closeout.md 中 intentionally deferred 的 4 个 backlog 任务。核心目标:将所有入口(MCP + LangChain)迁移到统一的四步 runtime flow，废弃 `recompute_active_tools(state)` 的就地修改语义，并完成 `skills_metadata` 从持久化 payload 的排除。

## Architecture

### Current State (pre-migration)

```
MCP entry points (8 tools)
  ├─ list_skills / read_skill / enable_skill / disable_skill
  ├─ grant_status / run_skill_action / change_stage / refresh_skills
  └─ Pattern: load_or_init(sid) → mutate state → recompute_active_tools(state) → save(state)
      └─ Direct reads: state.skills_metadata, state.active_tools

LangChain tool shim (tools/langchain_tools.py)
  ├─ enable_skill_tool / disable_skill_tool / run_skill_action_tool
  └─ Pattern: same as MCP (direct reads from state)

tool_rewriter.recompute_active_tools(state)
  └─ In-place mutation: state.active_tools = compute(...)
      └─ No DeprecationWarning yet (deferred to avoid log noise)

SessionState.DERIVED_FIELDS = {"active_tools"}
  └─ skills_metadata still persisted (deferred until MCP migration)
```

### Target State (post-migration)

```
MCP entry points (8 tools)
  ├─ Unified pattern: load → derive → mutate persisted-only → save
  │   └─ ctx = build_runtime_context(state, indexer, policy, clock)
  │   └─ Read from: ctx.active_tools, ctx.all_skills_metadata
  └─ No direct reads from state.active_tools / state.skills_metadata

LangChain tool shim
  └─ Same unified pattern as MCP

tool_rewriter.recompute_active_tools(state)
  └─ Thin adapter: compute_active_tools(build_runtime_context(...)) + DeprecationWarning
      └─ Docstring: "Deprecated. Use compute_active_tools(RuntimeContext) instead."

SessionState.DERIVED_FIELDS = {"active_tools", "skills_metadata"}
  └─ Both excluded from persisted payload via to_persisted_dict()
```

## Implementation Plan

### Stage A — MCP 入口迁移 (8 个 meta-tool)

**改哪些文件**:`src/tool_governance/mcp_server.py`、`tests/test_mcp_runtime_flow.py`(新增)。

**不改哪些文件**:`hook_handler.py`(已在前序 change 迁移)、`tools/langchain_tools.py`(留到 Stage B)、`core/tool_rewriter.py`(留到 Stage C)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `mcp_server.py` 和新增测试文件;参考 `hook_handler.py` 中已迁移的四步模板。

- [ ] A.1 `list_skills` 迁移:
  ```python
  # Before
  state = state_manager.load_or_init(session_id)
  skills = state.skills_metadata.values()
  
  # After
  state = state_manager.load_or_init(session_id)
  ctx = _build_runtime_ctx(rt, state)  # helper function
  skills = ctx.all_skills_metadata.values()
  ```
- [ ] A.2 `read_skill` 迁移:同 A.1，从 `ctx.all_skills_metadata` 读取
- [ ] A.3 `enable_skill` 迁移:
  ```python
  # Before
  state = state_manager.load_or_init(session_id)
  # ... policy check, grant creation, add to skills_loaded
  active_tools = tool_rewriter.recompute_active_tools(state)
  state_manager.save(state)
  return {"granted": True, "allowed_tools": active_tools}
  
  # After
  state = state_manager.load_or_init(session_id)
  # ... policy check, grant creation, add to skills_loaded
  ctx = _build_runtime_ctx(rt, state)
  state.sync_from_runtime(ctx.active_tools)  # compat mirror
  state_manager.save(state)
  return {"granted": True, "allowed_tools": list(ctx.active_tools)}
  ```
- [ ] A.4 `disable_skill` 迁移:同 A.3
- [ ] A.5 `grant_status` 迁移:只读操作，无需 derive，但为一致性仍走四步
- [ ] A.6 `run_skill_action` 迁移:
  ```python
  # Before
  state = state_manager.load_or_init(session_id)
  if skill_id not in state.skills_loaded: return error
  meta = state.skills_metadata.get(skill_id)
  
  # After
  state = state_manager.load_or_init(session_id)
  ctx = _build_runtime_ctx(rt, state)
  if skill_id not in state.skills_loaded: return error
  meta = ctx.all_skills_metadata.get(skill_id)
  ```
- [ ] A.7 `change_stage` 迁移:同 A.3(修改 `skills_loaded[skill_id].current_stage` 后 derive)
- [ ] A.8 `refresh_skills` 迁移:
  ```python
  # Before
  indexer.refresh()
  state.skills_metadata = indexer.build_index()
  
  # After
  indexer.refresh()
  # No need to update state.skills_metadata (it's derived)
  # Next turn's build_runtime_context will pick up fresh metadata
  ```
- [ ] A.9 新增 `_build_runtime_ctx(rt, state)` helper:
  ```python
  def _build_runtime_ctx(rt: GovernanceRuntime, state: SessionState) -> RuntimeContext:
      metadata = rt.skill_indexer.current_index()
      if not metadata:
          metadata = state.skills_metadata  # fallback for cold start
      return build_runtime_context(
          state=state,
          metadata=metadata,
          blocked_tools=rt.policy.blocked_tools,
          clock=datetime.now(timezone.utc)
      )
  ```
- [ ] A.10 新增 `tests/test_mcp_runtime_flow.py`:
  - 对每个 MCP 入口，断言"不直接读取 `state.active_tools` / `state.skills_metadata`"
  - 方法:mock `state.active_tools` / `state.skills_metadata` 为 sentinel 值，调用 MCP 入口，断言返回值不含 sentinel
- [ ] A.11 运行 `pytest tests/test_mcp_runtime_flow.py -q` 通过
- [ ] A.12 运行 `pytest tests/functional -q` 回归通过

### Stage B — LangChain tool shim 迁移

**改哪些文件**:`src/tool_governance/tools/langchain_tools.py`。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`core/tool_rewriter.py`(留到 Stage C)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `langchain_tools.py`;参考 Stage A 的迁移模式。

- [ ] B.1 `enable_skill_tool` 迁移:同 Stage A.3
- [ ] B.2 `disable_skill_tool` 迁移:同 Stage A.4
- [ ] B.3 `run_skill_action_tool` 迁移:同 Stage A.6
- [ ] B.4 其他 LangChain tool(如有)按相同模式迁移
- [ ] B.5 运行 `pytest tests/test_langchain_tools.py -q` 通过(若存在)
- [ ] B.6 运行 `pytest -q` 全量回归

### Stage C — Legacy adapter + DeprecationWarning + test migration

**改哪些文件**:`src/tool_governance/core/tool_rewriter.py`、`tests/test_tool_rewriter.py`。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`langchain_tools.py`(Stage B 已完成)、`models/state.py`(留到 Stage D)。

**上下文守则**:只打开 `tool_rewriter.py` 和其单测。

- [ ] C.1 `recompute_active_tools(state)` 改为 thin adapter:
  ```python
  def recompute_active_tools(state: SessionState) -> list[str]:
      """Deprecated. Use compute_active_tools(RuntimeContext) instead.
      
      This function is a thin adapter for backward compatibility.
      It will be removed in a future version.
      """
      import warnings
      warnings.warn(
          "recompute_active_tools(state) is deprecated. "
          "Use compute_active_tools(RuntimeContext) instead.",
          DeprecationWarning,
          stacklevel=2
      )
      # Build minimal RuntimeContext for compatibility
      ctx = build_runtime_context(
          state=state,
          metadata=state.skills_metadata,  # fallback to state snapshot
          blocked_tools=self._blocked_tools or [],
          clock=datetime.now(timezone.utc)
      )
      active_tools = compute_active_tools(ctx)
      state.active_tools = active_tools  # in-place mutation for compat
      return active_tools
  ```
- [ ] C.2 `tests/test_tool_rewriter.py` 断言迁移:
  - 将"就地修改 state"断言改为"`compute_active_tools` 返回值正确 + state 未被修改"
  - 示例:
    ```python
    # Before
    result = rewriter.recompute_active_tools(state)
    assert state.active_tools == expected
    
    # After
    ctx = build_runtime_context(state, metadata, blocked_tools, clock)
    result = compute_active_tools(ctx)
    assert result == expected
    assert state.active_tools == original_value  # unchanged
    ```
- [ ] C.3 新增 `test_recompute_active_tools_emits_deprecation_warning`:
  ```python
  def test_recompute_active_tools_emits_deprecation_warning():
      with pytest.warns(DeprecationWarning, match="deprecated"):
          rewriter.recompute_active_tools(state)
  ```
- [ ] C.4 运行 `pytest tests/test_tool_rewriter.py -q` 通过

### Stage D — Persisted field exclusion + grant expiry regression test

**改哪些文件**:`src/tool_governance/models/state.py`、`tests/test_state_manager.py`、`tests/test_grant_expiry_runtime_view.py`(新增)。

**不改哪些文件**:`mcp_server.py`(Stage A 已完成)、`langchain_tools.py`(Stage B 已完成)、`tool_rewriter.py`(Stage C 已完成)。

**上下文守则**:只打开 `models/state.py`、`state_manager.py`(确认 save 路径)、相关测试。

- [ ] D.1 `SessionState.DERIVED_FIELDS` 扩展:
  ```python
  # Before
  DERIVED_FIELDS: ClassVar[frozenset[str]] = frozenset({"active_tools"})
  
  # After
  DERIVED_FIELDS: ClassVar[frozenset[str]] = frozenset({"active_tools", "skills_metadata"})
  ```
- [ ] D.2 确认 `state_manager.save` 通过 `to_persisted_dict()` 排除派生字段(前序 change 已实现，本阶段仅验证)
- [ ] D.3 更新 `tests/test_state_manager.py::TestPersistedFieldContract`:
  ```python
  def test_persisted_json_excludes_derived_fields():
      # ...
      persisted = json.loads(row[1])
      assert "active_tools" not in persisted
      assert "skills_metadata" not in persisted  # NEW
  ```
- [ ] D.4 新增 `tests/test_grant_expiry_runtime_view.py`:
  ```python
  def test_expired_grant_not_in_runtime_active_tools():
      # 1. Enable skill with short TTL
      # 2. Wait for expiry
      # 3. Load state, build RuntimeContext
      # 4. Assert skill's tools not in ctx.active_tools
      # 5. Assert skills_loaded still has entry (for audit)
  ```
- [ ] D.5 运行 `pytest tests/test_state_manager.py tests/test_grant_expiry_runtime_view.py -q` 通过
- [ ] D.6 运行 `pytest -q` 全量回归

### Stage E — Spec / document alignment + closeout

**改哪些文件**:`docs/technical_design.md`(更新 "Runtime vs Persisted State" 小节)、`docs/dev_plan.md`(追加本 change 条目)、本 change 目录新增 `closeout.md`。

**不改哪些文件**:任何生产代码(应已在 Stage A-D 冻结)、`docs/requirements.md`(requirement delta 在 specs/ 下)。

**上下文守则**:只读 `docs/` 三份 md;事实从本 change 的 design / specs 取。

- [ ] E.1 运行 `pytest -q` 全量，记录 passed 数量
- [ ] E.2 运行 `openspec validate migrate-entrypoints-to-runtime-flow` 通过
- [ ] E.3 `docs/technical_design.md` · 更新 "Runtime vs Persisted State" 小节:
  - 补充"MCP / LangChain 入口已迁移到四步流程"
  - 更新 `DERIVED_FIELDS` 为 `{"active_tools", "skills_metadata"}`
  - 标注 `recompute_active_tools(state)` 为 deprecated
- [ ] E.4 `docs/dev_plan.md` · 追加本 change 的 Stage A-E 条目(完成日期、对应 commit range)
- [ ] E.5 产出 `closeout.md`:
  - 迁移清单(8 MCP + N LangChain)
  - 测试覆盖(MCP runtime flow + grant expiry regression)
  - DeprecationWarning 触发条件
  - 后续 backlog(若有)
- [ ] E.6 确认本 change **未**修改 `docs/requirements.md`(requirement 已落在 specs/ delta)
- [ ] E.7 对照 proposal §"In Scope" 与 specs/ Requirement 做自查
- [ ] E.8 产出 · 运行结果汇总表(full pytest、openspec validate、各 Stage commit hash)

## Out of Scope

显式排除以下范围:

- **不做 Redis / L3 跨实例缓存**
- **不做 StateStore / CacheStore abstraction**
- **不做 observability taxonomy 标准化**
- **不做 cache layer 重构**
- **不改 SQLite schema / grants 表 / audit_log 表**
- **不改 SKILL.md parse / SkillIndexer 实现**
- **不改 policy / blocked_tools / 任何 YAML 配置格式**
- **不改 `.mcp.json` / `hooks/hooks.json` / MCP 对外返回 shape**

## Open Questions

(无)本 change 是前序 change 的收尾工作，设计已在 `separate-runtime-and-persisted-state` 中确定。

## Success Criteria

- [ ] 8 个 MCP meta-tool 入口全部迁移到四步流程
- [ ] LangChain tool shim 全部迁移到四步流程
- [ ] `recompute_active_tools(state)` 改为 thin adapter + DeprecationWarning
- [ ] `tests/test_tool_rewriter.py` 断言迁移完成
- [ ] `tests/test_mcp_runtime_flow.py` 覆盖 8 个 MCP 入口
- [ ] `tests/test_grant_expiry_runtime_view.py` 覆盖 grant 过期场景
- [ ] `SessionState.DERIVED_FIELDS` 包含 `{"active_tools", "skills_metadata"}`
- [ ] `tests/test_state_manager.py::TestPersistedFieldContract` 断言两个派生字段均被排除
- [ ] 全量回归通过(pytest -q)
- [ ] `openspec validate` 通过
- [ ] 外部契约(MCP 返回 shape、audit event schema)零变化
