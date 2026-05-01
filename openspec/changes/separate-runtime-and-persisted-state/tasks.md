## 1. Stage A — 梳理现状与字段分类

**改哪些文件**:`src/tool_governance/models/state.py`(仅字段注释);`tests/test_state_manager.py`(新增占位测试,标 skip);本 change 目录下新增 `stageA_notes.md`(盘点结果)。

**不改哪些文件**:`core/tool_rewriter.py`、`core/prompt_composer.py`、`hook_handler.py`、`mcp_server.py`、`core/state_manager.py`、`storage/sqlite_store.py`、`bootstrap.py`、任何 YAML / JSON 配置。

**上下文守则**:本阶段每份源码文件**只读一次**,盘点结论直接写入 `stageA_notes.md`;后续 Stage B/C/D 以 notes 为准,不再回读源码。

- [x] 1.1 按 design §D2 表格盘点 `SessionState` 每个字段,记录"今天谁在读 / 谁在写",写入 `stageA_notes.md`
- [x] 1.2 盘点 12 个入口(4 hook + 8 MCP tool)的当前状态流转,标注每处是否做了"派生字段回写",产出入口清单到 `stageA_notes.md`
- [x] 1.3 在 `models/state.py` 每个字段上方加一行注释,标注 `persisted-only` / `derived` / `runtime-only`(仅注释,不改字段类型或默认值)
- [x] 1.4 在 `tests/test_state_manager.py` 新增 `@pytest.mark.skip(reason="enabled in Stage C")` 的契约测试占位:断言"序列化 SessionState 不包含 derived 字段集合"
- [x] 1.5 运行 `pytest -q` 确认基线通过(含新增 skip 项),记录当前测试总数到 `stageA_notes.md` 作为 Stage C/D 的对照基线
- [x] 1.6 产出 · `stageA_notes.md`(字段分类 + 入口盘点 + 基线测试计数);`models/state.py` 的分类注释 diff;`tests/test_state_manager.py` 的 skip 占位

## 2. Stage B — 引入 runtime/persisted state 边界

**改哪些文件**:新增 `src/tool_governance/core/runtime_context.py`;新增 `tests/test_runtime_context.py`。

**不改哪些文件**:任何既有调用方(`tool_rewriter.py` / `prompt_composer.py` / `hook_handler.py` / `mcp_server.py` / `bootstrap.py` / `core/state_manager.py`);`models/state.py` 字段与签名;`storage/sqlite_store.py` 与任何序列化路径;SQLite schema;配置。

**上下文守则**:只打开 `models/state.py`(仅读 Stage A 加好的分类注释)和两个新增文件;**不要**重读 hook / mcp / rewriter。

- [x] 2.1 实现 `RuntimeContext` 数据结构(按 design §D1 / OQ1:frozen dataclass 或 pydantic BaseModel,只读,无 mutator),持有 `active_tools` / `enabled_skills_view` / `policy_snapshot` / `clock` 等派生字段
- [x] 2.2 实现 `build_runtime_context(state, indexer, policy, clock) -> RuntimeContext` 纯函数:从持久态 + 当前索引 + policy 派生 runtime view;**不**修改入参,**不**写 SQLite
- [x] 2.3 单元测试 · 空 `SessionState` 构造得到"仅含 meta-tools 减 blocked_tools 的视图"
- [x] 2.4 单元测试 · 持久态引用未知 skill 时,runtime view 跳过该 skill、不授予任何工具(对齐 spec "System degrades safely" 场景)
- [x] 2.5 单元测试 · 同输入两次构造幂等(对齐 spec "Identical inputs yield equivalent runtime views")
- [x] 2.6 单元测试 · 构造结果的 `active_tools` 是 list 且与 `tool_rewriter` 旧实现在同输入下返回等价集合(回归锚点,用于 Stage C 迁移时做对照)
- [x] 2.7 运行 `pytest tests/test_runtime_context.py -q` 通过,再跑 `pytest -q` 整体回归
- [x] 2.8 产出 · 新增 `runtime_context` 模块 + 5+ 条单元测试;**不**切换任何既有调用方;Stage A 的 skip 占位测试仍保持 skip

## 3. Stage C — 迁移 rewrite 与回写主路径

本阶段按 **C1 → C2 → C3 → C4** 四段顺序提交,每段一次 commit,避免一轮打开过多文件。

---

**段 C1 · rewriter / composer 新签名**

*改*:`core/tool_rewriter.py`、`core/prompt_composer.py`、`tests/test_tool_rewriter.py`(若存在 composer 单测则一并)。
*不改*:`hook_handler.py`、`mcp_server.py`、`bootstrap.py`、`core/state_manager.py`、序列化、SQLite。
*上下文守则*:只打开 rewriter + composer + 它们的单测。

- [x] 3.1 新增 `tool_rewriter.compute_active_tools(runtime_ctx) -> list[str]` 纯函数
- [ ] 3.2 保留 `tool_rewriter.recompute_active_tools(state)` 为 thin adapter:内部委托 `compute_active_tools` 后把结果赋回 `state.active_tools`,并发出 `DeprecationWarning` *(deferred to next change / see closeout backlog #3 — gated on MCP/LangChain migration to avoid production log noise)*
- [x] 3.3 `prompt_composer.compose_context / compose_skill_catalog / compose_active_tools_prompt` 新增接收 `RuntimeContext` 的版本(纯函数);旧 `(state)` 签名保留为 thin adapter + `DeprecationWarning`
- [ ] 3.4 `tests/test_tool_rewriter.py` 将"就地修改 state"断言迁移为"`compute_active_tools` 返回值正确 + runtime_ctx / state 均未被修改" *(deferred to next change / see closeout backlog #3 — moves with the DeprecationWarning on `recompute_active_tools`)*
- [x] 3.5 运行 `pytest tests/test_tool_rewriter.py -q` 通过

---

**段 C2 · hook / mcp 入口切换到四步流程**

*改*:`hook_handler.py`(4 入口)、`mcp_server.py`(8 入口)、`bootstrap.py`(若 fixture 依赖旧签名);`tests/functional/*`(仅调整对持久 JSON 内部字段的断言,保留对外行为断言)。
*不改*:rewriter / composer 实现(C1 已定稿);`state_manager.save` 序列化边界(留到 C3);SQLite;grants;audit event schema;`.mcp.json`、`hooks/hooks.json`、policy YAML。
*上下文守则*:每次一个文件,改完即提交;实现时查阅 Stage A `stageA_notes.md` 的入口清单,不再重读整个代码库。

- [x] 3.6 `hook_handler.handle_session_start` 改四步:Load → Derive → Mutate persisted-only(`skills_loaded` / `active_grants` / `updated_at`)→ Save
- [x] 3.7 `hook_handler.handle_user_prompt_submit` 改四步
- [x] 3.8 `hook_handler.handle_pre_tool_use` 改四步(gate-check 只消费 runtime view,**不**回写 state)
- [x] 3.9 `hook_handler.handle_post_tool_use` 改四步(`last_used_at` 写入 `skills_loaded`,仍属 persisted-only)
- [ ] 3.10 `mcp_server` 的 `list_skills` / `read_skill` / `enable_skill` / `disable_skill` / `grant_status` / `run_skill_action` / `change_stage` / `refresh_skills` 逐个切四步流程 *(deferred to next change / see closeout backlog #2 — MCP / LangChain entry-point migration is explicitly out of scope for this change)*
- [x] 3.11 运行 `pytest tests/functional -q` 通过

---

**段 C3 · 持久化序列化边界**

*改*:`core/state_manager.py`(`save` 路径 exclude derived 字段;`load_or_init` 路径确认忽略历史字段);`models/state.py`(若需显式配置 `model_config = ConfigDict(extra="ignore")`);`tests/test_state_manager.py`。
*不改*:`storage/sqlite_store.py`(仅透传 JSON,不动 SQL / schema);grants 与 audit_log 表;rewriter / composer 实现;hook / mcp 入口。
*上下文守则*:只打开 state_manager + models/state + 其单测。

- [x] 3.12 `state_manager.save` 使用 `SessionState.to_persisted_dict()` 后再落盘(本轮只 exclude `active_tools`;`skills_metadata` 保留为持久字段直至 MCP / LangChain 迁移 — 见 closeout backlog #1)
- [x] 3.13 `SessionState.model_config` 显式 `extra="ignore"` 以容忍历史 JSON 中的 derived 字段 *(依赖 pydantic v2 默认行为;`test_legacy_json_with_derived_fields_loads_cleanly` 已覆盖)*
- [x] 3.14 启用 Stage A 埋下的契约测试:断言序列化 JSON 不含 `active_tools`(`skills_metadata` 仍保留,见 closeout backlog #1)
- [x] 3.15 新增兼容性测试:构造一条含 `active_tools` / `skills_metadata` 历史字段的 JSON,经 `load_or_init` 加载后,读路径(走 `build_runtime_context`)返回派生值而非落盘旧值
- [x] 3.16 运行 `pytest tests/test_state_manager.py -q` 通过

---

**段 C4 · 降级路径测试**

*改*:`tests/test_state_manager.py`、`tests/test_runtime_context.py`,必要时新增 `tests/test_degradation.py`。
*不改*:任何生产代码(C1–C3 已实现所需降级逻辑)。
*上下文守则*:只碰测试文件。

- [x] 3.17 测试 · 持久记录不存在 → runtime view 为空视图(仅 meta-tools − blocked)且继续运行
- [x] 3.18 测试 · 持久记录引用未知 skill → runtime view 跳过 + `skills_loaded` 持久条目保留以供审计
- [x] 3.19 测试 · 持久记录携带历史 derived 字段 → 被静默忽略,不影响 governance 决策
- [x] 3.20 测试 · 索引为空 → runtime view 仅含 meta-tools − blocked,不崩溃
- [ ] 3.21 测试 · grant 已过期 → `cleanup_expired` 移除后 runtime view 不再包含该 skill 的工具 *(deferred to next change / see closeout backlog #4 — existing `cleanup_expired` tests cover the semantics; a ctx-visibility regression test is follow-up work)*
- [x] 3.22 运行 `pytest -q` 全量回归,与 Stage A 记录的基线计数比对:新增用例数 ≈ 本阶段新增测试条目

## 4. Stage D — 运行、收口、文档同步

**改哪些文件**:`docs/technical_design.md`(新增 "Runtime vs Persisted State" 小节);`docs/dev_plan.md`(追加本 change 阶段条目与完成日期);本 change 目录新增 `closeout.md`。

**不改哪些文件**:任何生产代码(应已在 Stage C 冻结);`docs/requirements.md`(requirement delta 已在本 change 的 specs/ 下,归档流程统一入库);`.mcp.json`、`hooks/hooks.json`、YAML 配置;SQLite schema。

**上下文守则**:只读 `docs/` 三份 md;其余事实从 Stage A `stageA_notes.md` + 本 change 的 design / specs 取,不回读源码。

- [x] 4.1 运行 `pytest -q` 全量,记录 passed 数量,对照 Stage A 基线 + Stage B/C 新增
- [x] 4.2 运行 `openspec validate separate-runtime-and-persisted-state` 通过
- [x] 4.3 `docs/technical_design.md` · 在 state 章节追加 "Runtime vs Persisted State" 小节,搬入 design §D2 字段分类表格 + §D5 四步流程
- [x] 4.4 `docs/dev_plan.md` · 追加本 change 的 Stage A–D 条目(完成日期、对应 commit range)
- [x] 4.5 产出 `closeout.md` · 字段分类结果、12 入口迁移清单、降级场景验证结果、后续 backlog(deprecated adapter 清理时点、`RuntimeContext` 命名 OQ1、degradation audit event 命名 OQ2)
- [x] 4.6 确认本 change **未**修改 `docs/requirements.md`(requirement 已落在 specs/ delta,随 `openspec archive` 统一入库)
- [x] 4.7 对照 proposal §"In Scope" 与 specs/ 5 条 Requirement 做自查,确认每条 Requirement 有对应测试证据(引用 Stage B/C 的测试文件 + 条目)
- [x] 4.8 产出 · 运行结果汇总表(full pytest、openspec validate、各 Stage commit hash)、文档 diff 摘要
