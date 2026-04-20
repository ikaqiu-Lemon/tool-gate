## 1. Stage A — 梳理现状与规划落点

**改哪些文件**:无代码改动;仅新增 `openspec/changes/formalize-cache-layers/stageA_notes.md`(本 change 内部参考,不进入 spec/docs)

**不改哪些文件**:`src/tool_governance/` 全部、`tests/` 全部、`docs/` 全部

**跑哪些命令**:
- `rg -n "_index" src/tool_governance/core/skill_indexer.py`
- `rg -n "VersionedTTLCache|skill_doc_cache" src/ tests/`
- `rg -n "build_index|current_index|read_skill|refresh_skills" src/`
- `rg -n "skills_metadata" src/ tests/`

**产出**:
- 一份 `stageA_notes.md`,记录 metadata / doc cache 所有调用点的文件:行号 + 分类(read / write / refresh / shadow snapshot)
- 确认统一 contract 的落点 = `SkillIndexer` 内部(其它模块零改动)
- 确认 `SessionState.skills_metadata` 与 `SkillIndexer._index` 无交叉写(即 session 快照路径与进程缓存路径独立)

**上下文控制**:
- 仅用 `rg` 精确搜索,不用 `Read` 打开全量文件
- 笔记文件 < 1 页;迁移表固化在 design.md D4,不在此重复
- Stage A 产出不反馈到 Stage B 的上下文(Stage B 按 design.md D4 直接动手)

- [x] 1.1 盘点 `SkillIndexer._index` 的所有读/写点并记录行号
- [x] 1.2 盘点 `VersionedTTLCache` 现有调用点(确认仅落在 `read_skill` 路径)
- [x] 1.3 盘点 `current_index()` 消费方(mcp_server、tests、hook_handler)
- [x] 1.4 确认 `SessionState.skills_metadata` 与 `SkillIndexer._index` 相互独立、无交叉写
- [x] 1.5 将 1.1–1.4 结果写入 `openspec/changes/formalize-cache-layers/stageA_notes.md`
- [x] 1.6 自检:`git diff --stat src/ tests/ docs/` 应为空(Stage A 不改主代码/测试/长期文档)

---

## 2. Stage B — 引入 metadata cache 正式抽象

**改哪些文件**:
- `src/tool_governance/core/skill_indexer.py`(构造函数新增参数 + 影子双写)
- `src/tool_governance/utils/cache.py`(若需扩 `make_key` 文档注释,纯注释)
- `tests/test_skill_indexer.py`(新增基础用例,仅增不改)

**不改哪些文件**:
- `src/tool_governance/models/` 全部、`src/tool_governance/storage/` 全部
- `src/tool_governance/mcp_server.py`、`hook_handler.py`、`tools/langchain_tools.py`、`core/observability.py`
- `tests/functional/`、`tests/test_integration.py`、`tests/test_cache.py`(若存在)此阶段不动
- `docs/` 全部(留到 Stage D)
- **不引入 Redis、不改 `SessionState`、不改 MCP 响应 shape、不改 hook 响应 shape**

**跑哪些命令**:
- `python -m pytest tests/test_skill_indexer.py -q`
- 全量:`python -m pytest -q`(断言零回归,通过数保持 Stage A 前基线,当前 167)

**产出**:
- `SkillIndexer.__init__` 接受 `metadata_cache: VersionedTTLCache | None = None`,默认构造独立实例
- 向后兼容:旧 `cache=` 位置参数映射为 `doc_cache`,发 `DeprecationWarning`
- **影子双写**:`build_index()` 内部除写 `self._index` 外,同步向 `metadata_cache` 写入 `(skill_id, version) → SkillMetadata`;读路径仍从 `_index` 出
- 测试新增:metadata cache 条目数 == `_index` 条目数、自定义 metadata_cache 实例被正确使用

**上下文控制**:
- 工作文件集 = 2 个源文件 + 1 个测试文件;不使用 `Read` 打开其它 src 文件
- 用 `Edit` 做点改,避免 `Write` 重写全文
- 新测试每条 ≤ 10 行;不复制大段 fixture
- **本阶段行为完全向前兼容**,可独立合并/回滚,不等 Stage C

- [x] 2.1 `SkillIndexer.__init__` 新增 `metadata_cache: VersionedTTLCache | None = None` 参数,默认独立实例
- [x] 2.2 `__init__` 兼容旧 `cache=` 位置参数:映射为 `doc_cache`,发 `DeprecationWarning`
- [x] 2.3 `build_index()` 内部在写入 `self._index` 的同时写 `metadata_cache`(影子双写)
- [x] 2.4 `tests/test_skill_indexer.py` 新增:build_index 后 `metadata_cache` 条目数 == `_index` 条目数
- [x] 2.5 `tests/test_skill_indexer.py` 新增:注入自定义 `metadata_cache` 时 `put`/`get` 流经其 API
- [x] 2.6 `tests/test_skill_indexer.py` 新增:`DeprecationWarning` 在旧调用形态下被触发
- [x] 2.7 跑 `python -m pytest tests/test_skill_indexer.py -q` 全绿
- [x] 2.8 跑全量 `python -m pytest -q` 通过数 ≥ Stage A 前基线(167)
- [x] 2.9 自检:`git diff --name-only` 只列出 `skill_indexer.py` / `cache.py` / `test_skill_indexer.py`

---

## 3. Stage C — 统一 contract 并迁移主路径

**改哪些文件**:
- `src/tool_governance/core/skill_indexer.py`(迁移 `list_skills` / `current_index` / `refresh` 读路径,彻底删除 `_index` 字段)
- `src/tool_governance/utils/cache.py`(如 Stage B 未改,此阶段仅扩文档注释明确 metadata/doc 共用)
- `tests/test_skill_indexer.py`(按 spec 5 条 Requirement 补齐 cache miss / version invalidation / fallback / refresh-failure 测试)
- `tests/test_cache.py`(若存在则扩,否则新建,覆盖两类缓存共享 `make_key` / TTL / `invalidate` / `hits` 语义)

**不改哪些文件**:
- `src/tool_governance/models/` / `storage/` / `mcp_server.py` / `hook_handler.py` / `tools/langchain_tools.py` / `core/observability.py`
- `tests/functional/`(对外零感知,用作回归哨兵,不增不改)
- `docs/` 全部(留到 Stage D)

**跑哪些命令**:
- `python -m pytest tests/test_skill_indexer.py tests/test_cache.py -q`
- `python -m pytest tests/functional -q`(确认对外行为未变)
- 全量:`python -m pytest -q`(断言通过数 ≥ Stage B 后基线)

**产出**:
- `SkillIndexer._index` 字段彻底移除;所有 metadata 读写走 `metadata_cache`
- `refresh()` 一次调用清空 `metadata_cache` + `doc_cache` 再 `build_index()`
- 测试覆盖 spec 要求的 5 条 Requirement 全部关键场景(含 "version bump 后旧 metadata 不命中"、"refresh failure 返回结构化错误")

**上下文控制**:
- 工作文件集与 Stage B 同族(skill_indexer + cache + 两个测试文件),无新开文件
- `_index` 字段的移除作为**单次 Edit 成组删除**,避免多轮迭代累积上下文
- 测试按 spec 场景一一对应,每条 ≤ 15 行;重用 Stage B 已有 fixture
- 每条新测试的 `#### Scenario` 名称直接映射到 spec 文件行,方便 reviewer 对照,不需要我再写额外说明

- [ ] 3.1 `list_skills()` 改为从 `metadata_cache` 读当前非过期条目
- [ ] 3.2 `current_index()` 改为从 `metadata_cache` 聚合返回(返回形状 `dict[str, SkillMetadata]` 不变)
- [ ] 3.3 `refresh()` 改为 `metadata_cache.clear()` + `doc_cache.clear()` + `build_index()`,删除 `self._index = {}`
- [ ] 3.4 `build_index()` 内部移除对 `self._index` 的写入,仅写 `metadata_cache`
- [ ] 3.5 从 `SkillIndexer` 类彻底删除 `self._index` 属性定义
- [ ] 3.6 测试 · cache miss 路径:条目缺失时自动磁盘重建并回填(spec "Cache miss triggers a clean rebuild")
- [ ] 3.7 测试 · metadata version bump:frontmatter version 递增后旧条目不再命中(spec "Version bump supersedes a cached metadata entry")
- [ ] 3.8 测试 · doc version bump:SKILL.md 正文变化 + version 递增后旧 doc 条目不再命中(spec "Version bump supersedes a cached document")
- [ ] 3.9 测试 · 整池 clear 后 list / read 结果与带缓存路径 content-identical(spec "Cached and rebuilt values are interchangeable")
- [ ] 3.10 测试 · refresh 后 `metadata_cache.currsize == 0` 且 `doc_cache.currsize == 0`(spec "Refresh skills index" / "Metadata and document entries honor a common invalidation surface")
- [ ] 3.11 测试 · refresh 失败场景:文件不可读时返回结构化错误,不返回过期缓存(spec "Refresh failure degrades safely")
- [ ] 3.12 跑 `python -m pytest tests/test_skill_indexer.py tests/test_cache.py -q` 全绿
- [ ] 3.13 跑 `python -m pytest tests/functional -q` 零回归(外部行为未变)
- [ ] 3.14 跑全量 `python -m pytest -q`,记录最终通过数

---

## 4. Stage D — 运行、收口、文档同步

**改哪些文件**:
- `docs/technical_design.md` §3.4(表格改写为"统一 cache contract + 两种使用场景")
- `docs/dev_plan.md` 尾部(追加 "Cache Layer Formalization" 条目,标记完成日期)
- `docs/技术方案文档.md`(若存在且包含 §3.4 镜像段,同步;不存在则跳过)
- `openspec/changes/formalize-cache-layers/closeout.md`(新建,记录摘要 + 测试数 + 后续 backlog)

**不改哪些文件**:
- `src/tool_governance/` 全部(Stage D 不碰代码)
- `tests/` 全部(Stage C 已定型,Stage D 不再改测试)
- `docs/requirements.md`(F2 已描述 LRU/TTL 缓存,行为未变,不动)
- `docs/需求文档.md`(同 requirements,不动)
- `openspec/specs/`(spec 修订在 archive 阶段由 `/opsx:archive` 完成,本 change 不直接改 `openspec/specs/skill-discovery/spec.md`)

**跑哪些命令**:
- `python -m pytest -q`(最终一次全量,数字写进 closeout)
- `openspec validate formalize-cache-layers`
- 可选:`ruff check src/ tests/` + `mypy src/`(若 CI 有此关卡)

**产出**:
- `docs/technical_design.md` §3.4 更新:从"两层缓存表格"改为"统一 contract + 两种使用",新增"进程生命周期与缓存有效性"小段(应对 design.md R3)
- `docs/dev_plan.md` 尾部小节记录本 change 的 Stage A–D 完成日期
- `closeout.md` 内容:变更摘要、测试套数与通过率、命中率观测点、遗留 backlog(design.md OQ1 / OQ2 / OQ3 各一行)
- 可直接 `/opsx:archive` 的干净状态

**上下文控制**:
- 仅打开需要修改的 doc 章节(`§3.4` 局部 + dev_plan 尾部),不读 full docs
- `closeout.md` 限长 ≤ 60 行,沿用 phase13-hardening closeout 的简洁格式
- 不触发全量回归重跑 > 1 次;相信 Stage C 的 3.14 结果
- Stage D 做完即本 change 完成,无需保留任何 Stage 间上下文

- [ ] 4.1 更新 `docs/technical_design.md` §3.4 表格:"两层缓存" → "统一 cache contract + 两种使用场景"
- [ ] 4.2 在 `docs/technical_design.md` §3.4 末尾追加"进程生命周期与缓存有效性"小段(对应 design.md Risk R3)
- [ ] 4.3 检查并同步中文镜像 `docs/技术方案文档.md` §3.4(若存在)
- [ ] 4.4 `docs/dev_plan.md` 尾部新增 "Cache Layer Formalization (formalize-cache-layers)" 小节,标记 Stage A–D 完成日期
- [ ] 4.5 确认 `docs/requirements.md` §6.1 和 §5.1 F2 无需改动(行为未变)
- [ ] 4.6 跑最终全量 `python -m pytest -q`,记录套数与通过率
- [ ] 4.7 跑 `openspec validate formalize-cache-layers` 通过
- [ ] 4.8 产出 `openspec/changes/formalize-cache-layers/closeout.md`:摘要 + 测试套数 + 命中率观测 + 后续 backlog(OQ1 metadata TTL 默认值、OQ2 version 字段缺失降级、OQ3 `current_index()` 长期去留)
- [ ] 4.9 自检:`git diff --stat src/ tests/` 为空(Stage D 零代码改动);`git diff --stat docs/` 仅覆盖 `technical_design.md` / `dev_plan.md` / 镜像文件
- [ ] 4.10 本 change 准备 archive:运行 `/opsx:archive formalize-cache-layers`(不在本文件执行,由用户决策触发)
