# 样例 02 · 受控编辑:分阶段与 blocked_tools

> [!WARNING]
> **Deprecated / Legacy Example**
>
> 本样例保留用于历史参考和 pre-Stage-first 演示。它**不是** Stage-first governance 的 canonical demo。
>
> 如需了解当前 Stage-first Skill governance 流程，请从 [`examples/simulator-demo`](../simulator-demo/) 开始。
> 不建议新用户使用本样例学习 Stage-first governance。

> 本样例展示 tool-gate 在**中风险 + 需要写入**的场景下如何落地"先理解、再修改"的两阶段工作流,同时通过 `blocked_tools` 演示全局红线。

> ⚠️ **Preflight**:本 workspace **不负责**项目安装。先读 [`../QUICKSTART.md`](../QUICKSTART.md)(§1 概念 + wiring / §2 零知识安装 / §7 preflight 自检),按 §2 在**仓库根**完成一次性安装之后再回来跑本样例。workspace 目录仅负责 demo run。

---

## 快速开始

### 一键运行

```bash
cd examples/02-doc-edit-staged
./start_simulation.sh
```

### 查看日志

```bash
# 审计报告
cat logs/session_*/audit_summary.md

# 指标
cat logs/session_*/metrics.json | jq .

# 事件流
cat logs/session_*/events.jsonl
```

### 重置环境

```bash
rm -rf .demo-data logs
```

---

## 项目整体框架结构

### 完整目录树

```
examples/02-doc-edit-staged/
├── start_simulation.sh              # 【唯一入口】启动模拟
├── README.md                        # 【完整文档】本文档
├── .mcp.json                        # MCP 配置文件
│
├── scripts/                         # 脚本目录
│   ├── agent_realistic_simulation.py  # Agent 主实现
│   └── skill_handlers.py            # 技能动作处理器
│
├── skills/                          # 【活跃技能目录】当前可用的技能
│   └── yuque-doc-edit/              # 语雀文档编辑技能
│       └── SKILL.md                 # 技能定义（SOP + metadata + stages）
│
├── config/                          # 策略配置目录
│   └── demo_policy.yaml             # 演示策略（require_reason + blocked_tools）
│
├── mcp/                             # Mock MCP 服务器目录
│   ├── mock_yuque_stdio.py          # 模拟语雀 API
│   └── mock_shell_stdio.py          # 模拟 Shell 命令（混杂变量工具）
│
├── schemas/                         # JSON Schema 定义目录
│   ├── yuque_get_doc.schema.json
│   ├── yuque_list_docs.schema.json
│   ├── yuque_update_doc.schema.json
│   └── run_command.schema.json
│
├── contracts/                       # 工具契约文档目录
│   ├── yuque_tools_contract.md      # 语雀工具契约
│   └── shell_tools_contract.md      # Shell 工具契约
│
├── .demo-data/                      # 【自动生成】运行时数据目录
│   ├── governance.db                # SQLite 审计数据库
│   └── session_state.json           # 会话状态持久化
│
└── logs/                            # 【自动生成】会话日志目录
    └── session_{timestamp}/         # 每次运行生成一个会话目录
        ├── events.jsonl             # JSONL 格式事件流
        ├── audit_summary.md         # Markdown 格式审计报告
        ├── metrics.json             # JSON 格式指标汇总
        ├── state_before.json        # 会话开始时状态快照
        └── state_after.json         # 会话结束时状态快照
```

### 目录说明

#### 核心目录

| 目录 | 用途 | 说明 |
|------|------|------|
| `scripts/` | Agent 实现 | 包含 Agent 主逻辑和技能处理器 |
| `skills/` | 活跃技能 | 当前可被发现和启用的技能定义 |
| `config/` | 策略配置 | 治理策略（require_reason、blocked_tools 等） |
| `mcp/` | Mock 服务器 | 模拟外部 API 的 MCP 服务器实现 |

#### 辅助目录

| 目录 | 用途 | 说明 |
|------|------|------|
| `schemas/` | JSON Schema | 工具参数的 JSON Schema 定义（用于验证） |
| `contracts/` | 工具契约 | Mock 工具的输入输出契约文档 |

#### 自动生成目录

| 目录 | 用途 | 说明 |
|------|------|------|
| `.demo-data/` | 运行时数据 | 包含审计数据库和会话状态，运行时自动创建 |
| `logs/` | 会话日志 | 每次运行生成一个 `session_{timestamp}/` 子目录 |

---

## 0. 业务背景与展示目标

**业务背景**:样例 01 的关联报告出炉后,用户决定把"相关文档"区块**实际写回**一篇指定的文档。写回动作是中等风险,需要一个**明确的理由**(`require_reason`);并且写入前用户想先看一眼原文避免覆盖别人的新修改。

**展示目标**:
1. 证明中风险技能不带 `reason` 被拒,带上 `reason` 后进入 `analysis` 阶段
2. 证明 `analysis` 阶段只能读,不能写;只有 `change_stage("execution")` 后 `yuque_update_doc` 才可用
3. 证明 `blocked_tools` 全局红线高于任何阶段授权 —— `run_command` 无论什么时候都过不了

---

## 1. 需求点

- N1 · `yuque-doc-edit` 技能 `risk_level: medium`,策略 `require_reason: true`;不带 reason 的 `enable_skill` 直接 deny
- N2 · 启用后进入默认阶段 `analysis`,`active_tools` = `meta + yuque_get_doc + yuque_list_docs`;`yuque_update_doc` 不在其中
- N3 · `change_stage("yuque-doc-edit", "execution")` 后,`active_tools` 切换为 `meta + yuque_get_doc + yuque_update_doc`
- N4 · 全局 `blocked_tools: [run_command]`:即使第三方 `mock-shell` MCP 在 `.mcp.json` 里注册,`run_command` 任何时刻尝试都被 deny,且原因标记 `blocked`(区别于 `tool_not_available`)
- N5 · 审计表应出现 `skill.enable (denied)` → `skill.enable (granted)` → `stage.change analysis → execution` → `tool_not_available yuque_update_doc stage=analysis` → `tool.call yuque_update_doc decision=allow stage=execution` → `tool.call run_command decision=deny reason=blocked`

---

## 2. 用户请求场景

**用户请求**: "帮我把样例 01 输出的相关文档区块写回 rag-overview-v2"

**Agent 工作流程**:
1. **发现技能**: 使用 `list_skills()` 列出可用技能
2. **读取详情**: 使用 `read_skill("yuque-doc-edit")` 获取技能信息
3. **尝试启用（无 reason）**: 使用 `enable_skill()` ❌ **被拒绝（reason_missing）**
4. **重新启用（带 reason）**: 使用 `enable_skill(reason="...")` ✅ **成功，进入 analysis 阶段**
5. **读取文档**: 使用 `yuque_get_doc()` 读取原文档内容
6. **尝试写入（analysis 阶段）**: 尝试 `yuque_update_doc()` ❌ **被拒绝（不在 analysis 白名单）**
7. **检查授权状态**: 使用 `grant_status()` 确认当前阶段
8. **切换阶段**: 使用 `change_stage("execution")` 切换到执行阶段
9. **写入文档（execution 阶段）**: 使用 `yuque_update_doc()` ✅ **成功写入**
10. **尝试 shell 命令**: 尝试 `run_command()` ❌ **被拒绝（全局 blocked）**
11. **提供结果**: 总结完成的工作和受限的操作

**预期治理行为**:

| 操作 | 阶段 | 结果 | 原因 |
|------|------|------|------|
| `enable_skill` (无 reason) | - | ❌ 拒绝 | require_reason=true |
| `enable_skill` (带 reason) | - | ✅ 允许 | 进入 analysis 阶段 |
| `yuque_get_doc` | analysis | ✅ 允许 | 在 analysis 白名单中 |
| `yuque_update_doc` | analysis | ❌ 拒绝 | 不在 analysis 白名单中 |
| `change_stage("execution")` | - | ✅ 允许 | 阶段切换 |
| `yuque_update_doc` | execution | ✅ 允许 | 在 execution 白名单中 |
| `run_command` | execution | ❌ 拒绝 | 全局 blocked_tools |

---

## 3. 操作步骤详解

| 时间戳 | 操作者输入 | 模型预期动作 | 系统侧事件 |
|---|---|---|---|
| T+0s | `./start_simulation.sh` | — | `SessionStart` hook → 加载 state → `additionalContext` 注入技能目录 |
| T+3s | "帮我把样例 01 输出的相关文档区块写回 rag-overview-v2" | `list_skills()` | `UserPromptSubmit` hook → 重算 `active_tools` |
| T+9s | — | `read_skill("yuque-doc-edit")` | MCP `read_skill` 返回 SOP + stages + `risk_level: medium` |
| T+16s | — | `enable_skill("yuque-doc-edit")`（未带 reason） | `PolicyEngine.evaluate` → `require_reason=true` → deny |
| T+23s | — | `enable_skill("yuque-doc-edit", reason="...")`（带 reason） | `PolicyEngine.evaluate` → granted → 进入 analysis 阶段 |
| T+30s | — | `yuque_get_doc(doc_id="rag-overview-v2")` | `PreToolUse` allow（analysis 允许读） |
| T+37s | — | `yuque_update_doc(...)`（analysis 阶段） | `PreToolUse` deny（不在 analysis 白名单） |
| T+44s | — | `grant_status()` | 返回当前阶段和 TTL 信息 |
| T+51s | — | `change_stage("yuque-doc-edit", "execution")` | state 表更新 stage=execution，重算 active_tools |
| T+58s | — | `yuque_update_doc(...)`（execution 阶段） | `PreToolUse` allow（在 execution 白名单） |
| T+65s | — | `run_command(cmd="df -h")` | `PreToolUse` deny（全局 blocked_tools） |

---

## 4. 系统内部行为说明

- **`require_reason` 分支**:`PolicyEngine.evaluate(skill, reason=None)` 当 `skill_policies.<skill>.require_reason=true` 时,短路返回 `decision=denied, reason=reason_missing`,**不生成 grant 也不扣减 TTL**。
- **Stage 过滤**:`ToolRewriter.compute_active_tools` 会根据 `state_manager.get_stage(skill_id)` 选择对应阶段的 `allowed_tools`;默认进入技能 `stages[0]`。
- **`blocked_tools` 优先级**:策略评估顺序 = `global blocked → skill-specific policy → risk default`。因此即使某个 skill 的 `allowed_tools` 里写了 `run_command`,`ToolRewriter` 也会在最终合集前把它剔除。
- **`grant_status` 的诊断价值**:该元工具返回 `active_tools` 快照 + 每个 grant 的 TTL/stage/reason。当模型被拒时,调一次 `grant_status` 能自己回答"我现在该怎么走下一步"。

---

## 5. 预期输出与验证

### 5.1 预期指标

```json
{
  "session_id": "session-{timestamp}",
  "duration_seconds": 70.5,
  "shown_skills": 1,
  "read_skills": 1,
  "enabled_skills": 1,
  "denied_skills": 1,
  "reason_missing_count": 1,
  "total_tool_calls": 5,
  "successful_tool_calls": 3,
  "denied_tool_calls": 2,
  "tool_not_available_count": 1,
  "blocked_tools_count": 1,
  "stage_changes": 1
}
```

### 5.2 审计日志形状

```
created_at                         event                subject                                          meta
2026-04-19T11:15:00+08:00          skill.read           skill=yuque-doc-edit                             risk=medium
2026-04-19T11:15:08+08:00          skill.enable         skill=yuque-doc-edit                             decision=denied reason=reason_missing
2026-04-19T11:15:15+08:00          skill.enable         skill=yuque-doc-edit                             decision=granted stage=analysis reason="..."
2026-04-19T11:15:22+08:00          tool.call            tool=yuque_get_doc  stage=analysis               decision=allow
2026-04-19T11:16:02+08:00          tool.call            tool=yuque_update_doc  stage=analysis           decision=deny reason=tool_not_available
2026-04-19T11:16:08+08:00          stage.change         skill=yuque-doc-edit  from=analysis to=execution
2026-04-19T11:16:20+08:00          tool.call            tool=yuque_update_doc  stage=execution          decision=allow
2026-04-19T11:16:38+08:00          tool.call            tool=run_command                                 decision=deny reason=blocked
```

### 5.3 验证命令

```bash
# 验证 JSONL 格式
python3 -c "import json; [json.loads(line) for line in open('logs/session_*/events.jsonl')]"

# 验证 JSON 格式
python3 -c "import json; json.load(open('logs/session_*/metrics.json'))"

# 查看审计数据库
sqlite3 .demo-data/governance.db "SELECT * FROM audit_log ORDER BY created_at;"
```

---

## 6. Mock 工具契约速览

| 工具 | 所在 MCP | 本样例调用? | 契约详表 |
|---|---|---|---|
| `yuque_get_doc` | `mock-yuque` | ● 主业务工具(analysis + execution) | [`contracts/yuque_tools_contract.md#yuque_get_doc`](./contracts/yuque_tools_contract.md#yuque_get_doc) |
| `yuque_list_docs` | `mock-yuque` | ● 主业务工具(analysis) | [`contracts/yuque_tools_contract.md#yuque_list_docs`](./contracts/yuque_tools_contract.md#yuque_list_docs) |
| `yuque_update_doc` | `mock-yuque` | ● 主业务工具(仅 execution) | [`contracts/yuque_tools_contract.md#yuque_update_doc`](./contracts/yuque_tools_contract.md#yuque_update_doc) |
| `run_command` | `mock-shell` | ○ **混杂变量工具**,永远被 `blocked_tools` 拦截 | [`contracts/shell_tools_contract.md#run_command`](./contracts/shell_tools_contract.md#run_command) |

> ⚠️ `mock_shell_stdio.py` 是**混杂变量工具**,仅为制造真实工具混杂环境以验证 tool-gate 的拦截能力。它**不代表**本项目支持任意 shell 执行,也不是任何主业务能力。

---

## 7. 代码与测试依据

- 主链路对照实现:
  - `src/tool_governance/core/policy_engine.py` → `require_reason` 分支、`blocked_tools` 优先级
  - `src/tool_governance/core/tool_rewriter.py` → stage 过滤 + global blocked 剥离
  - `src/tool_governance/core/state_manager.py` → `change_stage` 持久化与审计
- 对照 functional tests:
  - `tests/functional/test_functional_stage.py` — `change_stage` + `stage.change` 审计
  - `tests/functional/test_functional_policy_e2e.py::E6` — `require_reason` 双分支
  - `tests/functional/test_functional_policy_e2e.py::E4` — `blocked_tools` 剥离 + PreToolUse deny

---

## 8. Session Logging 实现

本样例实现了完整的会话日志记录，符合 `tool-gate/docs/session_logging_prompt.md` 规范。

### 日志文件

每次运行生成 `logs/session_{timestamp}/` 目录，包含:

1. **events.jsonl** - JSONL 格式事件流
   - 每行一个 JSON 对象
   - 包含所有治理事件（skill.list, skill.read, skill.enable, tool.call, stage.change 等）
   - 按时间戳排序

2. **audit_summary.md** - Markdown 格式审计报告
   - 基础信息（session_id, 时间, 工作目录）
   - 用户请求
   - Skill 暴露与读取漏斗
   - 阶段切换统计
   - 工具调用统计
   - 工具调用明细表
   - 治理效果分析
   - 任务完成情况

3. **metrics.json** - 结构化指标
   - 会话时长
   - Skill 漏斗指标（shown/read/enabled/denied）
   - reason_missing 计数
   - 工具调用指标（total/successful/denied）
   - 工具不可用计数
   - 全局阻止计数
   - 阶段切换次数

4. **state_before.json** - 会话开始时状态快照
   - skills_metadata
   - skills_loaded
   - active_grants
   - 时间戳

5. **state_after.json** - 会话结束时状态快照
   - 同上结构
   - 反映会话结束时的最终状态

### 记录的事件类型

- `session.start` - 会话开始
- `skill.list` - 列出技能
- `skill.read` - 读取技能详情
- `skill.enable` - 启用技能（包含决策：granted/denied 和 deny_reason）
- `stage.change` - 阶段切换
- `tool.call` - 工具调用（包含决策：allow/deny 和 error_bucket）
- `agent.action` - Agent 动作（包含推理过程）
- `agent.deliverable` - Agent 交付物
- `session.end` - 会话结束

---

## 9. Reset 与 Troubleshooting

### 9.1 Reset(跑第二次前清理 demo 状态)

```bash
cd examples/02-doc-edit-staged/
rm -rf ./.demo-data logs
```

只删本 workspace 的 `.demo-data/` 和 `logs/`;**不要触碰** `skills/`、`mcp/`、`schemas/`、`contracts/`、`config/`、`.mcp.json` —— 它们是演示资产本身。

### 9.2 本 workspace 专属 troubleshooting

| 症状 | 根因 | 验证 | 修复 |
|---|---|---|---|
| 第一次 `enable_skill("yuque-doc-edit")` 返回 `decision=denied reason=reason_missing` | 本 workspace 策略 `require_reason: true`;中风险技能必须带 `reason` 才能启用 —— 这是**预期行为** | 读 `config/demo_policy.yaml` 中 `skill_policies.yuque-doc-edit.require_reason` | 在 `enable_skill` 的第二次调用里传 `reason="..."` 参数 |
| `change_stage("yuque-doc-edit","execution")` 之前 `yuque_update_doc` 被拒 | stage 不匹配归类 `tool_not_available`;文案会提示"stage=analysis" | 读审计日志中的 `tool.call tool_not_available yuque_update_doc stage=analysis` | 调 `change_stage("yuque-doc-edit","execution")` 后重试 |
| `run_command` 任何时候都被 deny | `run_command` 在**全局** `blocked_tools` 列表,优先级高于任何 skill 授权 —— 这是预期 | 审计日志最后一行 `tool.call run_command decision=deny reason=blocked` | 不修;`run_command` 是混杂变量工具,永不放行 |

---

## 10. 设计原则

### Agent 无感知设计

Agent 代码完全不知道自己在演示环境中运行:
- ✅ 无 "simulation"、"mock"、"demo" 等字样
- ✅ 类名为 `Agent`（不是 `SimulationAgent`）
- ✅ Session ID 格式为 `session-{timestamp}`（不是 `demo-`、`test-`）
- ✅ 所有输出消息都是自然语言（"任务完成" 而非 "模拟完成"）

### 自然交互

- 用户请求使用真实工作场景的语言
- Agent 响应就像在帮助真实用户
- 错误消息提供建设性指导
- 日志记录完整的推理过程

### 完整可观测性

- 所有治理决策都有审计记录
- 事件流可重放分析
- 指标可量化评估
- 状态快照可对比验证

---

## 11. 相关文档

- [`../QUICKSTART.md`](../QUICKSTART.md) - 项目安装和快速入门
- [`../../docs/session_logging_prompt.md`](../../docs/session_logging_prompt.md) - Session Logging 规范
- [`contracts/yuque_tools_contract.md`](./contracts/yuque_tools_contract.md) - 语雀工具契约
- [`contracts/shell_tools_contract.md`](./contracts/shell_tools_contract.md) - Shell 工具契约

---

## 附录：快速参考

### 一行命令

```bash
# 运行
./start_simulation.sh

# 查看最新日志
cat logs/session_*/audit_summary.md | tail -100

# 验证
python3 -c "import json; [json.loads(line) for line in open('logs/session_*/events.jsonl')]"

# 重置
rm -rf .demo-data logs
```

### 预期行为速查

| 操作 | 阶段 | 结果 |
|------|------|------|
| enable_skill (无 reason) | - | ❌ 拒绝 |
| enable_skill (带 reason) | - | ✅ 允许 |
| yuque_get_doc | analysis | ✅ 允许 |
| yuque_update_doc | analysis | ❌ 拒绝 |
| change_stage | - | ✅ 允许 |
| yuque_update_doc | execution | ✅ 允许 |
| run_command | execution | ❌ 拒绝 |

### 关键指标

- **shown_skills**: 1
- **read_skills**: 1
- **enabled_skills**: 1
- **denied_skills**: 1
- **reason_missing_count**: 1
- **total_tool_calls**: 5
- **successful_tool_calls**: 3
- **denied_tool_calls**: 2
- **tool_not_available_count**: 1
- **blocked_tools_count**: 1
- **stage_changes**: 1
