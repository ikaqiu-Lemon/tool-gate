## Why

项目技术方案文档 (`docs/technical_design.md` §3.4) 承诺了**两层缓存**:metadata cache(session 级)+ document cache(进程级 LRU/TTL)。代码现实只兑现了一半 —— **document cache** 由 `utils/cache.py::VersionedTTLCache` 正式承载(有 version key、TTL、hit/miss 计数、统一 `invalidate`/`clear` API),**metadata cache** 却退化成 `core/skill_indexer.py` 里一个普通 `_index: dict` 私有属性:没有 TTL,没有版本键,没有命中率观测,也没有独立失效入口(只能整体 `build_index()` 重建)。

这导致:

- **L2 语义不统一**:同一层"本机缓存"出现两种机制(`VersionedTTLCache` vs 内部 dict),后续接入者在 `skill_indexer` 里读代码时看不出 metadata 也在缓存,容易误把 `_index` 当作权威索引
- **重复 IO / 重复解析无法独立治理**:要让 metadata 失效必须走 `refresh_skills` 的全量重建,没法像 doc cache 那样按版本/按键做细粒度失效
- **为未来的 cache/store abstraction 留不出干净的边界**:探索对话中已经看到 L3(跨实例共享)不是本期目标,但如果现在不把 L2 的两种缓存抽象对齐,后续任何形式的抽象层(无论是 Redis / 文件 / 其它)都要先处理 L2 内部的不对称

本 change 只做 L2 的语义补齐,不扩围到 L3。

## What Changes

- **正式引入 metadata cache**:把 `SkillIndexer` 当前内部 `_index` dict 承担的"元数据缓存"职责迁到 `VersionedTTLCache` 的第二个实例上(或通过 key prefix 隔离同一个实例,具体在 design.md 决定),让 list/metadata 读路径也经过统一缓存抽象
- **统一 L2 缓存的四项语义**(metadata + doc 共享一致契约):
  - **Key**:沿用 `skill_id::version`(`VersionedTTLCache.make_key`),metadata cache 的 value 是 `SkillMetadata`,doc cache 的 value 是 `SkillContent`
  - **TTL**:可通过 `cache.py` 构造参数配置,两类缓存可独立设值,默认 maxsize/TTL 保持当前 `VersionedTTLCache()` 的取值(maxsize=100, ttl=300)以免首轮体感变化
  - **Version 失效**:依赖 `make_key` 的版本后缀自然淘汰,旧版本条目不主动驱逐,由 TTL/LRU 兜底
  - **Invalidate/Refresh**:`refresh_skills` 一次调用同时清空 metadata 与 doc 两个缓存(不改对外行为,只收敛内部顺序);提供 `invalidate(skill_id)` 形式的单条失效入口以备未来使用,本期不暴露到 MCP meta-tool 层
- **非破坏保证**:`mcp_server` / `hook_handler` / LangChain 入口对外响应(`list_skills`、`read_skill`、`refresh_skills` 的返回 shape)**不变**;变更落在 `skill_indexer` 实现层 + `utils/cache.py` 抽象层
- **观测增量**:metadata cache 纳入 `hits`/`misses` 计数(`VersionedTTLCache` 已有),首次具备"metadata cache 命中率"这个可观测量(对齐 requirements §6.1 的"session 内 skill 元数据缓存命中率 > 95%" KPI)

### Non-Goals

显式排除以下范围,避免讨论漂移:

- **不引入 Redis**:L3 跨实例 / 跨机会话共享缓存不在本期,`skillmeta:*` / `skilldoc:*` 这类键名与分布式一致性话题一律延后
- **不改 `SessionState`**:`skills_metadata` 字段及其 SQLite 序列化格式保持原状;本 change 的 metadata cache 与 `SessionState.skills_metadata` 是两层(前者是进程级抽象,后者是 session 级快照),各自独立
- **不做 runtime/persisted state 拆分**:不引入新的"进程态 vs 持久态"概念,SQLite 仍是 state 的权威源
- **不改 Langfuse**:审计 / 观测链路不动;本 change 只新增 cache 命中率这种轻量计数器,不引入新的 observation 类型
- **不改 SOP / 配置策略**:`default_policy.yaml`、`blocked_tools`、`skill_policies` 全部保持原状

## Capabilities

### New Capabilities

(无)本期是对已承诺但未兑现的 L2 缓存语义做补齐,不引入新 capability。

### Modified Capabilities

- `skill-discovery`:缓存契约从"metadata 由 `SessionState` 承载 + doc 走 `VersionedTTLCache`"升级为"**metadata 与 doc 均通过 `VersionedTTLCache` 抽象提供统一的 key / TTL / version / invalidate 语义**,`SessionState.skills_metadata` 仍作为 session 快照,但不再兼任进程级 metadata 缓存"。这是 spec 级别的契约变更:`list_skills` 的"是否走缓存 / 如何失效 / 如何观测"在规范文本里会被明确写出,而今天的 spec 只规定了结果而没有规定缓存路径。

## Impact

- **代码**:
  - `src/tool_governance/core/skill_indexer.py` —— `_index` dict 的职责被 `VersionedTTLCache` 吸收,`list_skills()` / `current_index()` 改为走缓存;`build_index()` 语义变为"清缓存 + 扫描 + 回填",对外返回形状不变
  - `src/tool_governance/utils/cache.py` —— 可能新增 `make_metadata_key()` / 按 key prefix 区分的工厂方法,或拆为 `MetadataCache`/`DocCache` 两个类共用同一内核;具体形态交给 design.md
- **测试**:
  - `tests/test_skill_indexer.py` —— 新增 metadata cache 的 hit/miss/TTL-expire/version-mismatch 四条路径用例
  - `tests/test_cache.py`(若存在)—— 新增 metadata key 构造与 invalidate 单元测试
  - `tests/functional/` —— 预期零修改(对外行为不变)
- **文档**:
  - `docs/technical_design.md` §3.4 表格从"两层缓存"重写为"统一抽象 + 两种使用场景",说明 metadata 与 doc 共享缓存契约
  - `docs/dev_plan.md` 追加本 change 的条目(不改早期 Phase 1–4 叙事)
- **依赖**:不新增;`cachetools>=5.0` 已在 `pyproject.toml`
- **非影响**:`SessionState` 字段、SQLite schema、`hooks/hooks.json`、`.mcp.json`、`config/default_policy.yaml`、`src/tool_governance/core/observability.py`、Langfuse 集成 —— 全部不动

## Risks / Rollback

- **风险 R1 · 版本失效不同步**:`refresh_skills` 需要保证 metadata 与 doc 两个缓存**同一调用内**被清空,否则可能出现"metadata 拿到新版、doc 仍命中旧版"的不一致快照
  - **缓解**:`refresh_skills` 实现用单个 `cache.clear()`(若两类缓存共享实例)或按固定顺序 `metadata.clear()` → `doc.clear()`(若拆双实例);契约测试固化顺序
- **风险 R2 · 刷新逻辑错误**:细粒度 `invalidate(skill_id)` 引入新路径,若版本比较错误可能出现"缓存未失效 → 返回过期 metadata"的静默问题
  - **缓解**:metadata 的 cache key 沿用现有 `{skill_id}::{version}` 构造;版本自身由 `SKILL.md` frontmatter 提供,本 change 不改版本来源;单元测试覆盖版本号变化场景
- **风险 R3 · 命中率退化**:进程每次启动均为冷缓存,若 hook_handler 子进程每次新启,metadata cache 在当前架构下与 doc cache 同样吃这个"冷启"代价 —— 不是新损失,但需要在文档中说明,避免评审人把"命中率 < 95%"归因到本变更
  - **缓解**:`docs/technical_design.md` §3.4 新增一段"进程生命周期与缓存有效性"说明
- **风险 R4 · 抽象层复杂度**:两类缓存共享抽象后,`VersionedTTLCache` 的 API 表面变宽(可能新增 prefix/factory),对"最小改动"原则是个张力点
  - **缓解**:design.md 在三个方案(单实例+prefix / 双实例 / 轻包装器)间选最小表面;选型原则:优先保持现有 `get/put/invalidate/clear` 四件套不变
- **回滚路径**:
  - 本 change 预计落在**单一 commit**(或小量 commit + squash),回滚 = `git revert <commit>`
  - `skill_indexer._index` 代码删除前先降级为"若 cache 未注入则回退到内部 dict"的兼容形态,使实现层切换可逆;全部测试通过后再在下一 commit 彻底移除内部 dict
  - 对外接口(`mcp_server` / `hook_handler` 对外响应、`VersionedTTLCache` 四件套 API)全程未变,回滚不触发 spec / 行为外溢
