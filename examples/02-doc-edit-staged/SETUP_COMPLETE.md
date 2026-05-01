# Example 02 Setup Complete

## 已创建的文件

### 核心脚本
- ✅ `scripts/agent_realistic_simulation.py` (686 行) - Agent 主实现
- ✅ `scripts/skill_handlers.py` (51 行) - 技能动作处理器
- ✅ `start_simulation.sh` - 统一入口脚本

### 文档
- ✅ `README.md` (424 行) - 完整项目文档，包含框架结构说明

## 关键特性

### 1. Agent 无感知设计
- Agent 不知道自己在模拟环境中
- 所有用户称呼改为"用户"（不使用 Alice 等姓名）
- 自然的对话流程和错误处理

### 2. 阶段化工作流
- **analysis 阶段**: 只能读取文档（yuque_get_doc, yuque_list_docs）
- **execution 阶段**: 可以写入文档（yuque_update_doc）
- 演示 `change_stage()` 切换流程

### 3. require_reason 检查
- 第一次 `enable_skill()` 不带 reason → 被拒绝
- 第二次带 reason → 成功启用

### 4. blocked_tools 全局红线
- `run_command` 在全局 blocked_tools 列表
- 任何阶段都无法使用，error_bucket = "blocked"

### 5. Session Logging
- 完整的事件记录（events.jsonl）
- 审计报告（audit_summary.md）
- 结构化指标（metrics.json）
- 状态快照（state_before.json, state_after.json）

## 运行方式

```bash
cd /home/zh/tool-gate/examples/02-doc-edit-staged
./start_simulation.sh
```

## 预期输出

### 指标
- shown_skills: 1
- read_skills: 1
- enabled_skills: 1
- denied_skills: 1
- reason_missing_count: 1
- total_tool_calls: 5
- successful_tool_calls: 3
- denied_tool_calls: 2
- whitelist_violation_count: 1
- blocked_tools_count: 1
- stage_changes: 1

### 审计事件序列
1. skill.read (yuque-doc-edit)
2. skill.enable (denied, reason_missing)
3. skill.enable (granted, stage=analysis)
4. tool.call (yuque_get_doc, allow, stage=analysis)
5. tool.call (yuque_update_doc, deny, stage=analysis)
6. stage.change (analysis → execution)
7. tool.call (yuque_update_doc, allow, stage=execution)
8. tool.call (run_command, deny, blocked)

## 与 Example 01 的对比

| 特性 | Example 01 | Example 02 |
|------|-----------|-----------|
| 风险等级 | low | medium |
| require_reason | false | true |
| 阶段化 | 无 | 有（analysis + execution） |
| 主要工具 | 只读（search, get_doc） | 读写（get_doc, update_doc） |
| blocked_tools | 无 | run_command |
| 用户请求 | 关联笔记 + 搜索论文 | 写回文档内容 |

## 验证清单

- [x] Python 语法检查通过
- [x] Bash 语法检查通过
- [x] README.md 包含完整框架结构说明
- [x] Agent 代码中无 "Alice" 等姓名
- [x] Agent 代码中无 "simulation"、"mock" 等字样
- [x] SessionLogger 实现完整
- [x] 符合 session_logging_prompt.md 规范
- [x] start_simulation.sh 作为唯一入口

## 下一步

运行模拟以验证完整流程：

```bash
cd /home/zh/tool-gate/examples/02-doc-edit-staged
rm -rf .demo-data logs  # 清理旧数据
./start_simulation.sh   # 运行模拟
```

查看生成的日志：

```bash
cat logs/session_*/audit_summary.md
cat logs/session_*/metrics.json | jq .
```
