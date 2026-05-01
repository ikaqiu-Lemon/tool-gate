## Why

当前代码里 `SessionState`(`models/state.py`)同时承担两种角色:

1. **持久态**:要跨 hook 进程 / 跨会话恢复、要进审计的字段(`skills_loaded`、`active_grants`,以及 SQLite 里的 `sessions.state_json` 快照)。
2. **当轮运行态**:`tool_rewriter.recompute_active_tools()` / `prompt_composer.compose_*()` 当轮消费的派生数据 —— `active_tools`、`skills_metadata`。

`hook_handler` 和 `mcp_server` 的每一个入口都走同一条模板:`load_or_init(sid) → mutate → save(state)`,把"从落盘 JSON rehydrate 出来的快照"直接当作当轮 runtime 输入喂给 rewriter / composer。结果:

- **`active_tools` 是派生量却被持久化**:它是 `(skills_loaded, skills_metadata, blocked_tools)` 的函数,但每轮先从 SQLite 读回旧值、再 `recompute` 覆盖、再写回。任何一个输入源(例如 `blocked_tools` 配置)变了,旧的 `active_tools` 仍会在持久 JSON 里短暂存活;跨进程首次 load 时使用者无法分辨读到的是"旧派生"还是"当轮权威"。
- **`skills_metadata` 既是 session 快照又是 rewriter 的真源**:进程级的 `SkillIndexer`(在 `formalize-cache-layers` 里刚刚补齐了 `metadata_cache` / `doc_cache`)已经是权威;但 hook 链路里仍有"持久化的 metadata 快照"这条影子路径,语义上形成两套 metadata 真源,和 cache-layer 已确立的"cache is not truth"原则互相拉扯。
- **tool/prompt rewrite 的输入边界不清**:`recompute_active_tools(state)` 就地修改 state 的语义,让"这次 rewrite 依赖的是什么"隐藏在 `SessionState` 这个大对象里,外部读代码的人看不出当轮输入只需 `(skills_loaded, 索引中的 metadata, policy/blocked)` —— 其它字段是**被顺带带着**而不是**被依赖**。
- **已归档的 `formalize-cache-layers` 的非目标之一**就是"不做 runtime/persisted state 拆分"(见其 proposal 第 30 行),它把这一块明确留给后续 change。现在正是时候。

本 change 只做**语义边界 + 最小代码重构**,目的是让"当轮执行依赖的 runtime 输入"和"用于恢复 / 审计 / 跨 hook 延续的持久态"在类型与数据流层面不再混用。

## What Changes

- **引入 RuntimeContext(暂定名,最终名 design.md 决)**:一个当轮构建、当轮消费、不落盘的数据结构,持有 `(skills_loaded_view, current_metadata, active_tools, active_grants_view, policy_snapshot)`,作为 `tool_rewriter` / `prompt_composer` 的显式输入边界。
- **收窄 `SessionState` 的"权威字段"**:
  - `skills_loaded` / `active_grants` / `session_id` / `created_at` / `updated_at` —— 继续作为持久态的真源。
  - `active_tools` —— 从"持久权威"降级为"每轮由 RuntimeContext 派生,可选地落盘仅作为审计/调试快照,不再作为任何读路径的输入"。
  - `skills_metadata` —— 从"session 持久快照"降级为"可选缓存镜像"。真源切到 `SkillIndexer`(已在 cache-layer change 中正式化);SessionState 可保留此字段以兼容历史 session,但读路径统一改为从 indexer 取。
- **规范 hook / mcp 入口流程**:每个入口显式分四步 —— (1) 加载持久态,(2) 从 `(state, indexer, policy)` 构建 RuntimeContext,(3) 仅对持久态字段做显式 mutate,(4) 保存持久态。`recompute_active_tools` 的返回值重新变为"函数结果"而非"对 state 的副作用"。
- **SQLite schema 不动**:持久形态仍是 `sessions.state_json`,仅缩窄 JSON payload 的字段集。老 session 读入时多余字段被 pydantic 容忍(`BaseModel` 默认行为),不会迁移失败。
- **测试**:`tests/test_state_manager.py`、`tests/test_tool_rewriter.py`、hook 链路相关功能测试按新边界调整;新增"RuntimeContext 不落盘"的契约测试。
- **非破坏**:`.mcp.json`、`hooks.json`、MCP 对外返回 shape、审计 event schema 全部不变。

**BREAKING(内部接口)**:`tool_rewriter.recompute_active_tools(state)` 的就地修改语义将被废弃,改为返回新的 RuntimeContext / active_tools 列表。外部调用点仅限本仓库内(`hook_handler`、`mcp_server`、`bootstrap`、测试),可在本 change 内一并迁移。对外 MCP 工具契约无变化。

### In Scope

- 新增 RuntimeContext 类型与构造路径(`core/` 目录内)
- `tool_rewriter` / `prompt_composer` 的输入从 `SessionState` 切到 RuntimeContext
- `hook_handler`(`handle_session_start` / `handle_user_prompt_submit` / `handle_pre_tool_use` / `handle_post_tool_use`)和 `mcp_server`(8 个 meta-tool)按新四步流程改写
- `SessionState` 中派生字段的"非权威"语义在代码注释 + specs 中明确
- 相关单元测试与功能测试的边界调整

### Out of Scope

显式排除以下范围,避免讨论漂移:

- **不引入 Redis / L3 跨实例缓存**(与 `formalize-cache-layers` 非目标一致)
- **不改 Langfuse / observability**(审计 event 源头、schema、上报链路全部不动)
- **不重做 cache layer**(`formalize-cache-layers` 2026-04-20 刚归档,保持其接口)
- **不做服务化 / 多实例部署**(仍是单进程 + SQLite)
- **不迁移到 LangGraph / Agent loop**(执行模型不动)
- **不改 SQLite schema、grants 表、audit_log 表**
- **不改 SKILL.md parse / SkillIndexer 实现**
- **不改 policy / blocked_tools / 任何 YAML 配置格式**

### 为什么本轮只做语义边界 + 最小代码重构

- **存储后端升级的前置条件是"持久面足够窄"**。在 `active_tools` / `skills_metadata` 还混在持久 JSON 里时,任何 L3 / 跨实例方案都得先处理这层不对称,成本白白放大。先做语义拆分,再谈后端。
- **cache-layer 已经立了"cache is not truth"的先例**。同一原则(派生量不能作为真源)在 state 层复用,收益是代码逻辑的统一,风险是局部的(只动内部接口),和做 Redis / Langfuse 改造完全不在一个量级。
- **回滚面足够小**:纯内部重构,外部契约(`.mcp.json`、hooks 返回、MCP tool shape、审计 event)零变化,`git revert` 即可复原。
- **不过度设计**:RuntimeContext 是最小抽象,不引入 state store 接口层 / 事件溯源 / CQRS 之类的通用架构。

## Capabilities

### New Capabilities

(无)本期是对已有"session-lifecycle"与"tool-surface-control"契约做边界澄清,不引入新 capability。

### Modified Capabilities

- `session-lifecycle`:明确 `SessionState` 字段的"持久权威 vs 派生快照"两类角色;持久态定义收窄到 `skills_loaded` / `active_grants` / 审计锚点;派生字段的持久化语义从"真源"降级为"可选审计快照"。
- `tool-surface-control`:`recompute_active_tools` 的契约从"就地修改 SessionState"改为"接收 RuntimeContext / 返回 active_tools 列表",明确当轮 rewrite 的输入边界。

## Impact

- **代码**:
  - `src/tool_governance/models/state.py` —— 字段注释澄清 runtime vs persisted 角色;`active_tools` / `skills_metadata` 字段标注为"派生"(字段本身为兼容历史 session 保留,读路径不再消费)
  - `src/tool_governance/core/tool_rewriter.py` —— `recompute_active_tools` 签名改造,就地修改语义废弃
  - `src/tool_governance/core/prompt_composer.py` —— 输入切到 RuntimeContext
  - `src/tool_governance/hook_handler.py` —— 4 个 handler 按新四步流程改写
  - `src/tool_governance/mcp_server.py` —— 8 个 `@mcp.tool` 按新四步流程改写
  - `src/tool_governance/core/`(新增) —— `runtime_context.py`(或合并入 `state_manager.py`,design.md 决)
- **测试**:
  - `tests/test_state_manager.py` —— 新增"持久态不含派生字段 / 派生字段读路径走 indexer"的契约用例
  - `tests/test_tool_rewriter.py` —— 签名迁移;新增"RuntimeContext 不落盘"用例
  - `tests/functional/`(hook / mcp 链路)—— 预期零对外行为变化,但内部断言点(如持久 JSON 形状)需调整
- **依赖**:不新增
- **非影响**:`.mcp.json`、`hooks/hooks.json`、`config/default_policy.yaml`、SQLite schema、grants / audit_log 表、`SkillIndexer` 及其 `metadata_cache` / `doc_cache`、Langfuse 集成、LangChain 入口

## Risks / Rollback

- **风险 R1 · 持久 JSON 字段收缩后的向后兼容**:老 session 的 `state_json` 里仍有 `active_tools` / `skills_metadata`;新代码应忽略而非报错
  - **缓解**:pydantic `BaseModel` 默认允许多余字段(Config 级确认一次);新增一条迁移契约测试:加载含历史字段的 JSON,读路径返回由 indexer 派生的值而非落盘旧值
- **风险 R2 · 忘改的读路径仍依赖 `state.active_tools`**:部分调用点可能通过属性直接访问派生字段,重构遗漏会导致"永远拿旧值"的静默错误
  - **缓解**:`state.active_tools` 在过渡期标注为 deprecated(或改 getter 返回 `None`/raise),让测试一次性定位所有调用点
- **风险 R3 · hook / mcp 入口重复的四步模板**:8 + 4 个入口手工改造容易漏一两处,出现"个别入口仍沿用旧就地修改"的异常
  - **缓解**:抽一个 `_with_runtime_context(sid, mutator)` 小工具函数承接"加载 → 构建 RuntimeContext → mutate → 保存"的固定序列;design.md 定形
- **风险 R4 · 测试边界调整的误伤**:功能测试里可能有断言直接检查持久 JSON 的 `active_tools` 字段,字段降级后会失败
  - **缓解**:在 specs 里明确"功能级断言应走 MCP 返回 / audit event,而非持久 JSON 内部字段";迁移期间给这类测试集中打补丁,并补一条注释说明为什么不再检查持久字段
- **回滚路径**:
  - 本 change 预计落在**1-2 个 commit**(RuntimeContext 引入 + hook/mcp 入口迁移)
  - 外部契约全程未变,回滚 = `git revert <commit(s)>`
  - 若中途发现 RuntimeContext 抽象不合适,可回退到"就地 mutate 但将 `recompute_active_tools` 的输出单独返回"的折中形态,不中断持久态的写路径
