## Why

项目的三份长期文档（需求文档 v1.1、技术方案文档 v1.1、开发计划 v2.1）已完成完整的需求定义、架构设计和阶段规划，但尚未有任何代码实现。本次 change 的目标是 **将文档中定义的 V1 全部功能（F1-F12）落地为可运行的 Claude Code 插件**，覆盖开发计划中的阶段 1-4。

当前是启动实现的正确时机：三份文档已达成内部一致，Claude Code 插件规范稳定，Skill-Hub 项目经验已充分迁移到设计中。

## What Changes

### 沿用现有 docs/ 的内容（不改变）

以下内容直接沿用三份长期文档中已确定的设计，本次 change 不引入新需求或架构变更：

- **治理对象与维度**：V1 聚焦 Skills + MCP Tools，覆盖可见性/语义/资格/授权/生命周期/组合 6 个维度（需求文档 S3-S4）
- **三层架构**：Claude Code 宿主 → 插件适配层（MCP Server + Hooks + Skills）→ 治理核心层（技术方案 S2）
- **数据模型**：SkillMetadata/StageDefinition、Grant、SessionState/LoadedSkillInfo、GovernancePolicy/SkillPolicy（技术方案 S3.1）
- **8 个固定元工具**：list_skills、read_skill、enable_skill、disable_skill、grant_status、run_skill_action、change_stage、refresh_skills（技术方案 S4.5）
- **4 个 Hook 事件**：SessionStart、UserPromptSubmit、PreToolUse、PostToolUse（技术方案 S4.3）
- **核心模块划分**：skill_indexer、state_manager、policy_engine、prompt_composer、tool_rewriter、grant_manager、sqlite_store（技术方案 S3.2-S3.4）
- **技术栈**：Python 3.11+、Pydantic v2、LangChain-core、cachetools、mcp SDK、SQLite（开发计划 S1.4）
- **插件目录结构**：严格遵循 Claude Code 插件规范 + ivan-magda 模板标准（开发计划 S2）
- **4 阶段开发计划**：脚手架 → 核心逻辑 → 插件集成 → 观测与测试（开发计划 S3）
- **非功能需求**：Hook < 50ms、MCP < 100ms、缓存 > 95%、内存 < 50MB（需求文档 S6）
- **安全设计**：safe_load、文件大小限制、append-only 审计日志（技术方案 S8）

### 本次 change 新增内容

本次 change 在沿用 docs/ 设计的基础上，增加以下 **实现层面** 的具体化工作：

1. **不确定项验证与决策**：技术方案中标记的 8 项不确定项（U1-U8）需在实现中逐一验证并记录决策结果
   - U1: Hook 输入中 session_id 字段名 → 实测确认
   - U3: Windows 上 python3 命令适配 → 实现平台检测逻辑
   - U5: run_skill_action 委托机制 → V1 版本确定具体分发策略
   - U8: PreToolUse matcher 对 MCP 工具名的通配支持 → 实测确认
2. **示例技能编写**：创建 2-3 个示例 skill（如 repo-read、code-edit）用于验证端到端流程
3. **默认策略配置**：将 policy 模型实例化为 `config/default_policy.yaml`
4. **CI/测试基础设施**：pytest 配置、fixture 设计、mock 策略
5. **跨平台兼容性处理**：Windows/macOS/Linux 三端的路径、命令、环境变量差异处理

## Capabilities

### New Capabilities

- `skill-discovery`: 技能的发现、读取和索引刷新（F1 list_skills、F2 read_skill、F12 refresh_skills）。覆盖 skill_indexer 模块、SKILL.md 解析、LRU/TTL 两层缓存
- `skill-authorization`: 技能的启用、禁用和授权生命周期管理（F3 enable_skill、F4 disable_skill、F5 grant_status）。覆盖 policy_engine、grant_manager、风险等级评估、TTL/scope 回收
- `tool-surface-control`: 每轮工具面动态控制（F7 UserPromptSubmit 重写、F9 PreToolUse 拦截、F11 change_stage）。覆盖 tool_rewriter（active_tools 重算）、prompt_composer（上下文注入）、阶段切换机制。这是整个治理机制的核心控制点
- `skill-execution`: 技能动作的验证与分发执行（F6 run_skill_action）。覆盖 grant 有效性校验、allowed_ops 白名单、操作分发框架
- `session-lifecycle`: 会话级状态管理与持久化（F8 SessionStart、F10 PostToolUse）。覆盖 state_manager、sqlite_store、会话初始化/恢复、Grant 过期清理
- `audit-observability`: 结构化审计记录与观测链路（需求文档 S4.8）。覆盖 SQLite 审计日志、漏斗指标（shown/read/enable/tool/task）、误调用分桶、Langfuse trace 集成

### Modified Capabilities

（无。openspec/specs/ 中无已有 spec，均为新建）

## Impact

### 新增代码

- `src/tool_governance/` 全部模块（约 10+ Python 文件）
- `.claude-plugin/plugin.json`、`.mcp.json`、`hooks/hooks.json`
- `skills/governance/SKILL.md` + 2-3 个示例技能
- `config/default_policy.yaml`
- `tests/` 全部测试文件（约 8+ 测试文件）
- `pyproject.toml`

### 依赖引入

- 运行时：mcp>=1.2.0、pydantic>=2.0、langchain-core>=0.3、cachetools>=5.0、pyyaml>=6.0
- 可选：fastapi、uvicorn（HTTP hook）、langfuse（观测）
- 开发：pytest、pytest-asyncio、ruff、mypy

### 受影响系统

- Claude Code 宿主：通过 hooks + MCP 机制集成，不修改 Claude Code 核心
- 用户现有 hooks：插件 hooks 并行执行，治理 hook 仅做检查和状态更新，不影响用户行为
- 存储：在 `${CLAUDE_PLUGIN_DATA}` 中创建 governance.db

---

## Docs Sync Plan（变更完成后回写 docs/ 的计划）

本次 change 完成后，需将以下实现结论回写到长期文档：

| 目标文档 | 回写内容 | 原因 |
|---------|---------|------|
| `docs/技术方案文档.md` S10 | 不确定项 U1-U8 的实测结论和最终决策 | 消除设计阶段的不确定性，更新为确定的技术事实 |
| `docs/技术方案文档.md` S4.2-4.3 | `.mcp.json` 和 `hooks.json` 的实际配置（如 Windows python 适配、matcher 格式） | 实现可能与设计示例有差异 |
| `docs/开发计划.md` S3 | 各阶段的实际完成状态和偏差记录 | 跟踪计划执行情况 |
| `docs/需求文档.md` S5.1 F6 | `run_skill_action` 的最终委托机制和示例技能定义 | 消除 [不确定项] 标记 |
| `docs/技术方案文档.md` S6 | 关键流程的实测性能数据（Hook 延迟、缓存命中率） | 用实测数据替代设计估算 |
