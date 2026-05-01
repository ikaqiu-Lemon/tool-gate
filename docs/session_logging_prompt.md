# Session Logging Prompt for Tool-Gate Project

**日志保存路径**: `/home/zh/tool-gate/examples/01-knowledge-link/logs`

**目标**: 在 tool-governance 中间件的会话生命周期内，自动记录治理事件，并在会话结束后生成结构化日志文件，便于复盘、评测、审计和项目展示。

---

## 核心理解

本项目是一个 **工具治理中间件**，而非独立的 Agent 运行时。它通过 Hook 机制拦截 Claude 的工具调用，执行白名单校验、Policy 评估、Grant 管理等治理逻辑。

### 关键架构特征

**Hook 层**: 
- `SessionStart` - 会话初始化
- `UserPromptSubmit` - 用户提示提交
- `PreToolUse` - 工具调用前检查
- `PostToolUse` - 工具调用后处理

**MCP 层**: 
- `list_skills` - 列出可用技能
- `read_skill` - 读取技能详情
- `enable_skill` - 启用技能
- `run_skill_action` - 执行技能操作

**存储层**: 
- `SQLiteStore.append_audit()` 已记录事件到 `audit_log` 表

**运行时**: 
- `RuntimeContext` 动态计算 `active_tools`
- `SessionState` 持久化 `skills_loaded` 和 `active_grants`

### 现有能力

- ✅ SQLite audit_log 表记录所有治理事件
- ✅ `funnel_counts()` 提供 shown/read/enable/tool_calls 统计
- ✅ LangfuseTracer 可选集成（通过环境变量启用）
- ✅ RuntimeContext 提供 active_tools 推导逻辑

### 缺失能力

- ❌ 无会话结束后的结构化日志导出
- ❌ 无 JSONL 事件流文件
- ❌ 无 Markdown 审计报告生成
- ❌ 无 metrics.json 指标汇总

---

## 实现方案

### 1. 新增日志记录模块

**文件**: `src/tool_governance/core/session_logger.py`

实现一个 `SessionLogger` 类，职责:
- 在 Hook 事件触发时记录关键信息（复用现有 `append_audit` 调用）
- 在会话结束时从 SQLite `audit_log` 表读取事件
- 生成以下文件到指定目录:
  - `session_{session_id}_events.jsonl` — 事件流
  - `session_{session_id}_audit.md` — 可读审计报告
  - `session_{session_id}_metrics.json` — 结构化指标
  - `session_{session_id}_state_before.json` — 会话开始时状态快照
  - `session_{session_id}_state_after.json` — 会话结束时状态快照

**设计原则**:
- **最小侵入**: 不修改 Hook 处理逻辑，只在现有 `append_audit` 调用后添加内存缓存
- **失败降级**: 日志写入失败时记录 warning，不影响主流程
- **可选启用**: 通过环境变量 `GOVERNANCE_LOG_DIR` 控制是否启用文件日志

---

### 2. 日志保存路径

**环境变量**: `GOVERNANCE_LOG_DIR=/home/zh/tool-gate/examples/01-knowledge-link/logs`

**目录结构**:
```
logs/
├── session_{session_id}/
│   ├── events.jsonl
│   ├── audit_summary.md
│   ├── metrics.json
│   ├── state_before.json
│   └── state_after.json
```

**文件命名规则**:
- 使用 `session_id` 作为子目录名（避免覆盖历史日志）
- 如果 `session_id` 是自动生成的 `auto-{pid}-{timestamp}`，保持原样
- 目录不存在时自动创建（`mkdir -p`）

---

### 3. 记录基础会话信息

**在 `SessionStart` 时记录**:
```python
{
  "session_id": str,
  "agent_id": None,  # 本项目无独立 agent_id
  "trace_id": str | None,  # 从 Langfuse tracer 获取（如果启用）
  "user_id": None,  # 当前未实现
  "tenant_id": None,  # 当前未实现
  "user_role": None,  # 当前未实现
  "original_request": None,  # Hook 层无法获取原始用户请求
  "start_time": datetime.utcnow().isoformat(),
  "model": None,  # Hook 层无法获取模型信息
  "working_directory": os.getcwd(),
  "environment": {
    "GOVERNANCE_DATA_DIR": str,
    "GOVERNANCE_SKILLS_DIR": str,
    "GOVERNANCE_CONFIG_DIR": str,
    "LANGFUSE_PUBLIC_KEY": "***" if set else None
  },
  "skill_hub_version": None,  # 可从 package 版本读取
  "policy_version": policy.model_dump() if available
}
```

**在会话结束时记录**:
```python
{
  "end_time": datetime.utcnow().isoformat(),
  "duration_seconds": float
}
```

---

### 4. 记录任务目标与边界

**限制**: Hook 层无法直接获取用户原始请求或 Agent 任务规划。

**可记录信息**:
- 从 `audit_log` 推断任务特征:
  - 是否涉及外部搜索: 检查是否有 `web_search` / `rag_paper_search` 等工具调用
  - 是否涉及写文件: 检查是否有 `yuque_update_doc` / `Write` 等工具调用
  - 是否涉及高风险工具: 检查 `risk_level=high` 的 Skill 是否被启用
  - 是否涉及多 Skill 协作: 统计 `enable` 事件数量

**输出格式** (在 Markdown 报告中):
```markdown
## 任务特征推断

- 启用的 Skills: yuque-knowledge-link
- 调用的工具: yuque_search, yuque_get_doc (3次)
- 被拒绝的工具: rag_paper_search, yuque_update_doc
- 涉及外部搜索: 是（尝试但被拒绝）
- 涉及写操作: 否
- 涉及高风险工具: 否
- 多 Skill 协作: 否（仅 1 个 Skill）
```


---

### 5. 记录 Skill 暴露与读取过程

**数据来源**: `audit_log` 表中的 `skill.list` 和 `skill.read` 事件

**记录字段**:
```python
{
  "event_type": "skill.list",
  "timestamp": str,
  "session_id": str,
  "shown_skills": [
    {
      "skill_id": str,
      "name": str,
      "description": str[:100],  # 截断
      "risk_level": str,
      "allowed_tools_count": int,
      "version": str
    }
  ]
}

{
  "event_type": "skill.read",
  "timestamp": str,
  "session_id": str,
  "skill_id": str,
  "cache_hit": bool,  # 从 SkillIndexer.doc_cache 判断
  "content_length": int,
  "read_duration_ms": float | None
}
```

**漏斗分析** (在 Markdown 报告中):
```markdown
## Skill 暴露与读取漏斗

| 阶段 | 数量 | 转化率 |
|------|------|--------|
| shown (list_skills) | 5 | 100% |
| read (read_skill) | 1 | 20% |
| enabled (enable_skill) | 1 | 100% |

**分析**:
- 展示了 5 个 Skills，但只读取了 1 个（yuque-knowledge-link）
- 读取后立即启用，转化率 100%
- 未读取的 Skills: skill-a, skill-b, skill-c, skill-d
```

---

### 6. 记录 Skill 启用与授权过程

**数据来源**: `audit_log` 表中的 `skill.enable` 事件 + `SessionState.skills_loaded` + `SessionState.active_grants`

**记录字段**:
```python
{
  "event_type": "skill.enable",
  "timestamp": str,
  "session_id": str,
  "skill_id": str,
  "decision": "granted" | "denied",
  "deny_reason": str | None,
  "risk_level": str,
  "policy_evaluation": {
    "auto_grant": bool,
    "requires_approval": bool
  },
  "before_state": {
    "skills_loaded": list[str],
    "active_tools_count": int
  },
  "after_state": {
    "skills_loaded": list[str],
    "active_tools_count": int,
    "new_tools": list[str]
  },
  "grant_info": {
    "grant_id": str,
    "ttl_seconds": int,
    "expires_at": str,
    "allowed_ops": list[str]
  }
}
```

**治理检查** (在 Markdown 报告中):
```markdown
## Skill 启用与授权

### enable_skill('yuque-knowledge-link')
- **时间**: 2026-04-29T07:36:15+08:00
- **决策**: granted (auto, risk=low)
- **Grant ID**: grant-abc123
- **TTL**: 3600s (expires at 2026-04-29T08:36:15+08:00)
- **Allowed Ops**: ["read", "search"]
- **Allowed Tools**: yuque_search, yuque_list_docs, yuque_get_doc
- **Active Tools 变化**: 0 → 3 (+3)

**治理检查**:
- ✅ 遵守先 read 再 enable 流程
- ✅ allowed_tools 与 active_tools 对齐
- ✅ 无未授权工具暴露
```


---

### 7. 记录 active_tools 重算过程

**数据来源**: `RuntimeContext.active_tools` 在每次 Hook 调用时重算

**实现方式**: 在 `hook_handler.py` 的 `_build_runtime_ctx` 调用后，记录 `active_tools` 快照

**记录字段**:
```python
{
  "event_type": "active_tools.recompute",
  "timestamp": str,
  "session_id": str,
  "hook_event": "SessionStart" | "UserPromptSubmit",
  "skills_loaded": list[str],
  "active_tools": list[str],
  "active_tools_count": int,
  "delta": {
    "added": list[str],
    "removed": list[str]
  },
  "trigger_reason": "session_start" | "prompt_submit" | "skill_enabled" | "grant_expired"
}
```

**收敛效果** (在 Markdown 报告中):
```markdown
## active_tools 重算与工具可见性

| 时间点 | Hook 事件 | skills_loaded | active_tools 数量 | 变化 |
|--------|-----------|---------------|-------------------|------|
| 07:36:00 | SessionStart | [] | 0 | 初始状态 |
| 07:36:15 | (enable_skill) | [yuque-knowledge-link] | 3 | +3 (yuque_search, yuque_list_docs, yuque_get_doc) |
| 07:36:20 | UserPromptSubmit | [yuque-knowledge-link] | 3 | 无变化 |

**工具集收敛效果**:
- 全量工具数（所有 Skills）: 50+
- 本会话实际暴露工具数: 3
- 工具集收敛比例: 94%
- 白名单外工具暴露: 0
```

---

### 8. 记录工具调用明细与治理判定

**数据来源**: `audit_log` 表中的 `tool.call` 事件

**记录字段**:
```python
{
  "event_type": "tool.call",
  "timestamp": str,
  "session_id": str,
  "tool_name": str,
  "tool_short_name": str,  # 提取 mcp__xxx__yyy → yyy
  "decision": "allow" | "deny" | "error",
  "error_bucket": "whitelist_violation" | "wrong_skill_tool" | "parameter_error" | None,
  "deny_reason": str | None,
  "owning_skill": str | None,  # 从 RuntimeContext 推断
  "in_active_tools": bool,
  "in_allowed_tools": bool,
  "duration_ms": float | None,  # 从 PreToolUse 到 PostToolUse 的时间差
  "retry_count": 0,  # 当前未实现 retry 机制
  "tool_input_summary": str,  # 脱敏后的参数摘要
  "tool_output_summary": str | None  # 脱敏后的结果摘要
}
```

**error_bucket 分类**:
- `whitelist_violation`: 工具不在当前 active_tools 中
- `wrong_skill_tool`: 工具属于某个 Skill，但该 Skill 未启用
- `parameter_error`: 工具执行失败（从 PostToolUse 的 `_is_error_response` 判断）

**治理判定** (在 Markdown 报告中):
```markdown
## 工具调用明细与治理判定

| # | 时间 | 工具 | 决策 | Error Bucket | 说明 |
|---|------|------|------|--------------|------|
| 1 | 07:36:20 | yuque_search | allow | - | ✅ 在白名单内 |
| 2 | 07:36:25 | yuque_list_docs | allow | - | ✅ 在白名单内 |
| 3 | 07:36:30 | yuque_get_doc | allow | - | ✅ 在白名单内 |
| 4 | 07:36:40 | yuque_get_doc | allow | - | ✅ 在白名单内 |
| 5 | 07:36:50 | yuque_get_doc | allow | - | ✅ 在白名单内 |
| 6 | 07:37:10 | rag_paper_search | deny | whitelist_violation | ❌ 工具不在白名单 |

**统计**:
- 总调用数: 6
- 成功: 5
- 被拒绝: 1
- 错误: 0
- whitelist_violation: 1
- wrong_skill_tool: 0
- parameter_error: 0
```


---

### 9. 记录 State、缓存与回收

**数据来源**: `SessionState` + `SkillIndexer.metadata_cache` + `SkillIndexer.doc_cache`

**会话开始时快照** (`state_before.json`):
```json
{
  "session_id": "demo-01",
  "skills_metadata": {},
  "skills_loaded": {},
  "active_tools": [],
  "active_grants": {},
  "created_at": "2026-04-29T07:36:00Z",
  "updated_at": "2026-04-29T07:36:00Z"
}
```

**会话结束时快照** (`state_after.json`):
```json
{
  "session_id": "demo-01",
  "skills_metadata": {
    "yuque-knowledge-link": {
      "skill_id": "yuque-knowledge-link",
      "name": "Yuque Knowledge Link",
      "risk_level": "low",
      "allowed_tools": ["yuque_search", "yuque_list_docs", "yuque_get_doc"],
      "version": "1.0.0"
    }
  },
  "skills_loaded": {
    "yuque-knowledge-link": {
      "skill_id": "yuque-knowledge-link",
      "version": "1.0.0",
      "current_stage": null,
      "last_used_at": "2026-04-29T07:36:50Z"
    }
  },
  "active_tools": ["yuque_search", "yuque_list_docs", "yuque_get_doc"],
  "active_grants": {
    "yuque-knowledge-link": {
      "grant_id": "grant-abc123",
      "skill_id": "yuque-knowledge-link",
      "ttl_seconds": 3600,
      "status": "active",
      "expires_at": "2026-04-29T08:36:15Z"
    }
  },
  "created_at": "2026-04-29T07:36:00Z",
  "updated_at": "2026-04-29T07:40:00Z"
}
```

**缓存情况** (在 Markdown 报告中):
```markdown
## State / Cache / Recovery

**运行前状态**:
- skills_loaded: 0
- active_tools: 0
- active_grants: 0

**运行后状态**:
- skills_loaded: 1 (yuque-knowledge-link)
- active_tools: 3
- active_grants: 1

**缓存统计**:
- metadata_cache: 5 entries (from SkillIndexer)
- doc_cache: 1 entry (yuque-knowledge-link SOP)
- cache hit/miss: 无法从当前代码直接获取

**一致性检查**:
- ✅ SessionState 与 RuntimeContext 一致
- ✅ skills_loaded 与 active_grants 对齐
- ⚠️ 当前运行未启用跨实例恢复（无 Redis）
```

---

### 10. 记录 Langfuse / Trace 信息

**数据来源**: `LangfuseTracer` (如果启用)

**实现方式**: 复用现有 `SQLiteStore.append_audit` 中的 `tracer.emit()` 调用

**记录字段**:
```python
{
  "langfuse_enabled": bool,
  "trace_id": str | None,
  "session_id": str,
  "observations": [
    {
      "name": "skill.read",
      "input": {"skill_id": "yuque-knowledge-link"},
      "timestamp": str
    },
    {
      "name": "skill.enable",
      "input": {"skill_id": "yuque-knowledge-link", "decision": "granted"},
      "timestamp": str
    },
    {
      "name": "tool.call",
      "input": {"tool_name": "yuque_search", "decision": "allow"},
      "timestamp": str
    }
  ]
}
```

**在 Markdown 报告中**:
```markdown
## Langfuse / Trace 信息

- **Langfuse 启用**: 否（LANGFUSE_PUBLIC_KEY 未设置）
- **Trace ID**: N/A
- **Session ID**: demo-01

**说明**: 当前会话未启用 Langfuse 追踪。如需启用，请设置环境变量:
\`\`\`bash
export LANGFUSE_PUBLIC_KEY=pk-xxx
export LANGFUSE_SECRET_KEY=sk-xxx
export LANGFUSE_HOST=https://cloud.langfuse.com
\`\`\`
```


---

### 11. 生成运行后审计总结

**文件**: `logs/session_{session_id}/audit_summary.md`

**结构**:
```markdown
# Agent Run Audit Summary

## 1. 基础信息
- Session ID: demo-01
- Trace ID: N/A
- 开始时间: 2026-04-29T07:36:00+08:00
- 结束时间: 2026-04-29T07:40:00+08:00
- 总耗时: 240 秒
- 工作目录: /home/zh/tool-gate/examples/01-knowledge-link
- Policy 版本: default_policy.yaml

## 2. 任务特征推断
（见第 4 节）

## 3. Skill 暴露与读取
（见第 5 节）

## 4. Skill 启用与授权
（见第 6 节）

## 5. active_tools 重算与工具可见性
（见第 7 节）

## 6. 工具调用明细与治理判定
（见第 8 节）

## 7. State / Cache / Recovery
（见第 9 节）

## 8. 任务完成度与交付物质量
**限制**: Hook 层无法直接评估任务完成度，只能从工具调用模式推断。

**推断**:
- 成功调用的工具: 5 次
- 被拒绝的工具: 1 次
- 可能的交付物: 基于 yuque_get_doc 调用，推测生成了文档关联报告

## 9. 漏斗指标与治理效果
| 指标 | 数值 | 说明 |
|---|---|---|
| shown_skills | 5 | list_skills 调用次数 |
| read_skills | 1 | read_skill 调用次数 |
| enabled_skills | 1 | enable_skill granted 次数 |
| called_tools | 5 | tool.call allow 次数 |
| denied_tools | 1 | tool.call deny 次数 |
| full_tools_count | 50+ | 所有 Skills 的工具总数（估算） |
| active_tools_avg | 3 | 平均 active_tools 数量 |
| active_tools_max | 3 | 最大 active_tools 数量 |
| tool_reduction_ratio | 94% | (50-3)/50 |
| whitelist_violation_count | 1 | rag_paper_search |
| wrong_skill_tool_count | 0 | - |
| parameter_error_count | 0 | - |

## 10. 失败归因与优化建议
**Knowledge Plane 问题**:
- 无

**Execution Plane 问题**:
- 现象: rag_paper_search 被拒绝
- 发生阶段: PreToolUse gate check
- 影响: Agent 无法执行在线搜索，降级使用内置知识
- 建议修复方式: 创建独立的 web-search Skill，包含 rag_paper_search 工具
- 优先级: P2

**Tool Execution 问题**:
- 无

**State / Cache 问题**:
- 无

**Observability 问题**:
- 现象: 无法获取原始用户请求和 Agent 任务规划
- 影响: 审计报告缺少任务目标和完成度评估
- 建议修复方式: 在 SessionStart 时注入用户请求到 detail 字段
- 优先级: P3

## 11. 本次运行结论
- ✅ Skill 治理链路生效，成功拦截 whitelist_violation
- ✅ active_tools 有效收敛，从 50+ 降至 3
- ✅ 无误调用或授权异常
- ⚠️ 缺少原始用户请求和任务完成度评估
- 🔧 下一步优化: 添加 web-search Skill，支持在线搜索
```


---

### 12. 生成结构化指标文件

**文件**: `logs/session_{session_id}/metrics.json`

**结构**:
```json
{
  "session_id": "demo-01",
  "agent_id": null,
  "trace_id": null,
  "start_time": "2026-04-29T07:36:00+08:00",
  "end_time": "2026-04-29T07:40:00+08:00",
  "duration_seconds": 240,
  "model": null,
  "shown_skills": 5,
  "read_skills": 1,
  "enabled_skills": 1,
  "called_tools": 5,
  "successful_tool_calls": 5,
  "failed_tool_calls": 0,
  "denied_tool_calls": 1,
  "full_tools_count": 50,
  "active_tools_avg": 3,
  "active_tools_max": 3,
  "tool_reduction_ratio": 0.94,
  "whitelist_violation_count": 1,
  "wrong_skill_tool_count": 0,
  "schema_error_count": 0,
  "tool_runtime_error_count": 0,
  "timeout_count": 0,
  "retry_count": 0,
  "recovery_success_count": 0,
  "cache_hit_count": null,
  "cache_miss_count": null,
  "task_completed": null,
  "deliverables": []
}
```

---

### 13. 实现要求

**最小侵入原则**:
- ✅ 不修改 Hook 处理逻辑（`handle_session_start`, `handle_pre_tool_use` 等）
- ✅ 不修改 MCP 工具逻辑（`list_skills`, `enable_skill` 等）
- ✅ 不修改 RuntimeContext 或 SessionState 数据结构
- ✅ 只在 `SQLiteStore.append_audit` 调用后添加内存缓存
- ✅ 在 `demo_script.py` 结束时调用 `SessionLogger.export()` 生成文件

**失败降级**:
- 日志写入失败时记录 `logger.warning`，不抛出异常
- 如果 `GOVERNANCE_LOG_DIR` 未设置，跳过文件日志生成
- 如果目录创建失败，记录 warning 并继续

**敏感信息脱敏**:
- 工具参数中的 `password`, `token`, `api_key`, `secret` 字段替换为 `***`
- 工具输出中的长文本截断为前 200 字符
- 环境变量中的密钥显示为 `***`

**JSONL 格式**:
- 每行必须是合法 JSON
- 使用 `json.dumps()` 序列化，不使用 `json.dump()` 直接写入
- 每个事件一行，按时间戳排序

**Markdown 格式**:
- 使用标准 Markdown 语法
- 表格使用 GitHub Flavored Markdown 格式
- 代码块使用三个反引号包裹，指定语言

**关键事件记录函数命名**:
- `SessionLogger.record_session_start()`
- `SessionLogger.record_skill_list()`
- `SessionLogger.record_skill_read()`
- `SessionLogger.record_skill_enable()`
- `SessionLogger.record_tool_call()`
- `SessionLogger.record_active_tools_recompute()`
- `SessionLogger.export()` — 生成所有日志文件

**复用现有封装**:
- 优先使用 `SQLiteStore.query_audit()` 读取事件
- 优先使用 `SQLiteStore.funnel_counts()` 获取漏斗指标
- 优先使用 `LangfuseTracer` 的现有集成（如果启用）
- 优先使用 Python 标准库 `logging` 模块

**测试验证**:
- 如果现有测试框架存在，补充最小测试或 smoke test
- 验证日志文件能生成
- 验证 JSONL 合法（每行可被 `json.loads` 加载）
- 验证 metrics 字段存在


---

### 14. 验证方式

完成后请运行必要的测试或最小 demo，至少验证：

**基础功能验证**:
- ✅ 指定日志目录能够自动创建
- ✅ Agent 完成一次任务后能生成 Markdown 日志
- ✅ 能生成 JSONL 工具调用事件
- ✅ 能生成 agent_metrics.json
- ✅ JSON 文件可被 Python json 加载
- ✅ JSONL 每一行可被 Python json.loads 加载

**内容完整性验证**:
- ✅ 日志中包含 session_id
- ✅ 日志中包含用户请求（如果可获取）
- ✅ 日志中包含工具调用记录
- ✅ 日志中包含 active_tools 变化
- ✅ 日志中包含 skills_loaded 状态
- ✅ 日志中包含任务完成度（如果可推断）

**事件记录验证**:
- ✅ 如果存在 read_skill 调用，日志中能看到对应事件
- ✅ 如果存在 enable_skill 调用，日志中能看到对应事件
- ✅ 如果存在工具拒绝，日志中能看到 deny 事件和 error_bucket

**降级处理验证**:
- ✅ 如果没有某些能力（例如 Redis / Langfuse / stage），在总结中明确标记为未启用或不可用，而不是报错
- ✅ 日志写入失败时不影响主流程

**验证命令示例**:
```bash
# 1. 运行 demo
cd /home/zh/tool-gate/examples/01-knowledge-link
export GOVERNANCE_DATA_DIR="$PWD/.demo-data"
export GOVERNANCE_SKILLS_DIR="$PWD/skills"
export GOVERNANCE_CONFIG_DIR="$PWD/config"
export GOVERNANCE_LOG_DIR="$PWD/logs"
python demo_script.py

# 2. 验证日志文件生成
ls -la logs/session_*/

# 3. 验证 JSON 合法性
python -c "import json; json.load(open('logs/session_demo-01/metrics.json'))"

# 4. 验证 JSONL 合法性
python -c "import json; [json.loads(line) for line in open('logs/session_demo-01/events.jsonl')]"

# 5. 查看 Markdown 报告
cat logs/session_demo-01/audit_summary.md
```

---

### 15. 最终输出

请在完成后给出：

1. **修改了哪些文件**:
   - 新增: `src/tool_governance/core/session_logger.py`
   - 修改: `examples/01-knowledge-link/demo_script.py` (添加 `SessionLogger.export()` 调用)
   - 修改: 其他需要集成的文件（如果有）

2. **新增了哪些日志文件**:
   - `logs/session_{session_id}/events.jsonl`
   - `logs/session_{session_id}/audit_summary.md`
   - `logs/session_{session_id}/metrics.json`
   - `logs/session_{session_id}/state_before.json`
   - `logs/session_{session_id}/state_after.json`

3. **日志保存路径**:
   - `/home/zh/tool-gate/examples/01-knowledge-link/logs`

4. **如何运行一次 demo 生成日志**:
   - 提供完整的命令行步骤

5. **如何验证 JSON / JSONL 合法**:
   - 提供验证命令

6. **本次实现是否改变 Agent 原有行为**:
   - 明确说明是否改变了工具调用逻辑、授权逻辑或任务结果

7. **当前仍未覆盖的日志字段或限制**:
   - 列出无法获取的字段（如 agent_id, model, original_request）
   - 列出技术限制（如无法获取 cache hit/miss 统计）
   - 列出未来可扩展的方向

---

## 附录：与原始 Prompt 的差异

本 Prompt 针对 tool-gate 项目的实际架构进行了以下调整：

### 主要差异

1. **无独立 Agent 运行时**: 
   - 原始 Prompt 假设有独立的 Agent 进程
   - 本项目是治理中间件，Agent 是 Claude 本身

2. **数据来源调整**:
   - 原始: 从 Agent 内存状态读取
   - 本项目: 从 SQLite `audit_log` 表和 `SessionState` 读取

3. **无法获取的字段**:
   - `agent_id`: 本项目无此概念
   - `model`: Hook 层无法获取
   - `original_request`: Hook 层无法获取
   - `task_goal`: 需要从工具调用模式推断

4. **已有基础设施**:
   - ✅ `SQLiteStore.append_audit()` 已记录事件
   - ✅ `funnel_counts()` 已提供漏斗统计
   - ✅ `LangfuseTracer` 已集成（可选）

5. **实现策略**:
   - 原始: 在 Agent 主循环中插入日志记录
   - 本项目: 从 SQLite 读取事件，在会话结束时生成文件

### 保留的核心需求

- ✅ JSONL 事件流
- ✅ Markdown 审计报告
- ✅ JSON 指标文件
- ✅ 状态快照
- ✅ 漏斗分析
- ✅ 治理判定
- ✅ 失败归因

### 新增的项目特定内容

- ✅ Hook 层事件记录
- ✅ RuntimeContext 与 SessionState 的区分
- ✅ active_tools 重算过程
- ✅ Grant 生命周期管理
- ✅ Policy 评估结果

