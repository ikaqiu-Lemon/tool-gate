## Context

三份长期文档已完整定义了架构、数据模型和开发计划：

- `docs/需求文档.md` v1.1 — V1 功能 F1-F12、治理维度、验收标准
- `docs/技术方案文档.md` v1.1 — 三层架构、模块接口、数据流、安全设计
- `docs/开发计划.md` v2.1 — 4 阶段计划、Skill-Hub 映射、风险项

本 design 不重复上述已确定的架构设计，而聚焦于 **从设计到代码落地需要做出的实现决策**——特别是 docs/ 中标记为 [不确定项] 的 8 个问题，以及跨进程状态共享、平台兼容性等 docs/ 未深入展开的实现细节。

当前状态：零代码、零测试。openspec/specs/ 为空。

## Goals / Non-Goals

**Goals:**

- 将 docs/ 中 V1 全部功能（F1-F12）实现为可在 Claude Code 中加载运行的插件
- 解决 docs/ 中 8 项不确定项（U1-U8），产出确定的实现方案
- 建立可运行的端到端验证环境（MCP Server + 4 Hook + 示例技能）
- 为 6 个 capability spec 提供统一的实现策略指导

**Non-Goals:**

- 不实现 V2 功能（F13-F18：任务分类、信任管理、多环境、插件间治理、多源加载、回放评测）
- 不修改 Claude Code 宿主代码
- 不引入 Docker/容器化部署
- 不引入完整 LangChain Agent/Chain/Memory 栈（仅用 langchain-core 的 @tool 和 ChatPromptTemplate）
- 不做 HTTP hook 服务（V1 全部使用 command 类型 hook）

## Decisions

### D1: 跨进程状态共享 — SQLite WAL 模式

**问题**：Hook handler（command 类型，每次事件 spawn 新进程）和 MCP Server（长驻 stdio 进程）是两个独立进程，都需要读写 SessionState。

**决策**：SQLite + WAL（Write-Ahead Logging）模式作为共享状态存储。

**理由**：
- docs/ 已选定 SQLite（技术方案 S3.3），WAL 模式天然支持并发读 + 单写
- Hook handler 是短命进程（< 50ms），写冲突概率极低
- MCP Server 长驻进程持有连接池，Hook handler 每次打开/关闭连接
- 替代方案（文件锁、Unix socket IPC）引入额外复杂度且无明显收益

**实现要点**：
- `sqlite_store.py` 初始化时执行 `PRAGMA journal_mode=WAL`
- Hook handler 使用 `timeout=5` 秒的 busy_timeout 处理偶发写锁
- MCP Server 在工具调用前 refresh state（避免读到 hook 未提交的旧数据）

### D2: Session ID 发现策略（解决 U1）

**问题**：docs/ 标记 U1 — Hook 输入中 session_id 的字段名不确定。

**决策**：多字段探测 + 环境变量回退 + 自动生成。

**实现**：
```
优先级：input.session_id → input.sessionId → input.conversation_id
→ env CLAUDE_SESSION_ID → 基于 PID+时间戳 自动生成并写入文件标记
```

**验证计划**：阶段 3 首次加载插件时，hook_handler.py 打印实际 hook 输入 JSON 到 stderr 日志，确认真实字段名后固化代码。

### D3: Windows 平台 Python 命令适配（解决 U3）

**问题**：docs/ 标记 U3 — Windows 上 `python3` 命令可能不存在。

**决策**：使用 wrapper 脚本 + `sys.executable` 自检。

**实现**：
- `.mcp.json` 和 `hooks.json` 中统一使用 wrapper 入口：
  - Windows: `python` (由 launcher 自动路由到 py -3)
  - Unix: `python3`
- 方案：`hooks.json` 中使用条件命令，或提供 `scripts/run.sh` / `scripts/run.bat` 统一入口
- 安装时通过 `pyproject.toml` 的 `[project.scripts]` 注册 console_script `tg-hook`，使命令与平台无关

**首选方案**：console_script 入口点（`tg-hook` 和 `tg-mcp`），`.mcp.json` 和 `hooks.json` 引用入口点名而非 `python3 path/to/script.py`。这完全消除平台差异。

### D4: run_skill_action 委托机制（解决 U5）

**问题**：docs/ 标记 U5 — `run_skill_action` 的实际执行逻辑取决于技能定义。

**决策**：V1 采用 **注册式分发表 + 内置执行器**。

**设计**：
```python
# skill_executor.py (新增模块)
SKILL_HANDLERS: dict[tuple[str, str], Callable] = {}

def register_handler(skill_id: str, op: str, handler: Callable):
    SKILL_HANDLERS[(skill_id, op)] = handler

def dispatch(skill_id: str, op: str, args: dict) -> dict:
    handler = SKILL_HANDLERS.get((skill_id, op))
    if handler is None:
        return {"error": f"No handler for {skill_id}.{op}"}
    return handler(args)
```

- 示例技能的 handler 在 `src/tool_governance/skills/` 下实现
- V1 提供 2 个示例技能的内置 handler（见 D8）
- 自定义技能可通过 SKILL.md 中的 `handler_module` 字段指定 Python 模块路径（V2 考虑）

### D5: PreToolUse Matcher 与 MCP 工具名格式（解决 U8）

**问题**：docs/ 标记 U8 — MCP 工具名格式为 `mcp__<server>__<tool>`，matcher 是否支持通配。

**决策**：hooks.json 使用 `"matcher": "*"`（匹配所有工具），在 hook_handler.py 内部做精细过滤。

**理由**：
- 使用 `*` 最安全——确保所有工具调用都经过治理检查
- 精细的 matcher 格式（如 `mcp__tool-governance__*`）即使支持也不应使用，因为治理需要拦截**所有**工具
- 在 hook_handler.py 中提取 short_name：`mcp__tool-governance__list_skills` → `list_skills`
- active_tools 中存储 short_name，匹配时做归一化

### D6: 模块初始化与依赖组装

**问题**：两个入口点（hook_handler.py、mcp_server.py）各自需要完整的依赖图。

**决策**：简单工厂模式，不引入 DI 框架。

**设计**：
```python
# bootstrap.py (新增)
def create_governance_runtime(data_dir: str, skills_dir: str) -> GovernanceRuntime:
    """组装所有依赖，返回运行时实例"""
    store = SQLiteStore(data_dir)
    cache = TTLCache(maxsize=100, ttl=300)
    indexer = SkillIndexer(skills_dir, cache)
    policy = load_policy(data_dir)
    # ... 组装其余模块
    return GovernanceRuntime(store=store, indexer=indexer, ...)
```

- `GovernanceRuntime` 是一个持有所有模块引用的 facade 对象
- hook_handler.py：每次调用时创建 runtime（短命进程，开销可接受）
- mcp_server.py：进程启动时创建一次 runtime，整个生命周期复用

### D7: 示例技能设计

**目的**：提供 2-3 个示例 skill 用于端到端验证。

| 技能 ID | 风险等级 | 用途 | allowed_tools | stages |
|---------|---------|------|--------------|--------|
| `repo-read` | low | 代码阅读与搜索 | Read, Glob, Grep | 无 |
| `code-edit` | medium | 代码编辑（带阶段） | — | analysis: [Read, Glob, Grep]; execution: [Read, Edit, Write] |
| `web-search` | low | 网络搜索 | WebSearch, WebFetch | 无 |

- `code-edit` 有 stages，用于验证 `change_stage` 机制
- `repo-read` 是最简单的 skill，用于冒烟测试
- `web-search` 验证非文件类工具的治理

### D8: 测试策略

| 层级 | 范围 | 工具 | 策略 |
|------|------|------|------|
| 单元测试 | 各 core/ 模块 | pytest | Mock 文件系统和 SQLite（使用 `:memory:` 数据库） |
| 集成测试 | 多模块协作 | pytest | 真实 SQLite（临时文件），模拟 hook 输入 JSON |
| 端到端验证 | 完整插件 | 手动 | 在 Claude Code 中加载插件，执行完整 8 步链路 |

- fixtures：`conftest.py` 提供 `tmp_skills_dir`（含示例 SKILL.md）、`memory_db`、`sample_state`
- 模拟 hook 输入：将实际 hook JSON 保存为 `tests/fixtures/` 下的 JSON 文件
- 阶段 3 的端到端验证结果记录到 `docs/技术方案文档.md` 不确定项部分

### D9: LangChain 集成边界

**决策**：严格限制 LangChain 在以下场景使用，不扩展。

| 用途 | LangChain 组件 | 位置 |
|------|---------------|------|
| 元工具类型定义 | `@tool` 装饰器（langchain-core） | `src/tool_governance/tools/` |
| Prompt 模板 | `ChatPromptTemplate` | `prompt_composer.py` |

不使用：Agent、Chain、Memory、VectorStore、Retriever、Callback（V2 Langfuse 集成时再引入 CallbackHandler）。

**理由**：治理逻辑是确定性的（if-else + 查表），不需要 LLM 参与决策。LangChain 只提供工具定义标准化和 prompt 模板管理的便利。

## Risks / Trade-offs

### R1: Hook 进程启动延迟

**风险**：command 类型 hook 每次 spawn Python 进程，冷启动可能超过 50ms 目标。

**缓解**：
- 测量实际延迟，若超标则考虑：(a) 减少 import 链（延迟加载非必要模块）；(b) 使用 `__pycache__` 字节码缓存；(c) 极端情况下切换到 HTTP hook + FastAPI 常驻服务
- UserPromptSubmit 最高频（每轮触发），优先优化其代码路径

### R2: 软引导 + 硬拦截的效果不确定

**风险**：无法直接覆盖模型工具列表（Skill-Hub 的 `request.override(tools=...)` 无对应物），只能通过 additionalContext 引导 + PreToolUse deny 拦截。模型可能忽略引导。

**缓解**：
- prompt_composer 输出的引导语需经过实测调优（措辞、位置、格式）
- PreToolUse deny 作为硬底线确保安全
- 阶段 3 端到端验证时重点观察模型对引导语的遵从度

### R3: SQLite 并发写冲突

**风险**：Hook handler 和 MCP Server 同时写 SQLite 可能产生 SQLITE_BUSY。

**缓解**：WAL 模式 + busy_timeout（D1）。实测中若频繁出现，考虑读写分离（hook 只读 + MCP 写，或反之）。

### R4: 示例技能不足以覆盖全部场景

**风险**：3 个示例技能可能无法触发所有边界条件（如高风险审批、多技能并发启用）。

**缓解**：测试中使用合成的 SKILL.md fixtures 覆盖边界场景，不依赖示例技能做全量测试。

## Deltas to Sync Back to docs/

本次实现完成后，以下决策需回写到长期文档：

| 决策 | 目标文档 | 内容 |
|------|---------|------|
| D1 SQLite WAL | `docs/技术方案文档.md` S3.3 | 新增 WAL 模式和并发策略说明 |
| D2 Session ID | `docs/技术方案文档.md` S10 U1 | 替换 [不确定项] 为确定方案 |
| D3 Windows python | `docs/技术方案文档.md` S10 U3, S4.2-4.3 | console_script 方案 + 实际配置 |
| D4 run_skill_action | `docs/需求文档.md` S5.1 F6, `docs/技术方案文档.md` S10 U5 | 注册式分发表设计 |
| D5 Matcher 格式 | `docs/技术方案文档.md` S10 U8 | 确认 `*` + 内部过滤方案 |
| D6 bootstrap | `docs/技术方案文档.md` S3 | 新增 GovernanceRuntime facade 说明 |
| D7 示例技能 | `docs/开发计划.md` S3 阶段 1 | 补充示例技能定义 |
| 性能实测 | `docs/技术方案文档.md` S6 | hook 延迟、缓存命中率实测数据 |
