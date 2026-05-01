# Example 02 - Doc Edit Staged 项目总结

**项目名称**: 样例 02 · 受控编辑:分阶段与 blocked_tools  
**完成时间**: 2026-04-30  
**状态**: ✅ 基础框架完成，⚠️ 部分功能需要修复

---

## 项目目标

创建一个演示阶段化工作流的模拟环境，展示：
1. 中风险技能的 require_reason 检查
2. 阶段化工作流（analysis → execution）
3. 全局 blocked_tools 红线
4. 完整的 Session Logging

---

## 已完成的工作

### 1. 核心脚本 ✅

**scripts/agent_realistic_simulation.py** (686 行)
- Agent 主实现，包含完整的工作流逻辑
- SessionLogger 类，实现完整的日志记录
- 支持 events.jsonl, audit_summary.md, metrics.json, state snapshots
- Agent 无感知设计，所有用户称呼改为"用户"

**scripts/skill_handlers.py** (51 行)
- yuque-doc-edit 技能的动作处理器
- 实现 append 和 preview 操作

**start_simulation.sh**
- 统一入口脚本
- 自动设置环境变量
- 运行后验证日志文件

### 2. 文档 ✅

**README.md** (424 行)
- 完整的项目框架结构说明
- 目录树和文件分类（核心/辅助/自动生成）
- 快速开始、验证命令、troubleshooting
- 预期行为和指标

**SETUP_COMPLETE.md**
- 设置完成验证清单
- 与 Example 01 的对比

### 3. Session Logging ✅

完全符合 `tool-gate/docs/session_logging_prompt.md` 规范：
- ✅ events.jsonl - JSONL 格式事件流
- ✅ audit_summary.md - Markdown 审计报告
- ✅ metrics.json - 结构化指标
- ✅ state_before.json - 会话开始状态
- ✅ state_after.json - 会话结束状态

### 4. Agent 无感知设计 ✅

- ✅ 无 "Alice" 等姓名，统一使用"用户"
- ✅ 无 "simulation"、"mock"、"demo" 等字样
- ✅ 类名为 `Agent`（不是 `SimulationAgent`）
- ✅ Session ID 格式为 `session-{timestamp}`
- ✅ 自然的对话流程和错误处理

---

## 运行结果

### 成功的部分 ✅

1. **基础流程正常**
   - list_skills → read_skill → enable_skill 流程完整
   - 第一次 enable_skill 无 reason 被拒绝
   - 第二次 enable_skill 带 reason 成功

2. **阶段白名单过滤**
   - yuque_get_doc 在 analysis 阶段成功
   - yuque_update_doc 在 analysis 阶段被拒绝
   - error_bucket 正确标记为 whitelist_violation

3. **日志记录完整**
   - 17 个事件全部记录
   - JSONL 格式正确，可以被解析
   - metrics.json 包含所有关键指标
   - audit_summary.md 格式规范

### 发现的问题 ⚠️

1. **change_stage 失败**
   - change_stage() 调用返回 success=false
   - 导致无法切换到 execution 阶段
   - 无法完成完整的阶段切换演示

2. **reason_missing 未正确记录**
   - 第一次 enable_skill 被拒绝，但 deny_reason=null
   - metrics.json 中 reason_missing_count=0
   - 应该明确记录 deny_reason="reason_missing"

3. **stage 初始值不正确**
   - enable_skill 返回 stage="unknown"
   - 应该返回 stage="analysis"（默认第一阶段）

4. **未测试 blocked_tools**
   - 由于 change_stage 失败，流程提前结束
   - 未能测试 run_command 的全局阻止功能

### 实际指标 vs 预期指标

| 指标 | 预期 | 实际 | 状态 |
|------|------|------|------|
| shown_skills | 1 | 1 | ✅ |
| read_skills | 1 | 1 | ✅ |
| enabled_skills | 1 | 1 | ✅ |
| denied_skills | 1 | 1 | ✅ |
| reason_missing_count | 1 | 0 | ❌ |
| total_tool_calls | 5 | 2 | ❌ |
| successful_tool_calls | 3 | 1 | ❌ |
| denied_tool_calls | 2 | 1 | ❌ |
| whitelist_violation_count | 1 | 1 | ✅ |
| blocked_tools_count | 1 | 0 | ❌ |
| stage_changes | 1 | 1 | ✅ |

---

## 需要修复的问题

### 优先级 P0（阻塞完整演示）

1. **修复 change_stage 功能**
   - 文件：`src/tool_governance/mcp_server.py`
   - 问题：change_stage() 调用失败
   - 影响：无法切换到 execution 阶段，无法完成完整演示
   - 建议：
     - 检查 skill 的 stages 定义
     - 检查 state_manager 中的 stage 管理逻辑
     - 添加详细的错误日志

### 优先级 P1（数据准确性）

2. **修复 reason_missing 记录**
   - 文件：`src/tool_governance/core/policy_engine.py`
   - 问题：require_reason=true 且 reason=None 时，deny_reason 为 null
   - 影响：无法准确统计 reason_missing 违规
   - 建议：明确返回 deny_reason="reason_missing"

3. **修复 stage 初始值**
   - 文件：`src/tool_governance/mcp_server.py` 或 `state_manager.py`
   - 问题：enable_skill 成功后 stage="unknown"
   - 影响：无法正确显示当前阶段
   - 建议：自动设置 stage 为 stages[0]

---

## 项目文件清单

### 核心文件（必需）
```
examples/02-doc-edit-staged/
├── start_simulation.sh              # 唯一入口
├── README.md                        # 完整文档
├── scripts/
│   ├── agent_realistic_simulation.py  # Agent 主实现
│   └── skill_handlers.py            # 技能处理器
├── skills/
│   └── yuque-doc-edit/
│       └── SKILL.md                 # 技能定义
├── config/
│   └── demo_policy.yaml             # 策略配置
├── mcp/
│   ├── mock_yuque_stdio.py          # 语雀 Mock
│   └── mock_shell_stdio.py          # Shell Mock
├── schemas/                         # JSON Schema
├── contracts/                       # 工具契约
└── .mcp.json                        # MCP 配置
```

### 自动生成文件
```
├── .demo-data/
│   ├── governance.db                # 审计数据库
│   └── session_state.json           # 会话状态
└── logs/
    └── session_{timestamp}/
        ├── events.jsonl
        ├── audit_summary.md
        ├── metrics.json
        ├── state_before.json
        └── state_after.json
```

### 报告文件
```
├── reports/
│   ├── simulation_run_report.md     # 运行报告
│   └── SUMMARY.md                   # 本文档
├── SETUP_COMPLETE.md                # 设置完成清单
└── agent_simulation_event_log.md    # 旧的事件日志（可删除）
```

---

## 与 Example 01 的对比

| 特性 | Example 01 | Example 02 |
|------|-----------|-----------|
| 风险等级 | low | medium |
| require_reason | false | true |
| 阶段化 | 无 | 有（analysis + execution） |
| 主要工具 | 只读（search, get_doc） | 读写（get_doc, update_doc） |
| blocked_tools | 无 | run_command |
| 用户请求 | 关联笔记 + 搜索论文 | 写回文档内容 |
| 运行状态 | ✅ 完全成功 | ⚠️ 部分成功 |

---

## 下一步行动

### 立即行动（修复阻塞问题）

1. **调试 change_stage 失败原因**
   ```bash
   # 检查 skill 定义
   cat skills/yuque-doc-edit/SKILL.md
   
   # 检查 MCP 服务器日志
   # 添加调试日志到 src/tool_governance/mcp_server.py
   ```

2. **修复 PolicyEngine 返回值**
   ```python
   # src/tool_governance/core/policy_engine.py
   if require_reason and not reason:
       return {
           "decision": "denied",
           "deny_reason": "reason_missing"  # 明确返回
       }
   ```

3. **修复 stage 初始化**
   ```python
   # enable_skill 成功后
   if skill.stages:
       state_manager.set_stage(skill_id, skill.stages[0].stage_id)
   ```

### 后续优化

4. **添加 run_command 测试**
   - 修复 change_stage 后
   - 在 execution 阶段尝试 run_command
   - 验证全局 blocked_tools 功能

5. **完善错误处理**
   - 添加更详细的错误日志
   - 改进 additionalContext 提示信息

6. **补充测试用例**
   - 单元测试：change_stage 功能
   - 集成测试：完整的阶段切换流程

---

## 验证清单

- [x] Python 语法检查通过
- [x] Bash 语法检查通过
- [x] README.md 包含完整框架结构
- [x] Agent 无感知设计实现
- [x] SessionLogger 实现完整
- [x] 日志文件格式正确
- [x] 基础流程可以运行
- [ ] change_stage 功能正常
- [ ] reason_missing 正确记录
- [ ] stage 初始值正确
- [ ] blocked_tools 测试通过
- [ ] 完整演示流程成功

---

## 总结

Example 02 的基础框架已经完成，包括：
- ✅ 完整的 Agent 实现和 Session Logging
- ✅ 规范的文档和项目结构
- ✅ Agent 无感知设计

但存在一些需要修复的问题：
- ❌ change_stage 功能失败
- ❌ reason_missing 未正确记录
- ❌ stage 初始值不正确

修复这些问题后，Example 02 将能够完整演示：
1. 中风险技能的 require_reason 检查
2. 阶段化工作流（analysis → execution）
3. 全局 blocked_tools 红线
4. 完整的治理决策链路

**当前状态**: 🟡 部分完成，需要修复核心功能后重新测试
