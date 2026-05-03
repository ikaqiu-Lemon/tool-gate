## Context

### 现状(状态流转今天怎么跑)

1. 持久化介质:`SQLiteStore` 的 `sessions` 表,一个 session 落成一条 `state_json` 记录(WAL 模式,单机单库)。
2. 内存模型:`SessionState`(pydantic)单一对象,字段 `session_id / skills_metadata / skills_loaded / active_tools / active_grants / created_at / updated_at`。
3. 入口模板:所有 hook handler(`SessionStart / UserPromptSubmit / PreToolUse / PostToolUse`)和所有 MCP meta-tool(`list_skills / read_skill / enable_skill / disable_skill / grant_status / run_skill_action / change_stage / refresh_skills`)都是同一条序列:
   - `state = state_manager.load_or_init(session_id)` — 从 SQLite 读回快照
   - 做业务逻辑,其中 `tool_rewriter.recompute_active_tools(state)` **就地修改** `state.active_tools`
   - `state_manager.save(state)` — 把整个对象序列化回 SQLite
4. rewriter 和 composer 消费的是 `SessionState` 整个对象,没有显式边界表明它们真正依赖的是 `(skills_loaded, skills_metadata, blocked_tools)` 这三个输入。
5. `formalize-cache-layers`(已于 2026-04-20 归档)已把"skill 索引"层的真源切到 `SkillIndexer._metadata_cache` / `_doc_cache`;`SessionState.skills_metadata` 实际上是一个遗留的 session 级镜像,它的"真源"身份没有被显式解除。

### 约束

- 单机 SQLite 保持不动(schema、WAL、连接模型、`SQLiteStore` API 全部不变)。
- 对外契约全部不变(`.mcp.json` / hooks JSON / MCP tool 返回 shape / 审计 event schema)。
- 不引入 Redis / StateStore 抽象 / 服务化 / 多实例。
- `SkillIndexer` 的 cache-layer 最近刚正式化,不再触碰。
- 不改 observability taxonomy、Langfuse 上报结构。

## Goals / Non-Goals

**Goals:**

- 在代码层面建立 **runtime view vs persisted record** 的显式边界:rewrite / prompt compose 只消费 runtime view;持久化只写 persisted record。
- 明确字段分类(runtime-only / persisted-only / derived-but-persistence-optional),形成字段级契约。
- 让 rewrite 从"就地修改 SessionState"改为"读 runtime view → 返回新的 active_tools"(无副作用),消除"派生字段被回写到持久化"的隐含耦合。
- 在 persisted 缺失 / 陈旧 / 带遗留字段时,以安全空视图继续运行,不崩溃、不越权。

**Non-Goals:**

- 不引入 Redis 或任何跨实例缓存 / 共享状态后端。
- 不引入通用 StateStore 接口层(把 `state_manager` 当"SQLite 门面"保留即可)。
- 不做服务化 / 多进程并发设计(当前仍是 hook 子进程 + 单 MCP server 的单机模型)。
- 不改 `SkillIndexer` / cache-layer / observability / Langfuse。
- 不引入事件溯源 / CQRS / 状态机抽象。
- 不改 SQLite schema 或 `sessions.state_json` 的反序列化入口(仅收窄它的输入 payload)。

## Decisions

### D1. Runtime view 是显式类型,不落盘

**选**:新增一个内存数据结构 `RuntimeContext`(或 `RuntimeView`,命名在实现时定稿),持有当轮 rewrite / composer 所需的全部输入的**派生视图**。它由 `(persisted SessionState, SkillIndexer 当前索引, policy/blocked_tools, 当前 clock)` 构造,不可写回 SQLite。

**不选**:给 `SessionState` 加一个 `@computed_field` 属性代替。——因为 pydantic computed field 仍会被 `model_dump_json` 导出,触不到"绝不持久化"这条边界;而且外部还是只能看到一个 `SessionState`,边界不显式。

**不选**:全局函数 `compute_active_tools(state, indexer, policy)`。——函数式写法减不了依赖,但 composer / rewriter 各自重算会有漂移;引入显式 context 对象能让"同一轮多次使用同一视图"这件事变成一次构造 + 多处读取。

### D2. 字段分类(持久面最小化)

| 字段 | 当前位置 | 分类 | 本 change 处理 |
|---|---|---|---|
| `session_id` | `SessionState` | persisted-only | 保持 |
| `created_at` / `updated_at` | `SessionState` | persisted-only(审计锚点) | 保持 |
| `skills_loaded`(每个 skill 的 `current_stage` / `last_used_at`) | `SessionState` | persisted-only(跨轮续作所需) | 保持 |
| `active_grants` | `SessionState` | persisted-only(授权续作所需) | 保持 |
| `active_tools` | `SessionState`(被回写) | **derived**(由 runtime 重算) | 不再作为任何读路径输入;是否仍序列化落盘,见 D3 |
| `skills_metadata` | `SessionState`(被回写) | **derived**(由 `SkillIndexer` 提供) | 读路径切到 indexer;字段保留兼容老 JSON,不作为权威 |
| *(RuntimeContext 所有字段)* | RuntimeContext | runtime-only | 不持久化 |

### D3. `active_tools` / `skills_metadata` 在持久 JSON 中的去留

**选 A(主路径)**:在序列化时剔除这两个字段。理由:一旦它们不再是任何读路径的输入,持久化它们就是纯冗余,还会诱导未来误读。

**选 B(兼容路径)**:暂时保留字段但显式注释"only for backward-compat inspection, never read by governance logic";后续 change 删除。

**决定**:实现中走**A**;反序列化仍然容忍这两个字段出现在历史 JSON(pydantic 默认行为,不配置 `extra="forbid"` 即可)。这样:
- 老 session 的 JSON 能被加载,多余字段被静默丢弃。
- 新写入的 JSON 不再包含这两个字段,从源头阻止漂移。
- 不需要 SQL schema 变更,也不需要迁移脚本。

### D4. rewrite / prompt compose 的调用契约

- 入口(hook handler / MCP tool)负责构造 `RuntimeContext`,然后把它传给 rewriter / composer。
- rewriter 的新签名:接收 runtime view,返回新的 `active_tools` 列表(无副作用)。调用方若需要在 runtime view 内记录,就把返回值赋回 runtime context;**不回写 SessionState**。
- composer 签名:接收 runtime view,返回字符串。
- 原来的 `recompute_active_tools(state)` 就地修改语义在本 change 内全部迁走;过渡期可保留一个 thin adapter 记为 `DeprecationWarning`,下一次 change 删除。

### D5. 持久化写回边界

入口统一四步:

1. **Load**:`state_manager.load_or_init(sid)` — 只读持久层。
2. **Derive**:`runtime = build_runtime_context(state, indexer, policy, clock)` — 纯函数,无副作用。
3. **Mutate**:仅对 `state.skills_loaded / active_grants / updated_at` 这类 persisted-only 字段做显式修改。派生值的变化**不回写**到 `state`。
4. **Save**:`state_manager.save(state)` — 只写 persisted-only 字段(得益于 D3,序列化自动剔除派生字段)。

### D6. 降级策略

| 场景 | 行为 |
|---|---|
| session 记录不存在 | 构造空 SessionState,再按四步流程走;runtime view 中 `active_tools = meta_tools ∪ ∅ − blocked` |
| 记录存在,`skills_loaded` 中的 skill 在 indexer 里找不到 | 从 runtime view 中跳过该 skill;persisted 里的条目保留(审计语义);不为未知 skill 放行任何工具 |
| 记录存在,含历史字段(`active_tools` / `skills_metadata`) | pydantic 静默丢弃;runtime view 全部由 indexer + policy 重算 |
| 记录存在,grant 已过期 | 走既有 `grant_manager.cleanup_expired` 路径(与 D5 的 Load 和 Mutate 步衔接);过期 grant 从 runtime view 中移除,从 `skills_loaded` 中移除,写回 persisted |
| `SkillIndexer` 返回空索引 | runtime view 中 `active_tools = meta_tools − blocked`(meta-tools 始终可用,governance 链路仍能自举) |
| pydantic 反序列化失败(JSON 损坏) | 沿用当前 `state_manager` 行为(抛出),hook 进程以非零退出;本 change 不改这条路径 |

**不选**:尝试"修复"损坏的持久 JSON。——修复逻辑会和真实损坏场景分歧很大,简单抛错 + Claude hook 框架的重试机制组合更安全。

## Risks / Trade-offs

- **R1 · 调用点遗漏**:8 个 MCP tool + 4 个 hook handler + `bootstrap.py` 的测试 fixture,每一处都要按新四步流程改。
  → 过渡期保留 `recompute_active_tools(state)` 的 deprecated adapter,让静态检查(mypy / pyright)在剩余调用点上能明确报 deprecation;单元测试覆盖"rewriter 不再修改 state"的反向断言。
- **R2 · 功能测试断言"持久 JSON 里有 active_tools"**:既有功能测试里若有这种断言,字段剔除后会失败。
  → 在 `tests/functional/` 里先 grep 这类断言,统一迁到"检查 MCP 返回 / audit event / runtime view"层面;迁移本身在本 change 内完成。
- **R3 · 首轮冷启性能**:之前首轮不用算 `skills_metadata`(持久 JSON 已带),改造后首轮必须走 indexer。
  → cache-layer change 已把 indexer 做成 TTL 缓存,单机进程冷启本来就要扫一次目录,不是新损失;如果出现观测回退,在 design doc 后续 iteration 补充 warm-up 策略(本轮不做)。
- **R4 · 降级被滥用**:"persisted 残缺就降级"可能掩盖真实 bug(例如 SQLite 没写成功被当成"空 session")。
  → 降级路径必须写 audit event(沿用既有 `append_audit`,新增 `state.degraded` event_type;具体 event_type 命名交给 tasks 阶段定,不属于本 design 的 observability taxonomy)。
- **R5 · RuntimeContext 设计偏轻**:它接近一个只读 dataclass,表面上看"只是把几个参数打个包",评审时可能被质疑"过度抽象"。
  → 明确它的两个不可替代作用:(a) 作为显式类型边界防止 rewriter 误碰 persisted 字段;(b) 作为未来做 L3 / 多实例时天然的"无状态 runtime 层"承载点。本 change 不展开(b)。

## Migration Plan

按用户要求拆 5 步:

### Step 1 — 梳理现状与字段分类

- 以 D2 表格为准,在 `models/state.py` 的字段注释里标注每个字段的分类(persisted-only / derived)。
- 在 `openspec/changes/separate-runtime-and-persisted-state/` 内产出本 design 已覆盖的表格即交付物;不改代码。
- 在 `tests/test_state_manager.py` 补一个"字段分类契约"测试占位(断言"SessionState 序列化后 JSON 不包含 derived 字段集合"),本步先标 skip,最后一步启用。

### Step 2 — 定义 runtime/persisted 边界

- 新增 `core/runtime_context.py`(或等价位置,实现时定):定义 `RuntimeContext` 结构 + `build_runtime_context(state, indexer, policy, clock)` 构造器。
- 该步产物是**只加不改**:不修改任何既有调用方;rewriter / composer 旧签名照旧工作。
- 单元测试:`RuntimeContext` 构造幂等性 + 从空 SessionState 构造得到"只含 meta-tools 的空视图"。

### Step 3 — 让 rewrite / compose 消费 runtime view

- `tool_rewriter.recompute_active_tools` 拆成两个签名:新的 `compute_active_tools(runtime_ctx) -> list[str]`(主路径,纯函数)+ 旧的就地修改版本降级为 thin adapter 加 `DeprecationWarning`。
- `prompt_composer.compose_*` 签名改为接收 runtime view;旧签名同样 thin adapter + warning。
- `hook_handler` / `mcp_server` 的 12 个入口逐个切换到 D5 的四步流程。
- 测试:`tests/test_tool_rewriter.py` 的"就地修改 state"断言统一改成"返回值等于预期 + state 不被修改"。

### Step 4 — 调整持久化回写边界

- `state_manager.save(state)` 的序列化路径剔除 `active_tools` / `skills_metadata` 字段(实现上可以是 `model_dump(exclude={"active_tools", "skills_metadata"})`,具体交给实现)。
- `state_manager.load_or_init` 反序列化容忍历史字段(验证 pydantic 默认不 `forbid`,必要时显式配置 `model_config = ConfigDict(extra="ignore")`)。
- 在此步之后,老 session 能读、新 session 写出的 JSON 体积更小;迁移无需脚本。

### Step 5 — 补测试与文档

- 契约测试启用(Step 1 占位):持久 JSON 不再包含 derived 字段。
- 降级路径测试:空 session / 未知 skill / 历史字段 / 索引为空 四条路径各一个用例。
- 功能测试(`tests/functional/`):审计 / hook 链路断言不动,但若有对持久 JSON 内部字段的断言按 R2 一并调整。
- `docs/technical_design.md` 同步:在 state 章节新增 "Runtime vs Persisted State" 小节,反映字段分类表格;`docs/dev_plan.md` 追加本 change 的阶段条目。本 change **不**反向写入 `docs/requirements.md`(具体 requirement 已经在 specs/ delta 中)。

**回滚**:每一步对应一个独立 commit,任一步回滚用 `git revert`。Step 4 是唯一改变持久字节的步骤:若要回滚它,`load_or_init` 路径不变,只需恢复 `save` 的序列化即可,老 session 兼容链路无需特殊处理。

## Open Questions

- **OQ1 · RuntimeContext 命名与位置**:叫 `RuntimeContext` 还是 `RuntimeView`?放 `core/runtime_context.py` 还是折进 `state_manager.py`?——交给 tasks 阶段定名;不阻塞 design 接受。
- **OQ2 · 降级 audit event 命名**:上文 R4 的 `state.degraded`(或 `state.reconstruct.degraded`)最终命名,交给 tasks 阶段与既有 audit taxonomy 对齐(既有 taxonomy 本 change 不扩围,仅复用 `append_audit` 现有接口)。
- **OQ3 · `recompute_active_tools` 旧 adapter 的清理窗口**:本 change 保留 + DeprecationWarning,下一次 change 删除 —— 时间点待项目节奏决定,不阻塞本 change 接受。
