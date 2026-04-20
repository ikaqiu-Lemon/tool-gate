## Context

项目技术方案文档(`docs/technical_design.md` §3.4)承诺了**两层缓存**:metadata cache(会话级)+ document cache(进程级 LRU/TTL)。代码现状只落地了一层。

**当前 doc cache 现状**(完整形态):

- 由 `utils/cache.py::VersionedTTLCache` 承载
- 契约四件套齐全:`make_key(skill_id, version)`、`TTLCache(maxsize=100, ttl=300)`、`get`/`put`/`invalidate(key)`/`clear()`、`hits`/`misses` 计数
- 调用点:仅 `read_skill()` 路径;以 `{skill_id}::{version}` 作 key

**当前 metadata cache 现状**(退化形态):

- 承载在 `SkillIndexer` 内部私有属性 `_index: dict[str, SkillMetadata]`
- 由 `build_index()` 扫描目录后整体覆盖;`current_index()` 返回只读视图
- **无 TTL**、**无版本键**、**无 per-entry invalidate**、**无命中率观测**
- 失效路径唯一:`refresh_skills` → `build_index()`(全量重建,无法针对单 skill 失效)
- 会话级快照 `SessionState.skills_metadata` 是**另一个东西**,由 hook_handler 在 `SessionStart` 时从 indexer 拷出,独立持久化至 SQLite —— 它是状态快照,不是进程级缓存

**问题归结**:

1. 同一层"本机缓存"两种机制,读 `skill_indexer` 的人不容易意识到 metadata 也在缓存
2. `refresh_skills` 清 doc cache 走的是 `self._cache.clear()`,清 metadata 走的是 `self._index = {}` —— 行为一致,路径分裂
3. 未来任何抽象层(即使不是 Redis)都必须先处理 L2 内部的不对称,否则抽象边界不清

**约束**:

- 不改对外响应(MCP 入口、hook 入口、LangChain 入口的 return shape 全部不变)
- 不改 `SessionState` 字段 / SQLite schema / Langfuse / 策略配置
- 单进程模型不变(hook_handler 子进程每次冷启,本 change 不引入进程外共享)

## Goals / Non-Goals

**Goals**:

- metadata 与 doc 共享**一个**显式缓存契约(key / version / TTL / refresh / invalidate)
- metadata cache 从 `SkillIndexer` 的私有 dict 升级为**命名抽象**,与 doc cache 对等
- 保证 "cache 是性能层,不是真相源"—— 任一条目 miss / 失效 / 清空时,都能通过重读磁盘重建,且重建值与缓存值在下游决策中不可区分
- 变更对外零感知:回滚即回到现状,单 commit revert 即可

**Non-Goals**:

- 不引入 Redis / 进程外缓存 / 跨实例共享
- 不拆 `SessionState` 的 runtime 态与 persisted 态
- 不改 Langfuse / audit event 分类 / observability taxonomy
- 不扩 `refresh_skills` 的 MCP 返回 shape,不新增 `invalidate(skill_id)` 类 MCP 元工具
- 不改 SKILL.md 解析边界(safe_load / 100KB 上限 / description 截断)
- 不重写 docs/ 下早期 Phase 1–4 叙事,只追加本 change 的条目

## Decisions

### D1 · 两个独立的 `VersionedTTLCache` 实例,不引入新类

候选:

| 方案 | 描述 | 评价 |
|---|---|---|
| A · 两实例 | `metadata_cache` + `doc_cache` 各自 `VersionedTTLCache()` | 语义清晰、零新抽象、符合最小侵入 |
| B · 单实例 + key prefix | 一个 `VersionedTTLCache`,key 前缀 `meta::` / `doc::` | 省一份 LRU 簿记,但 key 约定需全局遵守 |
| C · 新增 `MetadataCache` / `DocCache` 子类 | 每类一个类 | 引入继承层,类型信息强但抽象过早 |

**选 A**。理由:(1) 两类缓存语义独立(value 类型不同,`SkillMetadata` vs `SkillContent`),共享一个 LRU 池会让某一类的热点驱逐另一类;(2) `VersionedTTLCache` API 表面不变,其它调用方(测试、future 脚本)不感知;(3) 回滚时仅需删除 metadata_cache 实例,不破坏 doc 侧。

### D2 · 统一 cache contract(4 维)

两个实例共享同一套契约。下表即规范面:

| 维度 | 契约 |
|---|---|
| **Key** | `f"{skill_id}::{version}"`,由 `VersionedTTLCache.make_key(skill_id, version=meta.version)` 构造;version 来源为 SKILL.md frontmatter 的 `version` 字段(沿用今日取值) |
| **Value** | metadata cache = `SkillMetadata`;doc cache = `SkillContent`。两者都是 Pydantic model,可序列化 |
| **TTL / maxsize** | 构造参数,metadata 与 doc 可独立配置。首轮默认值保持 `(maxsize=100, ttl=300)`,与现状一致,避免体感变化 |
| **Invalidate** | 三级:`invalidate(key)` 单条、`clear()` 整池、TTL / LRU 自然淘汰 |
| **Observability** | `hits` / `misses` 计数,沿用 `VersionedTTLCache` 现有字段;不新增 MCP 暴露,不进 Langfuse event 分类 |

### D3 · 分层关系

```
    ┌───────────────────────────────────────────────────┐
    │  SessionState.skills_metadata  (session snapshot) │  ← 不变
    │  序列化至 SQLite,hook 每轮 load/save              │
    └─────────────▲─────────────────────────────────────┘
                  │ hook_handler 拷贝
    ┌─────────────┴──────────────┐
    │  SkillIndexer              │  ← 本 change 重构面
    │  ┌──────────────────────┐  │
    │  │ metadata_cache       │──┼──▶ VersionedTTLCache  (新)
    │  └──────────────────────┘  │
    │  ┌──────────────────────┐  │
    │  │ doc_cache            │──┼──▶ VersionedTTLCache  (不变)
    │  └──────────────────────┘  │
    │    scan(disk) ──▶ populate │  (失败 / miss 回退路径)
    └────────────────────────────┘
```

分层职责:

- **进程级缓存(本 change)**:`metadata_cache` + `doc_cache`,生命周期 = 单个 hook_handler / MCP server 子进程
- **会话级快照(不变)**:`SessionState.skills_metadata`,由 `SessionStart` 从 indexer 读入并序列化至 SQLite
- **磁盘真相源(不变)**:`skills/**/SKILL.md`

本 change 只修改最底层框内容;上两层跨层调用的**返回形状**不变。

### D4 · 调用点迁移表

| 函数 | 现状 | 目标 |
|---|---|---|
| `SkillIndexer.build_index()` | 扫描 → 覆盖 `self._index` | 扫描 → `metadata_cache.clear()` → 逐条 `put(key, meta)` → 返回 dict |
| `SkillIndexer.current_index()` | 返回 `self._index` | 从 `metadata_cache` 聚合所有非过期条目返回 dict(形状不变) |
| `SkillIndexer.list_skills()` | 遍历 `self._index.values()` | 遍历 `metadata_cache` 当前条目,miss 时触发 `build_index()` 惰性重建 |
| `SkillIndexer.read_skill(skill_id)` | 已使用 `VersionedTTLCache`(doc) | **不变** |
| `SkillIndexer.refresh()` | `self._cache.clear()` + `self._index = {}` | `metadata_cache.clear()` + `doc_cache.clear()` + `build_index()` |
| `SkillIndexer.__init__` | 接收 `cache: VersionedTTLCache | None = None` | 接收 `metadata_cache` 与 `doc_cache` 两个可选参数,各自 `or VersionedTTLCache()` |

### D5 · Cache-is-not-truth 的落地形态

三条不变量落地为实现约束:

- **Miss 触发重建**:`list_skills` / `read_skill` 在 metadata 或 doc cache miss 时,必须走磁盘重建路径并回填缓存;不得返回空结果或抛异常让上层感知 miss
- **重建失败时返回结构化错误,不返回旧值**:若磁盘也不可读(文件删除、IO 错误),返回 `{"error": ...}` 形态(与今天 `read_skill` miss 时 `{"error": "Skill '...' not found"}` 一致),**绝不把过期缓存当作 fallback**
- **上游决策不区分 cache/disk 来源**:`policy_engine`、`tool_rewriter`、审计写入接收到的是同型 `SkillMetadata` / `SkillContent`,本 change 不加 `from_cache: bool` 之类字段

### D6 · 兼容策略

- `SkillIndexer.__init__` 保留向后兼容签名:`cache` 旧参数继续存在,若仅传 `cache` 则其被当作 `doc_cache`,`metadata_cache` 自动构造默认实例;发出 `DeprecationWarning`
- `current_index()` 保持返回 `dict[str, SkillMetadata]` 形状,消费方(hook_handler、tests)零修改
- 本 change 不改 `tests/fixtures/` 任何 SKILL.md

### D7 · 回滚策略

- **单 commit**(或小组 commit + squash)落地,回滚 = `git revert`
- **半程回滚**:若上线后发现 metadata 缓存层行为异常,可将 `SkillIndexer.__init__` 中的 `metadata_cache` 替换为一个**空实现**(`get` 永远 miss、`put` 无操作),等价于"每次走磁盘",不触发外部行为变化,仅退化性能
- **API 不外溢**:`mcp_server` / `hook_handler` / `LangChain` 入口零修改,回滚不涉及 spec 变更

## Risks / Trade-offs

- **[Risk R1] 版本失效不同步** → 缓解:`refresh()` 按 `metadata → doc` 固定顺序 `clear()`;契约测试断言两个缓存调用完毕后 `currsize == 0`
- **[Risk R2] 细粒度 invalidate 版本比较错误,返回过期 metadata** → 缓解:metadata 与 doc 共享 `make_key` 构造函数,版本来源唯一(frontmatter);单元测试覆盖版本号变化场景
- **[Risk R3] 进程冷启使 metadata cache 首次命中率低** → 说明:现状亦如此(`_index` 也在冷启时为空),本 change 不引入新损失;`docs/technical_design.md` 追加一段"进程生命周期与缓存有效性"以避免评审人误读
- **[Risk R4] 两实例导致 LRU 记账翻倍** → 评估:缓存条目是 Pydantic 模型(KB 级),maxsize=100 × 2 = 200 条峰值,内存增量可忽略;对齐 NFR §6.1 "常驻内存 < 50MB"
- **[Trade-off T1] 选 A 两实例牺牲"单一池"的整体驱逐视角**;换回的是清晰的语义边界和零新类。若未来观测到某类缓存长期不平衡,可重新考虑 B 方案
- **[Trade-off T2] 兼容旧 `cache=` 参数增加构造层歧义**;换回的是"调用方零修改"的平滑过渡。`DeprecationWarning` 作为信号面,在下一 change 完全移除

## Migration Plan

按用户指定的 5 步拆分,每步产出在该步内自成"可合并单元":

### 步骤 1 · 梳理现状与调用点

- 文档化当前 `_index` 的所有读/写点(仅 `skill_indexer.py` 内部 + `mcp_server.refresh_skills` 经 `current_index()` 读)
- 文档化当前 `VersionedTTLCache` 的所有调用点(仅 `skill_indexer.read_skill`)
- 产出:本 design 的 D4 表(已完成)
- **不改代码**

### 步骤 2 · 引入 metadata cache 抽象

- `SkillIndexer.__init__` 新增 `metadata_cache: VersionedTTLCache | None = None` 参数,默认构造独立实例
- 保留 `_index` dict 作**双写观察点**:所有 write 同时写 `_index` 与 `metadata_cache`,read 仍从 `_index` 出(影子模式)
- 测试:新增 metadata cache hit/miss/invalidate/version mismatch 四类单元测试(通过影子 cache 断言)
- **行为无变化**,仅引入并行缓存

### 步骤 3 · 统一 metadata/doc cache contract

- 确认两实例 API / 默认值 / 观测字段对齐(见 D2 表)
- `refresh()` 改为 `metadata_cache.clear()` + `doc_cache.clear()` + `build_index()`,删除 `self._index = {}` 旧路径
- 测试:`refresh_skills` 回归测试断言"两缓存均被清空"
- **`_index` 仍在,但不再被 `refresh` 写**

### 步骤 4 · 迁移现有 metadata 读取路径

- `list_skills()` / `current_index()` 改为从 `metadata_cache` 读,`_index` 删除
- `build_index()` 返回值从 `self._index = {...}` 改为 `for key, meta in scanned: metadata_cache.put(key, meta)` 后聚合返回
- 接入向后兼容签名(D6):旧 `cache=` 参数映射到 `doc_cache`,发出 `DeprecationWarning`
- 测试:`tests/test_skill_indexer.py` 补 metadata cache 版本失效路径
- **`_index` 在此步彻底移除**

### 步骤 5 · 补测试与文档

- 契约测试:`tests/test_cache.py`(若不存在则新建)补 metadata cache 与 doc cache 共享 `make_key` / `TTL` / `invalidate` / `hits` 语义的共同用例
- `tests/functional/` 零修改(对外行为未变)确认
- `docs/technical_design.md` §3.4 "两层缓存"小节重写为"统一抽象 + 两种使用场景"
- `docs/dev_plan.md` 尾部追加本 change 的条目(不改早期 Phase 叙事)
- `docs/requirements.md` §6.1 "session 内 skill 元数据缓存命中率 > 95%" KPI 无变动,但文档说明现在有真实观测点

每步完成可单独 PR;合并顺序 1 → 2 → 3 → 4 → 5,任一步出问题就地 revert,上游 PR 不阻塞。

## Open Questions

- **OQ1 · metadata cache TTL 默认值**:是否应设大于 doc cache TTL(metadata 变更频率远低于 doc 内容)?本 change 先取相同值(300s)减少体感差异,待运行观测后决定是否调整
- **OQ2 · 版本字段缺失的降级行为**:SKILL.md frontmatter 未声明 `version` 时,`make_key` fallback 到 `"unknown"`,当前所有此类 skill 共享一个缓存槽。保持现状还是本 change 加一道 warning?倾向保持现状,不扩本 change 范围
- **OQ3 · `current_index()` 的长期去留**:该方法在 phase13 hardening 引入(D3),作为 `refresh_skills` 的二次读路径。迁移到 metadata cache 后,它可改为直接返回 `metadata_cache` 的当前快照(dict 形态),也可在后续 change 中废弃。本 change 保留,不做 API 破坏
